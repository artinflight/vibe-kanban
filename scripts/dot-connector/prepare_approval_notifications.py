"""Prepare only: no live install/restart, approval response, grant or config edit."""
import argparse
import hashlib
import json
import os
from pathlib import Path

BASELINE = {
    'approval_event_store.py': '540eeadc46f1670301d28e70a79e4d7cbdbf7443929742b18ada250138947e23',
    'approval_notifications.py': 'b0ef05682f34e20259da38930465999467d99711ecc1aa838860cf3949e3d1f9',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connector-source', type=Path, required=True)
    parser.add_argument('--notifier-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    output = args.output.resolve()
    if not os.path.ismount('/mnt/vk-storage') or not output.is_relative_to('/mnt/vk-storage'):
        raise ValueError('Mounted secondary SSD output required')
    if output.exists() or any(output.is_relative_to(p.resolve()) for p in [args.connector_source, args.notifier_source]):
        raise ValueError('New separate output directory required')
    connector = args.connector_source.resolve()
    notifier = args.notifier_source.resolve()
    assert digest(connector/'approval_event_store.py') == BASELINE['approval_event_store.py']
    assert digest(notifier/'events.py') == BASELINE['approval_event_store.py']
    assert digest(connector/'approval_notifications.py') == BASELINE['approval_notifications.py']
    assert not (connector/'approval_preview.py').exists()
    assert not (notifier/'approval_preview.py').exists()
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
    manifest = {'phase': 'prepared_not_installed', 'files': records, 'baseline': BASELINE,
                'backend_required': 'Claude action-context bridge; current backend has no native action details in ApprovalInfo',
                'routing_changes': 'none; proposed permission-routing changes were rejected by automatic approval review',
                'activation_requires': 'Exact coordinated backend/connector/notifier release authorization and owner admission; no restarts are performed by this script',
                'preserve': ['selected model/effort', 'SUPERVISED', 'native histories/ownership', 'subscriptions/principals/credentials', 'approval IDs/outcomes', 'genuine security decisions']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (output/'manifest.json').chmod(0o600)
    print(json.dumps({'phase': manifest['phase'], 'files': len(records), 'live_writes': 0, 'routing_changes': 0}))


if __name__ == '__main__':
    main()
