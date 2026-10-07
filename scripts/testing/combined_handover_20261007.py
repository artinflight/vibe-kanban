"""Full database workload, real candidate/v2 rollback, private ownership only."""
import json
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

BASE = Path('/mnt/vk-storage/vk-combined-release-20261007')
PACKAGE = Path('/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60')
LEGACY = Path('/mnt/vk-storage/vk-green-cutover-20261005')
BACKUP = Path('/mnt/vk-storage/vk-runtime-backup-20261007')
ROOT = BASE / 'full-handover-v4'
sys.path.insert(0, str(PACKAGE / 'tools'))
sys.path.insert(0, str(Path(__file__).parent / 'staging-low-peak-20261007'))
from vk_prep_common import digest, save
from vk_recovery_package import verify
from vk_desktop_transport import DesktopTransport
from vk_archive_store import configure_transport
from vk_rolling_backup import verify_snapshot_archive
from scratch_retirement import ScratchRetirement, CASES
import rehearse_vk_backup_boundary as rehearsal


def main():
    assert os.path.ismount('/mnt/vk-storage')
    assert verify(PACKAGE)['source_commit'] == '49cf82d603b765b4ceaf5a8b4462f046e6181c0f'
    os.umask(0o077)
    ROOT.mkdir(exist_ok=True)
    assert not any(ROOT.iterdir()), 'Never reuse a populated rehearsal root'
    restored = json.loads((BACKUP / 'recovery-result.json').read_text())
    assert restored['passed'] and restored['required_database_count'] == 69
    databases = {BACKUP / 'backups/desktop-recovery/files' / raw: checksum
                 for raw, checksum in restored['latest_database_hashes'].items()}
    assert len(databases) == 69 and all(digest(p) == checksum for p, checksum in databases.items())
    bindings = json.loads((BASE / 'final-package/manifest.json').read_text())
    assert bindings['source'] == '5ec5722455d9b12ae8a9b00b371351ad12a685ef'
    assert all(digest(BASE / 'final-package' / p) == value for p, value in bindings['files'].items())
    required = sum(p.stat().st_size for p in databases)
    floor = 2 * 1024**3
    stat = os.statvfs(ROOT)
    prior = BASE / 'full-handover'
    receipt = json.loads((prior / 'cleanup-allowlist.json').read_text())['desktop_receipt']
    archive = prior / 'handover-7843a8bab11d4cf9a246bc0d04fab4eb/backups/checkpoint-/e0b846d9685c4721a3a07c6dc92c93e4' / receipt['name']
    assert digest(archive) == receipt['sha256']
    # Retire the verified checkpoint payload before creating either delta.
    # Peak DB copies are runtime + rejected boundary + accepted boundary.
    # Size all runtime/snapshot copies; use the actual same-69-DB archive size
    # plus a GiB growth allowance, not an assumed generic compression ratio.
    # The independent floor monitor remains authoritative if actual use differs.
    budget = 3 * required + 3 * archive.stat().st_size + 1024**3 + floor
    assert stat.f_bavail * stat.f_frsize > budget, 'Measured rehearsal budget does not fit'
    save(ROOT / 'space-plan.json', {'database_bytes': required, 'database_count': 69,
         'measured_archive_bytes': archive.stat().st_size, 'growth_reserve_bytes': 1024**3,
         'planned_peak_with_floor': budget, 'free_before': stat.f_bavail * stat.f_frsize,
         'floor_bytes': floor, 'actual_peak_not_yet_proven': True})
    transport = DesktopTransport(ROOT / 'transport', hostname='10.0.0.109', host_key_alias='100.70.23.123')
    configure_transport('10.0.0.109', '100.70.23.123')
    destination = 'B:/vk-backups/vk-combined-handover-20261007'
    mirror = lambda p: transport.mirror(p, destination)
    rehearsal.mirror_desktop = lambda path, remote: transport.mirror(path, remote)
    copies = []
    real_journal = rehearsal.Journal

    class SizedJournal(real_journal):
        def __init__(self, plan):
            runtime = Path(plan['sources'][0])
            fixture = runtime.parent
            save(fixture / 'low-peak-fixture.json', {'schema': 1, 'root': str(fixture),
                 'production_modified': False, 'private_fixture': True})
            extra = runtime / 'production-sized-copies'
            extra.mkdir()
            for index, (original, checksum) in enumerate(databases.items()):
                target = extra / (str(index) + '.sqlite')
                shutil.copy2(original, target)
                assert digest(target) == checksum
                plan['sqlite_snapshots'].append(str(target))
                copies.append({'source': str(original), 'copy': str(target), 'sha256': checksum})
            super().__init__(plan)
    rehearsal.Journal = SizedJournal
    real_capture = rehearsal.capture

    def capture(*args, **kwargs):
        result = real_capture(*args, **kwargs)
        assert len(result['databases']) >= 71
        if result['parent'] is None:
            folder = Path(result['folder'])
            fixture = folder.parent.parent.parent
            retirement = ScratchRetirement(fixture, verify_snapshot_archive, mirror, consumers)
            plan = retirement.plan(folder, 'checkpoint-payload-verified', ())
            retirement.retire(plan, lambda value: save(fixture / 'checkpoint-retirement.json', value))
            for row in copies:
                with closing(sqlite3.connect(row['copy'])) as db:
                    with db:
                        version = db.execute('PRAGMA user_version').fetchone()[0]
                        db.execute('PRAGMA user_version=' + str(version + 1))
                assert not Path(row['copy'] + '-wal').exists()
        return result
    rehearsal.capture = capture
    real_launch = rehearsal.launch_command
    held = json.loads(Path('/mnt/vk-storage/vk-sfr-http-20261006/vk-continuation-http-c75bexq4/latest-before-rollback.json').read_text())
    assert held['version'] == 2 and any(g['initializationState'] == 'held' for g in held['goals'].values())
    assert all(g['grant'] is None for g in held['goals'].values())

    def launch(runtime, release, port, standby):
        ledger = runtime / 'capacity-controller/state.json'
        if not ledger.exists():
            save(ledger, held)
        # The old production executable is deliberately not a v2 rollback input.
        command = real_launch(runtime, release if standby else BASE / 'final-package/rollback', port, standby)
        module = str(BASE / 'final-package/autoswitch-module/releases/combined-5ec572245')
        command.extend(['--ro-bind', module, '/module', '--setenv', 'VK_CODEX_ROUTING_MODULE', '/module',
                        '--setenv', 'VK_ROUTING_EVENTS_FILE', '/green/private-routing-events.jsonl'])
        return command
    rehearsal.launch_command = launch
    real_restore = rehearsal.desktop_restore

    def consumers(paths):
        result = subprocess.run(['lsof', '-nP', '-F', 'pfn', '--', *map(str, paths)],
                                capture_output=True, text=True, timeout=30)
        warnings = {
            "lsof: WARNING: can't stat() nsfs file system /var/snap/lxd/common/ns/shmounts",
            "lsof: WARNING: can't stat() nsfs file system /var/snap/lxd/common/ns/mntns",
            'Output information may be incomplete.',
        }
        return (result.returncode == 1 and not result.stdout.strip()
                and set(line.strip() for line in result.stderr.splitlines()) <= warnings)

    def restore(head, fixture, destination_path, **kwargs):
        # This exact library calls restore only after all four assertions succeed.
        retirement = ScratchRetirement(fixture, verify_snapshot_archive, mirror, consumers)
        for folder in sorted((fixture / 'backups').glob('*/*')):
            if not (folder / 'payload/manifest.json').is_file():
                continue
            manifest = json.loads((folder / 'payload/manifest.json').read_text())
            if manifest['parent'] is None:
                receipt = json.loads((fixture / 'checkpoint-retirement.json').read_text())
                assert receipt['state'] == 'retired' and receipt['folder'] == str(folder)
                continue
            plan = retirement.plan(folder, 'handover-assertions-complete', CASES)
            receipt = fixture / ('retirement-' + folder.name + '.json')
            retirement.retire(plan, lambda value, p=receipt: save(p, value))
        descriptor, result = real_restore(head, fixture, destination_path, **kwargs)
        files = Path(result['destination']) / 'files'
        for row in copies:
            assert digest(files / row['copy'].lstrip('/')) == digest(row['copy'])
        ledger = files / str(fixture / 'runtime/capacity-controller/state.json').lstrip('/')
        actual = json.loads(ledger.read_text())
        assert actual['version'] == 2 and actual['goals'] == held['goals']
        save(ROOT / 'full-database-and-holds.json', {'databases_verified': len(copies),
             'all_new_holds_preserved': True, 'production_modified': False})
        return descriptor, result
    rehearsal.desktop_restore = restore
    samples = []
    done = threading.Event()

    def monitor():
        while not done.wait(.1):
            state = os.statvfs(ROOT)
            free = state.f_bavail * state.f_frsize
            samples.append(free)
            if free < floor:
                # Interrupt only this foreground test; the library finally block
                # thaws/stops only its strictly scoped private services.
                import _thread
                _thread.interrupt_main()
                return
    observer = threading.Thread(target=monitor)
    observer.start()
    start = time.monotonic()
    sys.argv = [sys.argv[0], '--root', str(ROOT), '--handover-directory', str(LEGACY),
        '--release', str(BASE / 'final-package/candidate'), '--desktop-directory', destination,
        '--desktop-hostname', '10.0.0.109', '--desktop-host-key-alias', '100.70.23.123', '--low-peak-restore']
    try:
        rehearsal.main()
    finally:
        done.set()
        observer.join()
        save(ROOT / 'measurement.json', {'seconds': time.monotonic()-start,
            'minimum_free_bytes': min(samples) if samples else None, 'floor_bytes': floor,
            'full_database_copies': copies, 'production_modified': False,
            'handover_source_sha256': digest(LEGACY / 'ownership_handover.py'),
            'rehearsal_source_sha256': digest(PACKAGE / 'tools/rehearse_vk_backup_boundary.py')})


if __name__ == '__main__':
    main()
