"""Offline regressions against the captured deployed connector, without patching it."""
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent / 'deployed-20261029'
sys.path[:0] = [str(ROOT / 'sidechat'), str(ROOT / 'connector')]
# Load the captured companion, not the shim's installed production directory.
sys.modules['sidechat_connector'] = importlib.import_module('connector')
import adapter
import test_recommend

PROJECT = '11111111-1111-4111-8111-111111111111'
ISSUE = '22222222-2222-4222-8222-222222222222'


class CurrentRecommend(test_recommend.Tests):
    def test_new_start_payload_shadow(self):
        # The old fixture predates mandatory issue scope. Exercise the same
        # Recommend payload assertion through the current preflight contract.
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass
            def read(self, _):
                return b'{"success":true,"data":{}}'
        with patch.object(adapter, 'http_get', return_value={'issues': [dict(id=ISSUE, project_id=PROJECT)]}), \
             patch.object(adapter.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = Response()
            adapter.local_start(dict(name='mock', prompt='mock', executor='CODEX',
                                     project_id=PROJECT, issue_id=ISSUE,
                                     model_id='chosen', reasoning_id='high',
                                     repositories=[dict(repo_id=PROJECT, branch='main')]))
            payload = json.loads(opener.return_value.open.call_args.args[0].data)
            config = payload['executor_config']
            self.assertEqual(config['routing']['mode'], 'shadow')
            self.assertEqual(config['model_id'], 'chosen')
            self.assertEqual(config['reasoning_id'], 'high')
            self.assertEqual(payload['linked_issue'], dict(issue_id=ISSUE, remote_project_id=PROJECT))


class CurrentDiscovery(unittest.TestCase):
    def test_additive_tools_and_broad_control_rejection(self):
        upstream = Mock()
        upstream.request.return_value = {'result': {'tools': []}}
        facade = adapter.Adapter(upstream)
        tools = facade.handle(dict(jsonrpc='2.0', id=1, method='tools/list'))['result']['tools']
        names = {tool['name'] for tool in tools}
        self.assertTrue(set(adapter.steering.HANDLERS) <= names)
        self.assertTrue(set(adapter.stop_control.HANDLERS) <= names)
        self.assertTrue(adapter.sidechat_connector.NAMES <= names)
        for name in ('shell', 'stop_execution', 'delete_workspace', 'generic_http'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                facade.handle(dict(jsonrpc='2.0', id=2, method='tools/call', params={'name': name}))

    def test_missing_issue_rejects_before_any_write(self):
        with patch.object(adapter.urllib.request, 'build_opener') as opener:
            with self.assertRaises(ValueError):
                adapter.local_start(dict(name='mock', prompt='mock', executor='CODEX'))
            opener.assert_not_called()


if __name__ == '__main__':
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite([loader.loadTestsFromName('test_capacity_queue'),
                               loader.loadTestsFromName('test_status_reads'),
                               loader.loadTestsFromTestCase(CurrentRecommend),
                               loader.loadTestsFromTestCase(CurrentDiscovery)])
    with patch('socket.create_connection', side_effect=AssertionError('Network forbidden in connector fixtures')):
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(not result.wasSuccessful())
