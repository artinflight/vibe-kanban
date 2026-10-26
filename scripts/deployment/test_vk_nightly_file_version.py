import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest

from vk_nightly_file_version import capture_version


class StableVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightly-one-version-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'history.jsonl'; self.path.write_bytes(b'complete history\n'*8192)
        self.limit = self.path.stat().st_size
        self.body = self.path.read_bytes()

    def capture(self, sink=None, **kw):
        return capture_version(self.path, sink or io.BytesIO(), maximum_bytes=self.limit, guard=lambda: None, **kw)

    def test_exact_bytes_and_Linux_metadata_have_explicit_later_epoch(self):
        sink = io.BytesIO(); row = self.capture(sink)
        self.assertEqual(sink.getvalue(), self.body)
        self.assertEqual(row['sha256'], hashlib.sha256(self.body).hexdigest())
        self.assertEqual(row['metadata']['mode'], self.path.stat().st_mode & 0o7777)
        self.assertTrue(row['later_epoch_supplement']); self.assertFalse(row['original_failed_epoch_repaired'])

    def test_growth_after_first_chunk_never_returns_a_seal(self):
        path = self.path
        class Growing(io.BytesIO):
            def write(self, value):
                result = super().write(value)
                with path.open('ab') as f: f.write(b'new live event\n')
                return result
        sink = Growing()
        with self.assertRaises(ValueError): self.capture(sink)
        self.assertGreater(len(sink.getvalue()), 0)
        self.assertTrue(self.path.exists())

    def test_same_size_mtime_rewrite_is_rejected_by_ctime(self):
        path = self.path; before = path.stat()
        class Rewrite(io.BytesIO):
            def write(self, value):
                result = super().write(value)
                with path.open('r+b') as f: f.write(b'new')
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                return result
        with self.assertRaises(ValueError): self.capture(Rewrite())

    def test_replaced_source_and_symlink_are_rejected(self):
        path = self.path
        class Replace(io.BytesIO):
            def write(self, value):
                result = super().write(value)
                other = path.with_suffix('.new'); other.write_bytes(b'new'); os.replace(other, path)
                return result
        with self.assertRaises(ValueError): self.capture(Replace())
        link = self.path.with_suffix('.link'); link.symlink_to(self.path)
        with self.assertRaises(ValueError): capture_version(link, io.BytesIO(), maximum_bytes=100, guard=lambda: None)

    def test_SQLite_wrong_budget_and_zero_write_are_rejected(self):
        with self.assertRaises(ValueError): capture_version(self.path, io.BytesIO(), maximum_bytes=1, guard=lambda: None)
        class Blocked(io.BytesIO):
            def write(self, value): return 0
        with self.assertRaises(OSError): self.capture(Blocked())
        self.path.write_bytes(b'SQLite format 3\0')
        with self.assertRaises(ValueError): self.capture()

    def test_partial_sink_writes_are_completed(self):
        class Partial(io.BytesIO):
            def write(self, value): return super().write(value[:7])
        sink = Partial(); self.capture(sink); self.assertEqual(sink.getvalue(), self.body)

    def test_guard_failure_preserves_source_and_does_not_retry(self):
        count = 0
        def guard():
            nonlocal count
            count += 1
            if count == 2: raise PermissionError('owned STOP/access refusal')
        with self.assertRaises(PermissionError): capture_version(self.path, io.BytesIO(), maximum_bytes=self.limit, guard=guard)
        self.assertEqual(self.path.read_bytes(), self.body)
        self.assertEqual(count, 2)

    def test_native_compatible_hash_uses_only_bounded_reads(self):
        from vk_nightly_file_version import stream_hash
        class Bounded(io.BytesIO):
            def read(self, count=-1):
                if not 0 < count <= 65536: raise AssertionError('unbounded native hash read')
                return super().read(count)
        self.assertEqual(stream_hash(Bounded(self.body)), hashlib.sha256(self.body).hexdigest())


if __name__ == '__main__': unittest.main()
