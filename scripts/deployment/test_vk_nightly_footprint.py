"""Tiny isolated metadata fixtures; no production capture, SSH or scheduling."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vk_nightly_footprint import Samples, compression_samples, inventory, walk
from vk_rolling_backup import scan
from vk_nightly_job import inventory as controller_inventory


class Footprint(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root/'data'
        self.data.mkdir()
        self.plan = {'sources': [str(self.data)], 'excluded_rebuildable_directories': []}

    def tearDown(self):
        self.temp.cleanup()

    def test_overlap_and_explicit_root_symlink_match_existing_scope(self):
        (self.data/'nested').mkdir()
        (self.data/'nested/file').write_bytes(b'payload')
        alias = self.root/'alias'
        alias.symlink_to(self.data, target_is_directory=True)
        self.plan['sources'] += [str(alias), str(self.data/'nested')]
        self.assertEqual({p for p, _ in walk(self.plan)}, scan(self.plan['sources'], self.plan))
        self.assertEqual(inventory(self.plan)['logical_bytes'], 7)

    def test_child_symlink_not_followed_and_excluded_tree_not_read(self):
        other = self.root/'other'
        other.mkdir()
        (other/'private').write_bytes(b'outside')
        (self.data/'child').symlink_to(other, target_is_directory=True)
        skip = self.data/'skip'
        skip.mkdir()
        (skip/'content').write_bytes(b'excluded')
        self.plan['excluded_rebuildable_directories'] = [str(skip)]
        result = inventory(self.plan)
        self.assertEqual(result['files'], 0)
        self.assertEqual(result['symlinks'], 1)

    def test_all_headers_detect_unusual_sqlite_names_and_required_coverage(self):
        dbfile = self.data/'old.backup-name'
        with sqlite3.connect(dbfile) as db:
            db.execute('create table example(value)')
        self.plan['critical_sqlite'] = [str(dbfile)]
        result = inventory(self.plan)
        self.assertEqual(list(result['databases']), [str(dbfile)])
        self.plan['critical_sqlite'].append(str(self.data/'missing'))
        with self.assertRaises(ValueError): inventory(self.plan)

    def test_existing_controller_inventory_contract_remains_read_only(self):
        dbfile = self.data/'state.sqlite'
        with sqlite3.connect(dbfile) as db:
            db.execute('create table example(value)')
        self.plan['sqlite_snapshots'] = [str(dbfile)]
        before = dbfile.stat()
        value = controller_inventory(self.plan)
        self.assertEqual(value['databases'], {str(dbfile): before.st_size})
        self.assertEqual(value['logical_file_bytes'], before.st_size)
        self.assertTrue(value['read_only'])
        self.assertFalse(value['content_hashed'])
        self.assertEqual(dbfile.stat().st_mode, before.st_mode)

    def test_unapproved_special_member_is_blocking(self):
        os.mkfifo(self.data/'pipe')
        with self.assertRaisesRegex(ValueError, 'special'): inventory(self.plan)

    def test_walk_is_lazy_before_descending(self):
        (self.data/'file').write_bytes(b'x')
        iterator = walk(self.plan)
        self.assertEqual(next(iterator)[0], str(self.data))
        # Reading the root yielded before the directory is opened. New children
        # are discovered lazily, rather than from a retained full file list.
        (self.data/'later').write_bytes(b'y')
        self.assertIn(str(self.data/'later'), {raw for raw, _ in iterator})

    def test_directory_substitution_cannot_expand_approved_scope(self):
        child = self.data/'child'
        child.mkdir()
        outside = self.root/'outside'
        outside.mkdir()
        (outside/'private').write_bytes(b'outside')
        iterator = walk(self.plan)
        next(iterator)
        self.assertEqual(next(iterator)[0], str(child))
        child.rename(self.data/'original')
        child.symlink_to(outside, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            list(iterator)

    def test_sample_memory_is_bounded_independent_of_source_file_count(self):
        samples = Samples(maximum=8)
        for i in range(30000): samples.add('/fixture/'+str(i), i+1)
        self.assertEqual(len(samples.heap), 9)
        self.assertEqual(len(samples.selected()), 8)

    def test_samples_report_estimates_and_reject_source_change(self):
        p = self.data/'content'
        p.write_bytes(b'fixed text content\n'*4096)
        result = compression_samples([(str(p), p.stat().st_size, p.stat().st_size)], p.stat().st_size)
        self.assertFalse(result['exact'])
        self.assertLess(result['estimated_objects'], p.stat().st_size)
        with self.assertRaisesRegex(ValueError, 'changed'):
            compression_samples([(str(p), 1, 1)], 1)


if __name__ == '__main__': unittest.main()
