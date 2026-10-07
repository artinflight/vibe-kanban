"""Private fixture coverage for non-destructive real-chain evidence collection."""
import json
from pathlib import Path
import unittest
import subprocess
from unittest.mock import patch

import test_vk_desktop_backups as fixtures
from vk_archive_migration import audit_archive, validate_heads, reuse_audit


class MigrationAudit(unittest.TestCase):
    setUp = fixtures.DesktopBackups.setUp
    tearDown = fixtures.DesktopBackups.tearDown
    mirror = fixtures.DesktopBackups.mirror
    backup = fixtures.DesktopBackups.backup

    def row(self, result):
        return {'local': str(Path(result['folder']) / result['archive']),
                'receipt': str(Path(result['folder']) / 'result.json'),
                'remote': self.directory + '/' + result['archive'],
                'sha256': result['receipt']['sha256'], 'bytes': result['receipt']['bytes']}

    def test_audit_preserves_original_and_retires_only_verified_private_database(self):
        first = self.backup()
        root = self.root / 'audit'; root.mkdir()
        row = self.row(first)
        result = audit_archive(row, root)
        self.assertTrue(Path(row['local']).is_file())
        self.assertTrue(Path(row['remote']).is_file())
        self.assertEqual(result['restored_sqlite_count'], 1)
        self.assertTrue(result['full_remote_stream_hash_verified'])
        self.assertFalse(result['all_non_database_payloads_materialized'])
        for snapshot in result['snapshots'].values():
            self.assertFalse(Path(snapshot['path']).exists())
        heads = [{'descriptor': row['receipt'], 'chain': [row['local']]}]
        self.assertTrue(validate_heads(heads, {row['local']: result})[0]['passed'])
        result['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'head receipt checksum'):
            validate_heads(heads, {row['local']: result})

    def test_wrong_locator_fails_before_scratch_or_deletion(self):
        first = self.backup()
        row = self.row(first); row['remote'] = 'B:/vk-backups/guessed/wrong.tar.zst'
        root = self.root / 'audit'; root.mkdir()
        with self.assertRaisesRegex(ValueError, 'locator'):
            audit_archive(row, root)
        self.assertEqual(list(root.iterdir()), [])
        self.assertTrue(Path(row['local']).is_file())

    def test_legacy_wal_sidecar_is_inventoried_not_used_as_database(self):
        first = self.backup()
        folder = Path(first['folder'])
        database = next((folder / 'payload/sqlite').glob('*.sqlite'))
        database.with_name(database.name + '-wal').touch()
        archive = folder / first['archive']
        subprocess.run(['tar', '--use-compress-program=zstd -T2 -3', '-cf', str(archive),
                        '-C', str(folder), 'payload'], check=True)
        first['receipt'] = self.mirror(archive)
        for name in ['result.json', first['archive'] + '.result.json']:
            (folder / name).write_text(json.dumps(first))
        root = self.root / 'audit'; root.mkdir()
        result = audit_archive(self.row(first), root)
        self.assertEqual(result['restored_sqlite_count'], 1)
        self.assertEqual(len(result['legacy_sidecars']), 1)
        self.assertTrue(archive.exists())

    def test_failed_database_check_retains_private_evidence_and_originals(self):
        first = self.backup()
        row = self.row(first)
        root = self.root / 'audit'; root.mkdir()
        with patch('vk_archive_migration.sqlite3.connect', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                audit_archive(row, root)
        self.assertEqual(len(list(root.rglob('*.sqlite'))), 1)
        self.assertFalse(list(root.rglob('private-copy-retirement.json')))
        self.assertTrue(Path(row['local']).exists())

    def test_free_space_floor_blocks_without_removing_archive(self):
        first = self.backup()
        row = self.row(first)
        root = self.root / 'audit'; root.mkdir()
        with patch('vk_archive_migration.reserve', side_effect=ValueError('space floor')):
            with self.assertRaisesRegex(ValueError, 'space floor'):
                audit_archive(row, root)
        self.assertTrue(Path(row['local']).exists())

    def test_reuse_rechecks_desktop_and_rejects_changed_archive_or_inventory(self):
        first = self.backup(); row = self.row(first)
        root = self.root / 'audit'; root.mkdir()
        result = audit_archive(row, root)
        prior = root / first['archive'].removesuffix('.tar.zst')
        resumed = self.root / 'resumed'; resumed.mkdir()
        self.assertTrue(reuse_audit(row, prior, resumed)['passed'])
        remote = Path(row['remote'])
        remote.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Desktop backup unavailable'):
            reuse_audit(row, prior, self.root / 'bad')
        with (prior / 'members.jsonl.gz').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'no longer matches'):
            reuse_audit(row, prior, self.root / 'bad')
