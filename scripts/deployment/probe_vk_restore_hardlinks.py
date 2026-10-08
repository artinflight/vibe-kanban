"""Private correctness probe; retains fixtures and never reads production payloads.

Exit 1 means the intended restore invariant failed, not that production data was
lost. The optional prototype uses a process-local file-open hook, not a source or
packaged reader modification. No fixture cleanup is performed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

from vk_archive_store import Archive, reference
from vk_change_journal import Journal
from vk_prep_common import digest, save, storage
from vk_rolling_backup import capture, restore_chain


def exercise(root, replacement, prototype=False):
    root = storage(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = root / 'source'; source.mkdir()
    a, b = source / 'A', source / 'B'
    a.write_bytes(b'old'); os.link(a, b)
    plan = {'sources': [str(source)], 'sqlite_snapshots': [],
            'excluded_rebuildable_directories': []}
    journal = Journal(plan); journal.tree(source); journal.ready = True
    directory = 'B:/vk-backups/private-hardlink-probe'
    cwd = Path.cwd()
    os.chdir(root)

    def mirror(path):
        from vk_archive_stream import StreamingArchive, RECEIVER
        if isinstance(path, StreamingArchive):
            return path.deliver(directory, [sys.executable, '-c', RECEIVER])
        remote = Path(directory) / path.name
        remote.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, remote)
        return {'desktop_verified': True, 'desktop_directory': directory,
                'name': path.name, 'sha256': digest(remote), 'bytes': remote.stat().st_size}

    def members(result):
        with Archive(reference(result), desktop_only=True).contents() as tar:
            return [{'name': row.name, 'type': row.type.decode(), 'link': row.linkname}
                    for row in tar if not row.name.startswith('payload/')]

    try:
        with patch('vk_archive_store.SSH', [sys.executable, '-']):
            first = capture(plan, root / 'backups', journal.report, mirror, publish=mirror)
            initial = restore_chain(first, root / 'backups/checkpoint-restore', desktop_only=True)
            first_files = Path(initial['destination']) / 'files' / str(source).lstrip('/')
            assert (first_files / 'A').read_bytes() == (first_files / 'B').read_bytes() == b'old'
            assert os.path.samefile(first_files / 'A', first_files / 'B')
            if replacement in ('A', 'B'):
                temporary = source / 'replacement'
                temporary.write_bytes(b'new'); temporary.replace(source / replacement)
            elif replacement == 'both-linked':
                a.write_bytes(b'new')
                b.unlink(); os.link(a, b)  # Both paths are explicitly captured.
            elif replacement != 'unchanged':
                raise ValueError('Unknown fixture')
            expected = {name: (source / name).read_text() for name in ('A', 'B')}
            expected_link = os.path.samefile(a, b)
            second = capture(plan, root / 'backups', journal.report, mirror, first, mirror)
            destination = root / 'backups/delta-restore'
            original_open = Path.open

            def new_inode_open(path, mode='r', *args, **kwargs):
                # Prototype of detaching only the overwritten private name.
                if (prototype and mode == 'wb' and path.is_relative_to(destination / 'files')
                        and path.exists() and path.stat().st_nlink > 1):
                    path.unlink()
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, 'open', new_inode_open):
                restored = restore_chain(second, destination, desktop_only=True)
            files = Path(restored['destination']) / 'files' / str(source).lstrip('/')
            actual = {name: (files / name).read_text() for name in ('A', 'B')}
            actual_link = os.path.samefile(files / 'A', files / 'B')
            assert expected == {name: (source / name).read_text() for name in ('A', 'B')}
            result = {'case': replacement, 'prototype_only': prototype,
                      'expected_content': expected, 'actual_content': actual,
                      'expected_shared_inode': expected_link, 'actual_shared_inode': actual_link,
                      'correctness_passed': actual == expected and actual_link == expected_link,
                      'restore_reported_passed': restored['passed'],
                      'checkpoint_members': members(first), 'delta_members': members(second),
                      'private_source_unchanged_by_restore': True,
                      'network_used': False, 'production_touched': False,
                      'archives_retained': [directory + '/' + r['archive'] for r in (first, second)]}
            save(root / 'result.json', result)
            return result
    finally:
        journal.close()
        os.chdir(cwd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--prototype', action='store_true')
    args = parser.parse_args()
    root = storage(args.root); root.mkdir(parents=True, mode=0o700, exist_ok=False)
    rows = [exercise(root / name, name, args.prototype)
            for name in ('unchanged', 'A', 'B', 'both-linked')]
    result = {'reader_sha256': digest(Path(__file__).with_name('vk_rolling_backup.py')),
              'probe_sha256': digest(Path(__file__)), 'cases': rows,
              'all_correctness_checks_passed': all(r['correctness_passed'] for r in rows),
              'prototype_only': args.prototype, 'production_changed': False}
    save(root / 'probe-result.json', result)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['all_correctness_checks_passed'] else 1)


if __name__ == '__main__':
    main()
