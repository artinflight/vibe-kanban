#!/usr/bin/env python3
"""Read production metadata; write only a new audit on mounted SSD.

This is an inventory, not a journal repair or backup acceptance certificate.
All errors remain in the receipt, including moves with plausible provenance.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time

TOOLS = Path('/mnt/vk-storage/vk-green-reprepare-20261005/operational-source/scripts/deployment')
PIN = '528282d00c985230aad3033dc235d8cd943e5f4d'
OLD = Path('/mnt/vk-storage/vk-green-cutover-20261005')
RECOVERY = Path('/mnt/vk-storage/workspace-incident-recovery-20261005/placement-preparation-20261005')


def minimal_roots(roots):
    selected = []
    for root in sorted(set(map(Path, roots)), key=lambda p: (len(p.parts), str(p))):
        if not any(parent == root or parent in root.parents for parent in selected):
            selected.append(root)
    return selected


def classify_move(error, events, coverage, placement):
    destination = error.get('directory_moved')
    if destination is None:
        return {'error': error, 'status': 'unresolved non-move error'}
    path = Path(destination)
    record = next((r for r in placement if r.get('new_admin') == destination
                   or r.get('target') == destination), None)
    candidates = [p for p, mask in events.items() if mask & 0x40000040 == 0x40000040
                  and p != destination and Path(p).name == path.name]
    if record and record.get('new_admin') == destination:
        expected = str(path.parent.parent / ('recovery-preparation-20261005-' + record['root']))
        if events.get(expected, 0) & 0x40000040 == 0x40000040:
            candidates = [expected]
    if path.name == '0.160.1-x86_64-unknown-linux-musl':
        candidates = [p for p, mask in events.items()
                      if Path(p).parent == path.parent and Path(p).name.startswith('.staging.' + path.name + '.')
                      and mask & 0x40000040 == 0x40000040]
    return {
        'destination': destination, 'exists': path.exists(), 'symlink': path.is_symlink(),
        'event_mask': events.get(destination, 0), 'source_candidates': candidates,
        'declared_covers': [r for r in coverage['recopy_roots'] if Path(r) in path.parents],
        'placement_receipt': record,
        'status': ('source evidence identified; current subtree/watch verification required'
                   if len(candidates) == 1 and path.exists() else
                   'unresolved: destination absent' if not path.exists() else
                   'unresolved: source evidence absent or ambiguous'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(TOOLS))
    from vk_prep_common import save, storage, digest
    from vk_change_journal import request
    from vk_rolling_backup import scan, Exclusions
    import subprocess
    assert subprocess.check_output(['git', '-C', str(TOOLS), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    output = storage(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = time.time()
    parent = json.loads((OLD / 'online-backup-result.json').read_text())
    plan = json.loads((OLD / 'backup-plan.json').read_text())
    coverage = json.loads((OLD / 'move-coverage.json').read_text())
    placement_file = RECOVERY / 'attempt2/placement-final.json'
    placement = json.loads(placement_file.read_text())['roots']
    full = request(OLD / 'journal.sock', 0)
    delta = request(OLD / 'journal.sock', parent['journal_sequence'])
    save(output / 'journal-full.json', full)
    save(output / 'journal-delta.json', delta)
    moves = [classify_move(e, full['events'], coverage, placement) for e in full['errors']]
    save(output / 'moves.json', {'errors_preserved': full['errors'], 'moves': moves,
         'placement_receipt': str(placement_file), 'placement_sha256': digest(placement_file),
         'coverage_accepted': False, 'journal_modified': False})
    print(json.dumps({'phase': 'move inventory retained', 'errors': len(moves)}), flush=True)
    exclusions = Exclusions(plan)
    paths = set(delta['changed'])
    # Retain every prior recovery root and every moved destination. Collapse
    # overlapping directories so a nested changed tree is traversed only once.
    inventory_roots = minimal_roots([p for p in paths if Path(p).is_dir()] +
        coverage['recopy_roots'] + [r['destination'] for r in moves if r.get('exists')])
    paths.update(scan(inventory_roots, plan, exclusions))
    paths = {p for p in paths if not exclusions(p)}
    databases = set(parent['databases']) | set(plan['sqlite_snapshots']) | set(plan['critical_sqlite'])
    errors, entries = [], []
    missing, nonregular = [], []
    for raw in sorted(paths):
        p = Path(raw)
        try:
            st = p.lstat()
            if stat.S_ISREG(st.st_mode):
                with p.open('rb') as stream:
                    is_database = stream.read(16) == b'SQLite format 3\0'
                if is_database:
                    databases.add(str(p.resolve()))
                entries.append({'path': raw, 'bytes': st.st_size, 'allocated': st.st_blocks * 512,
                                'device': st.st_dev, 'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns,
                                'sqlite': is_database})
            else:
                nonregular.append({'path': raw, 'mode': st.st_mode,
                                   'link': os.readlink(p) if p.is_symlink() else None})
        except FileNotFoundError:
            missing.append(raw)
        except OSError as error:
            errors.append({'path': raw, 'error': str(error)})
    db_rows = []
    for raw in sorted(databases):
        p = Path(raw)
        try:
            size = p.stat().st_size
            wal = Path(raw + '-wal')
            wal_size = wal.stat().st_size if wal.exists() else 0
            db_rows.append({'path': raw, 'bytes': size, 'wal_bytes': wal_size,
                            'snapshot_upper_bytes': size + wal_size})
        except OSError as error:
            errors.append({'database': raw, 'error': str(error)})
    omitted = {raw + suffix for raw in databases for suffix in ('', '-wal', '-shm')}
    file_bytes = sum(r['bytes'] for r in entries if str(Path(r['path']).resolve()) not in omitted)
    db_bytes = sum(r['snapshot_upper_bytes'] for r in db_rows)
    # Conservative tar/long-path/manifest overhead; no assumed compression savings.
    headers = (len(entries) + len(nonregular) + len(missing) + len(db_rows) + 1) * 4096
    archive_bound = (file_bytes + db_bytes + headers) * 110 // 100 + 1024 * 1024
    statv = os.statvfs(output)
    free = statv.f_bavail * statv.f_frsize
    save(output / 'file-inventory.json', {'regular': entries, 'nonregular': nonregular, 'absent': missing})
    after = request(OLD / 'journal.sock', full['sequence'])
    summary = {'started': started, 'finished': time.time(), 'operational_pin': PIN,
        'production_modified': False, 'backup_ready': False,
        'journal_errors': len(full['errors']), 'moves_outside_old_declared_roots':
        sum(not r.get('declared_covers') for r in moves),
        'source_evidenced_present_moves': sum(r['status'].startswith('source evidence') for r in moves),
        'database_count': len(db_rows), 'database_inventory': db_rows,
        'non_database_file_bytes': file_bytes, 'database_snapshot_upper_bytes': db_bytes,
        'archive_uncompressed_bound_bytes': archive_bound,
        'fresh_capture_upper_bytes': 2 * db_bytes + archive_bound,
        'free_bytes': free, 'free_floor_bytes': 2 * 1024**3,
        'errors': errors, 'regular_count': len(entries), 'absent_path_count': len(missing),
        'sized_subtree_roots': list(map(str, inventory_roots)),
        'concurrent_changed_paths': len(after['changed']),
        'inventory_is_live_estimate_not_fenced_upper_bound': True,
        'protected_roots': [{'path': p, 'present': Path(p).is_dir(), 'symlink': Path(p).is_symlink()}
                            for p in coverage['recopy_roots']],
        'reconciliation_remaining': [r for r in moves if not r['status'].startswith('source evidence')],
        'raw_receipt_sha256': digest(output / 'journal-full.json'),
        'moves_receipt_sha256': digest(output / 'moves.json')}
    save(output / 'summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in
                     ('database_inventory', 'protected_roots', 'reconciliation_remaining')}, indent=2))


if __name__ == '__main__':
    main()
