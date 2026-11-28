"""Real RAM SQLite source tests; B acceptance references here are fixtures only."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import time
import unittest

from vk_restart_sql_reuse import attributes, fingerprint, qualify_closed_source


class SQLReuse(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-sql-reuse-test-', dir='/dev/shm')
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.sqlite'
        with sqlite3.connect(self.source) as database:
            database.execute('create table value(content text)')
            database.execute('insert into value values(?)', ('a' * 256,))
        info = self.source.stat()
        metadata = {'device': info.st_dev, 'inode': info.st_ino, 'uid': info.st_uid,
                    'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
                    'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns,
                    'xattrs': attributes(self.source)}
        image = self.root / 'api.sqlite'
        with sqlite3.connect(self.source.as_uri() + '?mode=ro', uri=True) as src:
            with sqlite3.connect(image) as dst:
                src.backup(dst)
        with sqlite3.connect(image.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
            self.assertEqual(db.execute('pragma integrity_check').fetchall(), [('ok',)])
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        member = {'kind': 'file', 'bytes': image.stat().st_size, 'sha256': digest,
                  **{key: metadata[key] for key in ('uid', 'gid', 'mode', 'mtime_ns', 'xattrs')}}
        self.point = {'source': str(self.source), 'status': 'consistent_SQL_point_verified',
                      'method': 'SQLite-backup-API', 'source_API_point_qualifies_later_epoch_not_original': True,
                      'source_changed_online': False, 'original_source_API_point_at': time.time(),
                      'source_metadata_before': metadata, 'source_metadata_after': copy.deepcopy(metadata),
                      'source_identity_before': fingerprint(info), 'member': member,
                      'bytes': member['bytes'], 'sha256': digest,
                      'independent': {'integrity': 'ok', 'bytes': member['bytes'], 'sha256': digest},
                      'B_acceptance_object': {'sha256': 'a' * 64}}

    def tearDown(self):
        self.temp.cleanup()

    def qualify(self, mandatory=(), guard=lambda: None):
        return qualify_closed_source(self.source, self.point, mandatory_sources=mandatory, guard=guard)

    def test_exact_closed_source_keeps_original_epoch(self):
        original = copy.deepcopy(self.point)
        result = self.qualify()
        self.assertTrue(result['eligible_unchanged_SQL_reuse'])
        self.assertEqual(result['accepted_API_point_at'], self.point['original_source_API_point_at'])
        self.assertFalse(result['new_API_epoch_claimed'])
        self.assertFalse(result['backup_acceptance_claimed'])
        self.assertEqual(self.point, original)

    def test_even_empty_sidecars_force_fresh_API(self):
        for suffix in ('-wal', '-shm', '-journal'):
            with self.subTest(suffix=suffix):
                path = Path(str(self.source) + suffix)
                path.touch()
                self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])
                path.unlink()

    def test_mandatory_alias_or_isolated_source_cannot_reuse(self):
        self.assertFalse(self.qualify([str(self.source)])['eligible_unchanged_SQL_reuse'])

    def test_same_size_committed_SQL_change_is_not_unchanged(self):
        size = self.source.stat().st_size
        # tmpfs can stamp two writes in the same kernel clock tick. This case
        # tests the metadata guard; kernel-history refusal has separate coverage.
        time.sleep(0.02)
        with sqlite3.connect(self.source) as database:
            database.execute('update value set content=?', ('b' * 256,))
        self.assertEqual(self.source.stat().st_size, size)
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_restoring_mtime_does_not_hide_change(self):
        info = self.source.stat()
        time.sleep(0.02)
        with sqlite3.connect(self.source) as database:
            database.execute('update value set content=?', ('c' * 256,))
        os.utime(self.source, ns=(info.st_atime_ns, info.st_mtime_ns))
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_equal_bytes_in_replaced_inode_are_not_reusable(self):
        replacement = self.root / 'replacement.sqlite'
        shutil.copy2(self.source, replacement)
        os.replace(replacement, self.source)
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_online_changed_API_point_does_not_qualify(self):
        self.point['source_changed_online'] = True
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_sidecar_created_during_guard_is_not_missed(self):
        calls = 0
        def guard():
            nonlocal calls
            calls += 1
            if calls == 2:
                Path(str(self.source) + '-wal').touch()
        self.assertFalse(self.qualify(guard=guard)['eligible_unchanged_SQL_reuse'])

    def test_broken_independent_API_proof_cannot_qualify(self):
        self.point['independent']['sha256'] = '0' * 64
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])


if __name__ == '__main__':
    unittest.main()
