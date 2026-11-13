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

class CaptureBoundaryTests(unittest.TestCase):
    setUp = StreamBackupTests.setUp
    capture = StreamBackupTests.capture
    def test_read_only_open_of_wal_main_creates_only_empty_sidecar(self):
        from vk_native_stream_backup import generation, validate_capture_entry
        writer=sqlite3.connect(self.source);writer.execute('PRAGMA journal_mode=WAL');writer.close()
        before=generation(self.source);self.assertIsNone(before['-wal'])
        row=self.capture()
        self.assertTrue(validate_capture_entry(before,row))
        self.assertEqual(before[''],row['source_generation'][''])
        self.assertEqual(row['source_generation']['-wal'][3],0)
    def test_nonempty_or_replaced_wal_and_main_change_are_rejected(self):
        import copy
        from vk_native_stream_backup import generation,validate_capture_entry
        before=generation(self.source)
        for change in ['main','nonempty','replace']:
            original=copy.deepcopy(before);after=copy.deepcopy(before)
            after['-wal']=[1,2,33188,0,4,5,1000,1000]
            if change=='main':after[''][4]+=1
            elif change=='nonempty':after['-wal'][3]=32
            else:original['-wal']=[1,99,33188,0,4,5,1000,1000]
            with self.assertRaises(ValueError):validate_capture_entry(original,{'source_generation':after})
    def test_retained_custody_reports_prior_proof_not_fresh_decode(self):
        from vk_native_stream_backup import verify_retained_custody
        client=Objects();row=self.capture(client)
        def probe(segments):
            for segment in segments:self.assertIn(segment['sha256'],client.rows)
            return dict(prior_independent_readback_proofs_reused=True,fresh_body_decode_claimed=False,payload_bytes_read=0,new_payload_bytes_written=0)
        client.probe_accepted=probe
        result=verify_retained_custody(row,client,guard=lambda _:None)
        self.assertFalse(result['fresh_body_decode_claimed']);self.assertFalse(result['new_final_epoch_claimed'])
        with sqlite3.connect(self.source)as db:db.execute("INSERT INTO messages VALUES ('later')")
        with self.assertRaises(ValueError):verify_retained_custody(row,client,guard=lambda _:None)
    def test_missing_accepted_object_aborts_custody_reuse(self):
        from vk_native_stream_backup import verify_retained_custody
        client=Objects();row=self.capture(client)
        def absent(_):raise ValueError('missing accepted native object')
        client.probe_accepted=absent
        with self.assertRaisesRegex(ValueError,'missing accepted'):verify_retained_custody(row,client,guard=lambda _:None)
