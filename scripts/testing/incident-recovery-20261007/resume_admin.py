"""Resume only the unattempted suffix of the retained no-replace recovery plan."""
import json
from pathlib import Path
from place_missing import ROOT, move_no_replace, save, sha

plan = json.loads((ROOT / 'placement-plan.json').read_text())
prior = json.loads((ROOT / 'placement-result.json').read_text())
assert len(prior['outcomes']) == 108 and all(r['placed'] for r in prior['outcomes'])
assert not Path('/proc/2670802').exists()
proof = json.loads((ROOT / 'private-recovery-result.json').read_text())
outcomes = []
try:
    for row in plan['operations'][108:]:
        source, target = Path(row['source']), Path(row['target'])
        assert str(target).startswith('/home/mcp/') and '/.git/worktrees/' in str(target)
        assert source.is_relative_to(Path(proof['restore']['destination']) / 'files')
        check = source.rglob('*') if source.is_dir() and not source.is_symlink() else [source]
        for path in check:
            if path.is_file() and not path.is_symlink():
                name = str(path.relative_to(Path(proof['restore']['destination']) / 'files'))
                assert sha(path) == proof['files'][name]['sha256']
        placed = move_no_replace(source, target)
        outcomes.append({**row, 'placed': placed, 'collision_preserved': not placed})
finally:
    save(ROOT / 'placement-resume-result.json', {'outcomes': outcomes,
        'completed': len(outcomes) == len(plan['operations']) - 108 and all(r['placed'] for r in outcomes),
        'never_replaced': True})
print(json.dumps({'additional_placed': len(outcomes)}))
