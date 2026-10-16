import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('watch', Path(__file__).with_name('connectivity_watch.py'))
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class ConnectivityTests(unittest.TestCase):
    def test_distinguishes_native_child_timeout_from_network_timeout(self):
        prefix = 'list_models: failed to refresh available models: '
        self.assertEqual(watch.classify(prefix + 'request timed out'), 'model_refresh_request_timeout')
        self.assertEqual(watch.classify(prefix + 'timeout waiting for child process to exit'),
                         'model_refresh_child_timeout')
        self.assertEqual(watch.classify('account/read request failed: workspace routing discovery timed out'),
                         'routing_discovery_timeout')
        self.assertEqual(watch.classify(list(b'\x1b[31mworkspace routing discovery timed out')),
                         'routing_discovery_timeout')
        self.assertIsNone(watch.classify(['unexpected', 'journal', 'field']))

    def test_dns_retains_status_and_only_ip_answers(self):
        output = ';; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1\n'
        output += 'github.com. 60 IN CNAME example.com.\nexample.com. 60 IN A 140.82.114.3\n'
        with patch.object(watch, 'run', return_value=(0, output)):
            event = watch.dns_probe('github.com', '127.0.0.53')
        self.assertEqual(event['answers'], ['140.82.114.3'])
        with patch.object(watch, 'run', return_value=(0, 'status: SERVFAIL')):
            self.assertEqual(watch.dns_probe('github.com', '127.0.0.53')['status'], 'SERVFAIL')
        with patch.object(watch, 'run', return_value=(-6, '')):
            self.assertTrue(watch.dns_probe('github.com', '127.0.0.53')['probe_error'])

    def test_http_denial_still_records_working_transport(self):
        with patch.object(watch, 'run', return_value=(0, '403 1.2.3.4 0.01 0.02 0.04 0.05 0.06')) as run:
            event = watch.https_probe('chatgpt.com')
        self.assertTrue(event['transport_ok'])
        self.assertEqual(event['http_status'], 403)
        self.assertEqual(event['tls_s'], 0.04)
        argv = run.call_args.args[0]
        self.assertIn('-q', argv)
        self.assertIn('--noproxy', argv)
        self.assertNotIn('--insecure', argv)

    def test_dns_failure_and_command_timeout_do_not_log_error_bodies(self):
        with patch.object(watch, 'run', return_value=(6, '000  0.000 0 0 0 0')):
            event = watch.https_probe('github.com')
        self.assertFalse(event['transport_ok'])
        self.assertEqual(event['exit'], 6)
        with patch.object(watch.subprocess, 'run', side_effect=watch.subprocess.TimeoutExpired('curl', 1)):
            self.assertEqual(watch.run(['curl']), (124, ''))

    def native_fixture(self, directory):
        path = Path(directory) / 'logs.sqlite'
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE logs(id INTEGER PRIMARY KEY, ts INTEGER, level TEXT, '
                               'target TEXT, feedback_log_body TEXT, thread_id TEXT, process_uuid TEXT)')
            for ident, level, target in (
                (1, 'DEBUG', 'codex_core::session::handlers'),
                (2, 'ERROR', 'codex_core::tools::handlers'),
                (3, 'ERROR', 'codex_models_manager::manager'),
            ):
                connection.execute('INSERT INTO logs VALUES(?,?,?,?,?,?,?)',
                                   (ident, int(time.time()), level, target,
                                    'failed to refresh available models: request timed out SECRET',
                                    '01a1453b-3fb7-7021-b990-03e64b7169ed', 'pid:123:abcd'))
        instance = watch.Watcher.__new__(watch.Watcher)
        instance.args = SimpleNamespace(codex_logs=path, lookback=600)
        instance.state = {}
        instance.recent = watch.deque(maxlen=256)
        events = []
        instance.emit = events.append
        return instance, events

    def test_native_cursor_and_privacy_ignore_quoted_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            instance, events = self.native_fixture(directory)
            instance.native_events()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['native_id'], 3)
            self.assertNotIn('SECRET', str(events))
            instance.native_events()
            self.assertEqual(len(events), 1)
            # A persisted cursor is reused after a process restart.
            resumed, replay = self.native_fixture_restart(instance)
            resumed.native_events()
            self.assertEqual(replay, [])

    def native_fixture_restart(self, previous):
        resumed = watch.Watcher.__new__(watch.Watcher)
        resumed.args = previous.args
        resumed.state = dict(previous.state)
        resumed.recent = watch.deque(maxlen=256)
        events = []
        resumed.emit = events.append
        return resumed, events

    def test_replaced_native_database_recovers_from_smaller_id(self):
        with tempfile.TemporaryDirectory() as directory:
            instance, events = self.native_fixture(directory)
            instance.state['native_id'] = 999
            instance.native_events()
            self.assertEqual(len(events), 1)
            self.assertEqual(instance.state['native_id'], 3)

    def test_rotation_keeps_bounded_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            handler = watch.RotatingFileHandler(path, maxBytes=100, backupCount=2)
            logger = watch.logging.Logger('fixture')
            logger.addHandler(handler)
            for _ in range(20):
                logger.warning('x' * 60)
            handler.close()
            self.assertEqual(len(list(Path(directory).glob('events.jsonl*'))), 3)

    def test_journal_timeout_retains_cursor_then_deduplicates_recovery(self):
        instance = watch.Watcher.__new__(watch.Watcher)
        instance.args = SimpleNamespace(lookback=7200)
        instance.state = {'journal_since': 100}
        events = []
        instance.emit = events.append
        discovery = (0, 'vibe-kanban-native-review-20261015.service loaded active running VK')
        with patch.object(watch, 'run', side_effect=[discovery, (124, '')]):
            instance.journal_events()
        self.assertEqual(instance.state['journal_since'], 100)
        row = {'__CURSOR': 'fixture', '__REALTIME_TIMESTAMP': '1792160644981018',
               '_SYSTEMD_USER_UNIT': 'vibe-kanban-native-review-20261015.service',
               'MESSAGE': 'Codex spawn error: account/read request failed: workspace routing discovery timed out SECRET'}
        with patch.object(watch, 'run', side_effect=[discovery, (0, watch.json.dumps(row)),
                                                   discovery, (0, watch.json.dumps(row))]):
            instance.journal_events()
            instance.journal_events()
        self.assertEqual([e['kind'] for e in events], ['source_error', 'journal_error'])
        self.assertNotIn('SECRET', str(events))

    def test_journal_discovers_replacement_service_without_historical_glob(self):
        instance = watch.Watcher.__new__(watch.Watcher)
        instance.args = SimpleNamespace(lookback=600)
        instance.state = {'journal_since': 100}
        events = []
        instance.emit = events.append
        with patch.object(watch, 'run', side_effect=[
            (0, 'vibe-kanban-next.service loaded active running VK'), (1, ''),
        ]) as run:
            instance.journal_events()
        query = run.call_args_list[1].args[0]
        self.assertIn('vibe-kanban-next.service', query)
        self.assertNotIn('vibe-kanban*.service', query)
        self.assertGreater(instance.state['journal_since'], 100)
        self.assertEqual(events, [])

    def test_fixed_expiry_does_not_start_probes_after_restart(self):
        argv = ['watch', '--output', '/mnt/vk-storage/fixture', '--codex-logs', '/fixture',
                '--vk-db', '/fixture', '--until', '1']
        with patch('sys.argv', argv), patch.object(watch, 'Watcher') as watcher:
            watch.main()
        watcher.return_value.cycle.assert_not_called()


if __name__ == '__main__':
    unittest.main()
