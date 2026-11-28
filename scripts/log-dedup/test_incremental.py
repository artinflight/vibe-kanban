import json
from pathlib import Path
import tempfile
import unittest
import incremental as subject


class Fake:
    def __init__(self, rows, fail=False):
        self.rows = rows
        self.calls = 0
        self.fail = fail
        self.begins = 0
        self.finishes = 0
    def inventory(self):
        return {'files': self.rows}
    def begin(self, folder, operation):
        self.begins += 1
    def convert(self, folder, batch):
        self.calls += 1
        if self.fail:
            raise RuntimeError('uncertain after publication')
        excluded = [r['path'] for r in batch['rows'] if r.get('nonbeneficial')]
        return dict(independent_recovery_verified=True,
                    converted_files=len(batch['rows'])-len(excluded), nonbeneficial=excluded)
    def finish(self, folder, state):
        self.finishes += 1


def row(name, workspace='w', reason='eligible_closed', fingerprint='a', **more):
    return dict(path=name, workspace=workspace, reason=reason,
                fingerprint=fingerprint, bytes=10, **more)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'runs').mkdir()
        self.cfg = dict(state_root=str(self.root), maximum_run_files=100,
                        maximum_run_bytes=1000, maximum_batch_files=2,
                        maximum_batch_bytes=25, maximum_run_seconds=10)
    def tearDown(self):
        self.temp.cleanup()
    def test_active_and_pending_are_not_selected(self):
        adapter = Fake([row('one'), row('active', reason='active_session'), row('pending', reason='pending_capture')])
        value = subject.execute(self.cfg, adapter)
        self.assertEqual((value['selected_files'], adapter.calls), (1, 1))
    def test_workspace_and_resource_boundaries(self):
        result = subject.batches([row('a'), row('b'), row('c'), row('d', workspace='z')], maximum_files=2, maximum_bytes=25)
        self.assertEqual([len(r['rows']) for r in result], [2, 1, 1])
        with self.assertRaises(ValueError):
            subject.batches([dict(row('a'), bytes=26)], maximum_files=2, maximum_bytes=25)
    def test_uncertain_publication_never_replays(self):
        adapter = Fake([row('a')], fail=True)
        with self.assertRaises(RuntimeError):
            subject.execute(self.cfg, adapter)
        adapter.fail = False
        with self.assertRaisesRegex(ValueError, 'no replay'):
            subject.execute(self.cfg, adapter)
        self.assertEqual(adapter.calls, 1)
        self.assertTrue((self.root/'ACTIVE.private.json').exists())
    def test_unchanged_exclusion_skips_changed_version_rechecks(self):
        adapter = Fake([row('a', nonbeneficial=True)])
        subject.execute(self.cfg, adapter)
        subject.execute(self.cfg, adapter)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual((adapter.begins, adapter.finishes), (1, 1))
        adapter.rows[0]['fingerprint'] = 'b'
        subject.execute(self.cfg, adapter)
        self.assertEqual(adapter.calls, 2)
    def test_missing_independent_restore_keeps_review_hold(self):
        adapter = Fake([row('a')])
        adapter.convert = lambda *_: dict(independent_recovery_verified=False)
        with self.assertRaises(ValueError):
            subject.execute(self.cfg, adapter)
        self.assertEqual(subject.read(self.root/'LATEST.private.json')['phase'], 'needs_review')
    def test_budget_exits_only_between_complete_batches(self):
        adapter = Fake([row('a'), row('b', workspace='x')])
        ticks = iter([0, 0, 11, 12])
        value = subject.execute(self.cfg, adapter, clock=lambda:next(ticks))
        self.assertEqual(adapter.calls, 1)
        self.assertFalse(value['selected_scope_resolved'])
        self.assertFalse((self.root/'ACTIVE.private.json').exists())
    def test_backlog_over_budget_never_opens_adapter(self):
        self.cfg['maximum_run_files'] = 1
        adapter = Fake([row('a'), row('b')])
        with self.assertRaises(ValueError):
            subject.execute(self.cfg, adapter)
        self.assertEqual(adapter.calls, 0)
        self.assertFalse((self.root/'ACTIVE.private.json').exists())


if __name__ == '__main__':
    unittest.main()
