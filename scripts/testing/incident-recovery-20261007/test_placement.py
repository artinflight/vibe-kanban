import os
from pathlib import Path
import tempfile
import unittest
from place_missing import move_no_replace, copy_admin_no_replace


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='placement-test-', dir=Path(__file__).parent))

    def test_existing_file_retained(self):
        a, b = self.root / 'a', self.root / 'b'
        a.write_text('backup')
        b.write_text('new work')
        self.assertFalse(move_no_replace(a, b))
        self.assertEqual(b.read_text(), 'new work')
        self.assertEqual(a.read_text(), 'backup')

    def test_new_directory_moved_atomically(self):
        a, b = self.root / 'a', self.root / 'b'
        a.mkdir()
        (a / 'edit').write_text('uncommitted')
        self.assertTrue(move_no_replace(a, b))
        self.assertFalse(a.exists())
        self.assertEqual((b / 'edit').read_text(), 'uncommitted')

    def test_existing_empty_directory_not_replaced(self):
        a, b = self.root / 'a', self.root / 'b'
        a.mkdir()
        b.mkdir()
        (a / 'edit').write_text('backup')
        self.assertFalse(move_no_replace(a, b))
        self.assertFalse((b / 'edit').exists())

    def test_symlink_parent_rejected(self):
        source = self.root / 'source'
        source.write_text('backup')
        actual = self.root / 'actual'
        actual.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(actual)
        with self.assertRaises(OSError):
            move_no_replace(source, alias / 'destination')
        self.assertTrue(source.exists())
        self.assertFalse((actual / 'destination').exists())

    def test_existing_symlink_not_replaced(self):
        source, target = self.root / 'source', self.root / 'target'
        source.write_text('backup')
        target.symlink_to('/does-not-exist')
        self.assertFalse(move_no_replace(source, target))
        self.assertEqual(os.readlink(target), '/does-not-exist')

    def test_registration_copy_preserves_both_source_and_newer_collision(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'HEAD').write_text('ref: refs/heads/example')
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        # fd confines all actual writes to this synthetic SSD test directory.
        logical = Path('/home/mcp/synthetic/.git/worktrees/registration')
        try:
            self.assertTrue(copy_admin_no_replace(source, logical, fd))
            dest = self.root / 'registration/HEAD'
            self.assertEqual(dest.read_text(), (source / 'HEAD').read_text())
            dest.write_text('newer registration')
            self.assertFalse(copy_admin_no_replace(source, logical, fd))
            self.assertEqual(dest.read_text(), 'newer registration')
            self.assertTrue((source / 'HEAD').exists())
        finally:
            os.close(fd)

    def test_registration_single_file(self):
        source = self.root / 'source'
        source.write_text('ref: refs/heads/example')
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        logical = Path('/home/mcp/synthetic/.git/worktrees/registration/HEAD')
        try:
            self.assertTrue(copy_admin_no_replace(source, logical, fd))
            self.assertEqual((self.root / 'HEAD').read_text(), source.read_text())
        finally:
            os.close(fd)


if __name__ == '__main__':
    unittest.main()
