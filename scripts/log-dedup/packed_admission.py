"""Exact prepared-pack recovery through the existing held normal B client.

No capture, new owner, transport, service action, or local-body fallback. Previous
full restore receipts bind the whole catalog; mutation admission also reads the
selected immutable B bodies under the currently held recovery context.
"""
import hashlib
import json
from pathlib import Path
import uuid

import log_dedup as logs
import reclaim
from packed_graph import read_control


def pinned(reference):
    path = Path(reference['path'])
    if reclaim.file_hash(path) != reference['sha256']:
        raise logs.ArchiveError('Pinned recovery evidence changed')
    return json.loads(path.read_bytes())


class CheckpointCatalog:
    def __init__(self, index, read_reference=pinned):
        expected = {r['path']: r for r in index['packed_files']}
        if len(expected) != len(index['packed_files']) or not expected:
            raise logs.ArchiveError('Unique complete packed recovery catalog required')
        self.rows = {}
        for reference in index['checkpoints']:
            if not reference['name'].startswith('PACKED_'):
                continue
            verified = read_reference(reference)
            receipt = verified['checkpoint']
            actual = verified['actual_independent_normal_restore']
            points = receipt['manifest']['files']
            restored = actual['actual_normal_reader_restore']
            if (not actual['independent_owner_controls_restore_verified']
                    or not actual['normal_leased_consumer_entrypoint_verified']
                    or actual['manifest_sha256'] != receipt['manifest_sha256']
                    or actual['files'] != len(points) or len(restored) != len(points)
                    or reference['index_reference'] != receipt['index_reference']):
                raise logs.ArchiveError('Actual normal restoration proof is incomplete')
            back = {r['source']: r for r in restored}
            if len(back) != len(restored):
                raise logs.ArchiveError('Duplicate restoration result')
            for point in points:
                name, member = point['source'], point['member']
                wanted, proof = expected.get(name), back.get(name)
                if (name in self.rows or wanted is None or proof is None
                        or member['kind'] != 'file'
                        or (member['bytes'], member['sha256']) != (wanted['bytes'], wanted['sha256'])
                        or (proof['bytes'], proof['sha256']) != (wanted['bytes'], wanted['sha256'])
                        or not proof['Linux_metadata_verified']):
                    raise logs.ArchiveError('Restored member differs from packed selection')
                self.rows[name] = dict(point=point, receipt=receipt, expected=wanted)
        if set(self.rows) != set(expected):
            raise logs.ArchiveError('Packed checkpoint union is incomplete')

    def add_aliases(self, aliases):
        """Bind new prepared names to identical, already restored B bodies.

        The caller must obtain these aliases and new metadata from its actual
        B-restored mapping. Original checkpoint points/selectors stay unchanged.
        This does not claim the old point's metadata is the new file's metadata.
        """
        for alias in aliases:
            expected = alias['expected']
            name, source = expected['path'], alias['checkpoint_source']
            original = self.rows.get(source)
            if (name in self.rows or original is None
                    or (expected['bytes'],expected['sha256']) != (
                        original['point']['member']['bytes'],original['point']['member']['sha256'])
                    or not Path(name).is_absolute() or Path(name).resolve(strict=True)!=Path(name)
                    or logs.version(logs.regular(Path(name))) != expected['version']
                    or reclaim.file_hash(Path(name))!=expected['sha256']):
                raise logs.ArchiveError('Exact unchanged prepared alias and restored B body required')
            self.rows[name] = dict(original, expected=expected)

    def members(self, sealed):
        folder = Path(sealed['prepared'])
        names = {str(folder / Path(r['path']).name): r['packed_sha256'] for r in sealed['files']}
        names.update({str(folder / '.log-packs' / name): r['sha256'] for name, r in sealed['packs'].items()})
        for name, digest in names.items():
            row = self.rows.get(name)
            if row is None or row['point']['member']['sha256'] != digest:
                raise logs.ArchiveError('Publication differs from exact B-backed members')
            path = Path(name)
            if (logs.version(logs.regular(path)) != row['expected']['version']
                    or reclaim.file_hash(path) != digest):
                raise logs.ArchiveError('Prepared input changed since independent restoration')
        return names


class NormalPreparedRecovery:
    """Current held owner + B-restored metadata + exact prepared graph.

    mapping must itself be reopened from its immutable B checkpoint before this
    object is constructed. Use read_mapping() rather than a local JSON assertion.
    The controller still owns source/SQL/consumer admission and actual leases.
    """
    def __init__(self, catalog, recovery, mapping, guard):
        if not isinstance(catalog, CheckpointCatalog) or not callable(guard):
            raise logs.ArchiveError('Validated catalog and current owner guard required')
        if not recovery.location.startswith('desktop:B:/vk-backups/'):
            raise logs.ArchiveError('Canonical held normal B context required')
        self.catalog, self.recovery, self.mapping, self.guard = catalog, recovery, mapping, guard
        self.client = getattr(recovery, 'original', recovery).handle.db.client
        self.verified = {}
        self.check()

    def check(self):
        self.guard()
        self.recovery.check()

    @staticmethod
    def read_mapping(recovery, checkpoint, source, expected_sha256):
        point = next((r for r in checkpoint['manifest']['files'] if r['source'] == source), None)
        if point is None or point['member']['sha256'] != expected_sha256:
            raise logs.ArchiveError('Recovery mapping point differs')
        recovery.check()
        client = getattr(recovery, 'original', recovery).handle.db.client
        db = client.connect('packed-mapping-' + uuid.uuid4().hex,
                            checkpoint['index_reference']['sha256'], readonly=True)
        try:
            db.execute('begin')
            value = json.loads(read_control(db, checkpoint, point))
            recovery.check()
            return value
        finally:
            db.close()

    def __call__(self, sealed):
        self.check()
        mapping = self.mapping['groups'].get(sealed['plan_sha256'])
        if mapping is None or mapping['prepared'] != sealed['prepared']:
            raise logs.ArchiveError('B-restored publication plan is missing')
        expected = {r['path']: r for r in mapping['files']}
        if len(expected) != len(sealed['files']):
            raise logs.ArchiveError('B-restored source selection differs')
        for row in sealed['files']:
            wanted = expected.get(row['path'])
            # Access time can change during verification; data/permission/xattr
            # and modification-time preservation remain exact requirements.
            fields = ('path', 'original', 'original_sha256', 'packed_sha256')
            if wanted is None or any(row[k] != wanted[k] for k in fields):
                raise logs.ArchiveError('B-restored original binding differs')
            if ({k:v for k,v in row['metadata'].items() if k != 'atime_ns'}
                    != {k:v for k,v in wanted['metadata'].items() if k != 'atime_ns'}):
                raise logs.ArchiveError('B-restored Linux metadata differs')
        key = logs.sha(reclaim.canonical(sealed))
        if key in self.verified:
            return self.verified[key]
        members = self.catalog.members(sealed)
        db, active, count, size = None, None, 0, 0
        try:
            for name in sorted(members, key=lambda n: self.catalog.rows[n]['receipt']['index_reference']['sha256']):
                self.check()
                row = self.catalog.rows[name];receipt = row['receipt']
                reference = receipt['index_reference']['sha256']
                if active != reference:
                    if db is not None:db.close()
                    db = self.client.connect('packed-publication-' + uuid.uuid4().hex, reference, readonly=True)
                    db.execute('begin');active = reference
                body = read_control(db, receipt, row['point'])
                # read_control verifies immutable index/member/parts/full SHA.
                if hashlib.sha256(body).hexdigest() != members[name]:
                    raise logs.ArchiveError('Actual normal B body differs')
                count += 1;size += len(body)
            self.check()
            result = dict(plan_sha256=sealed['plan_sha256'], members=count, bytes=size,
                          actual_current_normal_B_bytes_verified=True, local_body_fallback=False)
            self.verified[key] = result
            return result
        finally:
            if db is not None:db.close()
