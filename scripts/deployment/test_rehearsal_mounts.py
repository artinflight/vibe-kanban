from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from rehearsal_mounts import history_mounts


class HistoryMountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'source'
        self.rel = Path('ab/session/processes')
        self.directory = self.root / self.rel
        self.directory.mkdir(parents=True)
        self.pack = self.base / 'packed'
        (self.pack / '.log-packs').mkdir(parents=True)
        self.saved = self.base / 'saved.jsonl'
        self.saved.write_text('verified original')
        (self.directory / 'current.jsonl').write_text('original loose')
        (self.pack / 'current.jsonl').write_text('verified packed')
        (self.directory / 'missing.recovered-final.json').write_text('keep recovery record')

    def mounts(self, packed=True):
        return history_mounts(self.root, '/sessions',
            {str(self.rel): self.pack} if packed else {},
            [str(self.rel / 'current.jsonl')] if packed else [],
            {str(self.rel / 'missing.jsonl'): self.saved})

    def test_preserves_neighbours_packs_and_recovery_in_same_directory(self):
        args = self.mounts()
        self.assertEqual(args.count('--tmpfs'), 1)
        self.assertEqual(args.count('--ro-bind'), 4)
        self.assertNotIn('--bind', args)
        self.assertIn(str(self.directory / 'missing.recovered-final.json'), args)
        self.assertIn(str(self.pack / 'current.jsonl'), args)
        self.assertIn(str(self.pack / '.log-packs'), args)
        self.assertIn(str(self.saved), args)
        self.assertFalse((self.directory / 'missing.jsonl').exists())

    def test_loose_overlay_preserves_existing_capture(self):
        args = self.mounts(False)
        self.assertIn(str(self.directory / 'current.jsonl'), args)
        self.assertNotIn(str(self.pack), args)

    def test_existing_destination_is_never_hidden(self):
        (self.directory / 'missing.jsonl').write_text('other owner')
        with self.assertRaises(ValueError):
            self.mounts()

    def test_symlink_member_is_rejected(self):
        (self.directory / 'missing.jsonl').symlink_to(self.saved)
        with self.assertRaises(ValueError):
            self.mounts()

    def test_escape_and_overlap_are_rejected(self):
        for relative in ['../escape.jsonl', '/ab/session/processes/missing.jsonl',
                         str(self.rel / 'current.jsonl')]:
            with self.assertRaises(ValueError):
                history_mounts(self.root, '/sessions', {str(self.rel): self.pack},
                    [str(self.rel / 'current.jsonl')], {relative: self.saved})

    def test_missing_pack_manifest_is_rejected(self):
        (self.pack / 'current.jsonl').unlink()
        with self.assertRaises(FileNotFoundError):
            self.mounts()

    def test_existing_pack_directory_is_not_hidden(self):
        (self.directory / '.log-packs').mkdir()
        with self.assertRaises(ValueError):
            self.mounts()


if __name__ == '__main__':
    unittest.main()
