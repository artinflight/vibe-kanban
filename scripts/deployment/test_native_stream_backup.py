import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vk_native_stream_backup import capture_sqlite, verify_unchanged


class Objects:
    def __init__(self, corrupt=False):
        self.rows = {}
        self.corrupt = corrupt
    def ensure(self, raw, *, readback_sink):
        sha = hashlib.sha256(raw).hexdigest()
        self.rows[sha] = raw
        readback_sink.write(b'bad' if self.corrupt else raw)
        return dict(sha256=sha, bytes=len(raw))
    def verify(self, segment, sink):
        sink.write(self.rows[segment['sha256']])


class StreamBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'source.sqlite'
        with sqlite3.connect(self.source) as db:
            db.execute('CREATE TABLE messages(value TEXT)')
            db.execute('INSERT INTO messages VALUES (?)', ('preserve history',))
    def capture(self, client=None, **options):
        return capture_sqlite(self.source, client or Objects(), maximum_image_bytes=options.pop('maximum_image_bytes', 1024**2),
                              chunk_bytes=4096, guard=lambda _: None, **options)
    def test_real_sqlite_roundtrip_and_later_write_invalidates_reuse(self):
        client = Objects()
        row = self.capture(client)
        self.assertEqual(row['disk_payload_bytes_written'], 0)
        self.assertTrue(verify_unchanged(row, client, guard=lambda _: None)['unchanged_image_reverified'])
        self.assertEqual(sorted(p.name for p in self.source.parent.iterdir()), ['source.sqlite'])
        with sqlite3.connect(self.source) as db:
            db.execute('INSERT INTO messages VALUES (?)', ('newer message',))
        with self.assertRaises(ValueError):verify_unchanged(row, client, guard=lambda _: None)
    def test_wal_snapshot_reopens_with_committed_history(self):
        writer = sqlite3.connect(self.source)
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('INSERT INTO messages VALUES (?)', ('committed WAL message',))
        writer.commit()
        client = Objects(); row = self.capture(client)
        restored = sqlite3.connect(':memory:')
        self.addCleanup(restored.close)
        restored.deserialize(b''.join(client.rows[s['sha256']] for s in row['segments']))
        self.assertEqual(restored.execute('SELECT COUNT(*) FROM messages').fetchone()[0], 2)
    def test_write_during_capture_is_rejected(self):
        writer = sqlite3.connect(self.source)
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=WAL')
        changed = False
        def progress(**_):
            nonlocal changed
            if not changed:
                writer.execute('INSERT INTO messages VALUES (?)', ('concurrent write',))
                writer.commit();changed = True
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            self.capture(progress=progress)
    def test_corrupt_independent_readback_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'restore differs'):
            self.capture(Objects(corrupt=True))
    def test_image_limit_prevents_snapshot_allocation(self):
        with self.assertRaisesRegex(ValueError, 'memory bound'):
            self.capture(maximum_image_bytes=1)
    def test_replaced_source_rejects_old_point_even_with_same_bytes(self):
        client = Objects(); row = self.capture(client)
        replacement = self.source.with_suffix('.replacement')
        replacement.write_bytes(self.source.read_bytes());replacement.replace(self.source)
        with self.assertRaises(ValueError):verify_unchanged(row, client, guard=lambda _: None)


if __name__ == '__main__':unittest.main()
