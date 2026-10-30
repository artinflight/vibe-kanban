"""Unresolved pressure is not resolved merely because an owner turn ended."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monitor
import pressure
import t26_watch as watch

OLD = '00000000-0000-4000-8000-000000000001'
WORKSPACE = '00000000-0000-4000-8000-000000000002'
SESSION = '00000000-0000-4000-8000-000000000003'


def sample(at, free=8_000_000_000):
    return {'policy': pressure.OS_DECIMAL, 'identity': 'os', 'at': at,
            'available': free, 'percent': 95, 'total_bytes': 100_000_000_000,
            'used_bytes': 100_000_000_000 - free,
            'mount': {'target': '/', 'source': '/dev/test', 'uuid': 'os',
                      'fstype': 'ext4', 'maj:min': '1:1'}}


class Rearm(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'incidents.sqlite'
        self.store = monitor.Store(self.path)
        self.owner = {'coding_or_script_turns': [], 'independent_jobs': [],
                      'queued': [], 'process_ids': [], 'inventory_unknown': False}
        self.config = {'rearm_completed_incidents': True, 'state_file': str(self.path),
                       'native_transport': {'enabled': True}}
        self.store.observations({'os': sample(1000)}, {}, 1000)
        with self.store.db:
            self.store.db.execute("INSERT INTO batches(id,status,execution,created,updated) "
                                  "VALUES (?,'completed','previous-execution',900,900)", (OLD,))
            self.store.db.execute("UPDATE incidents SET batch=?,delivery='accepted'", (OLD,))
            with patch.object(monitor.time, 'time', return_value=1000):
                self.store.audit('execution_completed', {'batch': OLD})

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def call(self, at=2800, owner=None, values=None, config=None):
        values = values or {'os': sample(at)}
        self.store.observations(values, {}, at)
        return watch.rearm_completed(self.store, config or self.config, values,
                                     owner or self.owner, at)

    def pending(self):
        return self.store.db.execute('SELECT batch,delivery FROM incidents').fetchone()

    def test_rearms_completed_unrecovered_once_and_preserves_old_receipt(self):
        self.assertIsNone(self.call())
        self.assertEqual(tuple(self.pending()), (None, 'pending'))
        self.call(2860)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM audit WHERE kind='completed_pressure_rearmed'").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute('SELECT status,execution FROM batches WHERE id=?', (OLD,)).fetchone()[:], ('completed', 'previous-execution'))

    def test_cooldown_is_from_verified_completion_not_acceptance(self):
        self.assertEqual(self.call(2799), 'unresolved_incident_cooldown')
        self.assertEqual(self.pending()['batch'], OLD)
        self.call(2800)
        self.assertIsNone(self.pending()['batch'])

    def test_existing_non_opted_consumers_unchanged(self):
        self.call(config={'rearm_completed_incidents': False})
        self.assertEqual(self.pending()['batch'], OLD)

    def test_busy_queued_jobs_or_unknown_owner_remain_held(self):
        for key, value in [('coding_or_script_turns', ['turn']), ('independent_jobs', ['job']),
                           ('queued', ['turn']), ('process_ids', [123]), ('inventory_unknown', True)]:
            with self.subTest(key=key):
                self.assertEqual(self.call(owner=dict(self.owner, **{key: value})), 'unresolved_incident_owner_busy')
                self.assertEqual(self.pending()['batch'], OLD)

    def test_no_replay_of_failed_killed_running_unknown_or_deferred(self):
        for status in ('failed', 'killed', 'accepted', 'dispatching', 'unknown', 'deferred'):
            with self.subTest(status=status):
                with self.store.db:
                    self.store.db.execute('UPDATE batches SET status=?', (status,))
                self.call()
                self.assertEqual(self.pending()['batch'], OLD)

    def test_other_unsettled_batch_blocks_rearm(self):
        with self.store.db:
            self.store.db.execute("INSERT INTO batches(id,status,created) VALUES ('other','unknown',1100)")
        self.call()
        self.assertEqual(self.pending()['batch'], OLD)

    def test_missing_or_wrong_completion_receipt_fails_closed(self):
        with self.store.db:
            self.store.db.execute('DELETE FROM audit')
            self.store.audit('execution_completed', {'batch': 'another-batch'})
        self.assertEqual(self.call(), 'unresolved_incident_completion_unverified')
        self.assertEqual(self.pending()['batch'], OLD)

    def test_future_completion_clock_regression_fails_closed(self):
        with self.store.db:
            self.store.db.execute("UPDATE audit SET at=10000 WHERE kind='execution_completed'")
        self.assertEqual(self.call(), 'unresolved_incident_completion_unverified')
        self.assertEqual(self.pending()['batch'], OLD)

    def test_missing_stale_or_changed_identity_sample_cannot_rearm(self):
        for values in ({}, {'os': dict(sample(1000), pressure={'eligible': True})},
                       {'os': dict(sample(2800), identity='other', pressure={'eligible': True})}):
            watch.rearm_completed(self.store, self.config, values, self.owner, 2800)
            self.assertEqual(self.pending()['batch'], OLD)

    def test_pressure_below_dispatch_threshold_is_still_required(self):
        self.call(values={'os': sample(2800, 10_000_000_000)})
        self.assertEqual(self.pending()['batch'], OLD)

    def test_physically_recovered_incident_never_rearms(self):
        with self.store.db:
            self.store.db.execute('UPDATE incidents SET recovered=2000')
        watch.rearm_completed(self.store, self.config, {}, self.owner, 2800)
        self.assertEqual(self.pending()['batch'], OLD)

    def test_actual_cycle_creates_new_batch_not_resend_and_deduplicates(self):
        class Bridge:
            sent = []
            def ready(self): return True
            def binding(self): return {'workspace_id': WORKSPACE, 'session_id': SESSION}
            def observe(self, key): return sample(2800)
            def send(self, document):
                self.sent.append(document['batch_id'])
                return {'kind': 'accepted', 'batch_id': document['batch_id'],
                        'intent_sha256': document['intent_sha256'],
                        'execution_id': '00000000-0000-4000-8000-000000000011',
                        'receipt_id': 'new-verified-receipt', 'reason': 'admitted'}
            def execution(self, execution): return 'running'
            def lookup(self, *args): return None
        bridge = Bridge()
        with patch.object(monitor.time, 'time', return_value=2800):
            meta, result = watch.cycle(self.store, self.config, {'os': sample(2800)}, {},
                                      self.owner, {}, 2800, bridge_factory=lambda _: bridge)
            self.assertEqual(result['status'], 'accepted')
            watch.cycle(self.store, self.config, {'os': sample(2801)}, {}, self.owner,
                        meta, 2801, bridge_factory=lambda _: bridge)
        self.assertEqual(len(bridge.sent), 1)
        self.assertNotEqual(bridge.sent[0], OLD)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM batches').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
