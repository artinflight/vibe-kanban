"""Check recovered paths and identify post-backup Git head drift, read-only."""
import json
import os
from pathlib import Path
import subprocess
import re
from place_missing import ROOT, PRIVATE, save

missing = json.loads((ROOT / 'missing-baseline-paths.json').read_text())
remaining = [p for p in missing if not os.path.lexists('/' + p)]
plan = json.loads((ROOT / 'placement-plan.json').read_text())
admins = set()
for row in plan['operations']:
    raw = row['target']
    if '/.git/worktrees/' in raw:
        prefix, tail = raw.split('/.git/worktrees/', 1)
        admins.add(prefix + '/.git/worktrees/' + tail.split('/')[0])
drift, errors, checked = [], [], []
for raw in sorted(admins):
    admin = Path(raw)
    prior = PRIVATE / 'files' / raw.lstrip('/')
    try:
        log = prior / 'logs/HEAD'
        if log.exists():
            old = log.read_text().splitlines()[-1].split()[1]
            basis = 'backup-reflog'
        else:
            old = (prior / 'HEAD').read_text().strip()
            if not re.fullmatch('[a-f0-9]{40}', old):
                raise ValueError('No backup log or immutable detached HEAD')
            basis = 'backup-detached-HEAD; historical no-reflog exception retained'
        common = (admin / (admin / 'commondir').read_text().strip()).resolve()
        name = (admin / 'HEAD').read_text().strip()
        ref = name.removeprefix('ref: ')
        current = subprocess.check_output(['git', '--git-dir=' + str(common), 'rev-parse', ref], text=True, timeout=10).strip()
        worktree = str(Path((admin / 'gitdir').read_text().strip()).parent)
        row = {'admin': raw, 'worktree': worktree, 'backup_head': old, 'current_head': current, 'basis': basis}
        checked.append(row)
        if old != current:
            drift.append(row)
    except (OSError, ValueError, subprocess.SubprocessError, IndexError) as e:
        errors.append({'admin': raw, 'error': str(e)})
result = {'baseline_missing_before': len(missing), 'baseline_missing_after': remaining,
          'git_checked': checked, 'git_head_drift': drift, 'git_audit_errors': errors,
          'post_backup_uncommitted_edits_fully_accounted': False,
          'production_database_restored': False}
save(ROOT / 'post-placement-audit-v2.json', result)
print(json.dumps({'baseline_missing_after': len(remaining), 'git_head_drift': drift, 'git_audit_errors': errors}))
