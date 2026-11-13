import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from vk_restart_tracking_client import deliver_when_ready


class SourceReady(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-ready-wait-', dir='/dev/shm')
        self.path = Path(self.temp.name) / 'health.json'
        self.now = 0.0
        self.health = {'phase': 'tracking', 'raw_errors': [], 'instance': 'epoch',
                       'owner_pid': 12, 'owner_start_ticks': 34,
                       'plan_sha256': 'plan', 'scope_sha256': 'scope',
                       'coverage_model': 'all-selected-inodes-v1',
                       'required_root_bindings': {'/root': {}}, 'heartbeat_utc': time.time(),
                       'ready': True, 'sequence': 3}
        self.write_health()
        self.responses = [self.report(True)]
        self.deliver_calls = 0
        self.waits = []
        self.module = SimpleNamespace(identity=lambda value: value['identity'],
                                      scope=lambda value: {'identity': 'scope'},
                                      query=lambda *_: None, request=self.request)
        self.client = SimpleNamespace(module=self.module, instance='epoch', endpoint=Path('/dev/shm/bound.sock'),
                                      owner=(12, 34, os.getuid()), timeout=90,
                                      check=lambda: None, query=self.module.query)
        self.source = SimpleNamespace(reference={'instance': 'epoch'},
                                      config={'endpoint': str(self.client.endpoint), 'status': str(self.path)},
                                      plan={'identity': 'plan', 'sources': ['/root']},
                                      check=lambda: self.health, deliver=self.deliver)

    def tearDown(self):
        self.temp.cleanup()

    def write_health(self):
        self.path.write_text(json.dumps(self.health))
        self.path.chmod(0o600)

    def report(self, ready):
        return {'ready': ready, 'errors': [], 'terminal': None, 'instance': 'epoch',
                'plan_sha256': 'plan', 'scope_sha256': 'scope',
                'coverage_model': 'all-selected-inodes-v1'}

    def request(self, *_args, **_kwargs):
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    def deliver(self):
        self.deliver_calls += 1
        return {'actual_native_B_reopen_verified': True, 'local_acknowledged': 7}

    def sleep(self, seconds):
        self.now += seconds

    def run_wait(self, seconds=1):
        return deliver_when_ready(self.source, self.client, maximum_seconds=seconds,
                                  on_wait=self.waits.append, clock=lambda: self.now, sleep=self.sleep)

    def test_real_unready_then_ready_never_changes_the_reports(self):
        unready = self.report(False)
        self.responses = [unready, self.report(True)]
        result = self.run_wait()
        self.assertTrue(result['actual_native_B_reopen_verified'])
        self.assertFalse(unready['ready'])
        self.assertEqual(self.deliver_calls, 1)
        self.assertEqual(self.client.timeout, 90)

    def test_exact_ready_race_waits_for_another_actual_barrier(self):
        calls = []
        def deliver():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError('complete actual barrier required for delivery')
            return {'verified': True}
        self.source.deliver = deliver
        self.assertEqual(self.run_wait(), {'verified': True})
        self.assertEqual(len(calls), 2)

    def test_real_coverage_error_is_never_waited_out(self):
        self.responses[0]['errors'] = [{'lost': 'kernel coverage'}]
        with self.assertRaisesRegex(ValueError, 'fault'):
            self.run_wait()
        self.assertEqual(self.deliver_calls, 0)

    def test_terminal_epoch_and_changed_plan_are_never_retried(self):
        for key, value in [('terminal', 'owner exited'), ('instance', 'another'), ('plan_sha256', 'changed')]:
            self.responses = [self.report(True)]
            self.responses[0][key] = value
            with self.assertRaisesRegex(ValueError, 'fault'):
                self.run_wait()
        self.assertEqual(self.deliver_calls, 0)

    def test_persistent_unready_expires_without_delivery(self):
        self.responses = [self.report(False)]
        with self.assertRaises(TimeoutError):
            self.run_wait(.5)
        self.assertEqual(self.deliver_calls, 0)
        self.assertEqual(self.client.timeout, 90)

    def test_native_access_or_health_failure_does_not_retry(self):
        def failed():
            self.deliver_calls += 1
            raise ValueError('native B access denied or actual health fault')
        self.source.deliver = failed
        with self.assertRaisesRegex(ValueError, 'native B'):
            self.run_wait()
        self.assertEqual(self.deliver_calls, 1)


if __name__ == '__main__':
    unittest.main()
