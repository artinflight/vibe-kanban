"""Read-only installed-baseline comparison and mocked reporting dispatch checks."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from prepare_usage_reporting import adapter as patch_adapter, status as patch_status
import usage_reporting


def nodes(source, exclude=()):
    return [ast.dump(n) for n in ast.parse(source).body if getattr(n, 'name', None) not in exclude]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--cu-workspace-id', required=True)
    args = parser.parse_args()
    raw = (args.installed / 'adapter.py').read_text()
    candidate = patch_adapter(raw)
    # Existing top-level execution/routing/read/write functions must be identical.
    before = {n.name: ast.dump(n) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
    after = {n.name: ast.dump(n) for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef)}
    assert before == after
    original_status = (args.installed / 'report_reconciliation.py').read_text()
    candidate_status = patch_status(original_status, args.cu_workspace_id)
    assert nodes(original_status, ('status',)) == nodes(candidate_status, ('status',))
    sys.path.append(str(args.installed))
    original = types.ModuleType('original_adapter')
    exec(compile(raw, 'original_adapter.py', 'exec'), original.__dict__)
    module = types.ModuleType('adapter')
    sys.modules['adapter'] = module
    exec(compile(candidate, 'candidate_adapter.py', 'exec'), module.__dict__)
    tests = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name)
        for name in ('test_capacity_queue', 'test_recommend', 'test_status_reads'))
    result = unittest.TextTestRunner(verbosity=1).run(tests)
    if not result.wasSuccessful():
        raise SystemExit(1)
    upstream = Mock()
    upstream.request.return_value = {'result': {'tools': [
        {'name': name, 'description': 'fixture', 'inputSchema': {'type': 'object'}}
        for name in sorted(original.ALLOWED)]}}
    old = original.Adapter(upstream)
    new = module.Adapter(upstream)
    message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
    old_tools = old.handle(message)['result']['tools']
    new_tools = new.handle(message)['result']['tools']
    added = {t['name'] for t in usage_reporting.TOOLS}
    assert old_tools == [t for t in new_tools if t['name'] not in added]
    assert len(new_tools) == len(old_tools) + len(added)
    init = new.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'initialize', 'params': {}})
    assert init['result']['serverInfo']['version'] == '1.6'
    for name in added:
        request = {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                   'params': {'name': name, 'arguments': {}}}
        with patch.object(usage_reporting, 'call', return_value=module.result({'fixture': name})) as call:
            response = new.handle(request)
            assert json.loads(response['result']['content'][0]['text']) == {'fixture': name}
            call.assert_called_once_with(module, name, {})
        for invalid in ([], False, 0, ''):
            request['params']['arguments'] = invalid
            with patch.object(usage_reporting, 'call') as call:
                try:
                    new.handle(request)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Non-object reporting arguments accepted')
                call.assert_not_called()
    for name in ('shell', 'delete_workspace', 'generic_http', 'stop_workspace', 'stop_execution'):
        try:
            new.handle({'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': name}})
        except ValueError:
            pass
        else:
            raise AssertionError('Unsupported control exposed')
    print(json.dumps({'existing_policy_read_tests': result.testsRun,
        'existing_tool_schemas_exactly_preserved': True, 'status_only_ast_change': True,
        'reporting_discovery_dispatch_invalid_args': 'passed', 'real_writes': 0,
        'candidate_adapter_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
        'candidate_status_sha256': hashlib.sha256(candidate_status.encode()).hexdigest()}))


if __name__ == '__main__':
    main()
