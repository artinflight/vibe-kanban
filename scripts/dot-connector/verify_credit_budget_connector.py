"""Verify installed-source policy preservation and budget dispatch without writes."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import credit_budget
from prepare_credit_budget_connector import patched


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--live-readback', action='store_true')
    args = parser.parse_args()
    raw = (args.source / 'adapter.py').read_text()
    candidate = raw if args.installed else patched(raw)
    def functions(source):
        return {node.name: ast.dump(node) for node in ast.parse(source).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert functions(raw) == functions(candidate), 'Existing policy/read/write functions changed'
    sys.path.append(str(args.source))
    module = types.ModuleType('adapter')
    sys.modules['adapter'] = module
    exec(compile(candidate, 'isolated-budget-adapter.py', 'exec'), module.__dict__)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name)
        for name in ('test_capacity_queue', 'test_recommend', 'test_status_reads'))
    tests = unittest.TextTestRunner(verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise SystemExit(1)
    upstream = Mock()
    upstream.request.return_value = {'result': {'tools': []}}
    facade = module.Adapter(upstream)
    initialized = facade.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {}})
    assert initialized['result']['serverInfo']['version'] == '1.5'
    tools = facade.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result']['tools']
    names = [tool['name'] for tool in tools]
    assert names.count('get_credit_budget') == 1
    assert set(module.stop_control.HANDLERS) <= set(names)
    assert module.sidechat_connector.NAMES <= set(names)
    assert next(t for t in tools if t['name'] == 'get_credit_budget') == credit_budget.TOOLS[0]
    request = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
               'params': {'name': 'get_credit_budget', 'arguments': {}}}
    with patch.object(credit_budget, 'read_credit_budget', return_value={'fixture': True}) as read:
        reply = facade.handle(request)
        assert json.loads(reply['result']['content'][0]['text']) == {'fixture': True}
        read.assert_called_once_with()
    for invalid in ([], False, 0, '', {'url': 'http://elsewhere/'}, {'refresh': True}):
        request['params']['arguments'] = invalid
        with patch.object(credit_budget, 'read_credit_budget') as read:
            try:
                facade.handle(request)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid budget arguments accepted')
            read.assert_not_called()
    for name in ('stop_execution', 'stop_workspace', 'shell', 'delete_workspace', 'generic_http'):
        try:
            facade.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': name}})
        except ValueError:
            pass
        else:
            raise AssertionError('Broad/unsupported control exposed')
    output = {'existing_regressions_passed': tests.testsRun,
        'budget_discovery_dispatch': 'passed', 'stop_and_sidechat_preserved': True,
        'broad_stop_shell_admin_denied': True, 'live_writes': 0,
        'baseline_sha256': hashlib.sha256(raw.encode()).hexdigest(),
        'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest()}
    if args.live_readback:
        request['params']['arguments'] = {}
        live = json.loads(facade.handle(request)['result']['content'][0]['text'])
        assert live['status'] == 'current' and live['fresh'] is True
        output['live_readback'] = {'status': live['status'], 'fresh': live['fresh'],
            'contractVersion': live['readback']['contractVersion'], 'version': live['readback']['version']}
    print(json.dumps(output))


if __name__ == '__main__':
    main()
