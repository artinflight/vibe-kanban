"""Recover this turn's exact owner files from pushed HEAD and recorded patches."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from place_missing import ROOT, sha, save

owner = Path('/mnt/vk-storage/worktrees/4e18-vk-staging-check/_vibe_kanban_repo')
rebuilt = ROOT / 'owner-rebuilt'
proof = json.loads((ROOT / 'private-recovery-result.json').read_text())
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=owner, text=True).strip() == '422fe5ba0a406f03dd3a658d25e2f632f66d49ab'
rows = []
for source in rebuilt.rglob('*'):
    if not source.is_file() or source.is_symlink():
        continue
    target = owner / source.relative_to(rebuilt)
    checksum = sha(source)
    if target.exists() and sha(target) == checksum:
        continue
    assert not target.is_symlink()
    if target.exists():
        archived = proof['files'][str(target).lstrip('/')]['sha256']
        assert sha(target) == archived, 'Current owner file changed after no-replace recovery'
        saved = ROOT / 'owner-restored-preimages' / source.relative_to(rebuilt)
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        assert sha(saved) == archived
    else:
        archived = None
    rows.append({'source': str(source), 'target': str(target), 'sha256': checksum, 'recovered_backup_sha256': archived})
save(ROOT / 'owner-edit-restoration-plan.json', {'files': rows,
    'basis': 'pushed 422fe5ba0 plus exact recorded current-turn apply_patch calls', 'not_a_branch_reset': True})
for row in rows:
    source, target = Path(row['source']), Path(row['target'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if row['recovered_backup_sha256'] is not None:
        assert sha(target) == row['recovered_backup_sha256']
    else:
        assert not os.path.lexists(target)
    temporary = target.with_name(target.name + '.incident-recovery-new')
    with temporary.open('xb') as output, source.open('rb') as contents:
        shutil.copyfileobj(contents, output)
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(source.stat().st_mode & 0o777)
    temporary.replace(target)
    assert sha(target) == row['sha256']
# The recovered index predates the last pushed commit. Preserve it, then align
# only our staging index to that exact unchanged HEAD; working files stay put.
index = Path('/home/mcp/_vibe_kanban_repo/.git/worktrees/_vibe_kanban_repo1/index')
shutil.copy2(index, ROOT / 'owner-index-before')
subprocess.run(['git', 'read-tree', '422fe5ba0a406f03dd3a658d25e2f632f66d49ab'], cwd=owner, check=True)
save(ROOT / 'owner-edit-restoration-result.json', {'files': rows, 'passed': True, 'head_unchanged': True,
    'preimages_retained': True, 'working_edits_reconstructed_from_transcript': True})
print(json.dumps({'owner_files_recovered_from_pushed_HEAD_and_transcript': len(rows)}))
