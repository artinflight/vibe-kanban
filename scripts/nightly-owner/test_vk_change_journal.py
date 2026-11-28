"""Real file-root inotify coverage; no live services or capture payloads."""
import os
from pathlib import Path
import tempfile
import unittest

from vk_change_journal import Journal
from vk_nightly_restart_baseline import capture_journal


class FileRootJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightly-file-root-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'runtime-manifest.json'
        self.source.write_text('original immutable artifact binding')
        self.plan = {'sources': [str(self.source)], 'excluded_rebuildable_directories': []}

    def journal(self):
        journal = Journal(self.plan)
        self.addCleanup(journal.close)
        journal.tree(self.source)
        journal.ready = True
        return journal

    def test_only_file_root_is_watched_and_updates_are_reported(self):
        journal = self.journal()
        self.assertEqual(journal.report()['watches'], 1)
        self.source.write_text('changed artifact binding')
        result = journal.report()
        self.assertTrue(result['ready'])
        self.assertIn(str(self.source), result['changed'])

    def test_atomic_file_replacement_invalidates_coverage(self):
        journal = self.journal()
        other = self.root / 'replacement'
        other.write_text('new inode cannot inherit the old watch')
        os.replace(other, self.source)
        result = journal.report()
        self.assertFalse(result['ready'])
        self.assertTrue(any('protected_root_deleted' in e or 'watch_removed' in e
                            for e in result['errors']))

    def test_deleted_required_file_invalidates_coverage(self):
        journal = self.journal()
        self.source.unlink()
        self.assertFalse(journal.report()['ready'])

    def test_file_root_does_not_enroll_unrequested_siblings(self):
        journal = self.journal()
        sibling = self.root / 'unrequested'
        sibling.write_text('outside the exact file scope')
        result = journal.report()
        self.assertTrue(result['ready'])
        self.assertEqual(result['changed'], [])

    def test_real_capture_journal_accepts_and_drains_file_roots(self):
        with capture_journal(self.plan) as report:
            self.assertTrue(report()['ready'])
            self.assertEqual(report()['watches'], 1)
            self.source.write_text('online preparation change')
            self.assertIn(str(self.source), report()['changed'])

    def test_directory_root_still_reports_child_creation(self):
        journal = Journal({'sources': [str(self.root)]})
        self.addCleanup(journal.close)
        journal.tree(self.root)
        journal.ready = True
        child = self.root / 'new-child'
        child.write_text('normal directory coverage')
        self.assertIn(str(child), journal.report()['changed'])


if __name__ == '__main__':
    unittest.main()
