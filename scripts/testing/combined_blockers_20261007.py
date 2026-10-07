"""Read-only deployment audit; writes new receipts, never changes live state."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/mnt/vk-storage/vk-combined-release-20261007')
PREP = Path('/mnt/vk-storage/vk-combined-preparation-20261007')
SOURCE = '2bc909d6375e13d0dd47f370eec0100fae3b2075'
PACKAGE = Path('/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-6db1a43e1')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    os.umask(0o077)
    assert os.path.ismount('/mnt/vk-storage')
    source = ROOT / 'source'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == SOURCE
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source)
    bundle = ROOT / ('bundle-' + SOURCE)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    assert manifest['sourceCommit'] == SOURCE
    for relative, expected in manifest['trackedHashes'].items():
        path = source / relative
        assert path.resolve().is_relative_to(source) and sha(path) == expected, relative
    for relative, expected in manifest['artifacts'].items():
        path = bundle / relative
        assert path.resolve().is_relative_to(bundle) and sha(path) == expected['sha256'], relative
        assert path.stat().st_size == expected['bytes']
    save(ROOT / 'repair-acceptance/bundle-verification.json', {
        'at': time.time(), 'source': SOURCE, 'manifest_sha256': sha(bundle / 'manifest.json'),
        'tracked_files': len(manifest['trackedHashes']), 'artifacts': manifest['artifacts'],
        'hashes_passed': True, 'rollout_ready': False,
        'external_frontend_required': True, 'runtime_acceptance_passed': False,
    })
    sys.path.insert(0, str(PACKAGE / 'tools'))
    from vk_recovery_package import verify
    from vk_change_journal import request
    import vk_rolling_backup
    from vk_runtime_ephemeral import install
    package = verify(PACKAGE)
    assert package['source_commit'] == '6db1a43e1bc10e991c5a9bfd27f3400166ec6594'
    install(vk_rolling_backup)
    plan = json.loads((PREP / 'backup-plan.json').read_text())
    watched = request(PREP / 'journal.sock', 0)
    save(PREP / 'journal-after-capture.json', watched)
    folder = PREP / 'backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6'
    warnings = (folder / 'tar.log').read_text()
    missing = []
    for line in warnings.splitlines():
        match = re.fullmatch(r'tar: (.+?): Warning: Cannot stat: No such file or directory', line)
        if match:
            path = '/' + match.group(1).lstrip('/')
            missing.append({'path': path, 'journal_changed': path in watched['changed'],
                            'event_mask': watched.get('events', {}).get(path),
                            'currently_exists': Path(path).exists(), 'is_symlink': Path(path).is_symlink()})
    try:
        vk_rolling_backup.validate_archive_warnings(warnings, watched, plan, True)
    except (ValueError, OSError) as error:
        warning_failure = str(error)
    else:
        raise AssertionError('Expected unresolved source-deletion guard to remain closed')
    services = {}
    for unit in ['vibe-kanban-green-production-20261005.service',
                 'vibe-kanban-blue-production-20261004.service', 'codexusage-preview.service']:
        raw = subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'MainPID',
                                       '-p', 'ActiveState', '-p', 'SubState', '-p', 'FreezerState'], text=True)
        services[unit] = dict(line.split('=', 1) for line in raw.splitlines())
    stat = os.statvfs(PREP)
    save(PREP / 'blocked-preparation.json', {
        'at': time.time(), 'package': str(PACKAGE), 'package_verification': package,
        'archive': str(folder / 'checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst'),
        'archive_bytes': (folder / 'checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst').stat().st_size,
        'capture': json.loads((PREP / 'capture-space.json').read_text()),
        'warning_failure_with_new_tools': warning_failure, 'missing_warning_evidence': missing,
        'historical_journal_errors_preserved': True, 'fresh_backup_accepted': False,
        'full_restore_proven': False, 'cutover_attempted': False, 'services': services,
        'free_bytes': stat.f_bavail * stat.f_frsize,
    })
    print(json.dumps({'bundle_hashes_passed': True, 'new_package_verified': True,
                      'backup_blocker': warning_failure, 'production_changed': False}))


if __name__ == '__main__':
    main()
