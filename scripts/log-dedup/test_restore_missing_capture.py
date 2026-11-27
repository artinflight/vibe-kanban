from pathlib import Path
import fcntl
import hashlib
import tempfile
import unittest
import uuid

from restore_missing_capture import restore_missing


class MissingCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'sessions'
        sid = str(uuid.uuid4())
        self.rel = f'{sid[:2]}/{sid}/processes/{uuid.uuid4()}.jsonl'
        self.dest = self.root / self.rel
        self.dest.parent.mkdir(parents=True)
        self.source = self.base / 'original'
        self.body = b'exact incomplete original\n'
        self.source.write_bytes(self.body)
        self.source.chmod(0o600)
        self.digest = hashlib.sha256(self.body).hexdigest()
        self.record = self.dest.with_suffix('.recovered-final.json')
        self.record.write_bytes(b'preserve recovery evidence')
        self.guard = lambda: None

    def restore(self):
        return restore_missing(self.root, self.rel, self.source, self.digest,
                               len(self.body), self.guard)

    def test_exact_restore_preserves_evidence_and_lock_inode(self):
        self.assertTrue(self.restore()['restored'])
        self.assertEqual(self.dest.read_bytes(), self.body)
        self.assertEqual(self.dest.stat().st_nlink, 1)
        self.assertEqual(self.record.read_bytes(), b'preserve recovery evidence')
        self.assertFalse(self.dest.with_suffix('.capture.json').exists())
        self.assertTrue(self.dest.with_suffix('.mutation.lock').is_file())
        self.assertFalse(list(self.dest.parent.glob('.*.restore-*')))

    def test_existing_file_or_symlink_never_overwritten(self):
        self.dest.write_bytes(b'other owner')
        with self.assertRaises(FileExistsError): self.restore()
        self.assertEqual(self.dest.read_bytes(), b'other owner')
        self.dest.unlink()
        self.dest.symlink_to(self.source)
        with self.assertRaises(FileExistsError): self.restore()
        self.assertTrue(self.dest.is_symlink())

    def test_corrupt_source_never_published(self):
        self.digest = '0' * 64
        with self.assertRaises(ValueError): self.restore()
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.dest.parent.glob('.*.restore-*')))

    def test_group_writable_source_refused_before_payload_creation(self):
        self.source.chmod(0o664)
        with self.assertRaises(ValueError): self.restore()
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.dest.parent.glob('.*.restore-*')))
        self.assertEqual(self.source.read_bytes(), self.body)

    def test_active_writer_excludes_restoration(self):
        with self.dest.with_suffix('.mutation.lock').open('w') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.restore()
        self.assertFalse(self.dest.exists())

    def test_owner_loss_before_publication_preserves_absence(self):
        calls = []
        def guard():
            calls.append(1)
            if len(calls) == 3: raise ValueError('Owner changed')
        self.guard = guard
        with self.assertRaises(ValueError): self.restore()
        self.assertFalse(self.dest.exists())

    def test_competing_publication_preserved(self):
        calls = []
        def guard():
            calls.append(1)
            if len(calls) == 3: self.dest.write_bytes(b'new owner')
        self.guard = guard
        with self.assertRaises(FileExistsError): self.restore()
        self.assertEqual(self.dest.read_bytes(), b'new owner')

    def test_parent_symlink_or_source_symlink_refused(self):
        original = self.source.with_suffix('.real')
        self.source.rename(original)
        self.source.symlink_to(original)
        with self.assertRaises(OSError): self.restore()
        self.assertFalse(self.dest.exists())
        self.source.unlink()
        original.rename(self.source)
        moved = self.dest.parent.with_name('real-processes')
        self.dest.parent.rename(moved)
        self.dest.parent.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(OSError): self.restore()


if __name__ == '__main__':
    unittest.main()
