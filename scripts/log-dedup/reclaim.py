#!/usr/bin/env python3
"""Crash-recoverable log conversion for the existing deployment controller.

No standalone live-admission flag. The controller supplies its held WriterFence,
qualified reader/consumer guard and independently readable Desktop B store.
"""
import base64
from contextlib import closing, contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import uuid

import log_dedup as logs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deployment'))
from vk_restart_writer_fence import WriterFence


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def file_hash(path):
    before = logs.regular(path)
    digest = hashlib.sha256()
    with path.open('rb') as source:
        if logs.version(os.fstat(source.fileno())) != logs.version(before):
            raise logs.ArchiveError('File changed during open')
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    if logs.version(logs.regular(path)) != logs.version(before):
        raise logs.ArchiveError('File changed during hash')
    return digest.hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_bytes(path, raw, metadata=None, before_publish=lambda _: None):
    temporary = path.parent / ('.log-dedup-' + str(uuid.uuid4()) + '.tmp')
    try:
        logs.write_new(temporary, raw)
        if metadata is not None:
            apply_metadata(temporary, metadata)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        before_publish(temporary)
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()  # Only this call's create-only staging file.


def metadata_for(path):
    st = logs.regular(path)
    if st.st_uid != os.getuid() or st.st_nlink != 1:
        raise logs.ArchiveError('Unique owned original required')
    return {'uid': st.st_uid, 'gid': st.st_gid, 'mode': stat.S_IMODE(st.st_mode),
            'atime_ns': st.st_atime_ns, 'mtime_ns': st.st_mtime_ns,
            'xattrs': {name: base64.b64encode(os.getxattr(path, name)).decode('ascii')
                       for name in os.listxattr(path)}}


def apply_metadata(path, value):
    os.chown(path, value['uid'], value['gid'])
    os.chmod(path, value['mode'])
    for name, raw in value['xattrs'].items():
        os.setxattr(path, name, base64.b64decode(raw, validate=True))
    os.utime(path, ns=(value['atime_ns'], value['mtime_ns']))


def terminal_process(database, entry):
    match = logs.LOG_PATH.fullmatch(entry['path'])
    if match is None:
        raise logs.ArchiveError('Invalid source reference')
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as conn:
        conn.execute('PRAGMA query_only=ON')
        row = conn.execute('SELECT session_id, status, completed_at FROM execution_processes WHERE id=?',
                           (uuid.UUID(match[3]).bytes,)).fetchone()
        active = conn.execute("SELECT 1 FROM execution_processes WHERE session_id=? AND status='running' LIMIT 1",
                              (uuid.UUID(match[2]).bytes,)).fetchone()
    if (active is not None or row is None or row[0] != uuid.UUID(match[2]).bytes
            or row[1] not in ('completed', 'failed', 'killed') or row[2] is None):
        raise logs.ArchiveError('Exact terminal execution/session binding required')


def verify_sidecars(root, entry):
    source = logs.safe_path(root, entry['path'])
    actual = logs.sidecars(source)
    expected = [(row['extension'], row['sha256']) for row in entry['sidecars']]
    if [(ext, logs.sha(raw)) for ext, raw, _ in actual] != expected:
        raise logs.ArchiveError('Source sidecar set/content changed')
    for ext, raw, _ in actual:
        if ext == 'capture.json' and json.loads(raw).get('capture_state') != 'closed':
            raise logs.ArchiveError('Pending capture cannot be converted')


def verify_recovery(store, plan, guard):
    """Read actual remote bodies, not booleans asserting a historical backup.

    The trusted owner adapter supplies open_original(relative, sha256), a context
    manager over the independently reopened canonical B body. No local fallback.
    """
    if not store.location.startswith('desktop:B:/vk-backups/'):
        raise logs.ArchiveError('Canonical Desktop B recovery provider required')
    for entry in plan['files']:
        bodies = [(entry['path'], entry['sha256'], entry['raw_bytes'])]
        for sidecar in entry['sidecars']:
            relative = str(Path(entry['path']).with_suffix('.' + sidecar['extension']))
            bodies.append((relative, sidecar['sha256'], sidecar['identity'][2]))
        for relative, expected, size in bodies:
            guard()
            digest = hashlib.sha256()
            count = 0
            with store.open_original(relative, expected) as source:
                while block := source.read(1024 * 1024):
                    count += len(block)
                    if count > size:
                        raise logs.ArchiveError('B recovery body exceeds exact source size')
                    digest.update(block)
            if count != size or digest.hexdigest() != expected:
                raise logs.ArchiveError('Current-version B recovery body mismatch')


def object_bytes(path, chunk):
    if logs.regular(path).st_size > logs.MAX_CHUNK + 1024:
        raise logs.ArchiveError('Oversized archive object')
    with gzip.open(path, 'rb') as source:
        raw = source.read(chunk['bytes'] + 1)
    if len(raw) != chunk['bytes'] or logs.sha(raw) != chunk['sha256']:
        raise logs.ArchiveError('Archive object integrity failure')


class Batch:
    def __init__(self, plan, archive, journal, fence, recovery, reader_guard, *, reserve_bytes):
        if not isinstance(fence, WriterFence):
            raise logs.ArchiveError('Existing deployment WriterFence required')
        if not callable(reader_guard) or type(reserve_bytes) is not int or reserve_bytes < 0:
            raise logs.ArchiveError('Qualified reader/consumer guard and explicit reserve required')
        if (not 1 <= len(plan['files']) <= 64
                or sum(row['raw_bytes'] for row in plan['files']) > 2 * 1024**3
                or len({row['path'] for row in plan['files']}) != len(plan['files'])):
            raise logs.ArchiveError('Explicit unique batch of at most 64 files and 2 GiB required')
        self.plan = plan
        self.archive = Path(archive).resolve()
        self.root = Path(plan['source_root'])
        if not self.root.is_absolute() or self.root.resolve(strict=True) != self.root:
            raise logs.ArchiveError('Literal canonical source root required')
        self.journal = Path(journal).resolve()
        if (self.journal == self.root or self.root in self.journal.parents
                or self.journal == self.archive or self.archive in self.journal.parents):
            raise logs.ArchiveError('Operation journal must be outside source/archive')
        self.fence, self.recovery, self.reader_guard = fence, recovery, reader_guard
        self.reserve = reserve_bytes
        self.digest = logs.sha(canonical(plan))
        self.state = None

    def guard(self):
        self.fence.check()  # Includes actual held lease, owner, ingress and DB checks.
        if self.fence.binding.get('log_source_root') != str(self.root):
            raise logs.ArchiveError('Writer custody does not bind this exact log root')
        self.reader_guard()  # Trusted controller: exact reader build, consumers, recovery owner.

    @contextmanager
    def locked(self):
        self.journal.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (self.journal.is_symlink() or self.journal.stat().st_uid != os.getuid()
                or self.journal.stat().st_mode & 0o077):
            raise logs.ArchiveError('Owned operation directory required')
        fd = os.open(self.journal / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077):
                raise logs.ArchiveError('Unique private journal lease required')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def save(self):
        atomic_bytes(self.journal / 'state.json', canonical(self.state) + b'\n')

    def initial(self):
        receipt = json.loads((self.archive / 'receipt.json').read_bytes())
        # A measured sample may contain deferred active/legacy files. Reuse its
        # immutable graph, but install only an exact subset of pinned entries.
        packed = {row['path']: row for row in receipt['files']}
        if (receipt['source_root'] != self.plan['source_root']
                or receipt['version'] != self.plan['version']
                or any(packed.get(row['path']) != row for row in self.plan['files'])):
            raise logs.ArchiveError('Packed receipt differs from selected frozen sources')
        logs.verify_or_restore(self.archive)
        current = self.journal / 'state.json'
        if current.exists():
            logs.regular(current)
            self.state = json.loads(current.read_bytes())
            if (self.state['plan_sha256'] != self.digest
                    or self.state['archive'] != str(self.archive)
                    or set(self.state['files']) != {row['path'] for row in self.plan['files']}):
                raise logs.ArchiveError('Operation journal identity mismatch')
        else:
            entries = {}
            for entry in self.plan['files']:
                source = logs.safe_path(self.root, entry['path'])
                if logs.version(logs.regular(source)) != entry['identity'] or file_hash(source) != entry['sha256']:
                    raise logs.ArchiveError('Frozen original identity/content changed')
                entries[entry['path']] = {'state': 'original', 'metadata': metadata_for(source),
                    'manifest_sha256': file_hash(self.archive / entry['path'])}
            self.state = {'version': 1, 'plan_sha256': self.digest,
                          'archive': str(self.archive), 'files': entries, 'complete': False}
            self.save()

    def source_kind(self, entry):
        source = logs.safe_path(self.root, entry['path'])
        record = self.state['files'][entry['path']]
        digest = file_hash(source)
        if digest == record['manifest_sha256']:
            actual = logs.version(logs.regular(source))
            if record.get('installed_identity') != actual:
                if record['state'] == 'install-intent' and record.get('manifest_inode') == actual[:4]:
                    record['installed_identity'] = actual
                    self.save()
                else:
                    raise logs.ArchiveError('Foreign installed manifest inode; preserve it')
            manifest = logs.reconstruct(source)
            if manifest['sha256'] != entry['sha256']:
                raise logs.ArchiveError('Installed manifest differs from original')
            return 'archive'
        if digest != entry['sha256']:
            raise logs.ArchiveError('Unknown/newer source content; preserve it')
        expected = record.get('restored_identity', entry['identity'])
        actual = logs.version(logs.regular(source))
        if actual != expected:
            # Rename may have completed just before a crash, before the final
            # journal update. Bind recovery to the recorded restored inode.
            pinned = record.get('restore_inode')
            if record['state'] == 'restore-intent' and pinned == actual[:4]:
                record['restored_identity'] = actual
                self.save()
            else:
                raise logs.ArchiveError('Original inode changed; preserve external replacement')
        return 'original'

    def require_capacity(self, additional=0):
        needed = sum(row['raw_bytes'] for row in self.plan['files']) + self.reserve + additional
        if shutil.disk_usage(self.root).free < needed:
            raise logs.ArchiveError('Insufficient original reconstruction/publication headroom')

    def publication_peak(self):
        fragment = os.statvfs(self.root).f_frsize or 4096
        total = 0
        seen = set()
        for entry in self.plan['files']:
            manifest_path = self.archive / entry['path']
            size = logs.regular(manifest_path).st_size
            total += ((size + fragment - 1) // fragment + 1) * fragment
            for chunk in logs.load_manifest(manifest_path)['chunks']:
                relative = str(Path(entry['path']).parent / '.log-objects' / (chunk['sha256'] + '.gz'))
                if relative in seen:
                    continue
                seen.add(relative)
                target = self.root / relative
                if not target.exists() and not target.is_symlink():
                    size = logs.regular(self.archive / relative).st_size
                    # Include a conservative full directory block per new object.
                    total += ((size + fragment - 1) // fragment + 1) * fragment
        return total

    def objects(self):
        copied = 0
        for entry in self.plan['files']:
            self.guard()
            manifest = logs.load_manifest(self.archive / entry['path'])
            source_dir = (self.archive / entry['path']).parent / '.log-objects'
            target_dir = (self.root / entry['path']).parent / '.log-objects'
            if target_dir.exists() and not stat.S_ISDIR(target_dir.lstat().st_mode):
                raise logs.ArchiveError('Object directory is an alias')
            target_dir.mkdir(mode=0o700, exist_ok=True)
            for chunk in manifest['chunks']:
                name = chunk['sha256'] + '.gz'
                target = target_dir / name
                if target.exists() or target.is_symlink():
                    object_bytes(target, chunk)
                    continue
                object_bytes(source_dir / name, chunk)
                temporary = target_dir / ('.new-' + str(uuid.uuid4()))
                try:
                    logs.write_new(temporary, (source_dir / name).read_bytes())
                    object_bytes(temporary, chunk)
                    os.link(temporary, target)  # Create-only publication, never replace an object.
                finally:
                    if temporary.exists():
                        temporary.unlink()
                copied += 1
                if copied % 64 == 0:
                    self.guard()
            sync_directory(target_dir)
            sync_directory(target_dir.parent)

    def clean_owned_restore_stages(self):
        # A killed rollback may leave a partial raw reconstruction. Retire only
        # the exact create-only inode recorded before writing any payload.
        for entry in self.plan['files']:
            record = self.state['files'][entry['path']]
            stage = record.get('restore_temp')
            if not stage:
                continue
            name = stage['name']
            if not name.startswith('.restore-') or str(uuid.UUID(name[9:])) != name[9:]:
                raise logs.ArchiveError('Unknown reconstruction staging reference')
            path = logs.safe_path(self.root, entry['path']).parent / name
            if path.exists() or path.is_symlink():
                self.guard()
                info = logs.regular(path)
                if (stage.get('inode') != [info.st_dev, info.st_ino]
                        or info.st_uid != os.getuid() or info.st_nlink != 1
                        or info.st_size > entry['raw_bytes']):
                    raise logs.ArchiveError('Foreign reconstruction staging inode; preserve it')
                # Inode ownership alone does not permit deleting newer bytes
                # written into that same inode by an external actor.
                before = logs.version(info)
                with path.open('rb') as staged:
                    class PrefixVerifier:
                        remaining = info.st_size
                        def write(self, raw):
                            count = min(self.remaining, len(raw))
                            if count and staged.read(count) != raw[:count]:
                                raise logs.ArchiveError('Reconstruction staging content changed; preserve it')
                            self.remaining -= count
                            return len(raw)
                    verifier = PrefixVerifier()
                    logs.reconstruct(self.archive / entry['path'], verifier)
                    if verifier.remaining:
                        raise logs.ArchiveError('Reconstruction staging exceeds original')
                if logs.version(logs.regular(path)) != before:
                    raise logs.ArchiveError('Reconstruction staging changed during comparison')
                path.unlink()
                sync_directory(path.parent)
            record.pop('restore_temp')
            self.save()

    def run(self, *, rollback=False, after_replace=lambda _: None):
        with self.locked():
            self.guard()
            self.initial()
            self.state['complete'] = False
            self.state['operation'] = 'rollback' if rollback else 'install'
            self.save()
            # Keep enough headroom for all originals plus reserve on fallback.
            self.require_capacity(0 if rollback else self.publication_peak())
            for entry in self.plan['files']:
                terminal_process(self.fence.binding['database'], entry)
                verify_sidecars(self.root, entry)
                self.source_kind(entry)
            verify_recovery(self.recovery, self.plan, self.guard)
            self.clean_owned_restore_stages()
            if not rollback:
                self.objects()  # All objects durable before the first manifest.
            self.require_capacity()
            for entry in self.plan['files']:
                self.guard()
                self.require_capacity()
                terminal_process(self.fence.binding['database'], entry)
                verify_sidecars(self.root, entry)
                kind = self.source_kind(entry)
                target = logs.safe_path(self.root, entry['path'])
                record = self.state['files'][entry['path']]
                if rollback and kind == 'archive':
                    record['state'] = 'restore-intent'
                    self.save()
                    temporary = target.parent / ('.restore-' + str(uuid.uuid4()))
                    record['restore_temp'] = {'name': temporary.name}
                    self.save()
                    try:
                        with temporary.open('xb') as output:
                            os.chmod(temporary, 0o600)
                            info = os.fstat(output.fileno())
                            record['restore_temp']['inode'] = [info.st_dev, info.st_ino]
                            self.save()  # Durable ownership before any raw payload write.
                            logs.reconstruct(target, output)
                            output.flush()
                            os.fsync(output.fileno())
                        if file_hash(temporary) != entry['sha256']:
                            raise logs.ArchiveError('Reconstruction mismatch')
                        apply_metadata(temporary, record['metadata'])
                        with temporary.open('rb') as ready:
                            os.fsync(ready.fileno())
                        record['restore_inode'] = logs.version(logs.regular(temporary))[:4]
                        self.save()
                        self.guard()
                        if self.source_kind(entry) != 'archive':
                            raise logs.ArchiveError('Source changed before rollback')
                        os.replace(temporary, target)
                        sync_directory(target.parent)
                        after_replace(entry['path'])
                        record['restored_identity'] = logs.version(logs.regular(target))
                        record.pop('restore_temp', None)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
                elif not rollback and kind == 'original':
                    record['state'] = 'install-intent'
                    self.save()
                    raw = (self.archive / entry['path']).read_bytes()
                    self.guard()
                    if self.source_kind(entry) != 'original':
                        raise logs.ArchiveError('Source changed before conversion')
                    def pin_manifest(temporary):
                        record['manifest_inode'] = logs.version(logs.regular(temporary))[:4]
                        self.save()
                        self.guard()
                        if self.source_kind(entry) != 'original':
                            raise logs.ArchiveError('Source changed at manifest publication')
                    atomic_bytes(target, raw, record['metadata'], before_publish=pin_manifest)
                    after_replace(entry['path'])
                    if self.source_kind(entry) != 'archive':
                        raise logs.ArchiveError('Installed archive failed readback')
                record['state'] = 'restored' if rollback else 'installed'
                self.save()
            self.guard()
            self.state['complete'] = True
            self.state['outcome'] = 'restored' if rollback else 'installed'
            self.save()
            return {'complete': True, 'outcome': self.state['outcome'], 'files': len(self.plan['files'])}
