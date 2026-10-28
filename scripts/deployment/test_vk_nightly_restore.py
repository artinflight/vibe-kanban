import base64
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zlib

from vk_nightly_restore import restore_generation
from vk_nightly_generation import CHUNKED, NightlyStore
from nightly_test_support import fixture_readback


class IndependentRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'generation'
        (self.folder / 'objects').mkdir(parents=True)
        self.entries = {}

    def row(self, **extra):
        return dict(mode=0o600, uid=os.getuid(), gid=os.getgid(), mtime_ns=1234567890123456789,
                    xattrs={}, **extra)

    def payload(self, key, data, **extra):
        h = hashlib.sha256(data).hexdigest()
        (self.folder / 'objects' / h).write_bytes(zlib.compress(data, 1))
        self.entries[key] = self.row(kind='file', sha256=h, bytes=len(data))
        self.entries[key].update(extra)
        return h

    def manifest(self):
        return dict(entries=self.entries, object_encoding='zlib-1-v1')

    def test_independent_sqlite_content_links_and_recorded_metadata(self):
        source = self.root / 'fixture.sqlite'
        with sqlite3.connect(source) as db:
            db.execute('create table proof(value)')
            db.execute("insert into proof values ('restored')")
        h = self.payload('selected/state.sqlite', source.read_bytes(), mode=0o440,
                         xattrs={'user.restore-test': base64.b64encode(b'proof').decode()})
        self.entries['selected'] = self.row(kind='directory')
        self.entries['selected']['mode'] = 0o750
        self.entries['selected/alias'] = dict(self.entries['selected/state.sqlite'], kind='hardlink',
                                            target='selected/state.sqlite')
        self.entries['literal'] = self.row(kind='symlink', target='../../never-follow')
        self.entries['literal']['mode'] = 0o777
        manifest = self.manifest()
        manifest['capture_context'] = {'restart_capture': {'databases': {'/live/state.sqlite': {
            'key': 'selected/state.sqlite', 'sha256': h, 'bytes': source.stat().st_size}}}}
        events = []
        result = restore_generation(self.folder, manifest, self.root / 'restore', checkpoint=events.append)
        self.assertTrue(result['independent_restore_verified'])
        self.assertEqual(result['sqlite_integrity_checks'], 1)
        restored = self.root / 'restore/selected/state.sqlite'
        self.assertNotEqual(restored.stat().st_ino, (self.folder / 'objects' / h).stat().st_ino)
        self.assertEqual(restored.stat().st_ino, (self.root / 'restore/selected/alias').stat().st_ino)
        self.assertEqual(events[-1]['phase'], 'complete')

    def test_corrupt_object_preserves_partial_and_refuses_reuse(self):
        h = self.payload('file', b'correct')
        (self.folder / 'objects' / h).write_bytes(zlib.compress(b'wrong', 1))
        destination = self.root / 'restore'
        with self.assertRaises(ValueError):
            restore_generation(self.folder, self.manifest(), destination)
        self.assertTrue((destination / 'file').exists())
        with self.assertRaises(FileExistsError):
            restore_generation(self.folder, self.manifest(), destination)

    def test_rejects_archived_link_ancestor_before_destination_creation(self):
        self.payload('link/escape', b'data')
        self.entries['link'] = self.row(kind='symlink', target='/tmp')
        with self.assertRaises(ValueError):
            restore_generation(self.folder, self.manifest(), self.root / 'restore')
        self.assertFalse((self.root / 'restore').exists())

    def test_independent_readback_detects_destination_change(self):
        self.payload('file', b'correct')
        def mutate(value):
            if value['phase'] == 'materialize':
                (self.root / 'restore/file').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'restored content'):
            restore_generation(self.folder, self.manifest(), self.root / 'restore', checkpoint=mutate)

    def test_reports_real_ownership_denial_without_escalation(self):
        self.payload('file', b'correct', uid=12345)
        events = []
        with patch('vk_nightly_restore.os.chown', side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(PermissionError, 'uid=12345'):
                restore_generation(self.folder, self.manifest(), self.root / 'restore', checkpoint=events.append)
        self.assertEqual((self.root / 'restore/file').read_bytes(), b'correct')
        self.assertEqual(events[-1]['phase'], 'independent_content_verified')
        self.assertFalse(events[-1]['recorded_metadata_verified'])

    def test_real_chunked_generation_restores_without_source_alias(self):
        data = b'exact history\\n' * 80000
        row = self.row(kind='file', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        store = NightlyStore(self.folder, 'a' * 64, lambda: self.root,
                            independent_readback=fixture_readback, object_encoding=CHUNKED)
        # The fixture store was created in setUp; enroll only the empty layout
        # expected by the production class, never a user backup directory.
        (self.folder / 'objects').rmdir()
        store.enroll_empty()
        store.advance([('history', row, io.BytesIO(data))], (), expected_previous=None,
                      reserve_bytes=4 * 1024**2, retention_adopted=False)
        manifest = store.current()
        result = restore_generation(self.folder / manifest['generation'], manifest, self.root / 'restore')
        self.assertTrue(result['passed'])
        self.assertEqual((self.root / 'restore/history').read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
