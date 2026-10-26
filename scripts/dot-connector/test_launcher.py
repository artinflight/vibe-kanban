import copy
import hashlib
import json
import unittest
import urllib.error
import uuid
from unittest.mock import Mock

import launcher

SID, EID, RID, PID = (str(uuid.uuid4()) for _ in range(4))
CONFIG = {'executor': 'CLAUDE_CODE', 'model_id': 'sonnet', 'reasoning_id': 'high',
          'permission_policy': 'SUPERVISED', 'variant': 'DEFAULT',
          'routing': {'mode': 'auto', 'floor': 'frontier', 'denied_models': ['blocked'], 'allow_escalation': False}}


def api():
    service = Mock()
    service.valid_uuid = lambda x: str(uuid.UUID(x))
    service.result = lambda x: {'content': [{'type': 'text', 'text': json.dumps(x)}], 'isError': False}
    service.handoff_result = lambda x: dict(service.result(x), isError=x['status'] != 'started')
    service.session_configs.return_value = [{'config': copy.deepcopy(CONFIG)}]
    service.http_get.return_value = {'success': True, 'data': None}
    return service


def content(reply):
    return json.loads(reply['content'][0]['text'])


class SelectionTests(unittest.TestCase):
    def test_exact_claude_config_preserved_only_shadow_changes(self):
        before = copy.deepcopy(CONFIG)
        result = launcher.claude_config(CONFIG)
        self.assertEqual(CONFIG, before)
        result['routing']['mode'] = 'auto'
        self.assertEqual(result, before)
        self.assertNotIn('quota', result)

    def test_unsupported_model_effort_executor_and_permissions_never_fallback(self):
        for changes in ({'executor': 'CLAUDE'}, {'executor': 'OTHER'}, {'model_id': 'gpt-6.1-sol'},
                        {'model_id': ''}, {'model_id': None}, {'reasoning_id': 'xhigh'},
                        {'model_id': 'haiku'}, {'variant': 'unknown-preset'}, {'permission_policy': 'BYPASS'}, {'provider': 'paid-extra'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                launcher.claude_config(dict(CONFIG, **changes))

    def test_supported_efforts_and_haiku_without_effort(self):
        for model in ('opus', 'opus[1m]', 'sonnet'):
            for effort in launcher.EFFORTS:
                selected = launcher.claude_config(dict(CONFIG, model_id=model, reasoning_id=effort))
                self.assertEqual(selected['model_id'], model)
                self.assertEqual(selected['reasoning_id'], effort)
        config = dict(CONFIG, model_id='haiku'); del config['reasoning_id']
        self.assertNotIn('reasoning_id', launcher.claude_config(config))

    def test_codex_path_delegates_unchanged(self):
        service = api()
        args = {'executor': 'CODEX', 'model_id': 'owner-model', 'reasoning_id': 'xhigh'}
        launcher.start(service, args)
        service.codex_local_start.assert_called_once_with(args)
        launcher.recommend(service, args)
        service.codex_recommend_config.assert_called_once_with(args)
        follow = {'session_id': SID, 'prompt': 'Continue'}
        launcher.followup(service, follow)
        service.codex_local_followup.assert_called_once_with(follow)
        service.post_fixed.assert_not_called()

    def test_followup_saved_draft_wins_preserves_policy(self):
        service = api()
        config = dict(CONFIG, model_id='opus', reasoning_id='max'); del config['routing']
        service.http_get.return_value = {'success': True, 'data': {'payload': {'data': {'executor_config': config}}}}
        selected = launcher.resolve_claude(service, SID, {'executor': 'CLAUDE_CODE'})
        self.assertEqual(selected['model_id'], 'opus')
        self.assertEqual(selected['reasoning_id'], 'max')
        self.assertEqual(selected['permission_policy'], 'SUPERVISED')
        self.assertEqual(selected['routing']['denied_models'], ['blocked'])
        self.assertEqual(selected['routing']['mode'], 'shadow')

    def test_cross_executor_draft_conflicts_and_failed_snapshot_no_post(self):
        for draft in ({'executor': 'CODEX', 'model_id': 'gpt-6.1-sol'}, {'executor': 'CLAUDE_CODE', 'model_id': 'unknown'}):
            service = api()
            service.http_get.return_value = {'success': True, 'data': {'payload': {'data': {'executor_config': draft}}}}
            with self.assertRaises(ValueError):
                launcher.resolve_claude(service, SID, {'executor': 'CLAUDE_CODE'})
            service.post_fixed.assert_not_called()
        service = api(); service.session_configs.side_effect = ValueError('Session is running')
        with self.assertRaises(ValueError):
            launcher.resolve_claude(service, SID, {'executor': 'CLAUDE_CODE'})
        service.post_fixed.assert_not_called()

    def test_fresh_claude_session_requires_explicit_selection_then_dispatches_once(self):
        service = api(); service.session_configs.return_value = []
        service.http_get.side_effect = [{'success': True, 'data': {'id': SID, 'executor': 'CLAUDE_CODE'}},
                                       {'success': True, 'data': None}]
        service.post_fixed.return_value = {'id': EID}
        args = {'session_id': SID, 'prompt': 'Explicit owner task', 'model_id': 'sonnet',
                'reasoning_id': 'high', 'permission_policy': 'SUPERVISED'}
        reply = launcher.followup(service, args)
        self.assertEqual(content(reply)['execution_id'], EID)
        service.post_fixed.assert_called_once()
        path, payload = service.post_fixed.call_args.args
        self.assertEqual(path, '/api/sessions/' + SID + '/follow-up')
        self.assertEqual(payload['executor_config']['executor'], 'CLAUDE_CODE')
        self.assertEqual(payload['executor_config']['reasoning_id'], 'high')
        self.assertIsNone(payload['retry_process_id'])
        self.assertIsNone(payload['perform_git_reset'])

    def test_no_saved_config_or_conflicting_explicit_selection_no_post(self):
        service = api(); service.session_configs.return_value = []
        with self.assertRaises(ValueError):
            launcher.resolve_claude(service, SID, {'executor': 'CLAUDE_CODE'})
        service.session_configs.return_value = [{'config': CONFIG}]
        with self.assertRaises(ValueError):
            launcher.resolve_claude(service, SID, {'executor': 'CLAUDE_CODE'}, {'reasoning_id': 'max'})
        service.post_fixed.assert_not_called()

    def test_partial_saved_draft_selection_cannot_be_overridden_implicitly(self):
        service = api(); service.session_configs.return_value = []
        service.http_get.return_value = {'success': True, 'data': {'payload': {'data': {'executor_config': {
            'executor': 'CLAUDE_CODE', 'permission_policy': 'PLAN', 'reasoning_id': 'high'}}}}}
        with self.assertRaises(ValueError):
            launcher.resolve_claude(service, SID, {}, {'model_id': 'sonnet', 'permission_policy': 'AUTO'})
        service.post_fixed.assert_not_called()

    def test_missing_draft_is_allowed_but_unavailable_draft_is_not(self):
        import io
        for status, body, allowed in ((400, b'{"message":"Scratch not found"}', True), (403, b'', False), (500, b'', False)):
            service = api()
            service.http_get.side_effect = urllib.error.HTTPError('fixture', status, '', {}, io.BytesIO(body))
            if allowed:
                self.assertEqual(launcher.resolve_claude(service, SID, {})['model_id'], 'sonnet')
            else:
                with self.assertRaises(ValueError):
                    launcher.resolve_claude(service, SID, {})
            service.post_fixed.assert_not_called()

    def test_queued_capacity_is_not_a_started_execution_or_fallback(self):
        service = api(); service.session_configs.return_value = []
        service.http_get.side_effect = [{'success': True, 'data': {'id': SID, 'executor': 'CLAUDE_CODE'}}, {'success': True, 'data': None}]
        service.post_fixed.return_value = {'connector_queued_for_capacity': True, 'queued_at': 'fixture'}
        value = content(launcher.followup(service, {'session_id': SID, 'prompt': 'Continue', 'model_id': 'sonnet'}))
        self.assertEqual(value['status'], 'queued'); self.assertIsNone(value['execution_id'])
        service.post_fixed.assert_called_once()


class HandoffTests(unittest.TestCase):
    def args(self):
        return {'session_id': SID, 'execution_id': EID, 'request_id': RID, 'prompt': 'Continue',
                'model_id': 'gpt-6.1-sol', 'reasoning_id': 'high'}

    def receipt(self, **changes):
        payload = self.args(); del payload['session_id']
        return dict({'session_id': SID, 'execution_id': EID, 'request_id': RID,
                     'request_sha256': hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                     'context_sha256': 'a' * 64, 'target_session_id': PID, 'target_execution_id': str(uuid.uuid4()), 'status': 'started'}, **changes)

    def service(self):
        service = api()
        service.http_get.side_effect = [{'success': True, 'data': None},
                                       {'success': True, 'data': {'version': 1, 'serialized': True, 'quota': 'unknown', 'extra_usage_authorized': False}}]
        service.post_fixed.return_value = self.receipt()
        return service

    def test_guarded_handoff_one_post_and_unknown_quota_never_buys_extras(self):
        service = self.service(); value = content(launcher.handoff(service, self.args()))
        self.assertEqual(value['status'], 'started')
        service.post_fixed.assert_called_once()
        path, payload = service.post_fixed.call_args.args
        self.assertEqual(path, '/api/sessions/' + SID + '/handoff')
        self.assertEqual(payload['model_id'], 'gpt-6.1-sol')
        self.assertEqual(payload['reasoning_id'], 'high')
        self.assertEqual(set(payload), set(self.args()) - {'session_id'})

    def test_replayed_request_reads_without_post(self):
        service = self.service(); service.http_get.side_effect = [{'success': True, 'data': self.receipt()}]
        launcher.handoff(service, self.args()); service.post_fixed.assert_not_called()

    def test_missing_guard_spa_or_unserialized_backend_never_posts(self):
        for capability in ({'success': False}, {'data': '<html>'}, {'success': True, 'data': {'version': 1, 'serialized': False}}):
            service = self.service(); service.http_get.side_effect = [{'success': True, 'data': None}, capability]
            with self.assertRaises(ValueError):
                launcher.handoff(service, self.args())
            service.post_fixed.assert_not_called()

    def test_lost_response_reconciles_same_request_never_retries(self):
        service = self.service(); reads = list(service.http_get.side_effect)
        service.http_get.side_effect = reads + [{'success': True, 'data': self.receipt()}]
        service.post_fixed.side_effect = TimeoutError()
        self.assertEqual(content(launcher.handoff(service, self.args()))['status'], 'started')
        service.post_fixed.assert_called_once()

    def test_uncertain_outcome_is_error_and_never_retargeted(self):
        service = self.service(); reads = list(service.http_get.side_effect)
        service.http_get.side_effect = reads + [{'success': True, 'data': None}]
        service.post_fixed.side_effect = TimeoutError()
        value = launcher.handoff(service, self.args())
        self.assertTrue(value['isError']); self.assertEqual(content(value)['status'], 'unknown')
        service.post_fixed.assert_called_once()

    def test_conflicting_receipt_or_unknown_arguments_no_post(self):
        service = self.service(); service.http_get.side_effect = [{'success': True, 'data': self.receipt(execution_id=PID)}]
        with self.assertRaises(ValueError):
            launcher.handoff(service, self.args())
        service.post_fixed.assert_not_called()
        with self.assertRaises(ValueError):
            launcher.handoff(service, dict(self.args(), billing='extra'))


if __name__ == '__main__':
    unittest.main()

class UnicodeReceiptTests(unittest.TestCase):
    def test_utf8_fingerprint_and_unknown_replay_is_not_success(self):
        sid = rid = eid = '00000000-0000-0000-0000-000000000000'
        args = dict(session_id=sid, request_id=rid, execution_id=eid, prompt='Continue — café',
                    model_id='gpt-6.1-sol', reasoning_id='high')
        service = api()
        service.http_get.return_value = {'success': True, 'data': dict(args, status='unknown', target_session_id=PID, context_sha256='a' * 64, target_execution_id=None,
            request_sha256='6c5971728ec7dc04586974eed98b465627549cd3f1d371336e50818108f575d1')}
        value = launcher.handoff(service, args)
        self.assertTrue(value['isError'])
        service.post_fixed.assert_not_called()
