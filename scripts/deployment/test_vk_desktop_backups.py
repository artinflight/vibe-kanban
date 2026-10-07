"""Tiny private SQLite/tar fixtures in the standard preparation test selection."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from vk_archive_store import Archive, reference, chain
from vk_change_journal import Journal
from vk_prep_common import digest
from vk_rolling_backup import capture, restore_chain, resume_delivery, verified_parent


class DesktopBackups(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ['TMPDIR']).resolve()
        if not root.is_relative_to('/mnt/vk-storage/') or not os.path.ismount('/mnt/vk-storage'):
            raise RuntimeError('Tests require mounted SSD task-local TMPDIR')
        self.tmp = tempfile.TemporaryDirectory(prefix='desktop-backup-unit-', dir=root)
        self.root = Path(self.tmp.name)
        self.cwd = Path.cwd()
        os.chdir(self.root)
        # Execute the exact remote read/hash program locally against a private B:.
        self.ssh = patch('vk_archive_store.SSH', [sys.executable, '-'])
        self.ssh.start()
        self.locators = patch.dict('vk_archive_store.LOCATORS', {}, clear=True)
        self.locators.start()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.database = self.source / 'db.sqlite'
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE data (value TEXT)')
            db.execute("INSERT INTO data VALUES ('initial')")
        (self.source / 'attachment.bin').write_bytes(b'fixture attachment')
        (self.source / 'dirty.txt').write_text('uncommitted fixture')
        self.plan = {'sources': [str(self.source)], 'sqlite_snapshots': [str(self.database)],
                     'excluded_rebuildable_directories': []}
        self.backups = self.root / 'backups'
        self.journal = Journal(self.plan)
        self.journal.tree(self.source)
        self.journal.ready = True
        self.directory = 'B:/vk-backups/test-first'

    def tearDown(self):
        self.journal.close()
        self.ssh.stop()
        self.locators.stop()
        os.chdir(self.cwd)
        self.tmp.cleanup()  # Only this exact tempfile-owned test root.

    def mirror(self, path):
        remote = Path(self.directory) / path.name
        remote.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, remote)
        return {'desktop_verified': True, 'sha256': digest(remote),
                'bytes': remote.stat().st_size, 'desktop_directory': self.directory,
                'name': path.name}

    def backup(self, parent=None, publish=None):
        return capture(self.plan, self.backups, self.journal.report, self.mirror,
                       parent, self.mirror if publish is None else publish)

    def remove_own_archive(self, result):
        path = Path(result['folder']) / result['archive']
        self.assertTrue(path.is_relative_to(self.root))
        path.unlink()

    def test_remote_only_parent_and_cross_directory_delta_restore(self):
        first = self.backup()
        self.assertFalse((Path(first['folder']) / 'verified-payload').exists())
        self.remove_own_archive(first)
        self.directory = 'B:/vk-backups/test-second'
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE data SET value='latest'")
        (self.source / 'dirty.txt').write_text('latest dirty fixture')
        second = self.backup(first)
        self.remove_own_archive(second)
        dest = self.backups / 'restore'
        result = restore_chain(second, dest, desktop_only=True)
        self.assertEqual(result['archives'], 2)
        files = dest / 'files' / str(self.source).lstrip('/')
        self.assertEqual((files / 'dirty.txt').read_text(), 'latest dirty fixture')
        self.assertEqual((files / 'attachment.bin').read_bytes(), b'fixture attachment')
        with sqlite3.connect(files / self.database.name) as db:
            self.assertEqual(db.execute('SELECT value FROM data').fetchone()[0], 'latest')
        self.assertEqual((self.source / 'dirty.txt').read_text(), 'latest dirty fixture')

    def test_low_peak_restore_retires_verified_duplicates_not_archives_or_final_databases(self):
        first = self.backup()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE data SET value='latest'")
        second = self.backup(first)
        dest = self.backups / 'low-peak-restore'
        result = restore_chain(second, dest, desktop_only=True, retire_verified_snapshots=True)
        self.assertEqual(len(result['private_snapshot_copies_retired']), 2)
        self.assertFalse(list((dest / 'snapshots').rglob('*.sqlite')))
        self.assertEqual(len(list((dest / 'verified-snapshot-retirement').glob('*.json'))), 2)
        for archive in [first, second]:
            self.assertTrue((Path(archive['folder']) / archive['archive']).exists())
        restored = dest / 'files' / str(self.database).lstrip('/')
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute('SELECT value FROM data').fetchall(), [('latest',)])
        self.assertTrue(self.database.exists())

    def test_low_peak_failure_does_not_retire_unverified_copies(self):
        first = self.backup()
        dest = self.backups / 'bad-low-peak'
        original_digest = __import__('vk_rolling_backup').digest
        def wrong(path):
            return '0' * 64 if Path(path).is_relative_to(dest) else original_digest(path)
        with patch('vk_rolling_backup.digest', side_effect=wrong):
            with self.assertRaisesRegex(ValueError, 'database hash mismatch'):
                restore_chain(first, dest, desktop_only=True, retire_verified_snapshots=True)
        self.assertEqual(len(list((dest / 'snapshots').rglob('*.sqlite'))), 1)
        self.assertFalse((dest / 'verified-snapshot-retirement').exists())

    def test_default_restore_keeps_private_snapshots(self):
        first = self.backup(); dest = self.backups / 'normal-restore'
        result = restore_chain(first, dest, desktop_only=True)
        self.assertEqual(result['private_snapshot_copies_retired'], [])
        self.assertEqual(len(list((dest / 'snapshots').rglob('*.sqlite'))), 1)

    def test_restore_free_space_floor_fails_before_stream_or_retirement(self):
        first = self.backup(); dest = self.backups / 'low-space'
        from types import SimpleNamespace
        with patch('vk_rolling_backup.os.statvfs', return_value=SimpleNamespace(f_bavail=1, f_frsize=4096)):
            with self.assertRaisesRegex(ValueError, 'free-space floor'):
                restore_chain(first, dest, desktop_only=True, retire_verified_snapshots=True)
        self.assertFalse(list(dest.iterdir()))
        self.assertTrue((Path(first['folder']) / first['archive']).exists())

    def test_missing_desktop_does_not_fall_back_to_local(self):
        first = self.backup()
        (Path(self.directory) / first['archive']).unlink()
        self.assertTrue((Path(first['folder']) / first['archive']).exists())
        with self.assertRaisesRegex(ValueError, 'Desktop backup unavailable'):
            self.backup(first)

    def test_rehearsal_consumer_downloads_only_metadata_and_streams_remote_payload(self):
        from rehearse_vk_backup_boundary import desktop_restore
        first = self.backup()
        self.remove_own_archive(first)
        root = self.root / 'rehearsal'; root.mkdir()
        real_run = __import__('subprocess').run
        copies = []
        def run(command, **kwargs):
            if command[0] != 'scp':
                return real_run(command, **kwargs)
            copies.append(command[-2])
            shutil.copyfile(Path(command[-2].removeprefix('desktop:')),
                            Path(command[-1]) / first['metadata_receipt']['name'])
        with patch('rehearse_vk_backup_boundary.subprocess.run', side_effect=run):
            descriptor, restored = desktop_restore(first, root, self.backups / 'driver-restore', low_peak=True)
        self.assertEqual(len(copies), 1)
        self.assertTrue(copies[0].endswith(first['metadata_receipt']['name']))
        self.assertEqual(restored['archives'], 1)
        self.assertEqual(len(restored['private_snapshot_copies_retired']), 1)
        self.assertEqual(descriptor['archive'], first['archive'])

    def test_rehearsal_consumer_rejects_changed_metadata_before_restore(self):
        from rehearse_vk_backup_boundary import desktop_restore
        first = self.backup()
        root = self.root / 'bad-rehearsal'; root.mkdir()
        def bad_copy(command, **kwargs):
            (Path(command[-1]) / first['metadata_receipt']['name']).write_text('{}')
        with patch('rehearse_vk_backup_boundary.subprocess.run', side_effect=bad_copy), \
                patch('rehearse_vk_backup_boundary.restore_chain') as restore:
            with self.assertRaisesRegex(ValueError, 'metadata download changed'):
                desktop_restore(first, root, root / 'restore', low_peak=True)
        restore.assert_not_called()

    def test_corrupt_desktop_blocks_capture_even_with_good_local(self):
        first = self.backup()
        remote = Path(self.directory) / first['archive']
        data = bytearray(remote.read_bytes());data[-1] ^= 1;remote.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.backup(first)

    def test_stream_hash_failure_after_read_does_not_pass(self):
        first = self.backup()
        ref = reference(first);ref['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'read/hash failed'):
            Archive(ref, desktop_only=True).manifest()

    def test_legacy_parent_locator_uses_exact_retained_descriptor(self):
        first = self.backup();self.remove_own_archive(first)
        ref = {k: reference(first)[k] for k in ('folder', 'archive', 'sha256')}
        self.assertEqual(Archive(ref, desktop_only=True).manifest()['parent'], None)
        descriptor = Path(first['folder']) / (first['archive'] + '.result.json')
        value = json.loads(descriptor.read_text());value['receipt']['sha256'] = '0' * 64
        descriptor.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            Archive(ref, desktop_only=True)

    def test_invalid_locator_and_archive_names_are_rejected(self):
        first = self.backup()
        for changes in ({'desktop_directory': 'B:/vk-backups/../secret'},
                        {'desktop_directory': "B:/vk-backups/x';write"},
                        {'archive': '../data.tar.zst'}, {'bytes': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Archive(reference(first) | changes)

    def test_direct_transport_requires_bound_identity_and_preserves_host_verification(self):
        import vk_archive_store as store
        for host, alias in [('10.0.0.109', None), (None, 'known-host'), ('bad;command', 'known')]:
            with self.assertRaises(ValueError):
                store.configure_transport(host, alias)
        with patch.object(store, 'SSH', list(store.DEFAULT_SSH)):
            store.configure_transport('10.0.0.109', '100.70.23.123')
            self.assertIn('StrictHostKeyChecking=yes', store.SSH)
            self.assertIn('HostKeyAlias=100.70.23.123', store.SSH)
            self.assertEqual(store.SSH[-3:], ['desktop', 'python', '-'])

    def test_scope_change_and_journal_loss_still_block(self):
        first = self.backup();self.remove_own_archive(first)
        self.journal.instance = 'replaced'
        with self.assertRaisesRegex(ValueError, 'journal instance'):
            self.backup(first)

    def test_failed_publish_can_resume_without_verification_copy(self):
        def fail(path):
            raise RuntimeError('injected delivery failure')
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            self.backup(publish=fail)
        folder = next((self.backups / 'checkpoint-').iterdir())
        self.assertFalse((folder / 'verified-payload').exists())
        result = resume_delivery(self.plan, self.backups, folder, self.journal.report,
                                 self.mirror, self.mirror)
        self.remove_own_archive(result)
        self.assertEqual(len(chain(result, desktop_only=True)), 1)

    def test_restore_destination_and_missing_locator_are_rejected(self):
        first = self.backup()
        with self.assertRaisesRegex(ValueError, 'task directory'):
            restore_chain(first, self.source / 'bad')
        with self.assertRaisesRegex(ValueError, 'empty'):
            restore_chain(first, self.backups)
        ref = reference(first);ref['folder'] = str(self.root / 'unknown')
        ref.pop('desktop_directory');ref.pop('bytes')
        with self.assertRaisesRegex(ValueError, 'No verified Desktop locator'):
            Archive(ref, desktop_only=True)

    def test_audit_checks_whole_chain_without_extracting(self):
        first = self.backup();self.remove_own_archive(first)
        second = self.backup(first);self.remove_own_archive(second)
        self.assertEqual(len(chain(second, desktop_only=True)), 2)
        self.assertFalse((self.backups / 'files').exists())

    def test_truncated_remote_stream_fails_without_using_local_copy(self):
        first = self.backup()
        remote = Path(self.directory) / first['archive']
        remote.write_bytes(remote.read_bytes()[:8])
        with self.assertRaises((ValueError, tarfile.ReadError)):
            Archive(reference(first), desktop_only=True).manifest()
        self.assertTrue((Path(first['folder']) / first['archive']).exists())

    def test_cycle_and_scope_mismatch_are_rejected(self):
        first = self.backup()
        manifest = json.loads((Path(first['folder']) / 'payload/manifest.json').read_text())
        cyclic = manifest | {'parent': reference(first)}
        with patch.object(Archive, 'manifest', return_value=cyclic):
            with self.assertRaisesRegex(ValueError, 'cycle'):
                chain(first)
        with patch.object(Archive, 'manifest', return_value=manifest | {'scope_sha256': 'bad'}):
            with self.assertRaisesRegex(ValueError, 'scope or plan mismatch'):
                chain(first)


if __name__ == '__main__':
    unittest.main()
