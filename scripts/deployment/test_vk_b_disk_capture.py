import hashlib
import sqlite3
import unittest
from unittest.mock import patch

import vk_b_disk_capture
import vk_rolling_backup
from test_vk_candidate_direct_b import ContractTests
from vk_change_journal import Journal


class DiskCaptureTests(ContractTests):
    def run_extended(self, factory, disk_inventory=False):
        plan = {'sources': [str(self.inc)], 'sqlite_snapshots': [str(self.db)],
                'excluded_rebuildable_directories': []}
        journal = Journal(plan)
        journal.tree(self.inc)
        journal.ready = True
        self.journals.append(journal)
        with patch.object(vk_b_disk_capture, 'Archive', self.factory), patch.object(vk_rolling_backup, 'Archive', self.factory):
            return vk_b_disk_capture.capture(plan, self.root / 'disk-extension', journal.report,
                    self.mirror, publish=self.mirror, max_snapshot_bytes=1, disk_snapshot=factory,
                    disk_inventory_root=self.store if disk_inventory else None)

    def test_extension_streams_verified_disk_image(self):
        target = self.store / 'sqlite-consistent-fixture.sqlite'
        with sqlite3.connect(self.db) as source, sqlite3.connect(target) as sink:
            source.backup(sink)
        with target.open('rb') as f:
            h = hashlib.file_digest(f, 'sha256').hexdigest()
        row = dict(source=str(self.db), backup_api_consistent_image=True,
                   online_preparation_only=True, writer_fenced=False, snapshot=target.name, mount_root=str(self.store), sha256=h,
                   bytes=target.stat().st_size, physical_b_verified=True,
                   integrity='ok', local_snapshot_payload_bytes=0)
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.store):
            result = self.run_extended(lambda raw: row)
        self.assertTrue(result['passed'])
        self.assertEqual(result['largest_serialized_snapshot_bytes'], 0)
        self.assertFalse(result['frozen_boundary_verified'])
        self.assertEqual(result['sqlite_snapshots'][str(self.db)]['sha256'], h)

    def test_extension_rejects_unverified_disk_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'unverified evidence'):
            self.run_extended(lambda raw: {'physical_b_verified': False})

    def test_extension_rejects_corrupt_disk_snapshot(self):
        target = self.store / 'sqlite-consistent-corrupt.sqlite'
        target.write_bytes(b'corrupt')
        row = dict(source=str(self.db), backup_api_consistent_image=True,
                   online_preparation_only=True, writer_fenced=False, snapshot=target.name, mount_root=str(self.store), sha256='0'*64,
                   bytes=7, physical_b_verified=True, integrity='ok', local_snapshot_payload_bytes=0)
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.store):
            with self.assertRaisesRegex(ValueError, 'changed before archiving'):
                self.run_extended(lambda raw: row)

    def test_path_inventory_is_bound_in_disk_store_without_local_list(self):
        for index in range(400):
            (self.inc / ('long-inventory-' + 'x' * 170 + str(index))).touch(exist_ok=False)
        target = self.store / 'sqlite-consistent-inventory.sqlite'
        with sqlite3.connect(self.db) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        with target.open('rb') as f:
            h = hashlib.file_digest(f, 'sha256').hexdigest()
        row = dict(source=str(self.db), backup_api_consistent_image=True,
                   online_preparation_only=True, writer_fenced=False,
                   snapshot=target.name, mount_root=str(self.store), sha256=h,
                   bytes=target.stat().st_size, physical_b_verified=True,
                   integrity='ok', local_snapshot_payload_bytes=0)
        with patch('vk_b_disk_snapshot.checked_mount', return_value=self.store), patch.object(vk_b_disk_capture, 'MAX_METADATA_BYTES', 64 * 1024):
            result = self.run_extended(lambda raw: row, disk_inventory=True)
        proof = result['b_path_inventory']
        with (self.store / proof['name']).open('rb') as f:
            self.assertEqual(hashlib.file_digest(f, 'sha256').hexdigest(), proof['sha256'])
        self.assertGreater(proof['paths'], 400)
        self.assertGreater(proof['bytes'], 64 * 1024)
        self.assertEqual(proof['local_payload_bytes'], 0)
        self.assertFalse(list((self.root / 'disk-extension').rglob('paths.nul')))


if __name__ == '__main__':
    suite = unittest.TestSuite(DiskCaptureTests(name) for name in (
        'test_extension_streams_verified_disk_image',
        'test_extension_rejects_unverified_disk_snapshot',
        'test_extension_rejects_corrupt_disk_snapshot',
        'test_path_inventory_is_bound_in_disk_store_without_local_list'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
