"""Retire exact disposable DB copies from the stopped adapter-error fixture."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ATTEMPTS = {
    'adapter': ('full-handover', '7843a8bab11d4cf9a246bc0d04fab4eb',
                'e0b846d9685c4721a3a07c6dc92c93e4', '1b4a242c9a44'),
    'connection-close': ('full-handover-v3', 'ebae0482382b4abdba649920b2b67ec1',
                         'ec3eddbff92141d0a118eb1b422a32f7', 'f82ef2c2e11c'),
}
sys.path.insert(0, '/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60/tools')
from vk_desktop_transport import DesktopTransport
from vk_prep_common import digest, save
from vk_rolling_backup import verify_snapshot_archive


def main():
    name = sys.argv[1] if len(sys.argv) == 2 else 'adapter'
    folder, fixture_id, capture_id, unit_id = ATTEMPTS[name]
    BASE = Path('/mnt/vk-storage/vk-combined-release-20261007') / folder
    FIXTURE = BASE / ('handover-' + fixture_id)
    CAPTURE = FIXTURE / 'backups/checkpoint-' / capture_id
    assert os.path.ismount('/mnt/vk-storage') and not (BASE / 'cleanup-result.json').exists()
    result = json.loads((FIXTURE / 'result.json').read_text())
    assert not result['passed'] and not result['cases'] and not result['production_modified']
    for unit in result['units'].values():
        assert unit in {f'vk-prep-rehearsal-{unit_id}-{role}.service' for role in ('candidate', 'incumbent')}
        assert subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip() == '0'
    manifest_path = CAPTURE / 'payload/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    archive = CAPTURE / ('checkpoint--' + capture_id + '.tar.zst')
    verify_snapshot_archive(archive, manifest['sqlite_snapshots'], manifest_path)
    transport = DesktopTransport(BASE / 'cleanup-transport', hostname='10.0.0.109', host_key_alias='100.70.23.123')
    receipt = transport.mirror(archive, 'B:/vk-backups/vk-combined-handover-20261007/failed-' + name)
    assert receipt['desktop_verified'] and receipt['sha256'] == digest(archive)
    rows = []
    measured = json.loads((BASE / 'measurement.json').read_text())
    retained_changed = []
    for row in measured['full_database_copies']:
        assert digest(row['source']) == row['sha256']
        if digest(row['copy']) != row['sha256']:
            retained_changed.append(row['copy'])
            continue
        rows.append((Path(row['copy']), row['sha256'], row['source']))
    for row in manifest['sqlite_snapshots'].values():
        path = CAPTURE / 'payload' / row['path']
        rows.append((path, row['sha256'], receipt['desktop_directory'] + '/' + receipt['name']))
    assert len(rows) + len(retained_changed) == 140
    frozen = []
    for path, checksum, retained in rows:
        assert path.is_relative_to(FIXTURE) and path.resolve() == path
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
        assert digest(path) == checksum
        frozen.append({'path': str(path), 'sha256': checksum, 'retained': retained,
                       'device': info.st_dev, 'inode': info.st_ino, 'mtime_ns': info.st_mtime_ns,
                       'bytes': info.st_size, 'allocated_bytes': info.st_blocks * 512})
    probe = subprocess.run(['lsof', '-nP', '-F', 'pfn', '--', *[r['path'] for r in frozen]],
                           capture_output=True, text=True, timeout=30)
    permitted = {
        "lsof: WARNING: can't stat() nsfs file system /var/snap/lxd/common/ns/shmounts",
        "lsof: WARNING: can't stat() nsfs file system /var/snap/lxd/common/ns/mntns",
        'Output information may be incomplete.',
    }
    assert probe.returncode == 1 and not probe.stdout.strip()
    assert set(line.strip() for line in probe.stderr.splitlines()) <= permitted
    # The two nsfs warnings concern unrelated LXD namespace handles, not this
    # mounted ext4 fixture. No protected process access or global clearance.
    proof = {'files': frozen, 'desktop_receipt': receipt, 'fixture_services_stopped': True,
             'changed_test_copies_retained': retained_changed,
             'target_references': [], 'unrelated_nsfs_warnings': probe.stderr.splitlines(),
             'global_protected_process_clearance_claimed': False,
             'scope': 'Only copies created by this turn; archive, metadata and original sources retained',
             'production_modified': False}
    save(BASE / 'cleanup-allowlist.json', proof)
    save(FIXTURE / 'RETIRED-TEST-COPIES.json', proof)
    before = os.statvfs(BASE).f_bavail * os.statvfs(BASE).f_frsize
    removed = []
    try:
        for row in frozen:
            path = Path(row['path'])
            info = path.lstat()
            assert (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size) == (row['device'], row['inode'], row['mtime_ns'], row['bytes'])
            assert not path.is_symlink() and info.st_nlink == 1
            path.unlink()
            removed.append(row['path'])
    finally:
        after = os.statvfs(BASE).f_bavail * os.statvfs(BASE).f_frsize
        save(BASE / 'cleanup-result.json', {'removed': removed, 'free_before': before,
             'free_after': after, 'completed': len(removed) == len(frozen), 'production_modified': False})
    print(json.dumps({'removed_test_copies': len(removed), 'allocated_bytes': sum(r['allocated_bytes'] for r in frozen), 'free_after': after}))


if __name__ == '__main__':
    main()
