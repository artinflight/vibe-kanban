import ctypes
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_inode_journal import Journal,WatchAdmissionError,require_full_coverage,check_watch_demand


class InodeJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'source';self.root.mkdir()

    def enroll(self):
        journal=Journal({'sources':[str(self.root)]});self.addCleanup(journal.close)
        journal.tree(self.root);journal.ready=True;return journal

    def test_existing_external_and_multiple_source_aliases_report_every_selected_name(self):
        original=self.root/'original';original.write_bytes(b'first');inside=self.root/'inside';outside=self.base/'outside'
        os.link(original,inside);os.link(original,outside);journal=self.enroll();start=journal.report(0)['sequence']
        outside.write_bytes(b'later');report=journal.report(start)
        self.assertTrue(report['ready']);self.assertEqual(set(report['changed']),{str(original),str(inside)})
        self.assertEqual(report['regular_inode_watches'],1);self.assertEqual(report['regular_alias_paths'],2)
        self.assertEqual(report['coverage_model'],'all-selected-inodes-v1')

    def test_external_symlink_alias_metadata_is_observed_without_following_target(self):
        target=self.base/'not-in-scope';target.write_bytes(b'preserved target')
        link=self.root/'link';link.symlink_to(target);outside=self.base/'link-alias';os.link(link,outside,follow_symlinks=False)
        journal=self.enroll();start=journal.report(0)['sequence']
        os.utime(outside,ns=(1000000000,2000000000),follow_symlinks=False)
        report=journal.report(start)
        self.assertTrue(report['ready']);self.assertIn(str(link),report['changed'])
        self.assertEqual(report['symlink_inode_watches'],1);self.assertEqual(report['regular_inode_watches'],0)
        self.assertEqual(target.read_bytes(),b'preserved target')

    def test_external_link_created_after_enrollment_and_new_source_file_are_covered(self):
        original=self.root/'original';original.write_bytes(b'first');journal=self.enroll();start=journal.report(0)['sequence']
        outside=self.base/'later-link';os.link(original,outside);outside.write_bytes(b'later')
        report=journal.report(start);self.assertTrue(report['ready']);self.assertIn(str(original),report['changed'])
        added=self.root/'added';added.write_bytes(b'new');journal.report(report['sequence'])
        second=self.base/'second-link';os.link(added,second);second.write_bytes(b'changed')
        after=journal.report(report['sequence']);self.assertTrue(after['ready']);self.assertIn(str(added),after['changed'])

    def test_atomic_replacement_and_deletion_do_not_leave_unobserved_new_inode(self):
        original=self.root/'file';original.write_bytes(b'old');journal=self.enroll();start=journal.report(0)['sequence']
        replacement=self.base/'replacement';replacement.write_bytes(b'new');os.replace(replacement,original)
        first=journal.report(start);self.assertTrue(first['ready']);self.assertIn(str(original),first['changed'])
        outside=self.base/'alias';os.link(original,outside);outside.write_bytes(b'changed')
        second=journal.report(first['sequence']);self.assertTrue(second['ready']);self.assertIn(str(original),second['changed'])
        original.unlink();last=journal.report(second['sequence']);self.assertTrue(last['ready']);self.assertIn(str(original),last['changed'])

    def test_directory_move_retains_inode_alias_names_and_future_external_writes(self):
        first=self.root/'first';first.mkdir();original=first/'file';original.write_bytes(b'old');outside=self.base/'alias';os.link(original,outside)
        journal=self.enroll();start=journal.report(0)['sequence'];second=self.root/'second';first.rename(second)
        moved=journal.report(start);self.assertTrue(moved['ready']);self.assertGreater(moved['rename_count'],0)
        outside.write_bytes(b'later');report=journal.report(moved['sequence'])
        self.assertTrue(report['ready']);self.assertIn(str(second/'file'),report['changed']);self.assertNotIn(str(original),report['changed'])

    def test_real_kernel_refusal_is_not_ignored_or_retried_using_another_route(self):
        original=self.root/'file';original.write_bytes(b'old');journal=Journal({'sources':[str(self.root)]});self.addCleanup(journal.close)
        def full(*_):ctypes.set_errno(errno.ENOSPC);return -1
        with patch.object(journal.lib,'inotify_add_watch',side_effect=full) as watch:
            with self.assertRaises(WatchAdmissionError):journal.tree(self.root)
        self.assertEqual(watch.call_count,1);self.assertFalse(journal.report(0)['ready'])

    def test_namespace_readiness_cannot_be_adopted_as_complete_inode_coverage(self):
        report=dict(ready=True,errors=[],terminal=None,barrier=True)
        with self.assertRaises(ValueError):require_full_coverage(report)
        report['coverage_model']='directory-namespace-only-v1'
        with self.assertRaises(ValueError):require_full_coverage(report)
        report['coverage_model']='all-selected-inodes-v1';require_full_coverage(report)
        for key,value in [('ready',False),('errors',[{'coverage_lost':True}]),('terminal','stopped'),('barrier',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):require_full_coverage(dict(report,**{key:value}))

    def test_known_watch_shortfall_is_rejected_without_changing_the_host(self):
        with self.assertRaises(WatchAdmissionError):check_watch_demand(849199,248899)
        check_watch_demand(100,248899) # Necessary condition only, not real enrollment.
        with self.assertRaises(ValueError):check_watch_demand(True,248899)
