"""Bounded archive carriers through the same Nightly checkpoint/restore owner.

Packing avoids a separate remote checkpoint per handful of tiny gzip objects.
The consumer reads carriers from immutable B checkpoints, independently extracts
and verifies every member, then serves only those B-derived sealed RAM bytes.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time
import uuid

import archive_closure as closure
import log_dedup as logs
from nightly_graph import canonical, member_path
from recovery_stream import NormalRecovery

LIMIT = 24 * 1024**2
SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL


def validate_members(graph, manifest):
    expected = {r['path']: r for r in graph['members']}
    actual = {}
    for index, row in enumerate(manifest['files']):
        wanted = expected.get(row['path'])
        if (wanted is None or row['path'] in actual or row['member'] != str(index)
                or row['sha256'] != wanted['sha256'] or row['bytes'] != wanted['bytes']):
            raise logs.ArchiveError('Packed B member differs from exact archive graph')
        member_path(Path(graph['root']), row['path'])
        actual[row['path']] = row
    return actual


def read_control(db, receipt, point):
    """Only immutable checkpoint parts; no path-based or staging fallback."""
    manifest = receipt['manifest']
    if hashlib.sha256(canonical(manifest)).hexdigest() != receipt['manifest_sha256']:
        raise logs.ArchiveError('Packed checkpoint manifest changed')
    if db.execute('select sha256,row from owner_control_manifest').fetchall() != [
            (receipt['manifest_sha256'], canonical(manifest).decode())]:
        raise logs.ArchiveError('Reopened packed checkpoint differs')
    if db.execute('select point from owner_control_files where source=?',
                  (point['source'],)).fetchone() != (canonical(point).decode(),):
        raise logs.ArchiveError('Reopened packed point differs')
    size = point['member']['bytes']
    if not 0 <= size <= LIMIT + 2 * 1024**2:
        raise logs.ArchiveError('Packed control exceeds RAM bound')
    count = (size + 1024**2 - 1) // 1024**2
    if db.execute('select count(*) from owner_control_parts where source=?',
                  (point['source'],)).fetchone() != (count,):
        raise logs.ArchiveError('Packed control part count differs')
    result = bytearray()
    for part in range(count):
        db.request('check')
        row = db.execute('select data from owner_control_parts where source=? and part=?',
                         (point['source'], part)).fetchone()
        if row is None or not isinstance(row[0], bytes) or not 0 < len(row[0]) <= 1024**2:
            raise logs.ArchiveError('Packed control part missing')
        result.extend(row[0])
        if len(result) > size:
            raise logs.ArchiveError('Packed control exceeds expected length')
    if len(result) != size or hashlib.sha256(result).hexdigest() != point['member']['sha256']:
        raise logs.ArchiveError('Packed control EOF differs')
    return result


def sealed_fd(body):
    fd = os.memfd_create('normal-B-archive-carrier', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        view = memoryview(body)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise OSError('Packed replay short write')
            view = view[n:]
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, SEALS)
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd)
        raise


class PackedGraph:
    def __init__(self, recovery, graph, records, scratch, record=lambda phase,value:None):
        self.recovery, self.graph, self.records, self.scratch = recovery, graph, records, Path(scratch)
        self.record = record
        self.last_owner_check = float('-inf')
        self.client = getattr(recovery, 'original', recovery).handle.db.client
        self.index, self.rows, self.fd, self.active, self.offsets = self, {}, None, None, {}
        digest = hashlib.sha256(canonical(graph)).hexdigest()
        for number, record in enumerate(records):
            if record['format'] != 'vk-packed-archive-graph-v1' or record['graph_sha256'] != digest:
                raise logs.ArchiveError('Packed graph receipt binding differs')
            for name, row in validate_members(graph, record['members']).items():
                if name in self.rows:
                    raise logs.ArchiveError('Duplicate packed graph member')
                self.rows[name] = (number, row)
        if set(self.rows) != {r['path'] for r in graph['members']}:
            raise logs.ArchiveError('Packed graph receipt union is incomplete')

    def check(self):
        # Only immutable B-derived sealed RAM is served here. Keep the real
        # owner/leases open, and poll their full remote proof once per second;
        # publication and checkpoint boundaries still use uncached owner checks.
        now = time.monotonic()
        if now - self.last_owner_check >= 1:
            self.recovery.check()
            self.last_owner_check = now
        if self.fd is not None and fcntl.fcntl(self.fd, fcntl.F_GET_SEALS) & SEALS != SEALS:
            raise logs.ArchiveError('B-derived carrier lost its RAM seals')

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
        self.fd, self.active, self.offsets = None, None, {}

    def load(self, number):
        self.check()
        if self.active == number:
            return
        self.recovery.check()
        self.close()
        record = self.records[number]
        receipt = record['checkpoint']
        points = {p['source']: p for p in receipt['manifest']['files']}
        if set(points) != {record['carrier_source'], record['manifest_source']}:
            raise logs.ArchiveError('Packed checkpoint scope differs')
        db = self.client.connect('packed-graph-' + uuid.uuid4().hex,
                                 receipt['index_reference']['sha256'], readonly=True)
        fd = manifest_fd = None
        try:
            db.execute('begin')
            fd = sealed_fd(read_control(db, receipt, points[record['carrier_source']]))
            raw = read_control(db, receipt, points[record['manifest_source']])
            manifest = json.loads(raw)
            if manifest != record['members']:
                raise logs.ArchiveError('B-derived packed manifest differs')
            validate_members(self.graph, manifest)
            manifest_fd = sealed_fd(raw)
            # This extraction reads the restored B carrier, never local staging.
            closure.extract_verify('/proc/self/fd/' + str(fd), '/proc/self/fd/' + str(manifest_fd),
                                   self.scratch / ('restore-' + uuid.uuid4().hex), self.check,
                                   record=lambda value:self.record('archive_carrier_members_restored',dict(carrier=number,**value)))
            with os.fdopen(os.dup(fd), 'rb') as body, tarfile.open(fileobj=body, mode='r:') as tar:
                members = tar.getmembers()
                for row, member in zip(manifest['files'], members):
                    self.offsets[row['path']] = (member.offset_data, member.size)
            self.fd, self.active = fd, number
            fd = None
        finally:
            if fd is not None:
                os.close(fd)
            if manifest_fd is not None:
                os.close(manifest_fd)
            db.close()

    def relative(self, name):
        prefix = self.graph['root'].lstrip('/') + '/'
        if not name.startswith(prefix) or name[len(prefix):] not in self.rows:
            raise logs.ArchiveError('Member outside exact packed graph namespace')
        return name[len(prefix):]

    def entry(self, name):
        self.check()
        _, row = self.rows[self.relative(name)]
        return dict(kind='file', bytes=row['bytes'], sha256=row['sha256'], **row['metadata'])

    def blocks(self, name):
        relative = self.relative(name)
        number, row = self.rows[relative]
        self.load(number)
        offset, size = self.offsets[relative]
        if size != row['bytes']:
            raise logs.ArchiveError('Packed member size differs')
        for position in range(0, size, 1024**2):
            self.check()
            yield os.pread(self.fd, min(1024**2, size - position), offset + position)
        self.check()


@contextmanager
def reopen_graph(recovery, graph, records, *, hook, normal, scratch, record=lambda phase,value:None):
    handle = PackedGraph(recovery, graph, records, scratch, record)
    try:
        for number, record in enumerate(records):
            proof = hook.verify_checkpoint(recovery, normal['B_controls'], recovery.provider_placement,
                normal['dependencies'], record['checkpoint'], resource_admission=normal['host_admission'])
            if not proof['actual_independent_normal_restore']['independent_owner_controls_restore_verified']:
                raise logs.ArchiveError('Normal packed carrier restore failed')
            handle.load(number)
        recovery.check()
        yield NormalRecovery(handle, source_namespace=graph['root'], location=recovery.location,
                             guard=handle.check)
        recovery.check()
    finally:
        handle.close()


def validate_checkpoint_prefix(graph, batches, retained):
    """A retained prefix must cover exactly the original bounded bundles."""
    if len(retained) > len(batches):
        raise logs.ArchiveError('Too many retained archive checkpoints')
    digest = hashlib.sha256(canonical(graph)).hexdigest()
    for number, receipt in enumerate(retained):
        if receipt.get('format') != 'vk-packed-archive-graph-v1' or receipt.get('graph_sha256') != digest:
            raise logs.ArchiveError('Retained archive graph binding differs')
        expected = [dict(row, sha256=row['expected_sha256'], member=str(index))
                    for index, row in enumerate(batches[number])]
        if receipt['members'].get('files') != expected:
            raise logs.ArchiveError('Retained archive checkpoint is not an exact prefix')
        validate_members(graph, receipt['members'])


@contextmanager
def checkpoint_graph(recovery, graph, *, hook, normal, operation, plan_sha256, seed, save, scratch, record=lambda phase,value:None, retained=(), attempt=None):
    if sum(r['bytes'] for r in graph['members']) > 2 * 1024**3:
        raise logs.ArchiveError('Bounded archive graph required')
    root, scratch = Path(graph['root']), Path(scratch)
    rows = []
    for row in graph['members']:
        path = member_path(root, row['path'])
        rows.append(dict(path=row['path'], bytes=row['bytes'], identity=list(closure.version(path.stat())),
                         metadata=closure.metadata(path), expected_sha256=row['sha256']))
    batches = list(closure.bundles(rows, maximum=LIMIT))
    validate_checkpoint_prefix(graph, batches, retained)
    if retained and (not isinstance(attempt, str) or not attempt.isalnum() or len(attempt) > 32):
        raise logs.ArchiveError('Explicit reconciled archive recovery attempt required')
    records = list(retained)
    # Independently reopen completed B checkpoints before appending anything.
    for receipt in retained:
        proof = hook.verify_checkpoint(recovery, normal['B_controls'], recovery.provider_placement,
            normal['dependencies'], receipt['checkpoint'], resource_admission=normal['host_admission'])
        if not proof['actual_independent_normal_restore']['independent_owner_controls_restore_verified']:
            raise logs.ArchiveError('Retained normal B archive restore failed')
    for number, batch in enumerate(batches):
        if number < len(retained):
            continue
        suffix = '-' + attempt if retained else ''
        folder = scratch / ('pack-' + str(number) + suffix)
        folder.mkdir(mode=0o700)
        packed = closure.pack_verify(root, batch, folder, recovery.check,
            record=lambda value:record('archive_carrier_members_packed',dict(carrier=number,**value)))
        points = [packed['carrier'], packed['manifest']]
        size = sum(Path(p).stat().st_size for p in points)
        receipt = hook.checkpoint(recovery, operation=operation, plan_sha256=plan_sha256,
                                 paths=points, maximum_bytes=size, seed_checkpoint_sha256=seed)
        accepted = dict(format='vk-packed-archive-graph-v1', graph_sha256=hashlib.sha256(canonical(graph)).hexdigest(),
                      checkpoint=receipt, carrier_source=packed['carrier'], manifest_source=packed['manifest'],
                      members=json.loads(Path(packed['manifest']).read_bytes()))
        save(number, accepted)
        records.append(accepted)
        record('archive_carrier_checkpoint_verified',dict(carrier=number,members=len(batch)))
    with reopen_graph(recovery, graph, records, hook=hook, normal=normal, scratch=scratch, record=record) as provider:
        yield provider
