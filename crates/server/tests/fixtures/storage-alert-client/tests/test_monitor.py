import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import types
import unittest
import sys
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('monitor', ROOT / 'monitor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sample(percent=98, identity='fixture-fs'):
    return dict(percent=percent, available=10, at=time.time(), identity=identity, policy=m.pressure.OS)


class FakeBridge:
    def __init__(self):
        self.samples = {'os': sample(), 'ssd': sample()}
        self.calls = []
        self.idle = True
        self.outcome = str(uuid.uuid4())
        self.status = 'running'
        self.lookup_result = None

    def binding(self):
        return {'workspace_id': '00000000-0000-4000-8000-000000000001',
                'session_id': '00000000-0000-4000-8000-000000000002',
                'executor_config_sha256': 'a' * 64}

    def ready(self):
        return self.idle

    def observe(self, key):
        result = dict(self.samples[key])
        result['at'] = time.time()
        return result

    def send(self, document):
        self.calls.append(document)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return {'kind': 'accepted', 'batch_id': document['batch_id'], 'intent_sha256': document['intent_sha256'],
                'execution_id': self.outcome, 'receipt_id': 'fixture-receipt'}

    def lookup(self, bid, fingerprint, document=None):
        return self.lookup_result

    def execution(self, eid):
        return self.status


class Incidents(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'state.db'
        self.s = m.Store(self.path)
        self.b = FakeBridge()

    def tearDown(self):
        self.s.close()
        self.temp.cleanup()

    def poll(self, values=None):
        values = values if values is not None else self.b.samples
        self.s.observations(values, {}, time.time())
        return self.s.dispatch(values, self.b, self.path)

    def restart(self):
        self.s.close()
        self.s = m.Store(self.path)

    def test_thresholds(self):
        self.assertEqual([m.level(p) for p in (83, 84, 85, 91, 92, 96, 97)],
                         ['normal', 'normal', 'warning', 'warning', 'critical', 'critical', 'emergency'])

    def test_dual_incidents_merge_and_repeat_restart_deduplicate(self):
        self.assertEqual(self.poll(), 'accepted')
        for _ in range(3):
            self.restart()
            self.assertEqual(self.poll(), 'held_prior_delivery')
        self.assertEqual(len(self.b.calls), 1)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 2)
        self.b.status = 'completed'
        self.assertEqual(self.poll(), 'no_action')
        self.assertEqual(len(self.b.calls), 1)

    def test_prompt_preserves_existing_pressure_relief_authority_and_approvals(self):
        self.assertEqual(self.poll(), 'accepted')
        prompt = self.b.calls[0]['intent']['prompt']
        for required in ('perform pressure relief already authorized', 'current safety and cleanup boundaries',
                         'Nightly/shared allocations as context', 'shared allocations alone are not a hold',
                         'actual resource/safety holds', 'normal backend admission', 'existing budget controls',
                         'fresh deletion/security/spending approval where the action is not already authorized',
                         'Keep Recommend-only'):
            self.assertIn(required, prompt)
        self.assertNotIn('authorizes read-only', prompt)
        self.assertNotIn('grants no cleanup', prompt)

    def test_warning_does_not_wake(self):
        self.assertEqual(self.poll({'ssd': sample(91)}), 'no_action')
        self.assertFalse(self.b.calls)

    def test_busy_then_idle_defers_without_overwriting_owner_work(self):
        self.b.idle = False
        self.assertEqual(self.poll(), 'deferred')
        self.restart()
        self.assertFalse(self.b.calls)
        self.b.idle = True
        self.assertEqual(self.poll(), 'accepted')
        self.assertEqual(len(self.b.calls), 1)

    def test_missing_capability_or_route_read_retries_safely(self):
        with patch.object(self.b, 'ready', side_effect=ValueError('route unavailable')):
            self.assertEqual(self.poll(), 'deferred')
            self.restart()
            self.assertEqual(self.poll(), 'deferred')
        self.assertFalse(self.b.calls)
        self.assertEqual(self.poll(), 'accepted')

    def test_timeout_never_retries_even_after_recovery_new_episode(self):
        self.b.outcome = TimeoutError()
        self.assertEqual(self.poll(), 'unknown')
        self.restart()
        self.assertEqual(self.poll({'os': sample(80), 'ssd': sample(80)}), 'held_prior_delivery')
        self.assertEqual(self.poll(), 'held_prior_delivery')
        self.assertEqual(len(self.b.calls), 1)
        self.assertEqual(self.s.db.execute('SELECT status FROM batches').fetchone()[0], 'unknown')

    def test_crash_between_intent_and_receipt_never_resends(self):
        with patch.object(self.b, 'send', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.poll()
        self.restart()
        self.assertEqual(self.poll(), 'held_prior_delivery')
        self.assertEqual(self.s.db.execute('SELECT status FROM batches').fetchone()[0], 'unknown')

    def test_failed_or_killed_execution_is_explicit_and_not_retried(self):
        for status in ('failed', 'killed'):
            with self.subTest(status=status):
                self.s.db.execute('DELETE FROM incidents')
                self.s.db.execute('DELETE FROM batches')
                self.s.db.commit()
                self.b.status = status
                self.assertEqual(self.poll(), 'accepted')
                self.assertEqual(self.poll(), 'no_action')
                self.assertEqual(self.s.db.execute('SELECT status FROM batches').fetchone()[0], status)

    def test_recovery_while_busy_cancels_pending(self):
        self.b.idle = False
        self.poll()
        self.assertEqual(self.poll({'os': sample(83), 'ssd': sample(83)}), 'no_action')
        self.assertFalse(self.b.calls)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NOT NULL').fetchone()[0], 2)

    def test_recovery_after_status_read_does_not_admit_stale_alert(self):
        self.b.samples = {'ssd': sample(80)}
        self.assertEqual(self.poll({'ssd': sample(98)}), 'recovered_or_invalid_before_admission')
        self.assertFalse(self.b.calls)

    def test_hysteresis_and_new_episode(self):
        self.poll({'ssd': sample(98)})
        self.b.status = 'completed'
        self.assertEqual(self.poll({'ssd': sample(84)}), 'no_action')
        self.assertEqual(self.poll({'ssd': sample(98)}), 'no_action')
        self.poll({'ssd': sample(83)})
        self.assertEqual(self.poll({'ssd': sample(98)}), 'accepted')
        self.assertEqual(len(self.b.calls), 2)

    def test_new_incidents_use_normal_admission_without_daily_ceiling(self):
        self.b.status = 'completed'
        for _ in range(4):
            self.assertEqual(self.poll(), 'accepted')
            self.restart()
            # The same episode remains deduplicated even after execution completion.
            self.assertEqual(self.poll(), 'no_action')
            self.poll({'os': sample(80), 'ssd': sample(80)})
        self.assertEqual(len(self.b.calls), 4)
        # Removing the artificial ceiling does not bypass a real admission hold.
        self.b.idle = False
        self.assertEqual(self.poll(), 'deferred')
        self.assertEqual(len(self.b.calls), 4)

    def test_independent_valid_volume_survives_ssd_read_failure(self):
        self.s.observations({'os': sample()}, {'ssd': 'unmounted'}, time.time())
        with patch.object(self.b, 'observe', side_effect=lambda key: sample() if key == 'os' else (_ for _ in ()).throw(ValueError())):
            self.assertEqual(self.s.dispatch({'os': sample()}, self.b, self.path), 'accepted')

    def test_stale_and_changed_identity_rejected(self):
        with self.assertRaises(ValueError):
            self.s.observations({'ssd': {**sample(), 'at': time.time() - 100}}, {}, time.time())
        self.s.observations({'ssd': sample()}, {}, time.time())
        with self.assertRaises(ValueError):
            self.s.observations({'ssd': sample(identity='replacement')}, {}, time.time())

    def test_commit_failure_prevents_mutation(self):
        self.s.observations(self.b.samples, {}, time.time())
        self.s.db.execute('PRAGMA query_only=ON')
        with self.assertRaises(sqlite3.OperationalError):
            self.s.dispatch(self.b.samples, self.b, self.path)
        self.assertFalse(self.b.calls)

    def test_phone_survives_agent_unavailable_and_keeps_own_dedup(self):
        calls = []
        self.b.idle = False
        now = time.time()
        self.s.phone('ssd', sample(), lambda *x: calls.append(x), now)
        self.poll()
        self.restart()
        self.s.phone('ssd', sample(), lambda *x: calls.append(x), now + 60)
        self.assertEqual(len(calls), 1)
        self.s.phone('ssd', sample(), lambda *x: calls.append(x), now + 21601)
        self.s.phone('ssd', sample(83), lambda *x: calls.append(x), now + 21602)
        self.assertEqual([c[1] for c in calls], ['emergency', 'emergency', 'normal'])
        self.assertFalse(self.b.calls)

    def test_phone_uncertain_does_not_blind_retry(self):
        now = time.time()
        self.s.phone('ssd', sample(), lambda *x: (_ for _ in ()).throw(TimeoutError()), now)
        self.restart()
        calls = []
        self.s.phone('ssd', sample(), lambda *x: calls.append(x), now + 60)
        self.assertFalse(calls)
        self.assertEqual(self.s.db.execute('SELECT status FROM phones').fetchone()[0], 'unknown')


class MountIdentity(unittest.TestCase):
    def setUp(self):
        self.v = dict(path='/fixture', uuid='fixture-fs', source='/dev/fixture', fstype='ext4')
        self.mount = dict(target='/fixture', uuid='fixture-fs', source='/dev/fixture',
                          fstype='ext4', options='rw,relatime', **{'maj:min': '8:1'})
        self.stat = types.SimpleNamespace(st_dev=os.makedev(8, 1))
        self.fs = types.SimpleNamespace(f_blocks=100, f_bfree=10, f_bavail=5, f_frsize=4096)

    def run_observation(self, row):
        with patch.object(m, 'mount', return_value=row), patch.object(m.os, 'stat', return_value=self.stat), \
                patch.object(m.os, 'statvfs', return_value=self.fs):
            return m.observe(self.v)

    def test_reserved_blocks_match_df_percent(self):
        self.assertEqual(self.run_observation(self.mount)['percent'], 95)

    def test_absent_replaced_readonly_or_aliased_mounts_rejected(self):
        for change in ({'target': '/'}, {'uuid': 'replacement'}, {'uuid': None},
                       {'source': '/dev/other'}, {'options': 'ro'}, {'fstype': 'tmpfs'},
                       {'maj:min': '8:2'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_observation({**self.mount, **change})

    def test_mount_change_during_read_rejected(self):
        with patch.object(m, 'mount', side_effect=[self.mount, {**self.mount, 'uuid': 'changed'}]), \
                patch.object(m.os, 'stat', return_value=self.stat), \
                patch.object(m.os, 'statvfs', return_value=self.fs), self.assertRaises(ValueError):
            m.observe(self.v)


class BridgeContract(unittest.TestCase):
    def test_actual_protocol_required_without_loading_connector_or_credentials(self):
        b = m.Bridge({'workspace_id': 'fixture', 'session_id': 'fixture'})
        for operation in (b.ready, lambda: b.send({}), lambda: b.lookup('batch', 'hash')):
            with self.assertRaises(m.ReviewedProtocolUnavailable):
                operation()

    def test_stable_batch_and_incident_binding_is_structured(self):
        with tempfile.TemporaryDirectory() as temp:
            s = m.Store(Path(temp) / 'state.db')
            try:
                b = FakeBridge()
                s.observations(b.samples, {}, time.time())
                self.assertEqual(s.dispatch(b.samples, b, 'private-fixture'), 'accepted')
                request = b.calls[0]
                uuid.UUID(request['batch_id'])
                for incident in request['intent']['incidents']:
                    uuid.UUID(incident['incident_id'])
                self.assertEqual(request['intent_sha256'], m.native.digest(request['intent']))
                self.assertEqual({k: request['intent'][k] for k in b.binding()}, b.binding())
            finally:
                s.close()


class ActivationBoundary(unittest.TestCase):
    def test_default_observation_never_opens_state_publisher_or_control(self):
        c = {'volumes': {'ssd': {}}, 'activation_approved': True}
        with patch.object(m.sys, 'argv', ['monitor.py', '--config', 'fixture']), \
                patch.object(m, 'read_config', return_value=c), \
                patch.object(m, 'sample_volume', return_value=sample()), \
                patch.object(m, 'Store', side_effect=AssertionError('state touched')), \
                patch.object(m, 'Bridge', side_effect=AssertionError('control touched')), \
                patch.object(m, 'publisher', side_effect=AssertionError('publisher touched')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            m.main()
        self.assertEqual(json.loads(output.getvalue())['mode'], 'observe_only')

    def test_active_flag_alone_cannot_admit(self):
        c = {'volumes': {}, 'activation_approved': False}
        with patch.object(m.sys, 'argv', ['monitor.py', '--config', 'fixture', '--activate']), \
                patch.object(m, 'read_config', return_value=c), \
                patch.object(m, 'Store', side_effect=AssertionError('state touched')), \
                self.assertRaisesRegex(ValueError, 'activation_not_approved'):
            m.main()

    def test_SSD_tuning_proposal_requires_its_own_activation_approval(self):
        c={'volumes':{'ssd':{'policy':m.pressure.SSD}},'activation_approved':True,'ssd_tuning_approved':False}
        with patch.object(m.sys,'argv',['monitor.py','--config','fixture','--activate']), \
                patch.object(m,'read_config',return_value=c), \
                patch.object(m,'sample_volume',return_value={**sample(),'policy':m.pressure.SSD}), \
                patch.object(m,'Store',side_effect=AssertionError('state touched')), \
                self.assertRaisesRegex(ValueError,'proposed_SSD_tuning_not_approved'):
            m.main()

    def test_second_monitor_cannot_open_the_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'state.db'
            c = {'activation_approved': True, 'volumes': {}, 'state_file': str(path),
                 'state_volume': {'path': temp, 'uuid': 'fixture'}}
            with path.with_suffix('.lock').open('a') as lock:
                m.fcntl.flock(lock, m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)
                with patch.object(m.sys, 'argv', ['monitor.py', '--config', 'fixture', '--activate']), \
                        patch.object(m, 'read_config', return_value=c), \
                        patch.object(m, 'observe', return_value=sample()), \
                        patch.object(m, 'mount', return_value={'uuid': 'fixture'}), \
                        patch.object(m, 'Store', side_effect=AssertionError('state touched')), \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    m.main()
            self.assertEqual(json.loads(output.getvalue())['status'], 'another_monitor_running')
            self.assertFalse(path.exists())

    def test_private_status_does_not_create_missing_state(self):
        spec = importlib.util.spec_from_file_location('status', ROOT / 'status.py')
        status = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(status)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'absent.sqlite'
            with self.assertRaises(sqlite3.OperationalError):
                status.status(path)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
