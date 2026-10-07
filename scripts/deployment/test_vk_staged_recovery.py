import json
from pathlib import Path
import unittest

import test_vk_desktop_backups as fixtures
from vk_archive_store import Archive, chain, reference
from vk_staged_recovery import staged_restore


class StagedRecovery(unittest.TestCase):
    setUp = fixtures.DesktopBackups.setUp
    tearDown = fixtures.DesktopBackups.tearDown
    mirror = fixtures.DesktopBackups.mirror
    backup = fixtures.DesktopBackups.backup
    remove_own_archive = fixtures.DesktopBackups.remove_own_archive

    def records(self, result):
        return {a.key: {'sha256': a.sha256, 'manifest': a.manifest(), 'verified_remote': a.verify()}
                for a in chain(result, desktop_only=True)}

    def test_latest_database_and_file_restore_with_local_archives_absent(self):
        first = self.backup()
        (self.source / 'dirty.txt').write_text('latest')
        second = self.backup(first)
        self.remove_own_archive(first); self.remove_own_archive(second)
        selected = {str(self.source / 'dirty.txt').lstrip('/')}
        proof = staged_restore(second, self.backups / 'staged', self.records(second), selected)
        self.assertTrue(proof['all_required_databases_restored'])
        self.assertEqual(proof['required_database_count'], 1)
        self.assertEqual(len(proof['streamed_archives']), 2)
        self.assertEqual(len(proof['regular_files_verified']), 1)
        self.assertFalse((self.backups / 'staged/files' / str(self.source / 'attachment.bin').lstrip('/')).exists())

    def test_deleted_selected_file_does_not_reappear(self):
        first = self.backup(); selected = str(self.source / 'dirty.txt').lstrip('/')
        (self.source / 'dirty.txt').unlink()
        second = self.backup(first)
        proof = staged_restore(second, self.backups / 'deleted', self.records(second), {selected})
        self.assertNotIn(selected, proof['regular_files_verified'])

    def test_changed_cached_manifest_fails_even_with_valid_archive(self):
        first = self.backup(); records = self.records(first)
        records[next(iter(records))]['manifest']['absent_paths'].append('/forged')
        with self.assertRaisesRegex(ValueError, 'Cached manifest differs'):
            staged_restore(first, self.backups / 'forged', records, set())

    def test_missing_remote_verification_rejected(self):
        first = self.backup(); records = self.records(first)
        records[next(iter(records))]['verified_remote']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'fresh exact Desktop verification'):
            staged_restore(first, self.backups / 'unverified', records, set())

    def test_missing_required_database_is_not_a_partial_pass(self):
        first = self.backup(); records = self.records(first)
        first['databases'].append('/missing-required.sqlite')
        with self.assertRaisesRegex(ValueError, 'Missing required database'):
            staged_restore(first, self.backups / 'missing-database', records, set())
