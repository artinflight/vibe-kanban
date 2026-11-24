import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import checkpoint_watch as subject
import automatic_watch
import dedup_alerts

SHARED = Path('/home/mcp/.local/lib/storage-alert-response')
if SHARED.is_dir():
    sys.path.insert(0, str(SHARED))
    import watch_events as events


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config_sha = self.write('CONFIG.private.json', {'scope': 'fixture'})
        started_sha = self.write('STARTED.private.json', dict(at=100, config_sha256=config_sha, pid=7, invocation='birth'))
        self.write('PROGRESS.private.json', dict(at=105, completed=1, total=3))
        self.job = dict(folder=str(self.root), operation='a'*32, attempt='checkpoint-test',
                        config_sha256=config_sha, started_sha256=started_sha, pid=7,
                        invocation='birth', unit='fixture.service', total=3,
                        deadline_at=1000, stall_seconds=600,
                        result_fields=dict(complete=True, references=3, independent_normal_B_catalog_reopen=True))
        self.status = dict(ActiveState='active', MainPID='7', InvocationID='birth', Result='success', ExecMainStatus='0')

    def write(self, name, value):
        p = self.root/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def snapshot(self, now=110):
        return subject.snapshot(self.job, now, lambda _: self.status)

    def finish(self):
        self.write('PROGRESS.private.json', dict(at=107, completed=3, total=3))
        self.write('RESULT.private.json', dict(at=108, **self.job['result_fields']))

    def test_healthy_progress_never_needs_a_model(self):
        self.assertFalse(self.snapshot()['needs_attention'])

    def test_live_result_waits_for_process_exit(self):
        self.finish()
        self.assertFalse(self.snapshot()['needs_attention'])
        self.assertEqual(self.snapshot()['phase'], 'waiting_for_script_exit')

    def test_success_requires_terminal_unit_and_complete_bound_result(self):
        self.finish()
        self.status.update(ActiveState='inactive', MainPID='0')
        self.assertEqual(self.snapshot()['state'], 'success')
        self.write('RESULT.private.json', dict(at=108, complete=True, references=2))
        self.assertEqual(self.snapshot()['state'], 'failure_recovery_pending')

    def test_collected_transient_unit_can_report_its_complete_receipt(self):
        self.finish()
        self.status.update(ActiveState='inactive', MainPID='0', InvocationID='')
        self.assertEqual(self.snapshot()['state'], 'success')
        (self.root/'RESULT.private.json').unlink()
        self.assertEqual(self.snapshot()['state'], 'failure_recovery_pending')

    def test_stopped_or_replaced_or_failed_unit_is_problem(self):
        for changes in (dict(ActiveState='inactive', MainPID='0'), dict(InvocationID='other'), dict(MainPID='8')):
            old = self.status.copy()
            self.status.update(changes)
            self.assertTrue(self.snapshot()['needs_attention'])
            self.status = old
        self.write('FAILURE.private.json', {'reason': 'fixture'})
        self.assertTrue(self.snapshot()['needs_attention'])

    def test_stall_and_deadline_are_one_problem_identity(self):
        first = self.snapshot(706)
        second = self.snapshot(1001)
        self.assertEqual(first['state'], 'failure_recovery_pending')
        self.assertEqual((first['operation'], first['attempt'], first['state']),
                         (second['operation'], second['attempt'], second['state']))

    def test_progress_read_race_allowed_but_bad_clock_is_problem(self):
        self.write('PROGRESS.private.json', dict(at=111, completed=2, total=3))
        self.assertFalse(self.snapshot()['needs_attention'])
        self.write('PROGRESS.private.json', dict(at=200, completed=2, total=3))
        self.assertTrue(self.snapshot()['needs_attention'])

    def test_changed_or_missing_evidence_alerts_instead_of_silent_hold(self):
        for name in ('CONFIG.private.json', 'STARTED.private.json', 'PROGRESS.private.json'):
            old = (self.root/name).read_bytes()
            (self.root/name).write_text('{broken')
            self.assertTrue(self.snapshot()['needs_attention'])
            (self.root/name).write_bytes(old)

    @unittest.skipUnless(SHARED.is_dir(), 'installed WakeWatch codec unavailable')
    def test_real_ledger_replay_and_acknowledgment_preserve_receipts(self):
        target = dict(enabled=True, workspace_id='081597f1-4a61-4f6a-8f56-95c2d6bc553c',
                      session_id='036f0739-6fcc-4e30-911a-e4c6e7e1f388', executor_config_sha256='a'*64,
                      max_validation_age_seconds=120, cooldown_seconds=60, vibe_db='/unused', owner_roots=['/unused'])
        registry = events.Registry(dict(version=1, activation_approved=True, state_volume={}, state_root='/unused',
            sources={'dedup-cutover': dict(enabled=True, max_age_seconds=60, driver='events-v1')},
            targets={'dedup-owner': target}, rules={'completion': dict(source='dedup-cutover', target='dedup-owner', resource='*',
                trigger=dict(field='needs_attention', op='eq', value=True), recover=dict(field='needs_attention', op='eq', value=False),
                recovery_samples=1, min_sample_seconds=1, max_gap_seconds=150, instruction='Inspect this checkpoint')}))
        path = self.root/'ledger.sqlite'
        store = events.EventStore(path)
        # Normal running observations create zero incidents.
        dedup_alerts.observe(store, registry, self.snapshot(), 110)
        self.assertEqual(len(store.pending(store.fresh(110))), 0)
        problem = self.snapshot(706)
        dedup_alerts.observe(store, registry, problem, 706)
        self.assertEqual(len(store.pending(store.fresh(706))), 1)
        with store.db:
            store.db.execute("INSERT INTO batches(id,status,created) VALUES ('uncertain','unknown',706)")
            store.db.execute("UPDATE incidents SET batch='uncertain'")
        store.db.close()
        store = events.EventStore(path)
        self.addCleanup(store.db.close)
        dedup_alerts.observe(store, registry, problem, 707)
        self.assertEqual(len(store.pending(store.fresh(707))), 0)
        self.assertEqual(store.db.execute('SELECT count(*) FROM batches').fetchone()[0], 1)
        # A separately reconciled initial success can retire only its unsubmitted alert.
        initial = dict(operation='b'*32, attempt='catchup-r2', state='success', needs_attention=True)
        dedup_alerts.observe(store, registry, initial, 708)
        result_sha = self.write('runs/' + 'b'*32 + '/RESULT.private.json', {'complete': True})
        acceptance_sha = self.write('acceptance.json', dict(complete=True, operation='b'*32, terminal={'result_sha256': result_sha}))
        config = dict(initial_operation='b'*32, incremental_state_root=str(self.root),
                      initial_acceptance=dict(path=str(self.root/'acceptance.json'), sha256=acceptance_sha))
        current = dict(operation='c'*32, state='idle', needs_attention=False)
        automatic_watch.observe_with_initial(config, dedup_alerts.observe, store, registry, current, 710, 0)
        self.assertEqual(len(store.pending(store.fresh(710))), 0)
        self.assertEqual(store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NOT NULL').fetchone()[0], 1)
        self.assertEqual(store.db.execute("SELECT status FROM batches WHERE id='uncertain'").fetchone()[0], 'unknown')
        automatic_watch.observe_with_initial(config, dedup_alerts.observe, store, registry, current, 712, 0)
        self.assertEqual(store.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 2)
        # A changed acceptance cannot silently suppress an alert.
        (self.root/'acceptance.json').write_text('{}')
        with self.assertRaises(ValueError):
            subject.acknowledge_initial(config, store, registry, 714)


if __name__ == '__main__':
    unittest.main()
