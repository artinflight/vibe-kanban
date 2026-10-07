"""Fail-closed retirement of private rehearsal SQLite duplicates, never sources.

Only the two verified phases below are supported. Archives, manifests, restore
outputs and the runtime are retained. Callers supply the existing archive member
verifier and a fresh Desktop full-hash verifier, not a cached boolean assertion.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

CASES = (
    'Failed backup returns the same original process without database restoration',
    'Verified rolling boundary is accepted by the existing handover with latest data',
    'Same-process cutback preserves writes and model/settings changes made after handover',
    'Repeated recovery preserves the released candidate and current owner',
)
FLOOR = 2 * 1024**3


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    st = Path(path).lstat()
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink,
            st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def require_real_path(path, root):
    path, root = Path(path), Path(root)
    require(path.is_absolute() and path.is_relative_to(root), 'Path outside private fixture')
    require(str(path) == os.path.normpath(str(path)), 'Non-canonical fixture path')
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'Symlink in fixture path')
    require(path.stat().st_dev == root.stat().st_dev, 'Fixture crosses filesystem')


class SpaceBudget:
    def __init__(self, root, floor=FLOOR):
        self.root, self.floor, self.samples = Path(root), floor, []
        require(floor >= FLOOR, 'Cannot lower the two-GiB free-space floor')

    def check(self, phase, additional_upper_bytes=0):
        require(additional_upper_bytes >= 0, 'Negative space reservation')
        st = os.statvfs(self.root)
        available = st.f_bavail * st.f_frsize
        self.samples.append({'at': time.time(), 'phase': phase, 'free_bytes': available,
                             'additional_upper_bytes': additional_upper_bytes})
        require(available - additional_upper_bytes >= self.floor,
                'Insufficient SSD headroom above free-space floor')
        return available


def require_full_workload(audit, expected_databases):
    require(audit.get('backup_ready') is True, 'Backup coverage is unresolved')
    require(not audit.get('errors'), 'Inventory contains errors')
    require(not audit.get('inventory_is_live_estimate_not_fenced_upper_bound', True),
            'Live estimate is not a bound for the full rehearsal')
    actual = {row['path'] for row in audit['database_inventory']}
    require(len(expected_databases) >= 67 and set(expected_databases) <= actual,
            'Full database workload was reduced')
    require(all(r['present'] and not r['symlink'] for r in audit['protected_roots']),
            'Protected recovery root is absent or linked')


class ScratchRetirement:
    def __init__(self, root, verify_archive_members, verify_desktop, verify_consumers):
        self.root = Path(root)
        require_real_path(self.root, self.root)
        require(self.root.name.startswith('handover-'), 'Not a private handover fixture')
        require(self.root.stat().st_uid == os.getuid() and
                stat.S_IMODE(self.root.stat().st_mode) == 0o700,
                'Private fixture ownership/mode is not exclusive')
        marker = self.root / 'low-peak-fixture.json'
        require_real_path(marker, self.root)
        self.marker = json.loads(marker.read_text())
        require(self.marker == {'schema': 1, 'root': str(self.root),
                                'production_modified': False, 'private_fixture': True},
                'Missing exact private fixture declaration')
        self.verify_archive_members = verify_archive_members
        self.verify_desktop = verify_desktop
        self.verify_consumers = verify_consumers

    def plan(self, folder, phase, cases):
        folder = Path(folder)
        require_real_path(folder, self.root)
        require(folder.parent.parent == self.root / 'backups' and
                folder.parent.name in ('checkpoint-', 'delta-'), 'Not a fixture capture folder')
        manifest_path = folder / 'payload/manifest.json'
        require_real_path(manifest_path, self.root)
        manifest = json.loads(manifest_path.read_text())
        require(manifest.get('production_boundary') is False, 'Production boundary is protected')
        snapshots = manifest['sqlite_snapshots']
        require(snapshots, 'No verified snapshots to retire')
        for original, row in snapshots.items():
            require_real_path(Path(original), self.root / 'runtime')
            require(re.fullmatch(r'sqlite/[a-f0-9]{64}\.sqlite', row['path']), 'Unsafe snapshot name')
        archives = list(folder.glob('*.tar.zst'))
        require(len(archives) == 1, 'Capture archive is ambiguous')
        archive = archives[0]
        require_real_path(archive, self.root)
        archive_identity = identity(archive)
        archive_hash = digest(archive)
        self.verify_archive_members(archive, snapshots, manifest_path)
        remote = self.verify_desktop(archive)
        require(remote.get('desktop_verified') is True and remote.get('sha256') == archive_hash,
                'Desktop full archive hash is unverified')
        require(remote.get('name') == archive.name and
                re.fullmatch(r'B:/vk-backups/[A-Za-z0-9_./-]+', remote.get('desktop_directory', '')) and
                '..' not in Path(remote['desktop_directory']).parts,
                'Desktop recovery locator is missing or changed')
        if phase == 'checkpoint-verified':
            require(manifest['parent'] is None, 'Checkpoint phase cannot retire a delta')
            result_path = folder / 'result.json'
            require_real_path(result_path, self.root)
            result = json.loads(result_path.read_text())
            require(result.get('passed') is True and result['receipt']['sha256'] == archive_hash,
                    'Checkpoint has not completed verification/delivery')
            subtrees = ['verified-payload/payload']
        elif phase == 'handover-assertions-complete':
            require(tuple(cases) == CASES, 'All four handover/cutback assertions must pass first')
            subtrees = ['payload']
        else:
            raise ValueError('Unknown retirement phase')
        rows = []
        for subtree in subtrees:
            for row in snapshots.values():
                path = folder / subtree / row['path']
                require_real_path(path, self.root)
                st = path.lstat()
                require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_uid == os.getuid(),
                        'Not an exclusively owned regular test copy')
                require(digest(path) == row['sha256'], 'Test copy differs from archived snapshot')
                rows.append({'path': str(path), 'sha256': row['sha256'],
                             'identity': identity(path), 'allocated_bytes': st.st_blocks * 512})
        require(self.verify_consumers([Path(r['path']) for r in rows]) is True,
                'Test-copy consumers are not verified idle')
        require(identity(archive) == archive_identity, 'Archive changed during retirement planning')
        return {'phase': phase, 'folder': str(folder), 'archive': str(archive),
                'archive_identity': archive_identity, 'archive_sha256': archive_hash,
                'manifest_identity': identity(manifest_path), 'manifest_sha256': digest(manifest_path),
                'desktop_receipt': remote, 'rows': rows, 'cases': list(cases)}

    def retire(self, plan, save_receipt):
        # Rebuild from the archive; an edited dry-run manifest cannot expand scope.
        current = self.plan(Path(plan['folder']), plan['phase'], plan['cases'])
        for key in ('rows', 'archive_identity', 'archive_sha256', 'manifest_identity', 'manifest_sha256'):
            require(current[key] == plan[key], 'Retirement plan changed: ' + key)
        save_receipt({**current, 'state': 'verified-before-unlink'})
        removed = []
        try:
            for row in current['rows']:
                path = Path(row['path'])
                require_real_path(path, self.root)
                require(identity(path) == row['identity'], 'Test copy changed before unlink')
                directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    st = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
                    require((st.st_dev, st.st_ino) == tuple(row['identity'][:2]), 'Test file replaced')
                    os.unlink(path.name, dir_fd=directory)
                finally:
                    os.close(directory)
                removed.append(row)
        finally:
            save_receipt({**current, 'state': 'retired' if len(removed) == len(current['rows']) else 'partial',
                          'removed': removed, 'reclaimed_allocated_bytes':
                          sum(r['allocated_bytes'] for r in removed)})
        return sum(r['allocated_bytes'] for r in removed)
