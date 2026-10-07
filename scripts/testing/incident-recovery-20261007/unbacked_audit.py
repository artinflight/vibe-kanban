"""List missing journal names not covered by the accepted backup inventory."""
import json
import os
from pathlib import Path
from place_missing import ROOT, save

backup = Path('/mnt/vk-storage/vk-runtime-backup-20261007')
before = json.loads((backup / 'initial-journal.json').read_text())
incident = json.loads((ROOT / 'journal-after.json').read_text())
inventory = set()
for name in ('full-result.json', 'delta-result.json'):
    result = json.loads((backup / name).read_text())
    inventory.update('/' + os.fsdecode(p).lstrip('/') for p in
                     (Path(result['folder']) / 'paths.nul').read_bytes().split(b'\0') if p)
older = set(before['changed'])
rows = []
for name, mask in incident['events'].items():
    if name.startswith('/mnt/vk-storage/worktrees/') and not os.path.lexists(name) and name not in inventory and name not in older:
        rows.append({'path': name, 'mask': mask})
save(ROOT / 'unbacked-name-candidates.json', {'paths': rows,
    'classification': 'Candidates, not proof of unique file loss; events lack precise deletion timestamps',
    'post_backup_edits_fully_accounted': False,
    'prior_missing_names_not_erased': True})
print(json.dumps({'new_unbacked_missing_name_candidates': len(rows), 'sample': rows[:12]}))
