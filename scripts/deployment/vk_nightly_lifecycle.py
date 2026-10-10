"""Bounded, unprivileged job lifecycle for a NEW enrolled normal-nightly scope.

Fixed source adapters supply an independent capture (parent=None), register their
own transient input files at creation, and seal them before materialization.
This is not a root authorization boundary or a general cleanup facility.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from vk_nightly_generation import (MAX_INDEX, PRODUCER as STORE_PRODUCER, advance_verified_capture, digest_stream,
                                  encoded, regular, write_new, object_blocks)


PRODUCER = 'vk-normal-nightly-job-v1'
MAX_INPUT_FILES = 1024  # Includes serial DB snapshots; actual plan declares 71 DBs.


def pin(info):
    return [info.st_dev, info.st_ino]


def directory_pin(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError('job directory substituted; preserve artifacts')
    return pin(info)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def unlink_pinned(path, identity, *, parent_identity=None):
    """Exact file only, no symlinks, and FD-relative identity recheck."""
    try:
        with regular(path) as stream:
            if pin(os.fstat(stream.fileno())) != identity:
                raise ValueError('job file substituted; preserve artifacts')
        expected_parent = parent_identity or directory_pin(path.parent)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if pin(os.fstat(fd)) != expected_parent: raise ValueError('unlink parent substituted')
            info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or pin(info) != identity:
                raise ValueError('job unlink identity changed; preserve artifacts')
            os.unlink(path.name, dir_fd=fd)
            os.fsync(fd)
        finally: os.close(fd)
    except FileNotFoundError:
        return  # Idempotent only for a recorded exact name.


class NightlyJob:
    def __init__(self, root, store, *, capture_limit_bytes, changed_limit_bytes):
        self.root, self.store = Path(root), store
        if self.root == store.root or self.root.parent != store.root.parent:
            raise ValueError('job and store must be separate siblings in the new operational scope')
        self.identity = directory_pin(self.root)
        for value in (capture_limit_bytes, changed_limit_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError('positive explicit capture/changed-byte limits required')
        self.capture_limit, self.changed_limit = capture_limit_bytes, changed_limit_bytes
        self._active_intent = None

    def enroll_empty(self):
        if list(self.root.iterdir()):
            raise ValueError('job scope enrollment requires a new empty directory')
        write_new(self.root / 'job-scope.json', encoded(self.binding()))
        sync_directory(self.root)

    def binding(self):
        return {'producer': PRODUCER, 'scope_sha256': self.store.scope,
                'root_identity': self.identity, 'store_identity': list(self.store.identity),
                'reserved_scratch': ['attempt.new', 'progress.new']}

    def check(self):
        self.store.check()
        if directory_pin(self.root) != self.identity:
            raise ValueError('job root substituted')
        with regular(self.root / 'job-scope.json') as stream:
            if json.loads(stream.read(4097)) != self.binding():
                raise ValueError('job scope binding changed')
        allowed = {'job-scope.json', 'job.lock', 'attempt.json', 'attempt.new', 'progress.json', 'progress.new'}
        if (self.root / 'attempt.json').exists():
            allowed.add(self.read()['input_name'])
        if {p.name for p in self.root.iterdir()} - allowed:
            raise ValueError('unexpected job evidence; preserve and reconcile')

    @contextmanager
    def held(self):
        self.check()
        fd = os.open(self.root / 'job.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a+b') as lease:
            if not stat.S_ISREG(os.fstat(lease.fileno()).st_mode): raise ValueError('invalid job lease')
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for name in ('attempt.new','progress.new'):
                scratch = self.root / name
                if os.path.lexists(scratch):
                    with regular(scratch) as stream: identity = pin(os.fstat(stream.fileno()))
                    unlink_pinned(scratch,identity)
            try: yield
            finally: self._active_intent = None

    def read(self):
        try:
            return self._read()
        except (KeyError,TypeError,AttributeError) as error:
            raise ValueError('invalid recorded job metadata; preserve artifacts') from error

    def _read(self):
        with regular(self.root / 'attempt.json') as stream:
            data=stream.read(MAX_INDEX + 1)
        if len(data)>MAX_INDEX:raise ValueError('job metadata exceeds explicit bound')
        value=json.loads(data)
        if os.path.lexists(self.root/'progress.json'):
            with regular(self.root/'progress.json') as stream: data=stream.read(16385)
            if len(data)>16384:raise ValueError('mutable progress exceeds explicit bound')
            progress=json.loads(data)
            if progress['binding'] != self.binding() or progress['candidate'] != value['candidate']:
                raise ValueError('replayed or substituted progress; preserve artifacts')
            for key in ('candidate_directories','partial','pointer'): value[key] = progress[key]
        if value['binding'] != self.binding() or not re.fullmatch('input-[0-9a-f]{32}', value['input_name']) \
                or not re.fullmatch('generation-[0-9a-f]{32}', value['candidate']):
            raise ValueError('invalid job intent; preserve artifacts')
        for checksum in value['expected_objects']:
            if not re.fullmatch('[0-9a-f]{64}', checksum): raise ValueError('unsafe recorded object selector')
        previous = value['previous']
        if previous:
            if not re.fullmatch('generation-[0-9a-f]{32}',previous['generation']): raise ValueError('unsafe previous generation')
            for raw,row in previous['files'].items():
                if raw != 'manifest.json' and not re.fullmatch('objects/[0-9a-f]{64}',raw): raise ValueError('unsafe recorded retention path')
                if not re.fullmatch('[0-9a-f]{64}',row['sha256']): raise ValueError('unsafe recorded retention digest')
        if value['partial'] and not re.fullmatch('partial-[0-9a-f]{32}',value['partial']['name']):
            raise ValueError('unsafe recorded partial selector')
        return value

    def save(self, value):
        # One bounded ledger, no retained per-night job history or payload cache.
        stage = self.root / 'attempt.new'
        write_new(stage, encoded(value))
        os.replace(stage, self.root / 'attempt.json')
        sync_directory(self.root)

    def register_input(self, path, fd):
        value = self.read();path = Path(path)
        if path.parent != self.root / value['input_name'] or not re.fullmatch('[A-Za-z0-9_.-]+', path.name):
            raise ValueError('input registration outside exact job directory')
        if len(value['inputs']) >= MAX_INPUT_FILES or path.name in value['inputs']:
            raise ValueError('duplicate/excessive transient input registration')
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode): raise ValueError('input must be a new regular file')
        value['inputs'][path.name] = {'identity': pin(info), 'sealed': False}
        self.save(value)

    def seal_input(self, path):
        value = self.read();path = Path(path)
        if path.parent != self.root / value['input_name'] or path.name not in value['inputs']:
            raise ValueError('unknown transient input')
        with regular(path) as stream:
            info = os.fstat(stream.fileno());checksum = digest_stream(stream)
        row = value['inputs'][path.name]
        if pin(info) != row['identity']: raise ValueError('transient input substituted')
        row.update(sealed=True, bytes=info.st_size, sha256=checksum)
        if sum(item.get('bytes', 0) for item in value['inputs'].values()) > self.capture_limit:
            raise ValueError('transient capture capacity exceeded')
        self.save(value)

    def snapshot(self, manifest):
        folder = self.store.root / manifest['generation']
        expected = {row['sha256'] for row in manifest['entries'].values() if row['kind']=='file'}
        if {p.name for p in folder.iterdir()} != {'objects','manifest.json'} \
                or {p.name for p in (folder/'objects').iterdir()} != expected:
            raise ValueError('unexpected previous-generation evidence; preserve')
        result = {'generation': manifest['generation'], 'folder': directory_pin(folder),
                  'objects': directory_pin(folder / 'objects'), 'files': {}}
        for path in [folder / 'manifest.json', *sorted((folder / 'objects').iterdir())]:
            with regular(path) as stream:
                result['files'][str(path.relative_to(folder))] = {
                    'identity': pin(os.fstat(stream.fileno())),
                    'sha256': digest_stream(stream)}
        return result

    def observe(self, event, detail):
        value = self._active_intent if self._active_intent is not None else self.read()
        if event == 'directories':
            value['candidate_directories'] = [directory_pin(path) for path in detail]
        elif event == 'partial':
            path, info = detail
            value['partial'] = {'name': path.name, 'identity': pin(info)}
        elif event == 'manifest':
            if value['candidate_manifest_sha256'] != hashlib.sha256(encoded(detail)).hexdigest():
                raise ValueError('materialized candidate differs from authenticated full capture')
            return
        elif event == 'pointer':
            path, info = detail
            value['pointer'] = {'name': path.name, 'identity': pin(info)}
        # Mutable per-file progress is small: do not rewrite/reparse a host-scale
        # immutable object inventory for every changed file (quadratic I/O).
        progress = {key: value[key] for key in ('binding','candidate','candidate_directories','partial','pointer')}
        stage = self.root/'progress.new'
        write_new(stage,encoded(progress));os.replace(stage,self.root/'progress.json');sync_directory(self.root)

    def run(self, capture_factory, *, retention_adopted=False, reserve_bytes):
        """Factory(folder, register, seal, *, parent=None) -> provider,id,descriptor.

        Adapter must bound bytes while streaming, close/reap its own producers
        before returning/raising, and register each exact input before writing.
        Full independent captures rebase input chains every run. Generation
        storage remains incremental; raw transfer is presently full, not delta.
        """
        if retention_adopted is not True: raise ValueError('nightly lifecycle adoption not authorized')
        with self.held():
            if (self.root / 'attempt.json').exists():
                return {'passed': False, 'status': 'reconciliation_required', 'next': 'reconcile the recorded attempt before capture'}
            # Reservation includes transient compressed input and changed object
            # payload plus manifest allowance; never silently use protected backups.
            import shutil
            if type(reserve_bytes) is not int or reserve_bytes < self.capture_limit + self.changed_limit + MAX_INDEX \
                    or shutil.disk_usage(self.store.root).free < reserve_bytes:
                raise ValueError('insufficient reserved capacity for bounded capture plus generation overlap')
            previous = self.store.current()
            if previous: self.store.verify(previous)
            value = {'binding': self.binding(), 'input_name': 'input-' + uuid.uuid4().hex,
                     'candidate': 'generation-' + uuid.uuid4().hex, 'inputs': {},
                     'previous': self.snapshot(previous) if previous else None,
                     'expected_objects': {}, 'candidate_directories': None, 'partial': None, 'pointer': None}
            self.save(value)
            folder = self.root / value['input_name'];folder.mkdir()
            value['input_identity'] = directory_pin(folder);self.save(value)
            try:
                provider, capture_id, descriptor = capture_factory(folder, self.register_input, self.seal_input, parent=None)
                registered = provider.records[capture_id]['result']
                if descriptor.get('parent') is not None or registered.get('parent') is not None:
                    raise ValueError('capture chain must be rebased; retired archive parents are forbidden')
                value = self.read()
                if not value['inputs'] or any(not row['sealed'] for row in value['inputs'].values()):
                    raise ValueError('transient capture inputs are not sealed')
                proof = provider.verify(capture_id)
                value['expected_objects'] = {row['sha256']: row['bytes'] for row in proof['entries'].values() if row['kind'] == 'file'}
                candidate_manifest = {
                    'producer': STORE_PRODUCER, 'generation': value['candidate'], 'scope_sha256': self.store.scope,
                    'parent': None, 'entries': proof['entries'],
                    'capture_context': {key: item for key,item in proof.items() if key != 'entries'}}
                if self.store.object_encoding:
                    candidate_manifest['object_encoding'] = self.store.object_encoding
                value['candidate_manifest_sha256'] = hashlib.sha256(encoded(candidate_manifest)).hexdigest()
                self.save(value)
                self._active_intent = value
                result = advance_verified_capture(self.store, provider, capture_id,
                    reserve_bytes=self.changed_limit, retention_adopted=False,
                    generation=value['candidate'], observe=self.observe, verified_proof=proof)
                # Independent clearance/readback has completed. Retention uses
                # the same resumable recorded identities on normal and crash paths.
                self._reconcile_held()
                return {**result, 'passed': True, 'status': 'current_verified', 'capture_parent': None,
                        'transient_inputs_retained': False,
                        'raw_transfer': proof.get('transport','full independent capture'),
                        'old_generation_retained': False, 'cleanup_performed': previous is not None,
                        'retention_blocker': None}
            except Exception as error:
                return {'passed': False, 'status': 'reconciliation_required', 'reason': str(error),
                        'next': 'reconcile the recorded attempt; preserve current and unknown artifacts'}

    def reconcile(self, *, retention_adopted=False, inputs_quiescent=False):
        if retention_adopted is not True or inputs_quiescent is not True:
            raise ValueError('adopted retention and adapter producer-quiescence attestation required')
        with self.held():
            return self._reconcile_held()

    def tick(self, capture_factory, attest_inputs_quiescent, *, retention_adopted=False, reserve_bytes):
        """Scripted scheduler entry: reconcile an owned prior attempt, then capture.

        The fixed adapter attests its actual producer/channel completion against
        this exact nonce; an active producer defers work without another capture.
        Same-account source callbacks are cooperative controls, not root security.
        """
        if retention_adopted is not True: raise ValueError('nightly lifecycle adoption not authorized')
        try:
            with self.held():
                if os.path.lexists(self.root/'attempt.json'):
                    attempt=self.read()
                    expected={'candidate':attempt['candidate'],'input_name':attempt['input_name'],
                              'scope_sha256':self.store.scope,'quiescent':True}
                    if attest_inputs_quiescent(attempt) != expected:
                        return {'passed':False,'status':'input_producer_active',
                                'next':'wait for this exact producer to close; next scripted tick retries without new inputs'}
                    self._reconcile_held()
            return self.run(capture_factory,retention_adopted=True,reserve_bytes=reserve_bytes)
        except (ValueError,OSError) as error:
            return {'passed':False,'status':'reconciliation_blocked','reason':str(error),
                    'next':'preserve current and unexpected artifacts; review the exact binding/identity discrepancy'}

    def _remove_recorded(self, folder, snapshot):
        if not os.path.lexists(folder): return
        if directory_pin(folder) != snapshot['folder']: raise ValueError('retention folder changed')
        objects = folder / 'objects'
        if os.path.lexists(objects) and directory_pin(objects) != snapshot['objects']:
            raise ValueError('retention objects directory changed')
        present = {str(p.relative_to(folder)) for p in folder.iterdir() if p.name != 'objects'}
        if os.path.lexists(objects): present.update('objects/' + p.name for p in objects.iterdir())
        if present - snapshot['files'].keys(): raise ValueError('unexpected retention evidence; preserve')
        # Validate all remaining inputs before the first unlink; missing exact
        # recorded names are permitted only on this resumable job path.
        for raw in sorted(present):
            path = folder / raw;row = snapshot['files'][raw]
            with regular(path) as stream:
                if pin(os.fstat(stream.fileno())) != row['identity'] or digest_stream(stream) != row['sha256']:
                    raise ValueError('retention input changed; preserve')
        for raw in sorted(present):
            unlink_pinned(folder / raw, snapshot['files'][raw]['identity'],
                          parent_identity=snapshot['objects'] if raw.startswith('objects/') else snapshot['folder'])
        if os.path.lexists(objects):
            if directory_pin(objects)!=snapshot['objects']:raise ValueError('objects changed before rmdir')
            objects.rmdir()
        if directory_pin(folder)!=snapshot['folder']:raise ValueError('generation changed before rmdir')
        folder.rmdir();sync_directory(folder.parent)

    def _reconcile_held(self):
        value = self.read();current = self.store.current()
        allowed = {'store.json','lease','current.json',value['candidate']}
        if value['previous']: allowed.add(value['previous']['generation'])
        if value['pointer']: allowed.add(value['pointer']['name'])
        if {p.name for p in self.store.root.iterdir()} - allowed:
            raise ValueError('unexpected store evidence; preserve all attempts')
        inputs = self.root / value['input_name']
        if os.path.lexists(inputs):
            if directory_pin(inputs) != value['input_identity']: raise ValueError('input directory changed')
            if {p.name for p in inputs.iterdir()} - value['inputs'].keys(): raise ValueError('unexpected transient input; preserve')
            for raw,row in value['inputs'].items():
                if not re.fullmatch('[A-Za-z0-9_.-]+',raw) or raw in ('.','..'): raise ValueError('unsafe input intent')
                if os.path.lexists(inputs/raw):
                    with regular(inputs/raw) as stream:
                        info=os.fstat(stream.fileno())
                        if pin(info) != row['identity']: raise ValueError('input substituted')
                        if row['sealed'] and (info.st_size != row['bytes'] or digest_stream(stream) != row['sha256']):
                            raise ValueError('sealed input changed; preserve')
        # A genuinely verified current is required before discarding any old
        # nightly. New incomplete inputs may be discarded without a first current.
        if current:
            self.store.verify(current)
            if self.store.independent_readback is None or self.store.independent_readback(
                    self.store.root / current['generation'], current) != {
                    'physical_b_verified': True, 'generation': current['generation'],
                    'scope_sha256': self.store.scope, 'manifest_sha256': hashlib.sha256(encoded(current)).hexdigest()}:
                raise ValueError('independent current readback failed; preserve all attempts')
        published = current is not None and current['generation'] == value['candidate']
        if published:
            if hashlib.sha256(encoded(current)).hexdigest() != value.get('candidate_manifest_sha256'):
                raise ValueError('published candidate differs from recorded job')
            # A crash may have followed current.json rename but preceded its
            # store-directory fsync. Make publication durable before retention.
            sync_directory(self.store.root)
            if value['previous']:
                self._remove_recorded(self.store.root / value['previous']['generation'], value['previous'])
        else:
            if (current['generation'] if current else None) != (value['previous']['generation'] if value['previous'] else None):
                raise ValueError('current moved outside job; preserve artifacts')
            folder = self.store.root / value['candidate']
            if os.path.lexists(folder):
                directories = value['candidate_directories']
                if not directories or directory_pin(folder) != directories[0]:
                    raise ValueError('incomplete candidate ownership not established; preserve')
                objects = folder / 'objects'
                snapshot = {'folder': directories[0], 'objects': directories[1], 'files': {}}
                if not os.path.lexists(objects):
                    # Resume only the recorded, empty directory left by an
                    # interruption after objects/ removal and before rmdir.
                    if list(folder.iterdir()):
                        raise ValueError('missing candidate objects with remaining evidence; preserve')
                else:
                    if directory_pin(objects) != directories[1]:
                        raise ValueError('incomplete candidate ownership not established; preserve')
                    expected = set(value['expected_objects'])
                    partial = value['partial']
                    if partial: expected.add(partial['name'])
                    if {p.name for p in folder.iterdir()} - {'objects','manifest.json'} \
                            or {p.name for p in objects.iterdir()} - expected:
                        raise ValueError('unexpected incomplete candidate evidence; preserve')
                    for path in [*objects.iterdir(), *([folder/'manifest.json'] if (folder/'manifest.json').exists() else [])]:
                        with regular(path) as stream:
                            info = os.fstat(stream.fileno());checksum = digest_stream(stream)
                        if path.parent == objects:
                            if partial and path.name == partial['name']:
                                if pin(info) != partial['identity']: raise ValueError('partial substituted')
                            else:
                                for _ in object_blocks(path, path.name, value['expected_objects'][path.name],
                                                       self.store.object_encoding): pass
                        elif checksum != value.get('candidate_manifest_sha256'):
                            raise ValueError('candidate manifest changed')
                        snapshot['files'][str(path.relative_to(folder))] = {'identity': pin(info), 'sha256': checksum}
                self._remove_recorded(folder, snapshot)
        pointer = value['pointer']
        if pointer:
            if not re.fullmatch(r'current-[0-9a-f]{32}\.json', pointer['name']): raise ValueError('unsafe pointer intent')
            unlink_pinned(self.store.root / pointer['name'], pointer['identity'])
        inputs = self.root / value['input_name']
        if os.path.lexists(inputs):
            if directory_pin(inputs) != value['input_identity']: raise ValueError('input directory changed')
            if {p.name for p in inputs.iterdir()} - value['inputs'].keys(): raise ValueError('unexpected transient input; preserve')
            for raw,row in value['inputs'].items():
                if not re.fullmatch('[A-Za-z0-9_.-]+',raw) or raw in ('.','..'): raise ValueError('unsafe input intent')
                unlink_pinned(inputs/raw,row['identity'],parent_identity=value['input_identity'])
            if directory_pin(inputs)!=value['input_identity']:raise ValueError('input directory changed before rmdir')
            inputs.rmdir();sync_directory(self.root)
        if os.path.lexists(self.root/'progress.json'):
            with regular(self.root/'progress.json') as stream: identity = pin(os.fstat(stream.fileno()))
            unlink_pinned(self.root/'progress.json',identity)
        with regular(self.root/'attempt.json') as stream: identity = pin(os.fstat(stream.fileno()))
        unlink_pinned(self.root/'attempt.json',identity)
        return {'passed': True, 'status': 'current_verified' if current else 'first_capture_retry_ready',
                'published': published, 'reconciliation_complete': True}
