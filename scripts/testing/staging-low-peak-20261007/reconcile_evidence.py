#!/usr/bin/env python3
"""Attach bounded provenance/current registration evidence without clearing errors."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from inventory import OLD, TOOLS, RECOVERY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(TOOLS))
    from journal_compat import kernel_watches, source_removal
    from vk_prep_common import digest, save, storage
    audit = storage(args.audit)
    moves = json.loads((audit / 'moves.json').read_text())
    raw = json.loads((audit / 'journal-full.json').read_text())
    coverage = json.loads((OLD / 'move-coverage.json').read_text())
    plan = json.loads((OLD / 'backup-plan.json').read_text())
    watcher = coverage['journal_identity']
    watches = kernel_watches(watcher['service'], str(watcher['pid']))
    roots = {Path(p).resolve() for p in plan['sources']}

    def covered(path):
        try:
            st = path.stat()
            return not path.is_symlink() and path.is_dir() and (
                (os.major(st.st_dev) << 20) | os.minor(st.st_dev), st.st_ino) in watches
        except FileNotFoundError:
            return False

    records = []
    for row in moves['moves']:
        path = Path(row['destination'])
        record = dict(row)
        if len(row['source_candidates']) == 1 and path.exists():
            try:
                record['verified_source'] = source_removal(path, path.parent, raw['events'], roots,
                    covered, {str(path): row['source_candidates'][0]})
                record['destination_parent_watched'] = covered(path.parent)
                record['classification'] = 'source-event and source-watch verified; needs bounded recopy coverage'
            except AssertionError as error:
                record['classification'] = 'source verification unresolved: ' + str(error)
        elif row['placement_receipt'] and not path.exists():
            original = row['placement_receipt']
            repository = Path(original['repository_target'])
            pointer = repository / '.git'
            try:
                gitdir = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', '--absolute-git-dir'],
                                                text=True, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).strip()
                gitdir = Path(gitdir)
                backlink = (gitdir / 'gitdir').read_text().strip()
                if Path(backlink).resolve() != pointer.resolve():
                    raise ValueError('Replacement backlink does not match workspace')
                subprocess.run(['git', '-C', str(repository), 'rev-parse', '--verify', 'HEAD^{commit}'],
                               stdout=subprocess.DEVNULL, check=True, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
                record.update(classification='retired recovery registration; current replacement verifies',
                              replacement_gitdir=str(gitdir), pointer_sha256=digest(pointer),
                              replacement_backlink=backlink, original_deletion_event=bool(row['event_mask'] & 0x200))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                record['classification'] = 'registration unresolved: ' + str(error)
        elif row['placement_receipt'] and path.exists():
            original = row['placement_receipt']
            record['classification'] = 'receipt-backed incoming recovery placement; source outside old journal'
            record['incoming_source'] = str(RECOVERY.parent / 'october4-recovered-tree' / original['root'])
        else:
            record['classification'] = 'unexplained move; no matching recorded source or recovery placement'
        records.append(record)
    result = {'production_modified': False, 'journal_modified': False, 'backup_ready': False,
        'original_errors_preserved': raw['errors'], 'kernel_watch_count': len(watches),
        'records': records, 'historical_exceptions_preserved': True,
        'raw_receipt_sha256': digest(audit / 'journal-full.json'),
        'placement_receipt_sha256': moves['placement_sha256'],
        'protected_roots': [{'path': p, 'exists': Path(p).is_dir(), 'watched': covered(Path(p))}
                            for p in coverage['recopy_roots']]}
    save(audit / 'move-reconciliation-evidence.json', result)
    from collections import Counter
    print(json.dumps(dict(Counter(r['classification'] for r in records)), indent=2))


if __name__ == '__main__':
    main()
