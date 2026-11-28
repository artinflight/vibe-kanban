"""Archive graph storage through the existing held Nightly B owner context.

Reuses its bounded checkpoint producer AND independent normal restore consumer.
Body reads reopen immutable B checkpoints through the same native control client;
there is no staging-file fallback, new transport, schedule, or service action.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import uuid

import log_dedup as logs
from recovery_stream import MEMBER, NormalRecovery

LIMIT = 24 * 1024**2


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def member_path(root, relative):
    if (not root.is_absolute() or str(root) == '/' or '..' in root.parts
            or not MEMBER.fullmatch(relative) or relative.split('/')[0] != relative.split('/')[1][:2]):
        raise logs.ArchiveError('Exact absolute archive namespace/member required')
    return root / relative


def groups(graph):
    if not graph['members'] or len({r['path'] for r in graph['members']}) != len(graph['members']):
        raise logs.ArchiveError('Nonempty unique graph required')
    batch, total = [], 0
    for row in graph['members']:
        if type(row['bytes']) is not int or not 0 <= row['bytes'] <= LIMIT:
            raise logs.ArchiveError('Graph member exceeds bounded checkpoint')
        if len(batch) == 48 or total + row['bytes'] > LIMIT:
            yield batch
            batch, total = [], 0
        batch.append(row)
        total += row['bytes']
    if batch:
        yield batch


class ControlGraph:
    def __init__(self, recovery, graph, receipts):
        self.recovery, self.graph, self.receipts = recovery, graph, receipts
        self.client = getattr(recovery, 'original', recovery).handle.db.client
        self.db, self.active = None, None
        self.rows = {}
        root = Path(graph['root'])
        expected = {str(member_path(root, r['path'])): r for r in graph['members']}
        for receipt in receipts:
            manifest = receipt['manifest']
            if hashlib.sha256(canonical(manifest)).hexdigest() != receipt['manifest_sha256']:
                raise logs.ArchiveError('Checkpoint manifest binding differs')
            for point in manifest['files']:
                source, member = point['source'], point['member']
                row = expected.get(source)
                if (row is None or source in self.rows or member['kind'] != 'file'
                        or member['sha256'] != row['sha256'] or member['bytes'] != row['bytes']):
                    raise logs.ArchiveError('B checkpoint differs from exact archive graph')
                self.rows[source] = (point, receipt)
        if set(self.rows) != set(expected):
            raise logs.ArchiveError('B checkpoint omits archive graph members')
        self.index = self

    def check(self):
        self.recovery.check()
        if self.db is not None:
            self.db.request('check')

    def close(self):
        if self.db is not None:
            db, self.db, self.active = self.db, None, None
            db.close()

    def entry(self, name):
        self.check()
        return self.rows['/' + name][0]['member']

    def blocks(self, name):
        self.check()
        point, receipt = self.rows['/' + name]
        ref = receipt['index_reference']
        if self.active != ref['sha256']:
            self.close()
            self.db = self.client.connect('scoped-graph-' + uuid.uuid4().hex,
                                          ref['sha256'], readonly=True)
            self.active = ref['sha256']
            self.db.execute('begin')
            rows = self.db.execute('select sha256,row from owner_control_manifest').fetchall()
            if rows != [(receipt['manifest_sha256'], canonical(receipt['manifest']).decode())]:
                raise logs.ArchiveError('Reopened B graph manifest differs')
        stored = self.db.execute('select point from owner_control_files where source=?',
                                 (point['source'],)).fetchone()
        if stored != (canonical(point).decode(),):
            raise logs.ArchiveError('Reopened B graph member differs')
        # One bounded part per RPC; never fetch a whole archive into memory.
        expected_parts = (point['member']['bytes'] + 1024**2 - 1) // 1024**2
        count = self.db.execute('select count(*) from owner_control_parts where source=?',
                                (point['source'],)).fetchone()
        if count != (expected_parts,):
            raise logs.ArchiveError('Reopened B graph part count differs')
        for part in range(expected_parts):
            self.check()
            row = self.db.execute('select data from owner_control_parts where source=? and part=?',
                                  (point['source'], part)).fetchone()
            if row is None or not isinstance(row[0], bytes) or not 0 < len(row[0]) <= 1024**2:
                raise logs.ArchiveError('Reopened B graph part missing or oversized')
            yield row[0]
        self.check()


@contextmanager
def reopen_graph(recovery, graph, receipts, *, hook, normal):
    """Normal independent full restore, followed by immutable B byte access."""
    if not recovery.location.startswith('desktop:B:/vk-backups/'):
        raise logs.ArchiveError('Held canonical B owner context required')
    handle = ControlGraph(recovery, graph, receipts)
    try:
        for receipt in receipts:
            recovery.check()
            actual = hook.verify_checkpoint(recovery, normal['B_controls'], recovery.provider_placement,
                                            normal['dependencies'], receipt,
                                            resource_admission=normal['host_admission'])
            proof = actual['actual_independent_normal_restore']
            if (proof.get('independent_owner_controls_restore_verified') is not True
                    or proof.get('manifest_sha256') != receipt['manifest_sha256']
                    or proof.get('files') != len(receipt['manifest']['files'])):
                raise logs.ArchiveError('Independent normal B graph restore did not pass')
        yield NormalRecovery(handle, source_namespace=graph['root'],
                             location=recovery.location, guard=recovery.check)
        recovery.check()
    finally:
        handle.close()


@contextmanager
def checkpoint_graph(recovery, graph, *, hook, normal, operation, plan_sha256, seed, save):
    """Back up exact staged members before acquiring live execution locks.

    save must durably retain each immutable receipt for failure/restart recovery.
    Earlier epochs are never overwritten or deleted. Inputs are bounded to 2 GiB.
    """
    if sum(r['bytes'] for r in graph['members']) > 2 * 1024**3:
        raise logs.ArchiveError('Bounded archive graph required')
    root = Path(graph['root'])
    receipts = []
    for number, batch in enumerate(groups(graph)):
        recovery.check()
        paths = [str(member_path(root, r['path'])) for r in batch]
        receipt = hook.checkpoint(recovery, operation=operation, plan_sha256=plan_sha256,
                                  paths=paths, maximum_bytes=max(1, sum(r['bytes'] for r in batch)),
                                  seed_checkpoint_sha256=seed)
        # Validate scope and bodies against the frozen graph before normal restore.
        partial = dict(graph, members=batch)
        ControlGraph(recovery, partial, [receipt])
        save(number, receipt)
        receipts.append(receipt)
    with reopen_graph(recovery, graph, receipts, hook=hook, normal=normal) as provider:
        yield provider
