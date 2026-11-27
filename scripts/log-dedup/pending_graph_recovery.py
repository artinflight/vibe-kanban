"""Qualify an interrupted, unpublished graph backup for the existing resume path.

No conversion, receipt rewriting, lock release or service action. Retained B graph
checkpoints are reopened by the qualified owner before live publication.
"""
import hashlib
from pathlib import Path

from checkpoint_control import canonical, read, require


def inspect(root, proof, full_hash=True):
    from controlled_conversion import reference, sha, verify_pins
    root = Path(root)
    number = proof['batch']
    require(type(number) is int and number >= 0, 'invalid pending batch')
    folder = root / f'batch-{number:04d}'
    require(proof['folder'] == str(folder), 'pending graph path differs')
    verify_pins(proof['pins'])
    for name in ('journal', 'RESULT.private.json', 'CONVERSION.private.json',
                 'DYNAMIC_RECOVERY.private.json', 'CARRIER_RETIREMENT_RESULT.private.json'):
        require(not (folder / name).exists(), 'pending batch has publication evidence; reconcile')
    expected = ['PLAN.private.json', 'PLAN_ALL.private.json', 'NONBENEFICIAL.private.json',
                'OWNER.private.json', 'OWNER_RESUME3.private.json', 'PREPARED.private.json',
                'PREPARATION_COMPLETE.private.json', 'CONFIGURATION.private.json',
                'B_REQUEST.private.json']
    graphs = sorted((folder / 'graph-recovery').glob('graph-checkpoint-*.json'),
                    key=lambda p: int(p.stem.rsplit('-', 1)[1]))
    require(graphs and [p.name for p in graphs] ==
            [f'graph-checkpoint-{n}.json' for n in range(len(graphs))],
            'pending graph receipt prefix differs')
    require(proof['pins'] == [reference(folder / p) for p in expected] +
            [reference(p) for p in graphs], 'pending proof scope changed')
    owner = read(folder / 'OWNER.private.json')
    resumed = read(folder / 'OWNER_RESUME3.private.json')
    attempt = resumed.get('archive_resume_attempt')
    require(isinstance(attempt, str) and attempt.isalnum() and len(attempt) <= 32
            and resumed == dict(owner, archive_resume_attempt=attempt),
            'resume owner changes more than the new carrier suffix')
    require(not (folder / 'graph-recovery' / f'pack-{len(graphs)}-{attempt}').exists(),
            'resume carrier already exists; reconcile rather than replay')
    plan = read(folder / 'PLAN.private.json', 8 * 1024**2)
    selection = read(root / 'FINITE_BATCHES.private.json', 8 * 1024**2)['batches'][number]
    excluded = read(folder / 'NONBENEFICIAL.private.json')
    names = [r['path'] for r in plan['files']]
    skipped = [r['path'] for r in excluded]
    require(set(names).isdisjoint(skipped) and len(names) == len(set(names))
            and set(names + skipped) == set(selection['names'])
            and all(r['reason'] == 'no_positive_allocated_benefit' for r in excluded)
            and owner['plan_sha256'] == hashlib.sha256(canonical(plan)).hexdigest(),
            'pending plan scope or digest differs')
    source = Path(plan['source_root'])
    require(source.is_absolute(), 'absolute source root required')
    for row in plan['files']:
        path = source / row['path']
        require(path.is_relative_to(source) and '..' not in Path(row['path']).parts
                and not Path(row['path']).is_absolute(), 'unsafe pending source path')
        members = [(path, row)] + [(path.with_suffix('.' + s['extension']), s)
                                    for s in row.get('sidecars', [])]
        for path, expected in members:
            st = path.lstat()
            require(path.is_file() and not path.is_symlink()
                    and [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]
                    == expected['identity'], 'unpublished original identity changed')
            if full_hash:
                require(sha(path) == expected['sha256'], 'unpublished original bytes changed')
    return proof


def evidence(root, number):
    from controlled_conversion import reference
    folder = Path(root) / f'batch-{number:04d}'
    names = ['PLAN.private.json', 'PLAN_ALL.private.json', 'NONBENEFICIAL.private.json',
             'OWNER.private.json', 'OWNER_RESUME3.private.json', 'PREPARED.private.json',
             'PREPARATION_COMPLETE.private.json', 'CONFIGURATION.private.json',
             'B_REQUEST.private.json']
    graphs = sorted((folder / 'graph-recovery').glob('graph-checkpoint-*.json'),
                    key=lambda p: int(p.stem.rsplit('-', 1)[1]))
    proof = dict(batch=number, folder=str(folder),
                 pins=[reference(folder / p) for p in names] + [reference(p) for p in graphs])
    return inspect(root, proof)
