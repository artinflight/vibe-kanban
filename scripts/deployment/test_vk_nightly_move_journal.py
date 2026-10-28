"""Actual inotify moves and failure cases on small isolated fixtures."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_change_journal import OVERFLOW, UNMOUNT, ISDIR
from vk_nightly_move_journal import Journal, FROM, TO, SELF
from vk_nightly_tracking import TrackingStore, FORMAT


class MoveJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightly-moves-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.old = self.source / 'old'
        (self.old / 'nested').mkdir(parents=True)
        (self.old / 'nested' / 'file').write_text('retained watch')

    def journal(self, extra=()):
        value = Journal({'sources': [str(self.source), *map(str, extra)]})
        self.addCleanup(value.close)
        value.tree(self.source)
        value.ready = True
        value.report()
        return value

    def test_real_same_parent_move_retains_watches_without_rescan(self):
        journal = self.journal()
        count = len(journal.watches)
        new = self.source / 'new'
        self.old.rename(new)
        with patch.object(journal, 'tree', side_effect=AssertionError('paired tree re-walked')):
            moved = journal.report()
        self.assertTrue(moved['ready'], moved)
        self.assertEqual(len(journal.watches), count)
        self.assertEqual(len(moved['rename_pairs']), 1)
        self.assertGreater(moved['rename_pairs'][0]['cookie'], 0)
        point = moved['sequence']
        (new / 'nested' / 'file').write_text('changed through retained inode')
        delta = journal.report(point)
        self.assertIn(str(new / 'nested' / 'file'), delta['changed'])
        self.assertNotIn(str(self.old / 'nested' / 'file'), delta['changed'])

    def test_move_into_new_parent_uses_same_watch_inode_not_invented_TO(self):
        journal = self.journal()
        nested = self.source / 'created'
        nested.mkdir()
        new = nested / 'new'
        self.old.rename(new)
        moved = journal.report()
        self.assertTrue(moved['ready'], moved)
        self.assertEqual(len(moved['rename_pairs']), 1)
        self.assertIn('same kernel watch/inode', moved['rename_pairs'][0]['qualification'])
        (new / 'nested' / 'file').write_text('still watched')
        self.assertIn(str(new / 'nested' / 'file'), journal.report()['changed'])

    def test_out_of_scope_move_stays_pending_then_faults(self):
        journal = self.journal()
        self.old.rename(self.root / 'outside')
        self.assertFalse(journal.report()['ready'])
        with patch('vk_nightly_move_journal.time.monotonic', return_value=10**12):
            result = journal.report()
        self.assertFalse(result['ready'])
        self.assertTrue(any('unmatched_directory_move' in error for error in result['errors']))

    def test_required_nested_root_move_cannot_be_relabelled(self):
        journal = self.journal(extra=[self.old])
        self.old.rename(self.source / 'new')
        result = journal.report()
        self.assertFalse(result['ready'])
        self.assertTrue(any('protected_root_moved' in error for error in result['errors']))

    def test_no_cookie_and_prior_overflow_never_become_valid_pair(self):
        journal = self.journal()
        wd = next(wd for wd, path in journal.watches.items() if path == str(self.source))
        journal.event(wd, OVERFLOW, '')
        journal.event(wd, FROM | ISDIR, 'old', 0)
        self.old.rename(self.source / 'new')
        result = journal.report()
        self.assertFalse(result['ready'])
        self.assertTrue(any('coverage_lost' in error for error in result['errors']))
        self.assertTrue(any('directory_move_cookie_missing' in error for error in result['errors']))

    def test_SELF_before_destination_pair_is_temporarily_unready(self):
        journal = self.journal()
        wd = next(wd for wd, path in journal.watches.items() if path == str(self.source))
        moved_wd = next(wd for wd, path in journal.watches.items() if path == str(self.old))
        journal.event(wd, FROM | ISDIR, 'old', 123)
        journal.event(moved_wd, SELF, '', 0)
        self.assertFalse(journal.report()['ready'])
        # Synthetic event ordering over actual retained watches. No filesystem
        # mutation here: testing the protocol state machine, not a new inode.
        journal.event(wd, TO | ISDIR, 'new', 123)
        self.assertTrue(journal.report()['ready'])

    def test_durable_queue_keeps_actual_old_new_names_for_delta_reconciliation(self):
        journal = self.journal()
        new = self.source / 'new'
        self.old.rename(new)
        value = journal.report()
        binding = dict(format=FORMAT, instance=value['instance'], owner_pid=os.getpid(),
                       plan_sha256='b' * 64, scope_sha256=value['scope_sha256'])
        with TrackingStore.held(self.root / 'queue.sqlite') as store:
            store.start(binding)
            store.commit(value)
            result = store.report(value['instance'], 0)
            self.assertTrue(result['ready'])
            self.assertTrue(result['events'][str(self.old)] & FROM)
            self.assertTrue(result['events'][str(new)] & TO)

    def test_unmount_remains_sticky(self):
        journal = self.journal()
        journal.event(-1, UNMOUNT, '')
        self.assertFalse(journal.report()['ready'])

    def test_enrollment_subscribes_before_listing_new_child_directory(self):
        journal = Journal({'sources': [str(self.source)]})
        self.addCleanup(journal.close)
        original = os.scandir
        created = self.source / 'concurrent'
        def listing(path):
            self.assertIn(str(path), journal.watches.values())
            if Path(path) == self.source and not created.exists():
                created.mkdir()
            return original(path)
        with patch('vk_nightly_move_journal.os.scandir', side_effect=listing):
            journal.tree(self.source)
        journal.ready = True
        self.assertTrue(journal.report()['ready'])
        (created / 'new').write_text('covered after subscription')
        self.assertIn(str(created / 'new'), journal.report()['changed'])


if __name__ == '__main__':
    unittest.main()
