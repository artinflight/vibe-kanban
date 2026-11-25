from copy import deepcopy
from datetime import datetime, timezone
import unittest
from check_rehearsal_orphans import verify_rows


class RehearsalOrphansTests(unittest.TestCase):
    def setUp(self):
        self.start = 1000
        self.end = 1010
        self.before = {b'active': dict(id=b'active', status='running', exit_code=None,
                                      completed_at=None, updated_at='original', body='pending input'),
                       b'closed': dict(id=b'closed', status='completed', exit_code=0,
                                      completed_at='prior', updated_at='prior', body='history')}
        self.after = deepcopy(self.before)
        self.after[b'active'].update(status='failed', completed_at=self.at(1005))

    @staticmethod
    def at(seconds):
        return datetime.fromtimestamp(seconds, timezone.utc).isoformat()

    def check(self):
        return verify_rows(self.before, self.after, self.start, self.end)

    def test_only_expected_orphan_bookkeeping_passes(self):
        self.assertEqual(self.check()['detached_orphans'], 1)

    def test_zero_running_rows_pass(self):
        self.before.pop(b'active')
        self.after.pop(b'active')
        self.assertEqual(self.check()['detached_orphans'], 0)

    def test_pending_input_or_unrelated_field_change_rejected(self):
        for field in ['body', 'updated_at', 'id', 'exit_code']:
            with self.subTest(field=field):
                saved = self.after[b'active'][field]
                self.after[b'active'][field] = 'changed'
                with self.assertRaises(ValueError):
                    self.check()
                self.after[b'active'][field] = saved

    def test_closed_execution_change_rejected(self):
        self.after[b'closed']['status'] = 'failed'
        with self.assertRaises(ValueError):
            self.check()

    def test_new_or_missing_execution_rejected(self):
        row = self.after.pop(b'closed')
        with self.assertRaises(ValueError):
            self.check()
        self.after[b'closed'] = row
        self.after[b'extra'] = row
        with self.assertRaises(ValueError):
            self.check()

    def test_incomplete_orphan_cleanup_rejected(self):
        self.after[b'active'] = deepcopy(self.before[b'active'])
        with self.assertRaises(ValueError):
            self.check()

    def test_completion_outside_phase_or_without_timezone_rejected(self):
        for stamp in [self.at(999), self.at(1011), None, 'invalid', '2026-01-01T00:00:00']:
            with self.subTest(stamp=stamp):
                self.after[b'active']['completed_at'] = stamp
                with self.assertRaises(ValueError):
                    self.check()

    def test_preexisting_completion_on_running_row_rejected(self):
        self.before[b'active']['completed_at'] = self.at(999)
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
