"""Prepare only: no live install/restart, approval response, grant or config edit."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

BASELINE = {
    'approval_event_store.py': '540eeadc46f1670301d28e70a79e4d7cbdbf7443929742b18ada250138947e23',
    'approval_notifications.py': 'b0ef05682f34e20259da38930465999467d99711ecc1aa838860cf3949e3d1f9',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_storage(output):
    if not os.path.ismount('/mnt/vk-storage') or not output.is_relative_to('/mnt/vk-storage'):
        raise ValueError('Mounted secondary SSD output required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connector-source', type=Path, required=True)
    parser.add_argument('--notifier-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    output = args.output.resolve()
    require_storage(output)
    if output.exists() or any(output.is_relative_to(p.resolve()) for p in [args.connector_source, args.notifier_source]):
        raise ValueError('New separate output directory required')
    connector = args.connector_source.resolve()
    notifier = args.notifier_source.resolve()
    for original, expected in [(connector/'approval_event_store.py', BASELINE['approval_event_store.py']),
                               (notifier/'events.py', BASELINE['approval_event_store.py']),
                               (connector/'approval_notifications.py', BASELINE['approval_notifications.py'])]:
        if digest(original) != expected:
            raise ValueError('Live baseline mismatch; reconcile before preparing')
    if (connector/'approval_preview.py').exists() or (notifier/'approval_preview.py').exists():
        raise ValueError('Preview module already exists; reconcile the installed release')
    repo = source.parent.parent
    protected = ['crates/executors', 'crates/services/src/services/approvals.rs',
                 'crates/services/src/services/approvals',
                 'scripts/dot-connector']
    dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--', *protected], text=True)
    if dirty.strip():
        raise ValueError('Commit reviewed routing and notification source before packaging')
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    tree = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    output.mkdir(parents=True, mode=0o700)
    records = []
    for folder, src, target in [('connector', 'approval_event_store.py', 'approval_event_store.py'),
                              ('connector', 'approval_notifications.py', 'approval_notifications.py'),
                              ('connector', 'approval_preview.py', 'approval_preview.py'),
                              ('notifier', 'approval_event_store.py', 'events.py'),
                              ('notifier', 'approval_preview.py', 'approval_preview.py')]:
        destination = output/folder/target
        destination.parent.mkdir(exist_ok=True, mode=0o700)
        destination.write_bytes((source/src).read_bytes())
        destination.chmod(0o600)
        records.append({'component': folder, 'file': target, 'sha256': digest(destination)})
    rollback = []
    for folder, original, name in [('connector', connector/'approval_event_store.py', 'approval_event_store.py'),
                                    ('connector', connector/'approval_notifications.py', 'approval_notifications.py'),
                                    ('notifier', notifier/'events.py', 'events.py')]:
        destination = output/'rollback'/folder/name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination.write_bytes(original.read_bytes())
        destination.chmod(0o600)
        if digest(destination) != digest(original):
            raise ValueError('Rollback copy verification failed')
        rollback.append({'component': folder, 'file': name, 'sha256': digest(destination),
                         'installed_mode': original.stat().st_mode & 0o777})
    manifest = {'source_commit': revision, 'source_tree': tree, 'rollback': rollback,
                'backend_artifact': None, 'cutover_ready': False, 'phase': 'prepared_not_installed', 'files': records, 'baseline': BASELINE,
                'backend_required': 'Claude action-context bridge; current backend has no native action details in ApprovalInfo',
                'routing_changes': 'Source candidate uses native Claude default/acceptEdits/plan evaluation, interactive unresolved callbacks and safe plan exit; no live policy/profile changes performed',
                'backend_compatibility': {'api_schema_change': False, 'notification_fields': 'additive; legacy actions unavailable', 'automatic_install': False},
                'activation_requires': 'Exact coordinated backend/connector/notifier release authorization and owner admission; no restarts are performed by this script',
                'preserve': ['selected model/effort', 'SUPERVISED', 'native histories/ownership', 'subscriptions/principals/credentials', 'approval IDs/outcomes', 'genuine security decisions']}
    # Reconcile mutable live/source inputs after staging, before sealing a receipt.
    for original, expected in [(connector/'approval_event_store.py', BASELINE['approval_event_store.py']),
                               (connector/'approval_notifications.py', BASELINE['approval_notifications.py']),
                               (notifier/'events.py', BASELINE['approval_event_store.py'])]:
        if digest(original) != expected:
            raise ValueError('Live baseline changed during preparation; do not activate staged output')
    if subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--', *protected], text=True).strip():
        raise ValueError('Source changed during preparation; do not activate staged output')
    if subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip() != revision:
        raise ValueError('Source HEAD changed during preparation; do not activate staged output')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (output/'manifest.json').chmod(0o600)
    print(json.dumps({'phase': manifest['phase'], 'files': len(records), 'rollback_files': len(rollback), 'live_writes': 0, 'routing_changes': 0}))


if __name__ == '__main__':
    main()
