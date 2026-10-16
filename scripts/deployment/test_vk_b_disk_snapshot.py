"""Fixture tests; actual physical-B acceptance is tested separately."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from vk_b_disk_snapshot import checked_mount, snapshot, fenced_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir='/mnt/vk-storage/vk-runtime-backup-20261009'))
        self.source = self.root / 'source.sqlite'
        self.writer = sqlite3.connect(self.source)
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.writer.execute('CREATE TABLE evidence(id INTEGER PRIMARY KEY, b BLOB)')
        self.writer.execute('INSERT INTO evidence VALUES(91, ?)', (b'in-WAL',))
        self.writer.commit()
        self.destination = self.root / 'destination'
        self.destination.mkdir()

    def tearDown(self):
        self.writer.close()  # Retain fixtures under the no-deletion instruction.

    def verify(self, name, checksum, size):
        target = self.destination / name
        with target.open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute('SELECT * FROM evidence').fetchall(), [(91, b'in-WAL')])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        return dict(physical_b_verified=True, sha256=actual, bytes=target.stat().st_size, integrity='ok')

    def run_snapshot(self, verifier=None, sources=None):
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.destination):
            return snapshot(self.source, self.destination,
                            {str(self.source)} if sources is None else sources,
                            destination_verifier=verifier or self.verify)

    def test_wal_ids_and_metadata_preserved(self):
        result = self.run_snapshot()
        self.assertTrue(result['backup_api_consistent_image'])
        self.assertFalse(result['whole_state_verified'])
        self.assertFalse(result['writer_fenced'])
        self.assertEqual(result['local_snapshot_payload_bytes'], 0)
        self.assertEqual(result['source_metadata_before']['uid'], self.source.stat().st_uid)

    def test_failed_remote_proof_retains_only_unaccepted_payload(self):
        with self.assertRaises(ValueError):
            self.run_snapshot(lambda *a: {})
        self.assertEqual(len(list(self.destination.glob('*.sqlite'))), 1)
        self.assertFalse(list(self.destination.glob('*.receipt.json')))

    def test_missing_scope_creates_no_output(self):
        with self.assertRaises(ValueError):
            self.run_snapshot(sources=set())
        self.assertFalse(list(self.destination.iterdir()))

    def test_symlink_source_rejected(self):
        alias = self.root / 'alias.sqlite'
        alias.symlink_to(self.source)
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.destination):
            with self.assertRaises(ValueError):
                snapshot(alias, self.destination, {str(alias)}, destination_verifier=self.verify)

    def test_existing_output_retained(self):
        target = self.destination / 'sqlite-consistent-fixed.sqlite'
        target.write_bytes(b'survivor')
        with patch('vk_b_disk_snapshot.uuid.uuid4', return_value=SimpleNamespace(hex='fixed')):
            with self.assertRaises(FileExistsError):
                self.run_snapshot()
        self.assertEqual(target.read_bytes(), b'survivor')

    def test_non_b_mount_and_other_identity_rejected(self):
        for kind, source in [('ext4', '/dev/sdb1'), ('fuse.sshfs', 'other:/B:/vk-backups')]:
            row = {'target': str(self.destination), 'fstype': kind, 'source': source}
            with patch('vk_b_disk_snapshot.subprocess.check_output', return_value=json.dumps({'filesystems': [row]}).encode()):
                with self.assertRaises(ValueError):
                    checked_mount(self.destination)

    def fence(self):
        return {'verified': True, 'all_writers_stopped_verified': True,
                'capture_id': 'fixture', 'scope': 'fixture', 'lease': 'fixture'}

    def immutable_verify(self, name, checksum, size):
        target = self.destination / name
        with target.open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        with sqlite3.connect(target.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
            self.assertEqual(db.execute('SELECT * FROM evidence').fetchall(), [(91, b'in-WAL')])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        return dict(physical_b_verified=True, sha256=actual, bytes=size,
                    integrity='ok', private_immutable_read=True)

    def test_fenced_raw_image_matches_stopped_source_without_RAM_image(self):
        self.writer.close()
        with self.source.open('rb') as f:
            expected = hashlib.file_digest(f, 'sha256').hexdigest()
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.destination):
            result = fenced_snapshot(self.source, self.destination, {str(self.source)},
                    verify_fence=self.fence, destination_verifier=self.immutable_verify)
        self.assertEqual(result['sha256'], expected)
        self.assertTrue(result['writer_fenced'])
        self.assertFalse(result['backup_api_consistent_image'])
        self.assertFalse(result['whole_state_verified'])

    def test_fenced_copy_rejects_unverified_writers_before_output(self):
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.destination):
            with self.assertRaisesRegex(ValueError, 'Actual stopped writers'):
                fenced_snapshot(self.source, self.destination, {str(self.source)},
                    verify_fence=lambda: {'verified': True}, destination_verifier=self.immutable_verify)
        self.assertFalse(list(self.destination.iterdir()))

    def test_fenced_copy_rejects_remaining_WAL_sidecars(self):
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.destination):
            with self.assertRaisesRegex(ValueError, 'sidecars'):
                fenced_snapshot(self.source, self.destination, {str(self.source)},
                    verify_fence=self.fence, destination_verifier=self.immutable_verify)
        self.assertFalse(list(self.destination.iterdir()))


if __name__ == '__main__':
    unittest.main()
