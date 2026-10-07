"""Fresh full online checkpoint with preserved historical gaps and a space floor.

No production service, routing, settings or data restore operations are exposed.
The prior journal and archive chain remain intact; a new full baseline is not
evidence that historical missing edits were recovered.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path('/mnt/vk-storage/vk-combined-preparation-20261007')
OLD = Path('/mnt/vk-storage/vk-green-cutover-20261005')
PACKAGE = Path('/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-312ac0b20')
PIN = '312ac0b20d3d626a4ac1afaf473e6a8325191671'
UNIT = 'vk-combined-prep-journal-20261007.service'
FLOOR = 4 * 1024**3


def imports():
    sys.path.insert(0, str(PACKAGE / 'tools'))
    from vk_recovery_package import verify
    assert verify(PACKAGE)['source_commit'] == PIN


def roots_present(roots):
    result = {}
    for raw in roots:
        path = Path(raw)
        assert path.is_dir() and not path.is_symlink(), raw
        assert not any(p.is_symlink() for p in path.parents), raw
        info = path.stat()
        result[raw] = [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid]
    return result


def initialize():
    from vk_change_journal import request
    from vk_prep_common import digest, save
    ROOT.mkdir(mode=0o700)
    plan = json.loads((OLD / 'backup-plan.json').read_text())
    extra = json.loads((OLD / 'supplemental-backup.json').read_text())['sources']
    plan['sources'] = sorted(set(plan['sources'] + extra))
    inventory_path = Path('/mnt/vk-storage/vk-archive-retirement-20261007/fresh-backup-size/summary.json')
    inventory = json.loads(inventory_path.read_text())
    assert inventory['database_count'] == 69 and not inventory['errors']
    databases = [r['path'] for r in inventory['database_inventory']]
    plan['critical_sqlite'] = sorted(set(plan['critical_sqlite'] + databases))
    plan['sqlite_snapshots'] = sorted(set(plan['sqlite_snapshots'] + databases))
    coverage = json.loads((OLD / 'move-coverage.json').read_text())
    protected = roots_present(coverage['recopy_roots'])
    assert all(Path(p).exists() for p in plan['sources'])
    assert all(any(Path(p).is_relative_to(Path(r).resolve()) for r in plan['sources']) for p in databases)
    for name in ['journal-full.json', 'journal-delta.json', 'moves.json']:
        shutil.copy2(inventory_path.parent / name, ROOT / ('historical-' + name))
    save(ROOT / 'historical-journal-fresh.json', request(OLD / 'journal.sock', 0))
    save(ROOT / 'backup-plan.json', plan)
    save(ROOT / 'protected-roots.json', protected)
    save(ROOT / 'baseline-transition.json', {
        'at': time.time(), 'full_checkpoint_required': True, 'prior_journal_preserved': str(OLD / 'journal.sock'),
        'prior_chain_preserved': str(PACKAGE), 'prior_inventory_sha256': digest(inventory_path),
        'old_exclusions_unchanged': True, 'supplemental_sources_added': extra,
        'required_database_count': len(databases), 'protected_root_count': len(protected),
        'historical_errors_preserved': True, 'historical_missing_edits_recovered': False,
        'reason': 'Full new scope includes connector ledger; no incremental reuse across journal/scope changes.',
        'operational_pin': PIN, 'backup_passed': False, 'cutover_ready': False,
    })
    command = ['systemd-run', '--user', '--unit=' + UNIT, '--property=Restart=no',
               '--property=Nice=10', '/usr/bin/python3', '-B', str(PACKAGE / 'tools/vk_change_journal.py'),
               '--plan', str(ROOT / 'backup-plan.json'), '--socket', str(ROOT / 'journal.sock')]
    subprocess.run(command, check=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if (ROOT / 'journal.sock').exists():
            observed = request(ROOT / 'journal.sock', 0)
            save(ROOT / 'initial-journal.json', observed)
            assert observed['ready'] and not observed['errors'], observed['errors']
            break
        time.sleep(1)
    else:
        raise RuntimeError('New read-only journal did not become ready')
    print(json.dumps({'initialized': True, 'sources': len(plan['sources']), 'required_databases': len(databases)}), flush=True)


def capture():
    from vk_change_journal import request
    from vk_desktop_transport import DesktopTransport
    from vk_prep_common import save
    from vk_rolling_backup import capture as full_capture
    from vk_runtime_ephemeral import install
    import vk_rolling_backup
    install(vk_rolling_backup)
    plan = json.loads((ROOT / 'backup-plan.json').read_text())
    expected = json.loads((ROOT / 'protected-roots.json').read_text())
    def journal(since):
        assert roots_present(expected) == expected, 'Protected root identity changed'
        return request(ROOT / 'journal.sock', since)
    transport = DesktopTransport(ROOT / 'transport', hostname='10.0.0.109', host_key_alias='100.70.23.123')
    capacity = json.loads(transport.command('powershell -NoProfile -Command "Get-Volume -DriveLetter B | Select-Object FileSystem,HealthStatus,SizeRemaining | ConvertTo-Json -Compress"'))
    assert capacity['FileSystem'] == 'NTFS' and capacity['HealthStatus'] == 'Healthy'
    assert capacity['SizeRemaining'] > 105 * 1024**3
    save(ROOT / 'desktop-space-before.json', capacity)
    mirror = lambda path: transport.mirror(path, 'B:/vk-backups/vk-combined-preparation-20261007')
    result = full_capture(plan, ROOT / 'backups', journal, mirror, publish=mirror)
    assert set(plan['critical_sqlite']).issubset(result['sqlite_snapshots'])
    assert result['parent'] is None and result['passed'] and not result['reused_sqlite_snapshots']
    save(ROOT / 'online-backup-result.json', result)
    print(json.dumps({'passed': True, 'databases': len(result['sqlite_snapshots']), 'archive_bytes': result['receipt']['bytes'], 'seconds': result['total_preparation_seconds']}), flush=True)


def supervised():
    from vk_prep_common import save
    assert not (ROOT / 'online-backup-result.json').exists()
    start = time.time()
    stat = os.statvfs(ROOT)
    initial = minimum = stat.f_bavail * stat.f_frsize
    assert initial > 12 * 1024**3
    with (ROOT / 'capture.log').open('x') as log:
        child = subprocess.Popen([sys.executable, '-B', __file__, 'capture'], stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        stopped = None
        while child.poll() is None:
            stat = os.statvfs(ROOT)
            minimum = min(minimum, stat.f_bavail * stat.f_frsize)
            if minimum < FLOOR or time.time() - start > 3600:
                stopped = 'space_floor' if minimum < FLOOR else 'capture_deadline'
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(.25)
        code = child.wait()
    result = {'exit_code': code, 'started_at': start, 'elapsed_seconds': time.time()-start,
              'initial_free_bytes': initial, 'minimum_free_bytes': minimum,
              'observed_host_consumption_bytes': initial-minimum, 'floor_bytes': FLOOR,
              'stopped_for': stopped, 'production_interrupted': False,
              'full_restore_or_handover_proven': False}
    save(ROOT / 'capture-space.json', result)
    print(json.dumps(result), flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    os.umask(0o077)
    subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
    imports()
    {'init': initialize, 'capture': capture, 'run': supervised}[sys.argv[1]]()
