"""Read-only impact inventory; never place backup data over live files."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
TOOLS = Path('/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60/tools')
sys.path.insert(0, str(TOOLS))
from vk_change_journal import request
from vk_prep_common import save

assert os.path.ismount('/mnt/vk-storage')
backup = Path('/mnt/vk-storage/vk-runtime-backup-20261007')
delta = json.loads((backup / 'delta-result.json').read_text())
full = json.loads((backup / 'full-result.json').read_text())
journal = request(Path('/mnt/vk-storage/vk-combined-preparation-20261007/journal.sock'))
save(ROOT / 'journal-after.json', journal)
expected = set()
for result in (full, delta):
    folder = Path(result['folder'])
    expected.update(os.fsdecode(raw).lstrip('/') for raw in (folder / 'paths.nul').read_bytes().split(b'\0') if raw)
    manifest = json.loads((folder / 'payload/manifest.json').read_text())
    absent = {p.lstrip('/').rstrip('/') for p in manifest['absent_paths']}
    expected = {p for p in expected if not any('/'.join(p.split('/')[:i]) in absent
                for i in range(1, len(p.split('/')) + 1))}
prefixes = ('mnt/vk-storage/worktrees/', 'home/mcp/code/worktrees/')
paths = sorted(p for p in expected if p.startswith(prefixes))
missing = [p for p in paths if not os.path.lexists('/' + p)]
groups = {}
for path in missing:
    prefix = next(p for p in prefixes if path.startswith(p))
    group = prefix + path[len(prefix):].split('/')[0]
    groups[group] = groups.get(group, 0) + 1
save(ROOT / 'missing-baseline-paths.json', missing)
save(ROOT / 'impact.json', {'at': time.time(), 'expected_backup_paths': len(paths),
    'missing_backup_paths': len(missing), 'affected_top_level_roots': groups,
    'baseline_at': delta.get('at'), 'baseline': delta['folder'],
    'post_backup_edits_accounted': False, 'production_restored': False,
    'rogue_pid': 2670802, 'rogue_pid_exists': Path('/proc/2670802').exists()})
print(json.dumps({'missing_backup_paths': len(missing), 'affected_roots': groups}))
