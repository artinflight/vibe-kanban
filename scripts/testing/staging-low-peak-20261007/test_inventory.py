import unittest
from pathlib import Path
from unittest.mock import patch

from inventory import classify_move, minimal_roots


class InventoryTests(unittest.TestCase):
    def test_nested_roots_preserve_complete_union(self):
        self.assertEqual(minimal_roots(['/a/b', '/a', '/ab', '/a/b/c', '/ab']), [Path('/a'), Path('/ab')])

    def test_outside_recopy_root_is_not_hidden(self):
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'is_symlink', return_value=False):
            row = classify_move({'directory_moved': '/protected/new/repo'},
                                {'/protected/old/repo': 0x40000040}, {'recopy_roots': ['/different']}, [])
        self.assertEqual(row['declared_covers'], [])
        self.assertEqual(row['source_candidates'], ['/protected/old/repo'])
        self.assertIn('verification required', row['status'])

    def test_unexplained_import_stays_unresolved(self):
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'is_symlink', return_value=False):
            row = classify_move({'directory_moved': '/protected/new/repo'}, {}, {'recopy_roots': []}, [])
        self.assertIn('unresolved', row['status'])

    def test_missing_destination_cannot_be_accepted_from_source_event(self):
        with patch.object(Path, 'exists', return_value=False), patch.object(Path, 'is_symlink', return_value=False):
            row = classify_move({'directory_moved': '/protected/new/repo'},
                                {'/protected/old/repo': 0x40000040}, {'recopy_roots': ['/protected/new']}, [])
        self.assertEqual(row['status'], 'unresolved: destination absent')

    def test_unknown_error_is_retained(self):
        error = {'coverage_lost': 0x4000}
        self.assertEqual(classify_move(error, {}, {'recopy_roots': []}, [])['error'], error)

    def test_recovery_mapping_still_requires_source_event(self):
        record = {'new_admin': '/repo/.git/worktrees/recovery-x', 'root': 'x'}
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'is_symlink', return_value=False):
            row = classify_move({'directory_moved': record['new_admin']}, {}, {'recopy_roots': []}, [record])
        self.assertEqual(row['source_candidates'], [])
        self.assertIn('unresolved', row['status'])


if __name__ == '__main__':
    unittest.main()
