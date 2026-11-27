import sqlite3
import os
import unittest

import audit
import test_reclaim as fixture_module


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ReclaimTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.source
        self.db = self.fixture.db

    def test_metadata_only_counts_and_closed_inactive_selection(self):
        value = audit.inventory(self.root, self.db)
        self.assertEqual(value['eligible_closed_inactive_files'], self.fixture.paths)
        self.assertEqual(value['totals']['raw_files'], 2)
        self.assertEqual(value['totals']['raw_bytes'], 2 * len(self.fixture.original))
        self.assertFalse(value['writer_fence_established'])
        self.assertNotIn('Stdout', str(value))

    def test_active_session_excludes_its_completed_logs(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE execution_processes SET status='running' WHERE rowid=1")
        value = audit.inventory(self.root, self.db)
        self.assertEqual(value['eligible_closed_inactive_files'], [])
        self.assertEqual(set(value['exclusions'].values()), {'session_has_running_execution'})

    def test_legacy_and_unbound_files_are_never_automatic_candidates(self):
        (self.root / self.fixture.paths[0]).with_suffix('.capture.json').unlink()
        with sqlite3.connect(self.db) as conn:
            conn.execute('DELETE FROM execution_processes WHERE rowid=2')
        value = audit.inventory(self.root, self.db)
        self.assertEqual(value['eligible_closed_inactive_files'], [])
        self.assertEqual(set(value['exclusions'].values()), {
            'legacy_capture_requires_explicit_owner_review', 'unbound_execution_or_session'})

    def test_damaged_capture_metadata_is_excluded_without_hiding_other_logs(self):
        (self.root / self.fixture.paths[0]).with_suffix('.capture.json').write_bytes(b'')
        value = audit.inventory(self.root, self.db)
        self.assertEqual(value['eligible_closed_inactive_files'], self.fixture.paths[1:])
        self.assertIn('capture_metadata_invalid', value['exclusions'].values())

    def test_comparison_records_append_growth_and_is_not_a_forecast(self):
        before = audit.inventory(self.root, self.db)
        with (self.root / self.fixture.paths[0]).open('ab') as target:
            target.write(b'new output\n')
        after = audit.inventory(self.root, self.db)
        value = audit.compare(before, after)
        self.assertEqual(value['new_files'], 0)
        self.assertEqual(value['existing_logical_delta_bytes'], 11)
        self.assertFalse(value['forecast'])
        self.assertFalse(value['matched_workload_verified'])
        after['database_identity'] = [0, 0]
        with self.assertRaises(ValueError):
            audit.compare(before, after)

    def test_conversion_does_not_double_count_shared_objects_or_logical_bytes(self):
        before = audit.inventory(self.root, self.db)
        with self.fixture.fence.held():
            self.fixture.batch().run()
        after = audit.inventory(self.root, self.db)
        self.assertEqual(before['totals']['raw_bytes'], after['totals']['raw_bytes'])
        self.assertEqual(after['totals']['archived_files'], 2)
        self.assertGreater(after['totals']['object_files'], 0)
        self.assertEqual(audit.compare(before, after)['raw_to_archive_files'], 2)

    def test_temporary_object_hardlink_does_not_double_count_physical_payload(self):
        with self.fixture.fence.held():
            self.fixture.batch().run()
        before = audit.inventory(self.root, self.db)
        directory = (self.root / self.fixture.paths[0]).parent / '.log-objects'
        original = next(directory.iterdir())
        os.link(original, directory / '.new-interrupted-publication')
        after = audit.inventory(self.root, self.db)
        self.assertEqual(before['totals']['total_payload_allocated_bytes'],
                         after['totals']['total_payload_allocated_bytes'])
        self.assertEqual(after['totals']['object_files'], before['totals']['object_files'] + 1)

    def test_missing_owner_evidence_and_capacity_never_report_production_ready(self):
        observation = audit.inventory(self.root, self.db)
        value = audit.readiness(observation, reader_qualification=None, backup_verification=None,
                                custody_adapter=None, ssd_free_bytes=1024**3)
        self.assertFalse(value['production_run_ready'])
        self.assertEqual(len(value['blockers']), 4)
        with self.assertRaises(ValueError):
            audit.inventory(self.root, self.db, maximum_files=1)


if __name__ == '__main__':
    unittest.main()
