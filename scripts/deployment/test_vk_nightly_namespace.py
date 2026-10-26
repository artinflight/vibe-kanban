"""Namespace bootstrap covers aliases/errors without reading any file body."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_namespace import audit
from vk_nightly_qualification import decode_observation


class NamespaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'file').write_bytes(b'unread payload')
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)

    def run_audit(self, plan, **kwargs):
        return audit(plan, self.db, checkpoint=lambda: None, maximum_paths=100, **kwargs)

    def test_overlapping_roots_alias_and_discovered_link_preserve_names_no_payload(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'never').write_text('not followed')
        (self.source / 'external').symlink_to(outside)
        with patch.object(Path, 'open', side_effect=AssertionError('body opened')):
            result = self.run_audit({'sources': [str(alias), str(self.source), str(self.source / 'file')]})
        self.assertTrue(result['complete'])
        self.assertFalse(result['baseline_accepted'])
        self.assertEqual(result['source_payload_bytes_read'], 0)
        self.assertEqual(result['observed_paths'], 4)
        self.assertEqual(result['symlinks'], 2)

    def test_exclusion_and_recorded_absence_are_exact(self):
        missing = str(self.root / 'absent')
        result = self.run_audit(dict(sources=[str(self.source), missing],
             excluded_rebuildable_directories=[str(self.source / 'file')],
             absent_source_exceptions=[dict(path=missing, current='absent')]))
        self.assertEqual(result['observed_paths'], 1)
        self.assertEqual(result['absent_source_exceptions'], [missing])

    def test_missing_required_source_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, 'required source unavailable'):
            self.run_audit({'sources': [str(self.root / 'missing')]})

    def test_bounded_partial_is_preserved_and_never_accepted_or_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            audit({'sources': [str(self.source)]}, self.db, checkpoint=lambda: None, maximum_paths=1)
        self.assertEqual(self.db.execute('select count(*) from namespace').fetchone()[0], 1)
        with self.assertRaisesRegex(ValueError, 'preserve previous'):
            self.run_audit({'sources': [str(self.source)]})

    def test_special_inode_requires_disposition_not_omission(self):
        os.mkfifo(self.source / 'fifo')
        result = self.run_audit({'sources': [str(self.source)]})
        self.assertEqual(result['specials'], 1)
        raw = self.db.execute('select row from namespace where name=?', (str(self.source / 'fifo').lstrip('/'),)).fetchone()[0]
        self.assertTrue(decode_observation(raw)['requires_explicit_disposition'])

    def test_live_child_disappearance_is_retained_as_pending_replay_not_a_complete_map(self):
        from vk_nightly_namespace import observe
        def observed(path):
            if Path(path).name == 'file':
                raise FileNotFoundError(2, 'concurrent disappearance', str(path))
            return observe(path)
        with patch('vk_nightly_namespace.observe', side_effect=observed):
            result = self.run_audit({'sources': [str(self.source)]})
        self.assertTrue(result['traversal_finished'])
        self.assertFalse(result['complete'])
        self.assertFalse(result['baseline_accepted'])
        self.assertEqual(result['pending_errors'], 1)
        self.assertEqual(self.db.execute('select count(*) from namespace_errors').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
