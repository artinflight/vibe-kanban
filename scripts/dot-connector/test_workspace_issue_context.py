import hashlib
import json
import types
import unittest
from unittest.mock import Mock

from workspace_issue_context import IssueContextError, dispatch_start, require_issue_context
from prepare_workspace_issue import prepare

PROJECT = '11111111-1111-4111-8111-111111111111'
ISSUE = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'
EXPECTED = {
    'workspace_issue_ids_missing': {
        'code': 'workspace_issue_ids_missing',
        'reason': 'Workspace creation was blocked because both project_id and issue_id are required.',
        'next_step': 'Create or select an issue in Vibe, then provide its project_id and issue_id.'},
    'workspace_issue_ids_invalid': {
        'code': 'workspace_issue_ids_invalid',
        'reason': 'Workspace creation was blocked because project_id or issue_id is not a valid UUID.',
        'next_step': 'Copy the project and issue UUIDs from Vibe, then submit the matching IDs again.'},
    'workspace_issue_not_verified': {
        'code': 'workspace_issue_not_verified',
        'reason': 'The issue could not be verified in the selected project.',
        'next_step': 'List issues in the selected project and select one, or create a dedicated issue there; '
                     'then provide its project_id and issue_id.'},
    'workspace_issue_lookup_unavailable': {
        'code': 'workspace_issue_lookup_unavailable',
        'reason': 'Vibe could not complete the selected project issue lookup.',
        'next_step': 'Retry the read-only project issue lookup when Vibe is available; '
                     'start the workspace only after issue verification succeeds.'},
    'workspace_issue_lookup_malformed': {
        'code': 'workspace_issue_lookup_malformed',
        'reason': 'Vibe returned incomplete or malformed project issue evidence.',
        'next_step': 'Check the project issue service response and retry the read-only lookup; '
                     'start the workspace only after complete, valid evidence is available.'},
}


def failure_cases():
    args = {'project_id': PROJECT, 'issue_id': ISSUE}
    return [
        ({}, None, 'workspace_issue_ids_missing'),
        ({'project_id': PROJECT}, None, 'workspace_issue_ids_missing'),
        (dict(args, issue_id=None), None, 'workspace_issue_ids_missing'),
        (dict(args, issue_id=' '), None, 'workspace_issue_ids_missing'),
        (dict(args, issue_id='bad'), None, 'workspace_issue_ids_invalid'),
        (dict(args, project_id=True), None, 'workspace_issue_ids_invalid'),
        (dict(args, issue_id=42), None, 'workspace_issue_ids_invalid'),
        (args, {'issues': []}, 'workspace_issue_not_verified'),
        (args, {'issues': [{'id': OTHER, 'project_id': PROJECT}]}, 'workspace_issue_not_verified'),
        (args, {'issues': [{'id': ISSUE, 'project_id': OTHER, 'title': 'private outside scope'}]}, 'workspace_issue_not_verified'),
        (args, TimeoutError('private timeout details'), 'workspace_issue_lookup_unavailable'),
        (args, ValueError('private malformed JSON'), 'workspace_issue_lookup_unavailable'),
        (args, {'success': False, 'issues': [], 'error': 'private service details'}, 'workspace_issue_lookup_unavailable'),
        (args, {'issues': None}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [None]}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [{'id': ISSUE}]}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [{'id': ISSUE, 'project_id': 'invalid'}]}, 'workspace_issue_lookup_malformed'),
        (args, [], 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'complete': False}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'complete': 'true'}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'success': 'false'}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'has_more': 'false'}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'next_offset': 10}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'next_cursor': 'private cursor'}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'has_more': True}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [], 'total': 1}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [{'id': ISSUE, 'project_id': PROJECT}]*2}, 'workspace_issue_lookup_malformed'),
        (args, {'issues': [{'id': ISSUE, 'project_id': PROJECT}, None]}, 'workspace_issue_lookup_malformed'),
    ]


def assert_error(test, result, code):
    expected = EXPECTED[code]
    test.assertEqual({'isError': True, 'content': [{'type': 'text', 'text': json.dumps(expected, sort_keys=True)}],
                      'structuredContent': expected}, result)
    test.assertEqual(expected, json.loads(result['content'][0]['text']))
    test.assertNotIn('private', json.dumps(result))
    test.assertNotIn(OTHER, json.dumps(result))


class ContextTests(unittest.TestCase):
    def test_exact_error_contract_and_scope_bound_lookup(self):
        for args, evidence, code in failure_cases():
            with self.subTest(code=code, evidence=type(evidence).__name__, args=args):
                read = Mock(side_effect=evidence) if isinstance(evidence, Exception) else Mock(return_value=evidence)
                with self.assertRaises(IssueContextError) as caught:
                    require_issue_context(args, read)
                error = caught.exception
                self.assertEqual(EXPECTED[code], error.detail)
                self.assertEqual(EXPECTED[code]['reason']+' Next step: '+EXPECTED[code]['next_step'], str(error))
                assert_error(self, error.tool_result(), code)
                if code in ('workspace_issue_ids_missing', 'workspace_issue_ids_invalid'):
                    read.assert_not_called()
                else:
                    read.assert_called_once_with('/v1/fallback/issues?project_id='+PROJECT)

    def test_absence_and_positive_wrong_project_are_indistinguishable(self):
        results = []
        for page in ({'issues': []}, {'issues': [{'id': ISSUE, 'project_id': OTHER}]}):
            def start(args): require_issue_context(args, lambda path: page)
            results.append(dispatch_start(start, {'project_id': PROJECT, 'issue_id': ISSUE}))
        self.assertEqual(results[0], results[1])

    def test_valid_context_keeps_input_and_only_reads_selected_project(self):
        args = {'project_id': PROJECT, 'issue_id': ISSUE, 'prompt': 'private prompt'}
        read = Mock(return_value={'issues': [{'id': ISSUE, 'project_id': PROJECT}], 'complete': True, 'total': 1})
        self.assertEqual({'project_id': PROJECT, 'issue_id': ISSUE}, require_issue_context(args, read))
        self.assertEqual('private prompt', args['prompt'])
        read.assert_called_once_with('/v1/fallback/issues?project_id='+PROJECT)

    def test_dispatch_preserves_success_and_does_not_hide_post_uncertainty(self):
        success = {'isError': False, 'content': [{'type': 'text', 'text': 'unchanged'}]}
        self.assertIs(success, dispatch_start(Mock(return_value=success), {}))
        for error in (TimeoutError('uncertain start'), ValueError('other validation')):
            with self.assertRaises(type(error)):
                dispatch_start(Mock(side_effect=error), {})

    def test_prepared_dispatch_reports_exact_fields_and_never_posts_on_rejection(self):
        source = b'''def local_start(args):
    require_issue_context(args, http_get)
    return start_post(args)
class Adapter:
    def handle(self, msg):
        name, args = msg["params"]["name"], msg["params"]["arguments"]
        if name:
            if name == "start_workspace": return {"jsonrpc":"2.0","id":msg["id"],"result":local_start(args)}
def untouched(): return 42
'''
        candidate = prepare(source, hashlib.sha256(source).hexdigest())
        ns = {'require_issue_context': require_issue_context}
        exec(candidate, ns)
        for args, evidence, code in failure_cases():
            with self.subTest(code=code):
                read = Mock(side_effect=evidence) if isinstance(evidence, Exception) else Mock(return_value=evidence)
                post = Mock()
                ns.update(http_get=read, start_post=post)
                response = ns['Adapter']().handle({'id': 7, 'params': {'name': 'start_workspace', 'arguments': args}})
                self.assertEqual(7, response['id'])
                assert_error(self, response['result'], code)
                post.assert_not_called()
        self.assertEqual(42, ns['untouched']())
        with self.assertRaises(ValueError): prepare(source, '0'*64)
        with self.assertRaises(ValueError): prepare(candidate, hashlib.sha256(candidate).hexdigest())

    def test_original_baseline_preparation_still_adds_the_precondition(self):
        source = b'''def local_start(args):
    allowed = set(args)
    if set(args)-allowed: raise ValueError("Unknown workspace argument")
    return "start"
class Adapter:
    def handle(self, msg):
        schema = {}
        schema["required"]=list(set(schema.get("required",[])+["prompt"]))
        description = "When linking issue_id, project_id is required."
        name, args = "start_workspace", {}
        if name:
            if name == "start_workspace": return {"jsonrpc":"2.0","id":msg["id"],"result":local_start(args)}
'''
        candidate = prepare(source, hashlib.sha256(source).hexdigest())
        self.assertIn(b'require_issue_context(args, http_get)', candidate)
        self.assertIn(b'dispatch_start(local_start,args)', candidate)
        self.assertIn(b'["prompt","project_id","issue_id"]', candidate)


if __name__ == '__main__': unittest.main()
