"""Match rehearsal work to the actual protected backup, including clean journals."""
import json
from pathlib import Path


def verify_workload(root, adapter, baseline, observed):
    roots = sorted(observed.get('required_subtree_recopy', []))
    if not observed.get('ready') or observed.get('errors'):
        raise ValueError('Current backup journal is not ready')
    if sorted(adapter.get('production_recopy_roots', [])) != roots or len(adapter['recopy_copies']) != len(roots):
        raise ValueError('Measured recopy workload differs from current backup')
    if roots and sorted(baseline['recopy_baseline']['roots']) != roots:
        raise ValueError('Current moved roots lack an authenticated baseline')
    if not roots:
        proof = json.loads((Path(root) / 'full-checkpoint-proof.json').read_text())
        if not (proof['passed'] and proof['full_current_checkpoint'] and proof['all_protected_recopy_roots_in_archive']):
            raise ValueError('Clean journal requires a verified full checkpoint')
        if baseline['journal_instance'] != observed['instance']:
            raise ValueError('Full checkpoint journal changed')
    return True
