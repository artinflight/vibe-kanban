"""Small real-archive tests. All fixtures and receipts stay on the SSD."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scratch_retirement import CASES, FLOOR, ScratchRetirement, SpaceBudget, digest, require_full_workload

PINNED = Path('/mnt/vk-storage/vk-green-reprepare-20261005/operational-source/scripts/deployment')
sys.path.insert(0, str(PINNED))
from vk_rolling_backup import verify_snapshot_archive


class RetirementTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ['VK_LOW_PEAK_TEST_ROOT']).resolve()
        self.assertTrue(base.is_relative_to('/mnt/vk-storage'))
        self.assertTrue(os.path.ismount('/mnt/vk-storage'))
        base.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='handover-', dir=base))
        self.folder = self.root / 'backups/checkpoint-/fixture'
        self.folder.mkdir(parents=True)
        (self.root / 'runtime').mkdir()
        (self.root / 'low-peak-fixture.json').write_text(json.dumps({
            'schema': 1, 'root': str(self.root), 'production_modified': False, 'private_fixture': True}))
        self.original = self.root / 'runtime/source.sqlite'
        with sqlite3.connect(self.original) as db:
            db.execute('CREATE TABLE data (content TEXT)')
            db.execute("INSERT INTO data VALUES ('keep original')")
        db.close()
        name = hashlib.sha256(str(self.original).encode()).hexdigest() + '.sqlite'
        self.copy = self.folder / 'payload/sqlite' / name
        self.copy.parent.mkdir(parents=True)
        self.copy.write_bytes(self.original.read_bytes())
        self.verified = self.folder / 'verified-payload/payload/sqlite' / name
        self.verified.parent.mkdir(parents=True)
        self.verified.write_bytes(self.copy.read_bytes())
        self.manifest = {'parent': None, 'production_boundary': False,
                         'sqlite_snapshots': {str(self.original): {'path': 'sqlite/' + name,
                                                                  'sha256': digest(self.copy)}}}
        self.manifest_path = self.folder / 'payload/manifest.json'
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.archive = self.folder / 'fixture.tar.zst'
        subprocess.run(['tar', '--zstd', '-cf', str(self.archive), '-C', str(self.folder), 'payload'], check=True)
        (self.folder / 'result.json').write_text(json.dumps({'passed': True,
            'receipt': {'sha256': digest(self.archive)}}))
        self.receipts = []
        self.guard = ScratchRetirement(self.root, verify_snapshot_archive,
            lambda path: {'desktop_verified': True, 'sha256': digest(path), 'synthetic_test_only': True,
                          'name': path.name, 'desktop_directory': 'B:/vk-backups/synthetic-only'},
            lambda paths: True)

    def plan(self, phase='checkpoint-verified', cases=()):
        return self.guard.plan(self.folder, phase, cases)

    def test_checkpoint_retires_only_verified_duplicate(self):
        archived, original = digest(self.archive), digest(self.original)
        plan = self.plan()
        amount = self.guard.retire(plan, self.receipts.append)
        self.assertGreater(amount, 0)
        self.assertFalse(self.verified.exists())
        self.assertTrue(self.copy.exists())
        self.assertEqual(digest(self.archive), archived)
        self.assertEqual(digest(self.original), original)
        self.assertTrue(self.manifest_path.exists())

    def test_completed_handover_retires_payload_and_restores_original_content(self):
        self.guard.retire(self.plan('handover-assertions-complete', CASES), self.receipts.append)
        restored = self.root / 'restoration'
        restored.mkdir()
        subprocess.run(['tar', '--zstd', '-xf', str(self.archive), '-C', str(restored)], check=True)
        self.assertEqual(digest(self.original), digest(restored / self.copy.relative_to(self.folder)))
        self.assertEqual(self.receipts[-1]['state'], 'retired')

    def test_incomplete_assertions_rejected(self):
        for cases in ((), CASES[:3], CASES[::-1]):
            with self.assertRaisesRegex(ValueError, 'four handover'):
                self.plan('handover-assertions-complete', cases)
        self.assertTrue(self.copy.exists())

    def test_unknown_phase_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown retirement'):
            self.plan('cleanup-everything')

    def test_unverified_desktop_rejected(self):
        self.guard.verify_desktop = lambda _: {'desktop_verified': False, 'sha256': digest(self.archive)}
        with self.assertRaisesRegex(ValueError, 'Desktop'):
            self.plan()

    def test_wrong_remote_hash_rejected(self):
        self.guard.verify_desktop = lambda _: {'desktop_verified': True, 'sha256': 'wrong'}
        with self.assertRaisesRegex(ValueError, 'Desktop'):
            self.plan()

    def test_missing_restore_locator_rejected(self):
        self.guard.verify_desktop = lambda _: {'desktop_verified': True, 'sha256': digest(self.archive)}
        with self.assertRaisesRegex(ValueError, 'locator'):
            self.plan()

    def test_uncertain_consumer_rejected(self):
        self.guard.verify_consumers = lambda _: False
        with self.assertRaisesRegex(ValueError, 'consumers'):
            self.plan()

    def test_changed_copy_rejected(self):
        self.verified.write_bytes(b'not the protected copy')
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.plan()

    def test_hardlink_to_original_rejected(self):
        self.verified.unlink()
        os.link(self.original, self.verified)
        with self.assertRaisesRegex(ValueError, 'exclusively owned'):
            self.plan()

    def test_symlink_to_original_rejected(self):
        self.verified.unlink()
        self.verified.symlink_to(self.original)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.plan()

    def test_changed_plan_cannot_add_original(self):
        plan = self.plan()
        plan['rows'][0]['path'] = str(self.original)
        with self.assertRaisesRegex(ValueError, 'plan changed'):
            self.guard.retire(plan, self.receipts.append)
        self.assertTrue(self.original.exists())

    def test_changed_archive_after_dry_run_rejected(self):
        plan = self.plan()
        self.archive.write_bytes(b'corrupt')
        with self.assertRaises(Exception):
            self.guard.retire(plan, self.receipts.append)
        self.assertTrue(self.verified.exists())

    def test_missing_completed_checkpoint_rejected(self):
        (self.folder / 'result.json').write_text(json.dumps({'passed': False}))
        with self.assertRaisesRegex(ValueError, 'completed'):
            self.plan()

    def test_replayed_retirement_rejected(self):
        plan = self.plan()
        self.guard.retire(plan, self.receipts.append)
        with self.assertRaises(FileNotFoundError):
            self.guard.retire(plan, self.receipts.append)

    def test_original_outside_fixture_rejected(self):
        self.manifest['sqlite_snapshots']['/production/source.sqlite'] = self.manifest['sqlite_snapshots'].pop(str(self.original))
        self.manifest_path.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'outside private'):
            self.plan()

    def test_original_archive_outside_fixture_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside private'):
            self.guard.plan(self.root.parent, 'checkpoint-verified', ())

    def test_group_writable_root_rejected(self):
        self.root.chmod(0o770)
        with self.assertRaisesRegex(ValueError, 'exclusive'):
            ScratchRetirement(self.root, None, None, None)


class SpaceAndCoverageTests(unittest.TestCase):
    def test_floor_cannot_be_lowered(self):
        with self.assertRaisesRegex(ValueError, 'two-GiB'):
            SpaceBudget('/mnt/vk-storage', FLOOR - 1)

    def test_reservation_and_low_space_fail_closed(self):
        fake = type('FS', (), {'f_bavail': FLOOR + 100, 'f_frsize': 1})()
        with patch('scratch_retirement.os.statvfs', return_value=fake):
            budget = SpaceBudget('/mnt/vk-storage')
            budget.check('fits', 100)
            with self.assertRaisesRegex(ValueError, 'headroom'):
                budget.check('does not fit', 101)
            self.assertEqual(len(budget.samples), 2)

    def test_all_original_databases_required_and_new_ones_preserved(self):
        expected = [str(i) for i in range(67)]
        value = {'backup_ready': True, 'errors': [], 'inventory_is_live_estimate_not_fenced_upper_bound': False,
                 'database_inventory': [{'path': str(i)} for i in range(68)],
                 'protected_roots': [{'present': True, 'symlink': False}]}
        require_full_workload(value, expected)
        value['database_inventory'].pop(0)
        with self.assertRaisesRegex(ValueError, 'workload was reduced'):
            require_full_workload(value, expected)

    def test_unresolved_journal_blocks_full_rehearsal(self):
        with self.assertRaisesRegex(ValueError, 'coverage is unresolved'):
            require_full_workload({'backup_ready': False}, [])

    def test_live_size_estimate_is_not_full_rehearsal_permission(self):
        with self.assertRaisesRegex(ValueError, 'not a bound'):
            require_full_workload({'backup_ready': True, 'errors': []}, [])


if __name__ == '__main__':
    unittest.main()
