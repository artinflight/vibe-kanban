"""Verify the prepared adapter against read-only installed source, entirely offline."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from prepare_launcher_connector import patched
import launcher

SID = 'dfca0918-0fd6-4f68-9b05-d90c068b6367'
PID = 'ec9a128a-0e87-42ee-bef6-a3a87f44fed5'
EID = '650e4e6a-dfb2-4219-9dc0-7f85de5e9628'
CONFIG = {'executor': 'CLAUDE_CODE', 'model_id': 'sonnet', 'reasoning_id': 'high', 'permission_policy': 'PLAN'}


def functions(source):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


def load(source, name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, '<offline-launcher-candidate>', 'exec'), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    raw = (args.source / 'adapter.py').read_text()
    candidate = patched(raw)
    before, after = functions(raw), functions(candidate)
    for old, new in (('local_start', 'codex_local_start'), ('local_followup', 'codex_local_followup'), ('recommend_config', 'codex_recommend_config')):
        node = ast.parse(raw)
        fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == old)
        fn.name = new
        assert ast.dump(fn) == after[new], old + ' behavior changed'
    for name in before.keys() - {'local_start', 'local_followup', 'recommend_config', 'resolve_followup_config'}:
        assert before[name] == after[name], name + ' changed'
    sys.path.append(str(args.source))
    module = load(candidate, 'adapter')
    # Old Recommend tests predate mandatory issue association; supply their
    # prerequisite in isolation. Separate real-preflight fixtures below prove it.
    with patch('workspace_issue_context.require_issue_context', return_value={'project_id': PID, 'issue_id': EID}):
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name)
                                  for name in ('test_capacity_queue', 'test_recommend', 'test_status_reads'))
        tests = unittest.TextTestRunner(verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise SystemExit(1)
    from jsonschema import Draft202012Validator
    upstream = Mock()
    upstream.request.return_value = {'result': {'tools': [{'name': name, 'inputSchema': {'type': 'object', 'properties': {'name':{'type':'string'}, 'prompt':{'type':'string'}, 'repositories':{'type':'array'}, 'session_id':launcher.UUID}}, 'description': 'Existing tool'}
                                                        for name in ('start_workspace', 'run_session_prompt', 'create_session', 'shell', 'stop_execution')]}}
    facade = module.Adapter(upstream)
    tools = facade.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result']['tools']
    by_name = {tool['name']: tool for tool in tools}
    assert by_name['start_workspace']['inputSchema']['properties']['executor']['enum'] == ['CODEX', 'CLAUDE_CODE']
    assert by_name['run_session_prompt']['inputSchema']['additionalProperties'] is False
    assert set(launcher.HANDLERS) <= by_name.keys()
    assert 'shell' not in by_name and 'stop_execution' not in by_name
    assert module.sidechat_connector.NAMES <= by_name.keys()
    assert set(module.stop_control.HANDLERS) <= by_name.keys()
    assert module.ALLOWED == module.READ | module.WRITE
    for tool in tools:
        Draft202012Validator.check_schema(tool['inputSchema'])
    validator = Draft202012Validator(by_name['start_workspace']['inputSchema'])
    for good in ({'executor':'CLAUDE_CODE','model_id':'sonnet','reasoning_id':'high','prompt':'Task','project_id':PID,'issue_id':EID},
                 {'executor':'CODEX','model_id':'exact-owner-choice','reasoning_id':'xhigh','prompt':'Task','project_id':PID,'issue_id':EID}):
        good.update(name='Fixture', repositories=[{'repo_id':SID,'branch':'staging'}])
        assert validator.is_valid(good), list(validator.iter_errors(good))
    for bad in ({'executor':'CLAUDE','prompt':'Task','project_id':PID,'issue_id':EID},
                {'executor':'CLAUDE_CODE','prompt':'Task','project_id':PID,'issue_id':EID},
                {'executor':'CLAUDE_CODE','model_id':'unsupported-model','prompt':'Task','project_id':PID,'issue_id':EID},
                {'executor':'CODEX','permission_policy':'AUTO','prompt':'Task','project_id':PID,'issue_id':EID},
                {'executor':'CLAUDE_CODE','model_id':'sonnet','reasoning_id':'xhigh','prompt':'Task','project_id':PID,'issue_id':EID}):
        bad.update(name='Fixture', repositories=[{'repo_id':SID,'branch':'staging'}])
        assert not validator.is_valid(bad), bad

    def call(name, arguments):
        return facade.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})

    # Authentication/caller attribution stays inside the existing observer.
    with patch('dispatch_notes.observe', side_effect=lambda kind, args, value, **kw: value) as observe, patch('dispatch_notes.current_caller', return_value={'kind': 'fixture'}):
        start = {'name': 'Fixture', 'executor': 'CLAUDE_CODE', 'model_id': 'sonnet', 'reasoning_id': 'high',
                 'prompt': 'Explicit owner task', 'repositories': [{'repo_id': SID, 'branch': 'staging'}], 'project_id': PID, 'issue_id': EID}
        with patch.object(module, 'http_get', return_value={'issues': [{'id': EID, 'project_id': PID}]}), patch.object(module, 'post_fixed', return_value={'workspace': {'id': SID}}) as post:
            call('start_workspace', start)
            assert post.call_count == 1
            path, payload = post.call_args.args
            assert path == '/api/workspaces/start'
            assert payload['executor_config']['executor'] == 'CLAUDE_CODE'
            assert payload['executor_config']['model_id'] == 'sonnet'
            assert payload['executor_config']['reasoning_id'] == 'high'
            assert payload['repos'] == [{'repo_id': SID, 'target_branch': 'staging'}]
        assert observe.call_args.args[0] == 'start_workspace'
        module.handoff_result({'status':'started','target_session_id':SID,'target_execution_id':EID})
        assert observe.call_args.args[0] == 'run_session_prompt'
        assert observe.call_args.args[1] == {'session_id':SID}
        assert json.loads(observe.call_args.args[2]['content'][0]['text']) == {'execution_id':EID}
        with patch.object(module, 'http_get', return_value={'issues': []}), patch.object(module, 'post_fixed') as post:
            reply = call('start_workspace', start)
            assert reply['result']['isError'] is True
            post.assert_not_called()
        for executor, selected in [('CLAUDE_CODE', CONFIG), ('CODEX', dict(CONFIG, executor='CODEX', model_id='gpt-6.1-sol'))]:
            with patch.object(module, 'http_get', side_effect=[{'success': True, 'data': {'id': SID, 'executor': executor}}, {'success': True, 'data': None}]), patch.object(module, 'session_configs', return_value=[{'config': selected}]), patch.object(module, 'post_fixed', return_value={'id': EID}) as post:
                call('run_session_prompt', {'session_id': SID, 'prompt': 'Continue explicit task'})
                assert post.call_count == 1
                assert post.call_args.args[1]['executor_config']['model_id'] == selected['model_id']
                assert post.call_args.args[1]['executor_config']['reasoning_id'] == selected['reasoning_id']
                assert post.call_args.args[1]['executor_config']['permission_policy'] == selected['permission_policy']
            assert observe.call_args.args[0] == 'run_session_prompt'
        with patch.object(module, 'http_get', side_effect=[{'success': True, 'data': {'id':SID,'executor':'CODEX'}}, {'success':True,'data':{'payload':{'data':{'executor_config':CONFIG}}}}]), patch.object(module, 'session_configs', return_value=[{'config':{'executor':'CODEX'}}]), patch.object(module, 'post_fixed') as post:
            try:
                call('run_session_prompt', {'session_id':SID,'prompt':'Continue'})
            except ValueError:
                pass
            else:
                raise AssertionError('Cross-executor draft was accepted')
            post.assert_not_called()
        for executor in ('CLAUDE_CODE', 'CODEX'):
            row = {'id': EID, 'session_id': SID, 'status': 'running', 'created_at': 'fixture', 'config': dict(CONFIG, executor=executor)}
            with patch.object(module, 'http_get', return_value={'success': True, 'data': {'id': SID, 'executor': executor}}), patch.object(module.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps([row]))), patch.object(module, 'post_fixed') as post:
                try:
                    call('run_session_prompt', {'session_id': SID, 'prompt': 'Continue'})
                except ValueError as error:
                    assert 'running' in str(error)
                else:
                    raise AssertionError('Running source accepted')
                post.assert_not_called()
    for name in launcher.HANDLERS:
        handler = Mock(return_value=module.result({'fixture': True}))
        with patch.dict(launcher.HANDLERS, {name: handler}):
            call(name, {'fixture': True})
        handler.assert_called_once_with(module, {'fixture': True})
    for name in ('shell', 'generic_http', 'delete_workspace', 'stop_execution', 'stop_workspace', 'merge'):
        try:
            call(name, {})
        except ValueError:
            pass
        else:
            raise AssertionError('Forbidden tool exposed')
    print(json.dumps({'baseline_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                      'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
                      'launcher_sha256': hashlib.sha256(Path(launcher.__file__).read_bytes()).hexdigest(),
                      'legacy_policy_capacity_status_regressions': tests.testsRun,
                      'exact_executor_schema_dispatch_issue_scope_observer_and_allowlist_checks': 'passed',
                      'live_calls': 0, 'live_writes': 0}))


if __name__ == '__main__':
    main()
