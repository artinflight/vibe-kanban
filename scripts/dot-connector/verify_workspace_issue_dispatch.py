"""Offline full-adapter dispatch acceptance. All reads and starts are mocked.

Requires the retained private adapter/dependencies; never starts its main loop,
upstream server, live tool request, validation workspace or agent.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    args = parser.parse_args()
    raw = args.adapter.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise SystemExit('Candidate changed; reconcile before testing')
    sys.path[:0] = [str(args.adapter.parent), str(args.dependencies), str(Path(__file__).parent)]
    spec = importlib.util.spec_from_file_location('adapter', args.adapter)
    adapter = importlib.util.module_from_spec(spec)
    sys.modules['adapter'] = adapter
    spec.loader.exec_module(adapter)
    from test_workspace_issue_context import PROJECT, ISSUE, OTHER, failure_cases, assert_error
    test = unittest.TestCase()
    upstream = Mock()
    facade = adapter.Adapter(upstream)
    base = {'project_id': PROJECT, 'issue_id': ISSUE, 'name': 'Synthetic offline acceptance',
            'prompt': 'Synthetic request; no live action', 'executor': 'CODEX', 'model_id': 'chosen',
            'reasoning_id': 'high', 'repositories': [{'repo_id': OTHER, 'branch': 'staging'}]}

    def dispatch(values):
        return facade.handle({'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
                              'params': {'name': 'start_workspace', 'arguments': values}})

    for values, evidence, code in failure_cases():
        # Keep valid non-context start inputs. Missing IDs remain truly missing.
        merged = {k: v for k, v in base.items() if k not in ('project_id', 'issue_id')}
        merged.update(values)
        read = Mock(side_effect=evidence) if isinstance(evidence, Exception) else Mock(return_value=evidence)
        with patch.object(adapter, 'http_get', read), patch.object(adapter.urllib.request, 'build_opener') as post:
            response = dispatch(merged)
            test.assertEqual({'jsonrpc', 'id', 'result'}, set(response))
            test.assertEqual(7, response['id'])
            assert_error(test, response['result'], code)
            post.assert_not_called()
        upstream.request.assert_not_called()
        if code in ('workspace_issue_ids_missing', 'workspace_issue_ids_invalid'):
            read.assert_not_called()
        else:
            read.assert_called_once_with('/v1/fallback/issues?project_id='+PROJECT)

    class Response:
        def __enter__(self): return self
        def __exit__(self, *unused): pass
        def read(self, limit): return b'{"success":true,"data":{"id":"mock-workspace","task_id":"22222222-2222-4222-8222-222222222222"}}'

    evidence = {'issues': [{'id': ISSUE, 'project_id': PROJECT}]}
    with patch.object(adapter, 'http_get', return_value=evidence), patch.object(adapter.urllib.request, 'build_opener') as post:
        post.return_value.open.return_value = Response()
        response = dispatch(base)
        post.return_value.open.assert_called_once()
        request = post.return_value.open.call_args.args[0]
        test.assertEqual('http://127.0.0.1:4720/api/workspaces/start', request.full_url)
        test.assertEqual('POST', request.get_method())
        test.assertEqual({'name': base['name'], 'prompt': base['prompt'],
                          'repos': [{'repo_id': OTHER, 'target_branch': 'staging'}],
                          'linked_issue': {'issue_id': ISSUE, 'remote_project_id': PROJECT},
                          'executor_config': {'executor': 'CODEX', 'variant': 'DEFAULT',
                              'model_id': 'chosen', 'reasoning_id': 'high',
                              'routing': {'mode': 'shadow', 'floor': 'assessed',
                                          'denied_models': [], 'allow_escalation': False}}}, json.loads(request.data))
        test.assertEqual({'id': 'mock-workspace', 'task_id': ISSUE}, json.loads(response['result']['content'][0]['text']))
        test.assertFalse(response['result']['isError'])
    # Once a POST has been attempted it must never become a known safe rejection.
    with patch.object(adapter, 'http_get', return_value=evidence), patch.object(adapter.urllib.request, 'build_opener') as post:
        post.return_value.open.side_effect = TimeoutError('uncertain mocked start')
        with test.assertRaises(TimeoutError): dispatch(base)
        post.return_value.open.assert_called_once()
    suite = unittest.TestSuite()
    for name in ('test_capacity_queue', 'test_recommend', 'test_status_reads'):
        def add(group):
            for case in group:
                if isinstance(case, unittest.TestSuite): add(case)
                elif case._testMethodName != 'test_new_start_payload_shadow': suite.addTest(case)
        add(unittest.defaultTestLoader.loadTestsFromName(name))
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print(json.dumps({'adapterSha256': args.sha256, 'fullDispatchRejectionCases': len(failure_cases()),
                      'exactErrorFieldsAndMessages': True, 'negativeStartPosts': 0,
                      'scopedReadOnly': True, 'outsideProjectExistenceNotDisclosed': True,
                      'validIssueLinkedPayloadAndResponseUnchanged': True, 'validMockedPostCount': 1,
                      'postTimeoutNotMisreportedAsPreflightRejection': True,
                      'incumbentControls': result.testsRun, 'liveNetworkCalls': 0,
                      'liveStartProbes': 0, 'realAgentsOrWorkspacesCreated': 0}))


if __name__ == '__main__': main()
