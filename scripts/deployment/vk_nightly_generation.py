"""Self-contained incremental nightly generations on an authenticated B mount.

Consumes reviewed archive entries; never reads arbitrary source paths. Stores
Linux metadata as manifest data because B does not reproduce Linux metadata.
No CLI, scheduler installation, live cleanup, source deletion or root access.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
import fcntl
import zlib


MAX_INDEX = 256 * 1024**2
MAX_ENTRIES = 1_000_000
PRODUCER = 'vk-nightly-generation-v1'
COMPRESSED = 'zlib-1-v1'


def object_blocks(path, checksum, size, encoding=None):
    """Lossless recovery stream with an exact decoded-size/hash bound.

    Encoding is manifest-bound, never guessed from bytes. Reject concatenated,
    truncated and oversized streams; no payload-sized allocation or temp file.
    """
    if encoding not in (None, COMPRESSED) or type(size) is not int or size < 0:
        raise ValueError('unknown object encoding or invalid recovery size')
    decoder = zlib.decompressobj() if encoding else None
    digest = hashlib.sha256(); count = 0
    with regular(path) as stream:
        before = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1024**2), b''):
            pending = block
            while pending:
                data = decoder.decompress(pending, 1024**2) if decoder else pending
                pending = decoder.unconsumed_tail if decoder else b''
                count += len(data)
                if count > size or (decoder and decoder.unused_data):
                    raise ValueError('object exceeds recovery bound or has trailing data')
                digest.update(data)
                if data: yield data
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('object changed during recovery')
    if (decoder and not decoder.eof) or count != size or digest.hexdigest() != checksum:
        raise ValueError('nightly decoded object readback failed')


def digest_stream(stream):
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(1024**2), b''):
        result.update(block)
    return result.hexdigest()


def regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise ValueError('nightly object is not a regular file')
    return os.fdopen(fd, 'rb')


def name(value):
    if not isinstance(value, str) or not value or value.startswith('/') or '\\' in value or any(
            part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('unsafe archive member name')
    return value


def encoded(value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    if len(data) > MAX_INDEX:
        raise ValueError('nightly manifest exceeds explicit 256MiB bound')
    return data


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


class NightlyStore:
    def __init__(self, root, scope_sha256, authenticate_mount, *, independent_readback=None, object_encoding=None):
        self.root = Path(root)
        self.authenticate = authenticate_mount
        self.scope = scope_sha256
        self.independent_readback = independent_readback
        if object_encoding not in (None, COMPRESSED):
            raise ValueError('unknown nightly object encoding')
        self.object_encoding = object_encoding
        if not re.fullmatch('[0-9a-f]{64}', scope_sha256):
            raise ValueError('exact reviewed backup scope digest required')
        # authenticate_mount must return the exact existing B mount containing
        # this NEW nightly-only directory; existing backup evidence is not enrolled.
        mounted = Path(self.authenticate()).resolve()
        if not self.root.is_relative_to(mounted) or self.root == mounted:
            raise ValueError('nightly root outside authenticated Desktop B mount')
        current = mounted
        for part in self.root.relative_to(mounted).parts:
            current /= part
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('symlink/non-directory nightly ancestor')
        self.identity = self.root.stat().st_dev, self.root.stat().st_ino

    def enroll_empty(self):
        """One-time SOURCE adapter; adoption is separately authorized by Staging."""
        self.check()
        if list(self.root.iterdir()):
            raise ValueError('nightly enrollment requires an empty new directory')
        write_new(self.root / 'store.json', encoded({'producer': PRODUCER, 'scope_sha256': self.scope,
                  'root_identity': list(self.identity)}))

    def inventory(self):
        with regular(self.root / 'store.json') as stream:
            binding = json.loads(stream.read(4097))
        if binding != {'producer': PRODUCER, 'scope_sha256': self.scope, 'root_identity': list(self.identity)}:
            raise ValueError('normal-nightly store not enrolled or substituted')
        generations = []
        for path in self.root.iterdir():
            if path.name not in ('store.json', 'lease', 'current.json'):
                if not re.fullmatch('generation-[0-9a-f]{32}', path.name):
                    raise ValueError('unexpected protected evidence or partial in nightly-only directory')
                generations.append(path.name)
        return generations

    def check(self):
        mounted = Path(self.authenticate()).resolve()
        current = mounted
        for part in self.root.relative_to(mounted).parts:
            current /= part
            if not stat.S_ISDIR(current.lstat().st_mode):
                raise ValueError('nightly ancestor substituted')
        info = self.root.stat()
        if (info.st_dev, info.st_ino) != self.identity:
            raise ValueError('nightly root substituted')

    def load(self, generation):
        if not re.fullmatch('generation-[0-9a-f]{32}', generation):
            raise ValueError('unknown nightly generation')
        folder = self.root / generation
        if not stat.S_ISDIR(folder.lstat().st_mode):
            raise ValueError('substituted generation')
        with regular(folder / 'manifest.json') as stream:
            data = stream.read(MAX_INDEX + 1)
        if len(data) > MAX_INDEX:
            raise ValueError('oversized nightly manifest')
        value = json.loads(data)
        if value.get('producer') != PRODUCER or value.get('scope_sha256') != self.scope or value.get('generation') != generation:
            raise ValueError('nightly manifest identity mismatch')
        if value.get('object_encoding') != self.object_encoding:
            raise ValueError('nightly encoding differs from bound store configuration')
        if len(value['entries']) > MAX_ENTRIES:
            raise ValueError('nightly entry count bound exceeded')
        for key, row in value['entries'].items():
            name(key)
            if row['kind'] == 'file' and not re.fullmatch('[0-9a-f]{64}', row['sha256']):
                raise ValueError('unsafe nightly object selector')
        return value, hashlib.sha256(data).hexdigest()

    def current(self):
        path = self.root / 'current.json'
        if not os.path.lexists(path):
            return None
        with regular(path) as stream:
            value = json.loads(stream.read(4097))
        manifest, checksum = self.load(value['generation'])
        if checksum != value['manifest_sha256']:
            raise ValueError('current nightly manifest changed')
        return manifest

    def verify(self, manifest):
        folder = self.root / manifest['generation']
        objects = folder / 'objects'
        if not stat.S_ISDIR(objects.lstat().st_mode):
            raise ValueError('substituted nightly objects directory')
        encoding = manifest.get('object_encoding')
        if encoding != self.object_encoding: raise ValueError('nightly object encoding changed')
        unique = {}
        for row in manifest['entries'].values():
            if row['kind'] == 'file':
                if row['sha256'] in unique and unique[row['sha256']] != row['bytes']:
                    raise ValueError('conflicting object sizes')
                unique[row['sha256']] = row['bytes']
        for checksum, size in unique.items():
            for _ in object_blocks(objects / checksum, checksum, size, encoding): pass

    def advance(self, changes, absent, *, expected_previous, reserve_bytes, retention_adopted=False,
                capture_context=None, generation=None, observe=None):
        """changes yields (safe archive name, metadata, stream or None).

        Database entries MUST come from consistent SQLite snapshots in the
        existing direct-B capture, never raw live SQLite files. Source hashes,
        journal completeness and capture authentication remain upstream gates.
        No glob enrollment: only a caller-bound previous current is reusable.
        """
        self.check()
        if type(retention_adopted) is not bool:
            raise ValueError('retention adoption must be an explicit boolean')
        fd = os.open(self.root / 'lease', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'a+b') as lease:
            if not stat.S_ISREG(os.fstat(lease.fileno()).st_mode):
                raise ValueError('nightly lease is not a regular file')
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = self.current()
            if (previous['generation'] if previous else None) != expected_previous:
                raise ValueError('concurrent or replayed nightly capture')
            outstanding = set(self.inventory()) - ({expected_previous} if expected_previous else set())
            if outstanding:
                raise ValueError('retained previous/failed nightly overlap needs reconciliation; no unbounded partial accumulation')
            if type(reserve_bytes) is not int or reserve_bytes < 0:
                raise ValueError('finite temporary-overlap capacity reservation required')
            import shutil
            if shutil.disk_usage(self.root).free < reserve_bytes + MAX_INDEX:
                raise ValueError('insufficient B capacity for verified temporary overlap')
            if previous:
                self.verify(previous)
            retained_hashes = {row['sha256'] for row in previous['entries'].values() if row['kind'] == 'file'} if previous else set()
            previous_sizes = {row['sha256']: row['bytes'] for row in previous['entries'].values()
                              if row['kind'] == 'file'} if previous else {}
            generation = generation or 'generation-' + uuid.uuid4().hex
            if not re.fullmatch('generation-[0-9a-f]{32}', generation):
                raise ValueError('invalid reserved nightly generation')
            folder = self.root / generation
            folder.mkdir(mode=0o700)
            objects = folder / 'objects'
            objects.mkdir(mode=0o700)
            if observe:
                observe('directories', (folder, objects))
            entries = dict(previous['entries']) if previous else {}
            removed = {name(raw) for raw in absent}
            entries = {key: row for key, row in entries.items() if key not in removed and not any(
                '/'.join(key.split('/')[:index]) in removed for index in range(1, key.count('/') + 1))}
            seen = set()
            changed_bytes = 0
            stored_bytes = 0
            written_sizes = {}
            for raw, metadata, stream in changes:
                raw = name(raw)
                if raw in seen or metadata.get('kind') not in ('file', 'directory', 'symlink', 'hardlink'):
                    raise ValueError('duplicate or unsupported nightly member')
                seen.add(raw)
                row = dict(metadata)
                if row['kind'] != 'directory' and entries.get(raw, {}).get('kind') == 'directory':
                    entries = {key: value for key, value in entries.items() if not key.startswith(raw + '/')}
                if row['kind'] == 'file':
                    if not re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')):
                        raise ValueError('unverified nightly file')
                    if stream is None:
                        if previous is None or row['sha256'] not in retained_hashes:
                            raise ValueError('new nightly file lacks verified content')
                        if previous_sizes.get(row['sha256']) != row['bytes']:
                            raise ValueError('retained object logical size changed')
                        old = self.root / previous['generation'] / 'objects' / row['sha256']
                        with regular(old) as retained:
                            if not self.object_encoding and os.fstat(retained.fileno()).st_size != row['bytes']:
                                raise ValueError('retained object size differs from verified metadata')
                        entries[raw] = row
                        if len(entries) > MAX_ENTRIES:
                            raise ValueError('nightly entry bound exceeded')
                        continue  # Already fully hashed by verify(previous).
                    if row['sha256'] in written_sizes:
                        checksum = hashlib.sha256(); size = 0
                        for block in iter(lambda: stream.read(1024**2), b''):
                            size += len(block); changed_bytes += len(block)
                            if size > row['bytes']: raise ValueError('duplicate content exceeds exact bound')
                            checksum.update(block)
                        if size != written_sizes[row['sha256']] or size != row['bytes'] or checksum.hexdigest()!=row['sha256']:
                            raise ValueError('duplicate content differs from verified object')
                        entries[raw] = row
                        if len(entries) > MAX_ENTRIES: raise ValueError('nightly entry bound exceeded')
                        continue
                    temporary = objects / ('partial-' + uuid.uuid4().hex)
                    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    if observe:
                        try:
                            observe('partial', (temporary, os.fstat(fd)))
                        except BaseException:
                            os.close(fd)
                            raise
                    checksum = hashlib.sha256()
                    size = 0
                    compressor = zlib.compressobj(1) if self.object_encoding else None
                    with os.fdopen(fd, 'wb') as sink:
                        for block in iter(lambda: stream.read(1024**2), b''):
                            changed_bytes += len(block)
                            size += len(block)
                            if size > row['bytes']:
                                raise ValueError('nightly input exceeds exact content bound')
                            checksum.update(block)
                            data = compressor.compress(block) if compressor else block
                            stored_bytes += len(data)
                            if stored_bytes > reserve_bytes:
                                raise ValueError('stored nightly bytes exceed overlap reservation')
                            sink.write(data)
                        if compressor:
                            data = compressor.flush(); stored_bytes += len(data)
                            if stored_bytes > reserve_bytes:
                                raise ValueError('stored nightly bytes exceed overlap reservation')
                            sink.write(data)
                        sink.flush()
                        os.fsync(sink.fileno())
                    if checksum.hexdigest() != row['sha256'] or size != row['bytes']:
                        raise ValueError('nightly incremental content mismatch')
                    target = objects / row['sha256']
                    if not target.exists():
                        os.link(temporary, target, follow_symlinks=False)
                    temporary.unlink()
                    written_sizes[row['sha256']] = size
                entries[raw] = row
                if len(entries) > MAX_ENTRIES:
                    raise ValueError('nightly entry bound exceeded')
            # New generation owns an independent link to every retained object:
            # it never needs the previous directory to restore unchanged files.
            for row in entries.values():
                if row['kind'] == 'hardlink' and (row.get('target') not in entries or entries[row['target']]['kind'] != 'file'):
                    raise ValueError('unresolved nightly hardlink')
                if row['kind'] == 'file' and not (objects / row['sha256']).exists():
                    os.link(self.root / previous['generation'] / 'objects' / row['sha256'],
                            objects / row['sha256'], follow_symlinks=False)
            manifest = {'producer': PRODUCER, 'generation': generation, 'scope_sha256': self.scope,
                        'parent': None, 'entries': entries, 'capture_context': capture_context}
            if self.object_encoding: manifest['object_encoding'] = self.object_encoding
            data = encoded(manifest)
            write_new(folder / 'manifest.json', data)
            if observe:
                observe('manifest', manifest)
            self.verify(manifest)
            if self.independent_readback is None or self.independent_readback(folder, manifest) != {
                    'physical_b_verified': True, 'generation': generation, 'scope_sha256': self.scope,
                    'manifest_sha256': hashlib.sha256(data).hexdigest()}:
                raise ValueError('independent physical B generation readback missing or mismatched')
            self.check()
            # Publication is last. No failed preparation advances current.
            pointer = encoded({'generation': generation, 'manifest_sha256': hashlib.sha256(data).hexdigest()})
            stage = self.root / ('current-' + uuid.uuid4().hex + '.json')
            for directory in (objects, folder):
                durable_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(durable_fd)
                finally:
                    os.close(durable_fd)
            write_new(stage, pointer)
            if observe:
                observe('pointer', (stage, stage.stat()))
            os.replace(stage, self.root / 'current.json')
            parent_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            retired = False
            if previous and retention_adopted:
                self._retire_previous_held(previous['generation'])
                retired = True
            return {'passed': True, 'generation': generation, 'previous': expected_previous,
                    'changed_bytes': changed_bytes, 'self_contained': True,
                    'stored_changed_bytes': stored_bytes,
                    'old_generation_retained': previous is not None and not retired,
                    'cleanup_performed': retired, 'local_payload_bytes': 0,
                    'retention_blocker': None if retention_adopted else 'Separately approved nightly-only retention adoption pending'}

    def retire_previous(self, generation, *, retention_adopted=False):
        """No recursion/globs: remove ONLY manifest-listed normal-nightly objects.

        Same-account arguments are not a privilege/security boundary.
        """
        if retention_adopted is not True:
            raise ValueError('nightly-only retention adoption not authorized')
        fd = os.open(self.root / 'lease', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'a+b') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self._retire_previous_held(generation)

    def _retire_previous_held(self, generation):
        self.check()
        self.inventory()
        current = self.current()
        if current is None or current['generation'] == generation:
            raise ValueError('cannot retire current/only nightly')
        self.verify(current)
        previous, checksum = self.load(generation)
        self.verify(previous)
        folder = self.root / generation
        objects = folder / 'objects'
        wanted = {row['sha256'] for row in previous['entries'].values() if row['kind'] == 'file'}
        if {p.name for p in folder.iterdir()} != {'objects', 'manifest.json'} or {p.name for p in objects.iterdir()} != wanted:
            raise ValueError('unexpected evidence in previous generation; preserve it')
        # Prevalidate ALL identities before any unlink; reject symlinks even when
        # a filename looks like a hash. Object hardlinks between generations are intended.
        paths = [objects / value for value in sorted(wanted)] + [folder / 'manifest.json']
        identities = {}
        for path in paths:
            with regular(path) as stream:
                info = os.fstat(stream.fileno())
                identities[path] = (info.st_dev, info.st_ino)
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        folder_fd = object_fd = None
        try:
            folder_fd = os.open(generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
            object_fd = os.open('objects', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=folder_fd)
            for path in paths:
                parent_fd = object_fd if path.parent == objects else folder_fd
                info = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != identities[path]:
                    raise ValueError('nightly retirement substitution; preserve remaining evidence')
                os.unlink(path.name, dir_fd=parent_fd)
            opened = os.fstat(object_fd)
            named = os.stat('objects', dir_fd=folder_fd, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                raise ValueError('objects directory changed; preserve names')
            os.rmdir('objects', dir_fd=folder_fd)
            opened = os.fstat(folder_fd)
            named = os.stat(generation, dir_fd=root_fd, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                raise ValueError('generation directory changed; preserve names')
            os.rmdir(generation, dir_fd=root_fd)
            os.fsync(root_fd)
        finally:
            for fd in (object_fd, folder_fd, root_fd):
                if fd is not None:
                    os.close(fd)


def render_schedule(job_script, configuration):
    """Source strings only. Installing/enabling a reviewed job is separate adoption.

    job_script is Staging's fixed direct-B capture + promotion composition; it
    must authenticate capture/mount/readback and approved nightly-only retention.
    This function neither invents that adapter nor schedules LLM/agent calls.
    """
    for path in (job_script, configuration):
        if not re.fullmatch('/[A-Za-z0-9_./-]+', str(path)) or '..' in Path(path).parts:
            raise ValueError('fixed absolute reviewed job/configuration paths required')
    service = ('[Unit]\nDescription=Verified normal VK nightly on B\n'
               '[Service]\nType=oneshot\nNoNewPrivileges=yes\nUMask=0077\n'
               'TimeoutStartSec=7200\nTimeoutStopSec=30\nExecStart=/usr/bin/python3 -B ' + str(job_script)
               + ' --config ' + str(configuration) + '\n')
    timer = ('[Unit]\nDescription=Normal VK nightly schedule\n[Timer]\n'
             'OnCalendar=*-*-* 02:00:00 UTC\nRandomizedDelaySec=60\nPersistent=true\n'
             'Unit=vk-normal-nightly.service\n[Install]\nWantedBy=timers.target\n')
    return {'service': service, 'timer': timer, 'enabled': False,
            'schedule_receipt': None, 'test_run_receipt': None}


def advance_verified_capture(store, provider, capture_id, *, reserve_bytes, retention_adopted=False,
                             generation=None, observe=None, verified_proof=None):
    """Reuse existing DirectBProvider's full archive/hash/metadata verification.

    Only changed file payloads traverse the existing B archive reader. Unchanged
    data acquires another B-local hardlink. A generation is self-contained; it
    has no parent dependency on a nightly selected for retirement.
    """
    # Optional proof comes only from the fixed caller's completed verification;
    # providers/callers are trusted code, not a privilege authorization boundary.
    proof = provider.verify(capture_id) if verified_proof is None else verified_proof
    if proof.get('scope_sha256') != store.scope or proof.get('full_current_state') is not True:
        raise ValueError('capture scope/authentication mismatch')
    previous = store.current()
    before = previous['entries'] if previous else {}
    entries = proof['entries']
    changed = {key: row for key, row in entries.items() if before.get(key) != row}
    retained = {row['sha256'] for row in before.values() if row['kind'] == 'file'}
    selected = {key for key, row in changed.items() if row['kind'] == 'file' and row['sha256'] not in retained}
    with provider.file_members(capture_id, selected) as streams:
        def changes():
            for key, row in changed.items():
                if row['kind'] != 'file' or key not in selected:
                    yield key, row, None
            for key, stream in streams:
                yield key, changed[key], stream
        return store.advance(changes(), set(before) - set(entries),
                             expected_previous=previous['generation'] if previous else None,
                             reserve_bytes=reserve_bytes, retention_adopted=retention_adopted,
                             generation=generation, observe=observe,
                             capture_context={key: value for key, value in proof.items() if key != 'entries'})
