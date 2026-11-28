"""Scoped packed publication; no CLI, deployment, scheduler or backup ownership.

The controller supplies actual execution custody, a complete pinned-reader roster
and a verifier binding independent recovery to the exact prepared graph. Retained
originals are hard links. Retirement leases the manifests AND their loose objects.
"""
from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess

import log_dedup as logs
import packed_objects as packed
import reclaim
from scoped_fence import ClosedLogFence, process_identity


def stable(st):
    # Our hard link changes ctime; body identity/length/mtime must not change.
    return logs.version(st)[:4]


def directory(path, create=False, source=False):
    if create:
        try:
            path.mkdir(mode=0o700)
            reclaim.sync_directory(path.parent)
        except FileExistsError:
            pass
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & (0o002 if source else 0o022):
        raise logs.ArchiveError('Owned nonsymlink directory required')


class PinnedReaders:
    def __init__(self, readers, owner_guard):
        if not readers or not callable(owner_guard):
            raise logs.ArchiveError('Actual complete reader roster required')
        self.owner_guard, self.identities = owner_guard, {}
        owner_guard()
        for row in readers:
            pid = row['pid']
            if type(pid) is not int or pid < 1 or pid in self.identities:
                raise logs.ArchiveError('Unique exact reader PID required')
            before = process_identity(pid)
            exe = Path('/proc', str(pid), 'exe')
            with exe.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            info = json.loads(subprocess.check_output([str(exe), '--build-info'], timeout=15))
            if digest != row['sha256'] or info.get('executionLogArchiveReaderPinProtocol') != 1:
                raise logs.ArchiveError('Reader lacks qualified manifest pin protocol')
            if process_identity(pid) != before:
                raise logs.ArchiveError('Reader changed during qualification')
            self.identities[pid] = before
        self.check()

    def check(self):
        self.owner_guard()
        if any(process_identity(pid) != identity for pid, identity in self.identities.items()):
            raise logs.ArchiveError('Pinned reader process or executable changed')


@contextmanager
def exclusive_lease(path, expected):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    acquired = False
    try:
        if stable(os.fstat(fd)) != expected or stable(logs.regular(path)) != expected:
            raise logs.ArchiveError('Retirement inode changed')
        fcntl.fcntl(fd, fcntl.F_SETOWN, os.getpid())
        fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_WRLCK)
        acquired = True
        yield fd
    finally:
        if acquired:
            fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_UNLCK)
        os.close(fd)


class PackedBatch:
    def __init__(self, plan, prepared, journal, fence, readers, recovery_guard, *, reserve_bytes):
        if not isinstance(fence, ClosedLogFence) or not isinstance(readers, PinnedReaders):
            raise logs.ArchiveError('Actual scoped writer and pinned reader custody required')
        if not callable(recovery_guard) or type(reserve_bytes) is not int or reserve_bytes < 0:
            raise logs.ArchiveError('Independent recovery verifier and explicit reserve required')
        self.plan, self.root = plan, Path(plan['source_root'])
        if self.root.resolve(strict=True) != self.root or fence.root != self.root:
            raise logs.ArchiveError('Canonical exact log root required')
        entries = plan['files']
        if (not 1 <= len(entries) <= 64 or len({r['path'] for r in entries}) != len(entries)
                or sum(r['raw_bytes'] for r in entries) > 2 * 1024**3
                or len({str(Path(r['path']).parent) for r in entries}) != 1):
            raise logs.ArchiveError('Bounded single-session selection required')
        self.parent = logs.safe_path(self.root, entries[0]['path']).parent
        self.prepared, self.journal = Path(prepared), Path(journal)
        if (self.prepared.resolve(strict=True) != self.prepared or self.journal.resolve() != self.journal
                or self.journal.is_relative_to(self.root) or self.journal.is_relative_to(self.prepared)
                or self.prepared.is_relative_to(self.root)):
            raise logs.ArchiveError('Canonical isolated preparation and journal required')
        self.key = logs.sha(reclaim.canonical(plan))
        self.retained = self.parent / ('.log-retained-' + self.key)
        self.fence, self.readers, self.recovery_guard = fence, readers, recovery_guard
        self.reserve = reserve_bytes

    def guard(self):
        self.fence.check()
        self.readers.check()
        for row in self.plan['files']:
            self.fence.validate_entry(row)
        directory(self.parent, source=True)
        fs = os.statvfs(self.parent)
        if fs.f_bavail * fs.f_frsize < self.reserve:
            raise logs.ArchiveError('Publication filesystem reserve reached')

    @contextmanager
    def locked(self):
        self.guard()
        directory(self.journal, create=True)
        fd = os.open(self.parent / '.log-pack.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o077:
                raise logs.ArchiveError('Unique private session publication lock required')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def save(self, name, value):
        reclaim.atomic_bytes(self.journal / name, reclaim.canonical(value) + b'\n')

    def seal(self):
        path = self.journal / 'PLAN.json'
        if path.exists():
            sealed = json.loads(path.read_bytes())
            if sealed['plan_sha256'] != self.key or sealed['prepared'] != str(self.prepared):
                raise logs.ArchiveError('Journal belongs to another operation')
            return sealed
        rows, packs = [], {}
        for entry in self.plan['files']:
            self.guard()
            source = logs.safe_path(self.root, entry['path'])
            st = logs.regular(source)
            if logs.version(st) != entry['identity']:
                raise logs.ArchiveError('Selected source version changed')
            meta = reclaim.metadata_for(source)
            physical = reclaim.file_hash(source)
            with source.open('rb') as stream:
                head = stream.read(len(logs.MAGIC))
            if head == logs.MAGIC:
                original = logs.reconstruct(source)
                logical = (original['sha256'], original['raw_bytes'])
            elif head == logs.PACKED_MAGIC:
                raise logs.ArchiveError('Repacking packed history requires a separate plan')
            else:
                logical = (physical, st.st_size)
            if logical != (entry['sha256'], entry['raw_bytes']):
                raise logs.ArchiveError('Actual source differs from logical selection')
            target = self.prepared / source.name
            result = packed.verify(target)
            if (result['sha256'], result['raw_bytes']) != logical:
                raise logs.ArchiveError('Packed logical history differs from original')
            for pack in logs.physical_objects(target, packed.load_manifest(target)):
                if reclaim.file_hash(pack) != pack.stem:
                    raise logs.ArchiveError('Full prepared pack hash differs')
                packs[pack.name] = dict(sha256=pack.stem, bytes=pack.stat().st_size)
            rows.append(dict(path=entry['path'], original=stable(st), metadata=meta,
                             original_sha256=physical, packed_sha256=reclaim.file_hash(target)))
            if logs.version(logs.regular(source)) != entry['identity']:
                raise logs.ArchiveError('Source changed during verification')
        sealed = dict(plan_sha256=self.key, prepared=str(self.prepared), files=rows, packs=packs)
        self.recovery_guard(sealed)
        self.guard()
        self.save('PLAN.json', sealed)
        return sealed

    def checked(self, path, expected, digest, links, metadata=None):
        st = logs.regular(path)
        if stable(st) != expected or st.st_uid != os.getuid() or st.st_nlink not in links:
            raise logs.ArchiveError('Expected owned inode changed')
        if reclaim.file_hash(path) != digest:
            raise logs.ArchiveError('Expected file bytes changed')
        if metadata is not None:
            import base64
            actual = dict(uid=st.st_uid, gid=st.st_gid, mode=stat.S_IMODE(st.st_mode),
                          mtime_ns=st.st_mtime_ns,
                          xattrs={k: base64.b64encode(os.getxattr(path, k)).decode() for k in os.listxattr(path)})
            if actual != {k: v for k, v in metadata.items() if k != 'atime_ns'}:
                raise logs.ArchiveError('Selected Linux metadata changed')

    def install_packs(self, sealed):
        store = self.parent / '.log-packs'
        directory(store, create=True)
        for name, row in sealed['packs'].items():
            self.guard()
            source, target = self.prepared / '.log-packs' / name, store / name
            if reclaim.file_hash(source) != row['sha256']:
                raise logs.ArchiveError('Prepared pack changed after recovery')
            temp = self.retained / name
            if not target.exists() and not target.is_symlink():
                fs = os.statvfs(store)
                if fs.f_bavail * fs.f_frsize < self.reserve + row['bytes']:
                    raise logs.ArchiveError('Insufficient space for one packed object')
                if not temp.exists():
                    with source.open('rb') as inp, temp.open('xb') as out:
                        os.fchmod(out.fileno(), 0o600)
                        while block := inp.read(1024 * 1024):
                            out.write(block)
                        out.flush()
                        os.fsync(out.fileno())
                if reclaim.file_hash(temp) != row['sha256']:
                    raise logs.ArchiveError('Interrupted pack staging requires review')
                self.guard()
                os.link(temp, target, follow_symlinks=False)
                reclaim.sync_directory(store)
            if reclaim.file_hash(target) != row['sha256']:
                raise logs.ArchiveError('Existing CAS pack differs; preserve it')
            if temp.exists():
                if not os.path.samefile(temp, target):
                    raise logs.ArchiveError('Foreign pack staging requires review')
                temp.unlink()
                reclaim.sync_directory(self.retained)

    def publish(self, checkpoint=lambda phase, path: None):
        with self.locked():
            if (self.journal / 'RETIRED.json').exists():
                raise logs.ArchiveError('Completed operation must not be republished')
            sealed = self.seal()
            self.recovery_guard(sealed)
            directory(self.retained, create=True)
            self.install_packs(sealed)
            for index, row in enumerate(sealed['files']):
                self.guard()
                source = logs.safe_path(self.root, row['path'])
                old, new = self.retained / (source.name + '.old'), self.retained / (source.name + '.new')
                state_path = self.journal / f'ENTRY-{index:03}.json'
                state = json.loads(state_path.read_bytes()) if state_path.exists() else None
                if state and stable(logs.regular(source)) == state['new']:
                    self.checked(source, state['new'], row['packed_sha256'], [1], row['metadata'])
                    packed.verify(source)
                    continue
                self.checked(source, row['original'], row['original_sha256'], [1, 2], row['metadata'])
                if not old.exists():
                    if logs.regular(source).st_nlink != 1:
                        raise logs.ArchiveError('Unexplained original hard link')
                    os.link(source, old, follow_symlinks=False)
                    reclaim.sync_directory(self.retained)
                    checkpoint('original_retained', source)
                self.checked(old, row['original'], row['original_sha256'], [2], row['metadata'])
                if not new.exists():
                    logs.write_new(new, (self.prepared / source.name).read_bytes())
                    reclaim.apply_metadata(new, row['metadata'])
                    with new.open('rb') as stream:
                        os.fsync(stream.fileno())
                    reclaim.sync_directory(self.retained)
                if reclaim.file_hash(new) != row['packed_sha256']:
                    raise logs.ArchiveError('Interrupted manifest staging requires review')
                self.checked(new, stable(logs.regular(new)), row['packed_sha256'], [1], row['metadata'])
                new_state = dict(new=stable(logs.regular(new)), source=row['path'])
                if state is not None and state != new_state:
                    raise logs.ArchiveError('Staged replacement inode changed')
                self.save(state_path.name, new_state)
                self.guard()
                self.checked(source, row['original'], row['original_sha256'], [2], row['metadata'])
                os.replace(new, source)
                reclaim.sync_directory(source.parent)
                reclaim.sync_directory(self.retained)
                checkpoint('manifest_published', source)
                packed.verify(source)
            self.guard()
            result = dict(published=len(sealed['files']), plan_sha256=self.key, originals_retained=True)
            self.save('PUBLISHED.json', result)
            return result

    def remaining_loose_references(self):
        referenced = set()
        paths = list(self.parent.glob('*.jsonl'))
        for other in self.parent.glob('.log-retained-*'):
            directory(other)
            if other != self.retained:
                paths.extend(other.glob('*.old'))
        for path in paths:
            logs.regular(path)
            with path.open('rb') as stream:
                head = stream.read(len(logs.MAGIC))
            if head == logs.MAGIC:
                referenced.update(c['sha256'] for c in logs.load_manifest(path)['chunks'])
            elif head == logs.PACKED_MAGIC:
                packed.load_manifest(path)
        return referenced

    def retire(self, checkpoint=lambda phase, path: None):
        with self.locked(), ExitStack() as stack:
            sealed = self.seal()
            published = json.loads((self.journal / 'PUBLISHED.json').read_bytes())
            if published['plan_sha256'] != self.key:
                raise logs.ArchiveError('Publication receipt differs')
            self.recovery_guard(sealed)
            previous = signal.getsignal(signal.SIGIO)
            def broken(*_):
                raise logs.ArchiveError('Consumer appeared during retirement')
            signal.signal(signal.SIGIO, broken)
            stack.callback(signal.signal, signal.SIGIO, previous)
            intent = self.journal / 'RETIREMENT.json'
            if intent.exists():
                retirement = json.loads(intent.read_bytes())
                if retirement['plan_sha256'] != self.key:
                    raise logs.ArchiveError('Retirement selection differs')
            else:
                retirement = dict(plan_sha256=self.key, objects={})
                for index, row in enumerate(sealed['files']):
                    source = logs.safe_path(self.root, row['path'])
                    state = json.loads((self.journal / f'ENTRY-{index:03}.json').read_bytes())
                    self.checked(source, state['new'], row['packed_sha256'], [1], row['metadata'])
                    packed.verify(source)
                    old = self.retained / (source.name + '.old')
                    self.checked(old, row['original'], row['original_sha256'], [1], row['metadata'])
                    with old.open('rb') as stream:
                        head = stream.read(len(logs.MAGIC))
                    if head == logs.MAGIC:
                        for chunk in logs.load_manifest(old)['chunks']:
                            key = chunk['sha256']
                            if key in retirement['objects']:
                                continue
                            obj = self.parent / '.log-objects' / (key + '.gz')
                            before = logs.regular(obj)
                            reclaim.object_bytes(obj, chunk)
                            retirement['objects'][key] = dict(identity=stable(before), sha256=reclaim.file_hash(obj))
                self.save('RETIREMENT.json', retirement)
            ready_path = self.journal / 'RELEASE_READY.json'
            ready = json.loads(ready_path.read_bytes()) if ready_path.exists() else None
            if ready is not None and ready['plan_sha256'] != self.key:
                raise logs.ArchiveError('Original release receipt differs')
            for index, row in enumerate(sealed['files']):
                state = json.loads((self.journal / f'ENTRY-{index:03}.json').read_bytes())
                source = logs.safe_path(self.root, row['path'])
                self.checked(source, state['new'], row['packed_sha256'], [1], row['metadata'])
                packed.verify(source)
                old = self.retained / (source.name + '.old')
                if old.exists():
                    self.checked(old, row['original'], row['original_sha256'], [1], row['metadata'])
                    stack.enter_context(exclusive_lease(old, row['original']))
                elif ready is None:
                    raise logs.ArchiveError('Missing original pin without proven safe release')
            referenced = self.remaining_loose_references()
            removed, retained = 0, 0
            candidates = retirement['objects'] if ready is None else {}
            for number, (key, row) in enumerate(candidates.items()):
                if key in referenced:
                    retained += 1
                    continue
                obj = self.parent / '.log-objects' / (key + '.gz')
                if number % 64 == 0:
                    self.guard()
                if not obj.exists() and not obj.is_symlink():
                    continue  # Only exact names in a durable prior unlink intent.
                self.checked(obj, row['identity'], row['sha256'], [1])
                with exclusive_lease(obj, row['identity']):
                    if stable(logs.regular(obj)) != row['identity']:
                        raise logs.ArchiveError('Object changed at unlink boundary')
                    obj.unlink()
                    removed += 1
                    checkpoint('object_retired', obj)
            self.guard()
            store = self.parent / '.log-objects'
            if store.exists():
                reclaim.sync_directory(store)
            if ready is None:
                ready = dict(plan_sha256=self.key, objects_removed_this_call=removed,
                             objects_kept_for_other_manifests=retained, all_original_leases_held=True)
                self.save('RELEASE_READY.json', ready)
            for row in sealed['files']:
                old = self.retained / (Path(row['path']).name + '.old')
                if old.exists():
                    self.guard()
                    if stable(logs.regular(old)) != row['original']:
                        raise logs.ArchiveError('Original changed at unlink boundary')
                    old.unlink()
                    checkpoint('original_retired', old)
            if self.retained.exists():
                reclaim.sync_directory(self.retained)
                self.retained.rmdir()
                reclaim.sync_directory(self.parent)
            result = dict(ready, originals_released=True)
            self.save('RETIRED.json', result)
            return result
