import copy
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

WORKSPACE = '00000000-0000-4000-8000-000000000001'
SESSION = '00000000-0000-4000-8000-000000000002'


def sample(key, free, at=1000):
    policy = pressure.OS_DECIMAL if key == 'os' else pressure.SSD_DECIMAL
    return {'policy': policy, 'identity': key, 'at': at, 'available': free,
            'percent': 95, 'total_bytes': 100_000_000_000, 'used_bytes': 100_000_000_000-free,
            'mount': {'target': '/' if key == 'os' else '/mnt/vk-storage', 'source': '/dev/test-'+key,
                      'uuid': key, 'fstype': 'ext4', 'maj:min': '8:17'}}


class FinalThresholds(unittest.TestCase):
    def test_strict_decimal_boundaries(self):
        for key, threshold in [('os', 10_000_000_000), ('ssd', 25_000_000_000)]:
            for free, expected in [(threshold-1, True), (threshold, False), (threshold+1, False)]:
                state, decision = pressure.advance({}, sample(key, free))
                self.assertEqual(expected, decision['eligible'])

    def test_recovery_and_gaps(self):
        state, _ = pressure.advance({}, sample('ssd', 24_999_999_999))
        for at in [1060, 1120]:
            state, d = pressure.advance(state, sample('ssd', 27_000_000_000, at))
            self.assertFalse(d['recovered'])
        state, d = pressure.advance(state, sample('ssd', 27_000_000_000, 1180))
        self.assertTrue(d['recovered'])
        state, d = pressure.advance(state, sample('ssd', 24_999_999_999, 1240))
        self.assertTrue(d['eligible'])
        state, _ = pressure.advance(state, sample('ssd', 27_000_000_000, 1300))
        state, d = pressure.advance(state, sample('ssd', 27_000_000_000, 1500))
        self.assertFalse(d['recovered'])
        state, d = pressure.advance(state, sample('ssd', 27_000_000_000, 1560), periodic=False)
        self.assertFalse(d['recovered'])

    def test_policy_migration_refused(self):
        with self.assertRaises(ValueError):
            pressure.advance({'policy': pressure.SSD_PHYSICAL, 'identity': 'ssd'}, sample('ssd', 1))


class Runner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'incidents.sqlite'
        self.store = monitor.Store(self.path)
        self.owner = {'coding_or_script_turns': [], 'independent_jobs': [], 'queued': [],
                      'process_ids': [], 'inventory_unknown': False}
        self.config = {'state_file': str(self.path), 'native_transport': {'enabled': False}}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def tick(self, at, owner=None, meta=None, config=None, bridge=None, values=None, errors=None):
        return watch.cycle(self.store, config or self.config, values or {'ssd': sample('ssd', 6_000_000_000, at)},
                           errors or {}, owner or self.owner, meta or {}, at,
                           bridge_factory=bridge or (lambda _: self.fail('unexpected dispatch')))

    def test_initial_low_dedup_restart_and_backoff(self):
        meta, out = self.tick(1000)
        self.assertEqual(out['status'], 'pending_native_release_and_binding')
        self.assertEqual(out['pending_incidents'], 1)
        incident = self.store.db.execute('SELECT id FROM incidents').fetchone()[0]
        meta, out = self.tick(1030, meta=meta)
        self.assertEqual(out['status'], 'backoff')
        self.store.close()
        self.store = monitor.Store(self.path)
        for at in range(1060, 5000, 60):
            meta, out = self.tick(at, meta=meta)
        self.assertEqual([r[0] for r in self.store.db.execute('SELECT id FROM incidents')], [incident])
        self.assertLessEqual(meta['next_attempt'] - at, 3600)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)

    def test_running_owner_and_independent_jobs_never_launch(self):
        for key, value in [('coding_or_script_turns', ['running-owner']), ('independent_jobs', ['detached-job']),
                           ('process_ids', [123]), ('queued', ['owner']), ('inventory_unknown', True)]:
            with self.subTest(key=key):
                self.store.close()
                self.path = Path(self.temp.name)/(key+'.sqlite')
                self.store = monitor.Store(self.path)
                owner = dict(self.owner, **{key: value})
                _, out = self.tick(1000, owner=owner, config={'state_file':str(self.path), 'native_transport':{'enabled':True}})
                expected = 'pending_owner_busy_or_inventory_unknown'
                self.assertEqual(out['status'], expected)
                self.assertEqual(out['pending_incidents'], 1)
                self.assertEqual(self.store.db.execute('SELECT delivery FROM incidents').fetchone()[0], 'pending')

    def test_report_exact_identities_growth_and_missing_baseline(self):
        first = sample('ssd', 7_000_000_000, 1000)
        second = sample('ssd', 6_000_000_000, 1060)
        text = watch.report({'ssd': second}, [{'at':1000,'volumes':{'ssd':first}}], self.owner, 1060)
        for expected in ['6000000000 bytes', '25000000000 bytes', '/dev/test-ssd', 'UUID=ssd',
                         'consumption=1000000000 bytes', '24h growth: baseline unavailable']:
            self.assertIn(expected, text)

    def test_mixed_volume_valid_root_not_hidden_by_ssd_error(self):
        _, out = self.tick(1000, values={'os':sample('os', 9_999_999_999)}, errors={'ssd':'mount_missing'})
        self.assertEqual(out['pending_incidents'], 1)
        self.assertEqual(self.store.db.execute('SELECT volume FROM incidents').fetchone()[0], 'os')

    def test_bounded_history_and_global_cooldown(self):
        history = [{'at':at,'volumes':{}} for at in range(1000, 100000, 60)]
        meta, _ = self.tick(100000, meta={'history':history})
        self.assertLessEqual(len(meta['history']), 1441)
        config = dict(self.config, native_transport={'enabled':True})
        _, out = self.tick(100000, meta={'last_accepted':99999}, config=config)
        self.assertEqual(out['status'], 'episode_cooldown')

    def test_clock_regression_bounds_wait_without_redispatch(self):
        meta, out = self.tick(1000, meta={'next_attempt':100000000, 'last_accepted':100000000, 'owner_wait_policy':1})
        self.assertLessEqual(meta['next_attempt'] - 1000, 3600)
        self.assertLessEqual(meta['last_accepted'], 1000)
        self.assertEqual(out['status'], 'backoff')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)

    def test_commit_failure_never_sends(self):
        class Bridge:
            def ready(self): return True
            def binding(self): return {'workspace_id':WORKSPACE, 'session_id':SESSION}
            def observe(self, key): return sample(key, 1, 1000)
            def send(self, doc): raise AssertionError('must commit intent before sending')
        self.store.observations({'ssd':sample('ssd',1)}, {}, 1000)
        self.store.db.execute("CREATE TRIGGER full_store BEFORE INSERT ON batches BEGIN SELECT RAISE(ABORT, 'full'); END")
        with patch.object(monitor.time, 'time', return_value=1000):
            with self.assertRaises(Exception) as caught:
                self.store.dispatch({'ssd':sample('ssd',1)}, Bridge(), self.path)
        self.assertNotIsInstance(caught.exception, AssertionError)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM batches').fetchone()[0], 0)

    def test_report_size_and_sqlite_hard_cap_fail_closed(self):
        with self.assertRaises(ValueError):
            watch.atomic_json(Path(self.temp.name)/'report.json', {'oversized':'x'*65536})
        self.store.db.execute('PRAGMA max_page_count=32')
        with self.assertRaises(__import__('sqlite3').DatabaseError):
            self.store.db.execute('CREATE TABLE excessive AS SELECT zeroblob(200000) AS payload')
        self.store.db.rollback()
        self.assertLessEqual(self.path.stat().st_size, 32*4096)

    def test_native_accepted_dedup_and_lost_response_no_resend(self):
        class Bridge:
            sends = 0
            def ready(self): return True
            def binding(self): return {'workspace_id':WORKSPACE,'session_id':SESSION}
            def observe(self, key): return sample(key, 6_000_000_000, 1000)
            def send(self, doc):
                self.sends += 1
                return {'kind':'accepted','batch_id':doc['batch_id'], 'intent_sha256':doc['intent_sha256'],
                        'execution_id':'00000000-0000-4000-8000-000000000010','receipt_id':'test-receipt','reason':'admitted'}
            def lookup(self, *args): return None
            def execution(self, *args): return 'completed'
        bridge = Bridge()
        config = dict(self.config, native_transport={'enabled':True})
        with patch.object(monitor.time, 'time', return_value=1000):
            meta, out = self.tick(1000, config=config, bridge=lambda _:bridge)
            self.assertEqual(out['status'], 'accepted')
            for at in range(1060, 8000, 60):
                meta, out = self.tick(at, meta=meta, config=config, bridge=lambda _:bridge)
        self.assertEqual(bridge.sends, 1)
        self.store.db.execute("UPDATE batches SET status='unknown'")
        self.store.db.commit()
        with patch.object(monitor.time, 'time', return_value=9000):
            self.tick(9000, config=config, bridge=lambda _:bridge)
        self.assertEqual(bridge.sends, 1)


if __name__ == '__main__':
    unittest.main()
