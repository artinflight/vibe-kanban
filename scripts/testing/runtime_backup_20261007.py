"""Bounded fresh capture and Desktop-only recovery; no production lifecycle API."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import time
from unittest.mock import patch

ROOT = Path('/mnt/vk-storage/vk-runtime-backup-20261007')
OLD = Path('/mnt/vk-storage/vk-combined-preparation-20261007')
PACKAGE = Path('/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60')
PIN = '49cf82d603b765b4ceaf5a8b4462f046e6181c0f'
FLOOR = 8 * 1024**3
sys.path.insert(0, str(PACKAGE / 'tools'))
from vk_prep_common import digest, save, storage
from vk_recovery_package import verify
from vk_desktop_transport import DesktopTransport
from vk_change_journal import request
from vk_archive_store import Archive, configure_transport, reference
import vk_rolling_backup as backup
from vk_runtime_ephemeral import install


def setup():
    os.umask(0o077)
    storage(ROOT)
    assert verify(PACKAGE)['source_commit'] == PIN
    configure_transport('10.0.0.109', '100.70.23.123')
    install(backup)


def journal(since):
    expected = json.loads((OLD / 'protected-roots.json').read_text())
    for raw, identity in expected.items():
        path = Path(raw)
        assert path.is_dir() and not path.is_symlink()
        assert not any(p.is_symlink() for p in path.parents)
        info = path.stat()
        assert [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] == identity
    return request(OLD / 'journal.sock', since)


def prepare():
    ROOT.mkdir(mode=0o700)
    plan = json.loads((OLD / 'backup-plan.json').read_text())
    observed = journal(0)
    backup.check_journal(observed, plan)
    save(ROOT / 'backup-plan.json', plan)
    save(ROOT / 'initial-journal.json', observed)
    code = Path('/home/mcp/.cargo/git/checkouts/codex-9eee5d47a939c68c/3d2ee51/codex-rs')
    names = ['core/src/shell_snapshot.rs', 'thread-store/src/local/writer_lock.rs']
    binary = Path('/mnt/vk-storage/vk-model-autoswitch-v1/codex-current/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex')
    diagnostics = [b'Shell snapshot successfully created', b'Failed to delete shell snapshot at',
                   b'failed to remove thread writer lock', b'failed to coordinate thread writer lock cleanup']
    image = binary.read_bytes()
    assert all(message in image for message in diagnostics)
    save(ROOT / 'lifecycle-evidence.json', {
        'at': time.time(), 'cached_source_commit': '3d2ee51ca2d5db578f328aa75e20aa22c0197c9a',
        'cached_source_version': '0.153.4; not exact installed-build provenance',
        'source_hashes': {str(code / name): digest(code / name) for name in names},
        'runtime_binary': str(binary), 'runtime_sha256': digest(binary),
        'runtime_version': subprocess.check_output([str(binary), '--version'], text=True).strip(),
        'lifecycle_diagnostics_present': True, 'file_contents_or_environment_disclosed': False,
        'tools': verify(PACKAGE), 'prior_failed_capture_preserved': True,
        'historical_journal_gaps_preserved': True, 'required_databases': len(plan['critical_sqlite']),
        'strategy': 'New full online capture, then current delta and bounded B-only restore; final fence still required.',
    })


def capture(parent=None):
    plan = json.loads((ROOT / 'backup-plan.json').read_text())
    transport = DesktopTransport(ROOT / 'transport', hostname='10.0.0.109', host_key_alias='100.70.23.123')
    capacity = json.loads(transport.command('powershell -NoProfile -Command "Get-Volume -DriveLetter B | Select-Object FileSystem,HealthStatus,SizeRemaining | ConvertTo-Json -Compress"'))
    assert capacity['FileSystem'] == 'NTFS' and capacity['HealthStatus'] == 'Healthy'
    assert capacity['SizeRemaining'] > 32 * 1024**3
    save(ROOT / ('desktop-before-delta.json' if parent else 'desktop-before-full.json'), capacity)
    mirror = lambda path: transport.mirror(path, 'B:/vk-backups/vk-runtime-backup-20261007')
    result = backup.capture(plan, ROOT / 'backups', journal, mirror, parent, publish=mirror)
    assert result['passed'] and result['receipt']['desktop_verified'] and result['metadata_receipt']['desktop_verified']
    assert set(plan['critical_sqlite']).issubset(result['databases'])
    if parent is None:
        assert set(plan['critical_sqlite']).issubset(result['sqlite_snapshots'])
        assert not result['reused_sqlite_snapshots']
    save(ROOT / ('delta-result.json' if parent else 'full-result.json'), result)
    print(json.dumps({'passed': True, 'databases': len(result['databases']),
                      'bytes': result['receipt']['bytes'], 'seconds': result['total_preparation_seconds']}), flush=True)


def restore():
    from vk_staged_recovery import staged_restore
    head = json.loads((ROOT / 'delta-result.json').read_text())
    full = json.loads((ROOT / 'full-result.json').read_text())
    records = {}
    for result in (full, head):
        archive = Archive(reference(result), desktop_only=True)
        remote = archive.verify()
        manifest = json.loads((Path(result['folder']) / 'payload/manifest.json').read_text())
        records[archive.key] = {'sha256': archive.sha256, 'verified_remote': remote, 'manifest': manifest}
    selected = json.loads(Path('/mnt/vk-storage/vk-desktop-provider-20261007/staged-plan.json').read_text())['selection']
    if isinstance(selected, dict):
        selected = [name for group in selected.values() for name in group]
    # The previous selection contains explicit real attachment/history/worktree
    # files; no selection is silently dropped when unavailable in the new chain.
    by_remote = {Archive(reference(row)).key: row for row in (full, head)}
    protected = json.loads((OLD / 'protected-roots.json').read_text())
    audits = []
    original_contents = Archive.contents
    @contextmanager
    def inventory_checked_contents(archive):
        row = by_remote[archive.key]
        folder = Path(row['folder'])
        expected = {raw.decode().rstrip('/') for raw in (folder / 'paths.nul').read_bytes().split(b'\0') if raw}
        allowed = set()
        for line in (folder / 'tar.log').read_text().splitlines():
            match = re.fullmatch(r'tar: (.+?): (?:socket ignored|(?:Warning: )?Cannot stat: No such file or directory)', line)
            if match:
                raw = '/' + match.group(1).lstrip('/')
                assert raw in row['online_archive_warnings_recaptured_by_next_delta']
                allowed.add(raw.lstrip('/').rstrip('/'))
        seen = set()
        with original_contents(archive) as tar:
            class AuditedTar:
                def __iter__(self):
                    for member in tar:
                        if not member.name.startswith('payload/'):
                            seen.add(member.name.rstrip('/'))
                        yield member

                def extractfile(self, member):
                    return tar.extractfile(member)
            yield AuditedTar()
        assert not expected - seen - allowed, 'Archive omitted inventory members'
        if row['parent'] is None:
            assert all(raw.lstrip('/').rstrip('/') in seen for raw in protected), 'Protected root absent from full archive'
        audits.append({'remote': archive.remote, 'expected_members': len(expected),
                       'seen_members': len(seen), 'classified_nonpayload_members': sorted(allowed),
                       'all_inventory_members_accounted': True,
                       'all_protected_roots_in_full': row['parent'] is None})
    with patch.object(Archive, 'contents', inventory_checked_contents):
        result = staged_restore(head, ROOT / 'backups/desktop-recovery', records, selected)
    assert result['passed'] and result['all_required_databases_restored']
    assert set(selected).issubset(result['regular_files_verified'])
    save(ROOT / 'recovery-result.json', {**result, 'full_inventory_audit': audits})
    print(json.dumps({'passed': True, 'databases': result['required_database_count'],
                      'selected_files': len(result['regular_files_verified']),
                      'full_non_database_tree_materialized': False}), flush=True)


def preserve_tools():
    archive = ROOT / 'recovery-tools-49cf82d60.tar.gz'
    assert not archive.exists()
    subprocess.run(['tar', '-czf', str(archive), '-C', str(PACKAGE.parent), PACKAGE.name], check=True)
    transport = DesktopTransport(ROOT / 'transport', hostname='10.0.0.109', host_key_alias='100.70.23.123')
    receipt = transport.mirror(archive, 'B:/vk-backups/vk-runtime-backup-20261007')
    save(ROOT / 'tools-desktop.json', {'package': verify(PACKAGE), 'receipt': receipt})
    print(json.dumps(receipt), flush=True)


def classify_prior():
    folder = OLD / 'backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6'
    plan = json.loads((OLD / 'backup-plan.json').read_text())
    manifest = json.loads((folder / 'payload/manifest.json').read_text())
    watched = journal(manifest['journal_sequence'])
    backup.check_journal(watched, plan)
    assert watched['instance'] == manifest['journal_instance']
    classified = backup.validate_archive_warnings((folder / 'tar.log').read_text(), watched, plan, True)
    proof = {'tools_pin': PIN, 'warnings': classified, 'classification_passed': True,
             'journal_instance': watched['instance'], 'sequence': watched['sequence'],
             'failed_archive_promoted': False, 'old_receipts_modified': False,
             'note': 'Only warning classification; a separate new full capture is required.'}
    save(ROOT / 'prior-warning-classification.json', proof)
    print(json.dumps(proof), flush=True)


def preserve_evidence():
    required = ['full-result.json', 'delta-result.json', 'recovery-result.json']
    assert all(json.loads((ROOT / name).read_text())['passed'] for name in required)
    archive = ROOT / 'runtime-backup-evidence.tar.gz'
    assert not archive.exists()
    files = sorted([*ROOT.glob('*.json'), *ROOT.glob('*.log')])
    assert all(p.is_file() and not p.is_symlink() for p in files)
    hashes = {p.name: digest(p) for p in files}
    save(ROOT / 'evidence-files.json', hashes)
    files.append(ROOT / 'evidence-files.json')
    with tarfile.open(archive, 'w:gz') as tar:
        for path in files:
            tar.add(path, arcname=path.name, recursive=False)
        tar.add(Path(__file__).resolve(), arcname='runtime_backup_20261007.py', recursive=False)
    transport = DesktopTransport(ROOT / 'transport', hostname='10.0.0.109', host_key_alias='100.70.23.123')
    receipt = transport.mirror(archive, 'B:/vk-backups/vk-runtime-backup-20261007')
    save(ROOT / 'evidence-desktop.json', receipt)
    print(json.dumps(receipt), flush=True)


def supervise(action):
    assert action in ('full', 'delta', 'restore')
    start = time.time()
    usage = os.statvfs(ROOT)
    initial = minimum = usage.f_bavail * usage.f_frsize
    assert initial > FLOOR + (28 if action == 'full' else 6) * 1024**3
    stopped = None
    with (ROOT / (action + '.log')).open('x') as log:
        child = subprocess.Popen([sys.executable, '-B', __file__, action], stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        while child.poll() is None:
            usage = os.statvfs(ROOT)
            minimum = min(minimum, usage.f_bavail * usage.f_frsize)
            if minimum < FLOOR or time.time() - start > 3600:
                stopped = 'space_floor' if minimum < FLOOR else 'deadline'
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(.5)
        code = child.wait()
    save(ROOT / (action + '-space.json'), {'at': start, 'elapsed_seconds': time.time()-start,
         'exit_code': code, 'initial_free_bytes': initial, 'minimum_free_bytes': minimum,
         'observed_host_consumption_bytes': initial-minimum, 'floor_bytes': FLOOR,
         'stopped_for': stopped, 'production_changed': False, 'tools_pin': PIN})
    print(json.dumps({'action': action, 'exit_code': code, 'seconds': time.time()-start,
                      'minimum_free_bytes': minimum, 'stopped_for': stopped}), flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    setup()
    action = sys.argv[1]
    if action == 'prepare':
        prepare()
    elif action == 'full':
        capture()
    elif action == 'delta':
        capture(json.loads((ROOT / 'full-result.json').read_text()))
    elif action == 'restore':
        restore()
    elif action == 'preserve-tools':
        preserve_tools()
    elif action == 'classify-prior':
        classify_prior()
    elif action == 'preserve-evidence':
        preserve_evidence()
    elif action == 'run':
        supervise(sys.argv[2])
    else:
        raise ValueError('Unknown bounded action')
