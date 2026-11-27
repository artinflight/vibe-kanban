"""Workspace archive adapter for the maintained, source-pinned Nightly owner.

Uses its existing native B object capture, immutable selected-file indexes and
independent normal Linux B reader. No SSH/server implementation, new body codec,
backup timer, global inventory or service action lives here. The owner supplies
an already-qualified context factory and exact current configuration/leases.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import uuid

from catalog import canonical
from lifecycle import digest
import payloads

EMPTY_INDEX = '295adaa7a96156ecb42cb882734ab52b98cf03494919718a365d86181fe56660'


def nightly_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def nightly_digest(value):
    return hashlib.sha256(nightly_json(value)).hexdigest()


def immutable(path, raw):
    path = Path(path)
    payloads.parent_safe(path)
    if os.path.lexists(path):
        st = path.lstat()
        if (path.is_symlink() or not path.is_file() or st.st_uid != os.getuid()
                or st.st_nlink != 1 or st.st_mode & 0o077 or path.read_bytes() != raw):
            raise ValueError('Conflicting retained archive control file')
        return
    with path.open('xb') as out:
        os.chmod(path, 0o600)
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    payloads.directory_sync(path.parent)


def requests(manifest, plan_path):
    """Partition only declared files within the existing 128-member protocol."""
    groups = {}
    for row in manifest['payloads']['entries']:
        if row['kind'] != 'file':
            continue
        root = Path(manifest['payloads']['roots'][row['root']])
        namespace = str(root.parent)
        path = root / row['relative']
        groups.setdefault(namespace, []).append(dict(relative=str(path.relative_to(root.parent)),
            normal_namespace_name=str(path).lstrip('/'), bytes=row['bytes'], sha256=row['sha256'],
            Linux_metadata={k: row['metadata'][k] for k in ('uid', 'gid', 'mode', 'mtime_ns', 'xattrs')}))
    for namespace, files in sorted(groups.items()):
        for start in range(0, len(files), 128):
            yield dict(source_root=namespace, files=files[start:start+128],
                       plan_path=str(plan_path), plan_sha256=nightly_digest(manifest))


class Blocks(io.RawIOBase):
    """Adapt the normal reader's bounded iterator without buffering a whole file."""
    def __init__(self, blocks):
        self.iterator, self.pending = iter(blocks), memoryview(b'')

    def readable(self):
        return True

    def readinto(self, target):
        if not self.pending:
            try:
                self.pending = memoryview(next(self.iterator))
            except StopIteration:
                return 0
        count = min(len(target), len(self.pending))
        target[:count] = self.pending[:count]
        self.pending = self.pending[count:]
        return count

    def close(self):
        if hasattr(self.iterator, 'close'):
            self.iterator.close()
        super().close()


class NormalB:
    def __init__(self, context, factory, selected, controls, template, work_root, guard):
        self.context, self.factory, self.selected, self.controls = context, factory, selected, controls
        self.template = json.loads(json.dumps(template))
        self.work_root, self.guard = Path(work_root), guard
        self.source_versions = {}
        payloads.parent_safe(self.work_root)
        st = self.work_root.lstat()
        if (self.work_root.is_symlink() or not self.work_root.is_dir()
                or st.st_uid != os.getuid() or st.st_mode & 0o077):
            raise ValueError('Private owned SSD control root required')
        self.check()

    def check(self):
        self.guard()
        folder = Path(self.template['source_folder'])
        pins = self.template['source_sha256']
        for module in (self.factory, self.selected, self.controls):
            file = Path(module.__file__)
            if file.parent != folder or file.name not in pins:
                raise ValueError('Archive adapter Nightly source identity differs')
        # Includes dynamically bootstrapped B reader dependencies, not just the
        # three entry modules. Qualification must package this complete closure.
        for name, sha in pins.items():
            path = folder / name
            if Path(name).name != name or path.resolve(strict=True) != path:
                raise ValueError('Canonical pinned Nightly source required')
            before = payloads.signature(path.lstat())
            if name in self.source_versions:
                if before != self.source_versions[name]:
                    raise ValueError('Pinned Nightly source changed during operation')
            else:
                if (hashlib.sha256(path.read_bytes()).hexdigest() != sha
                        or payloads.signature(path.lstat()) != before):
                    raise ValueError('Nightly dependency source changed')
                self.source_versions[name] = before

    def folder(self, operation):
        operation = str(uuid.UUID(operation))
        path = self.work_root / operation
        if not path.exists():
            path.mkdir(mode=0o700)
            payloads.directory_sync(path.parent)
        st = path.lstat()
        if path.is_symlink() or not path.is_dir() or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ValueError('Exact private archive operation directory required')
        return path

    def capture(self, manifest):
        self.check()
        folder = self.folder(manifest['operation_id'])
        plan = folder / 'manifest.json'
        immutable(plan, canonical(manifest).encode())
        batches = []
        with self.context() as recovery:
            if not recovery.location.startswith('desktop:B:/vk-backups/'):
                raise ValueError('Canonical Desktop B owner required')
            base = getattr(recovery, 'original', recovery)
            client = base.handle.db.client
            # Reuse recipes already in the held normal catalog. Missing file
            # versions use the existing CAS, whose identical chunks are reused.
            carriers = {(m['sha256'], m['bytes']): m for m in base.handle.rows.values()}
            for number, request in enumerate(requests(manifest, plan)):
                self.check()
                recovery.check()
                key = 'workspace-archive-' + uuid.UUID(manifest['operation_id']).hex + '-' + str(number)
                request_path = folder / ('request-' + str(number) + '.json')
                immutable(request_path, nightly_json(request))
                db = client.connect(key, EMPTY_INDEX)
                try:
                    db.execute('create table if not exists archive_request(sha256 text primary key)')
                    existing = db.execute('select sha256 from archive_request').fetchall()
                    wanted = nightly_digest(request)
                    if not existing:
                        db.execute('insert into archive_request values(?)', (wanted,))
                    elif existing != [(wanted,)]:
                        raise ValueError('Uncertain B operation belongs to a different request')
                    self.factory.capture_missing(recovery, request, carriers, self.template['dependencies'], db,
                        maximum_source_bytes=sum(f['bytes'] for f in request['files']), chunk_bytes=payloads.CHUNK)
                    result = self.factory.build_rows(request, carriers, self.template['dependencies'])
                    if not result['complete']:
                        raise ValueError('Complete declared B dependency closure is unavailable')
                    # Exactly the maintained selected-reader index schema. The
                    # normal reader separately reopens its immutable B image.
                    db.execute('create table if not exists selected_recovery_request(format text,request_sha256 text)')
                    db.execute('create table if not exists selected_recovery_members(name text primary key,row blob) without rowid')
                    old = db.execute('select format,request_sha256 from selected_recovery_request').fetchall()
                    if not old:
                        db.execute('begin immediate')
                        try:
                            for name, row in sorted(result['rows'].items()):
                                db.execute('insert into selected_recovery_members values(?,?)',
                                           (name, self.factory.encode_member(row)))
                            db.execute('insert into selected_recovery_request values(?,?)',
                                       ('vk-nightly-selected-original-versions-v1', wanted))
                            db.execute('commit')
                        except BaseException:
                            if db.in_transaction:
                                db.execute('rollback')
                            raise
                    elif old != [('vk-nightly-selected-original-versions-v1', wanted)]:
                        raise ValueError('Existing selected generation differs')
                    sealed = client.seal_checkpoint(db.key, dict(workspace_archive=manifest['operation_id'], request_sha256=wanted))
                finally:
                    db.close()
                config = json.loads(json.dumps(self.template))
                config.update(request_file=str(request_path), request_file_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
                    canonical_plan_sha256=request['plan_sha256'],
                    index=dict(index_name=key+'-reader', checkpoint_sha256=sealed['sha256']),
                    index_reference=dict(format='vk-nightly-selected-original-versions-v1', layer='nightly-controls-v1',
                        selector=sealed['sha256']+'.sqlite', sha256=sealed['sha256'], bytes=sealed['bytes']))
                batches.append(dict(request=request, configuration=config))
            bundle = dict(format='vk-workspace-normal-B-v1', manifest=manifest, batches=batches)
            bundle_path = folder / 'recovery.json'
            immutable(bundle_path, nightly_json(bundle))
            raw_bytes = bundle_path.stat().st_size
            receipt = self.controls.checkpoint(recovery, operation=manifest['operation_id'],
                plan_sha256=nightly_digest(manifest), paths=[str(bundle_path)], maximum_bytes=raw_bytes,
                seed_checkpoint_sha256=EMPTY_INDEX)
            return dict(format='vk-workspace-normal-B-locator-v1', operation_id=manifest['operation_id'],
                manifest_sha256=digest(manifest), bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                bundle_source=str(bundle_path), checkpoint=receipt)

    def _bundle(self, locator, expected):
        self.check()
        if locator['format'] != 'vk-workspace-normal-B-locator-v1' or locator['manifest_sha256'] != expected:
            raise ValueError('Exact workspace B locator required')
        receipt = locator['checkpoint']
        with self.context() as recovery:
            actual = self.controls.verify_checkpoint(recovery, self.template['B_controls'], recovery.provider_placement,
                self.template['dependencies'], receipt, resource_admission=self.template['host_admission'])
            proof = actual['actual_independent_normal_restore']
            if (proof.get('independent_owner_controls_restore_verified') is not True
                    or proof.get('manifest_sha256') != receipt['manifest_sha256'] or proof.get('files') != 1):
                raise ValueError('Independent normal B manifest restore did not pass')
            base = getattr(recovery, 'original', recovery)
            ref = receipt['index_reference']
            db = base.handle.db.client.connect('workspace-bundle-' + uuid.uuid4().hex, ref['sha256'], readonly=True)
            try:
                db.execute('begin')
                if db.execute('select sha256,row from owner_control_manifest').fetchall() != [
                        (receipt['manifest_sha256'], nightly_json(receipt['manifest']).decode())]:
                    raise ValueError('Reopened B control manifest differs')
                points = receipt['manifest']['files']
                if len(points) != 1 or points[0]['source'] != locator['bundle_source']:
                    raise ValueError('Exact B recovery bundle scope required')
                point = points[0]
                if point['member']['sha256'] != locator['bundle_sha256']:
                    raise ValueError('B bundle version differs')
                raw = bytearray()
                count = (point['member']['bytes'] + payloads.CHUNK - 1) // payloads.CHUNK
                for part in range(count):
                    recovery.check()
                    row = db.execute('select data from owner_control_parts where source=? and part=?',
                                     (locator['bundle_source'], part)).fetchone()
                    if not row or not isinstance(row[0], bytes) or not 0 < len(row[0]) <= payloads.CHUNK:
                        raise ValueError('Incomplete B recovery bundle')
                    raw.extend(row[0])
                if len(raw) != point['member']['bytes'] or hashlib.sha256(raw).hexdigest() != locator['bundle_sha256']:
                    raise ValueError('B recovery bundle hash/length differs')
                bundle = json.loads(raw)
                if (bundle['format'] != 'vk-workspace-normal-B-v1'
                        or digest(bundle['manifest']) != expected
                        or bundle['manifest']['operation_id'] != locator['operation_id']):
                    raise ValueError('Workspace B recovery binding differs')
                return bundle
            finally:
                db.close()

    def describe(self, locator, expected):
        """Reopen immutable normal-B metadata without recapturing cold bodies."""
        bundle = self._bundle(locator, expected)
        paths, _ = self._selected_configs(bundle)
        for path in paths:
            self.check()
            with self.selected.open_recovery(str(path), bundle['manifest']) as selected:
                selected.check()
        return bundle['manifest']

    def _selected_configs(self, bundle):
        manifest = bundle['manifest']
        folder = self.folder(manifest['operation_id'])
        wanted = list(requests(manifest, folder / 'manifest.json'))
        if [b['request'] for b in bundle['batches']] != wanted:
            raise ValueError('B bundle does not cover the exact workspace file set')
        paths, names = [], {}
        for i, batch in enumerate(bundle['batches']):
            request_path = folder / ('request-' + str(i) + '.json')
            saved = batch['configuration']
            # Old recovery metadata never chooses executable/connection inputs.
            # Use today's qualified owner/reader closure while preserving the
            # immutable logical provider and selected-index identities. Otherwise
            # an ordinary software upgrade would make every old archive unreadable.
            dynamic = {'request_file', 'request_file_sha256', 'canonical_plan_sha256', 'index', 'index_reference'}
            if (set(saved) - set(self.template) - dynamic
                    or saved.get('format') != self.template['format']
                    or saved.get('dependencies') != self.template['dependencies']
                    or saved.get('B_controls', {}).get('B_root') != self.template['B_controls']['B_root']):
                raise ValueError('Recovered reader changed logical provider identity or schema')
            immutable(request_path, nightly_json(batch['request']))
            expected = dict(request_file=str(request_path),
                request_file_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
                canonical_plan_sha256=nightly_digest(manifest))
            if any(saved.get(k) != v for k, v in expected.items()):
                raise ValueError('Recovered request binding differs')
            index = saved['index']
            reference = saved['index_reference']
            key = 'workspace-archive-' + uuid.UUID(manifest['operation_id']).hex + '-' + str(i) + '-reader'
            if (set(index) != {'index_name', 'checkpoint_sha256'} or index['index_name'] != key
                    or reference.get('sha256') != index['checkpoint_sha256']):
                raise ValueError('Recovered selected-index identity differs')
            config = dict(self.template, **expected, index=index, index_reference=reference)
            # Keep previously qualified reader configurations intact. New source
            # or resource settings get their own immutable, content-named input.
            config_path = folder / ('reader-' + str(i) + '-' + nightly_digest(config) + '.json')
            immutable(config_path, nightly_json(config))
            paths.append(config_path)
            for file in batch['request']['files']:
                names[file['normal_namespace_name']] = i
        return paths, names

    @contextmanager
    def recall(self, locator, expected):
        # Metadata recall releases its owner context before selected body recall
        # acquires the same normal lease. Never nest competing B controllers.
        bundle = self._bundle(locator, expected)
        manifest = bundle['manifest']
        paths, names = self._selected_configs(bundle)
        provider = self
        with ExitStack() as stack:
            class Reader:
                active = None
                selected = None
                context = None

                @contextmanager
                def open_body(self, row):
                    name = str(Path(manifest['payloads']['roots'][row['root']]) / row['relative']).lstrip('/')
                    index = names[name]
                    provider.check()
                    if self.active != index:
                        if self.context is not None:
                            self.context.close()
                        self.context = ExitStack()
                        stack.callback(self.context.close)
                        self.selected = self.context.enter_context(provider.selected.open_recovery(str(paths[index]), manifest))
                        self.active = index
                    self.selected.check()
                    with io.BufferedReader(Blocks(self.selected.handle.blocks(name)), buffer_size=65536) as body:
                        yield body
            reader = Reader()
            reader.manifest = manifest
            yield reader
