"""Source-only mock tests for the exact deployed notification recovery overlay."""
import copy
import hashlib
import json
from pathlib import Path
import importlib.util
import unittest
import uuid
from unittest.mock import Mock

path=Path(__file__).with_name('templates')/'issue_workflow.py'
spec=importlib.util.spec_from_file_location('notification_recovery_fixture_workflow',path)
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
PID, RID, REPO, DOT, WID, OLD, IID, SID, EID = [str(uuid.UUID(int=i)) for i in range(1, 10)]

def envelope(value):
    return {'success': True, 'data': copy.deepcopy(value)}

class Backend:
    def __init__(self):
        self.row = None
        self.payload = None
        self.posts = []
        self.starts = 0
        self.allowed = True
        self.failure = None
        self.chat_failure = False
        self.notification_failure = None
        self.note_failure = False
        self.capabilities = dict(version=1, atomic_reservation=True, conditional_relink=True, durable_launch_receipts=True)

    def authorize(self, project):
        if not self.allowed or project != PID:
            raise w.Blocked('not_authorized')
        return 'authenticated-owner'

    def recommend_config(self, config):
        return dict(config, routing={'mode': 'shadow', 'floor': 'assessed', 'denied_models': [], 'allow_escalation': False})

    def get(self, path):
        if path == '/api/issue-workflows/capabilities':
            return envelope(self.capabilities)
        if path == '/api/issue-workflows/' + RID + '?project_id=' + PID:
            return envelope(self.row)
        if path == '/api/issue-workflows/workspaces/' + WID + '?project_id=' + PID:
            return envelope(dict(project_id=PID, workspace_id=WID, issue_id=OLD, link_revision=0))
        raise AssertionError('Unsupported read ' + path)

    def post(self, path, payload):
        self.posts.append((path, copy.deepcopy(payload)))
        if self.failure == path + ':before':
            raise TimeoutError('PRIVATE read error')
        if path == '/api/issue-workflows':
            if self.payload is not None and self.payload != payload:
                raise w.Blocked('request_identity_changed')
            self.payload = copy.deepcopy(payload)
            if self.row is None:
                op = payload['operation']
                self.row = dict(request_id=RID, project_id=PID, request_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                                operation=op, issue_id=IID, dot_user_id=DOT, workspace_id=None if op == 'create' else WID,
                                session_id=SID if op == 'start' else None,
                                previous_issue_id=OLD if op == 'relink' else None,
                                chat_previous_issue_id=payload['link'].get('chat_previous_issue_id') if payload['link'] else None,
                                link_revision=None if op == 'create' else 0 if op == 'start' else 1,
                                phase='linked' if op == 'relink' else 'reserved', execution_process_id=None,
                                current_link=True, assignment_verified=True, chat_completed=op == 'create', executions=[])
        elif path.endswith('/chat-ready'):
            self.row['chat_completed'] = True
        elif path.endswith('/launch'):
            if self.row['phase'] == 'reserved':
                self.starts += 1
                self.row['phase'] = 'launching'
                if self.failure == 'crash_before_process':
                    raise TimeoutError('PRIVATE crash')
                self.row['executions'] = [dict(id=EID, status='running', run_reason='codingagent', dropped=False)]
                if self.failure == 'crash_after_process':
                    raise TimeoutError('PRIVATE crash')
                self.row.update(phase='started', execution_process_id=EID)
        else:
            raise AssertionError(path)
        if self.failure == path + ':after':
            raise TimeoutError('PRIVATE lost response')
        return envelope(self.row)

    def chat_preflight(self, owner, project, workspace, old):
        if self.chat_failure:
            raise w.Blocked('scope_changed')

    def chat_scope(self, owner, value, read):
        if self.chat_failure:
            raise w.Blocked('scope_changed')
        assert read()['current_link'] is True
        return dict(thread_id=RID, project_id=PID, issue_id=IID, workspace_id=WID)

    def notifications(self, chat):
        if self.notification_failure:
            raise self.notification_failure
        return dict(status='configured', delivery='not_confirmed')

    def note(self, args, value):
        if self.note_failure:
            raise OSError('PRIVATE note failure')
        return value

class BackendProtocolTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.workflow = w.Workflow(self.backend)
        self.args = dict(request_id=RID, project_id=PID, title='Dedicated', description='Requested work', status_id='todo')
        self.start = dict(self.args, name='Workspace', prompt='Bounded work', executor='CODEX',
                          model_id='owner-model', reasoning_id='owner-effort', variant='owner-profile',
                          repositories=[dict(repo_id=REPO, branch='staging')])
        self.link = dict(project_id=PID, request_id=RID, workspace_id=WID, issue_id=IID,
                         expected_issue_id=OLD, expected_link_revision=0)

    def run_start(self):
        return self.workflow.call('create_issue_and_start_workspace', self.start)

    def test_atomic_backend_reserve_chat_ack_and_guarded_launch(self):
        r = self.run_start()
        self.assertEqual(r['status'], 'started')
        self.assertEqual([p for p, _ in self.backend.posts], ['/api/issue-workflows', '/api/issue-workflows/' + RID + '/chat-ready', '/api/issue-workflows/' + RID + '/launch'])
        config = self.backend.payload['start']['executor_config']
        for key in ('model_id', 'reasoning_id', 'variant'):
            self.assertEqual(config[key], self.start[key])
        self.assertEqual(config['routing']['mode'], 'shadow')
        self.assertEqual(self.run_start()['workspace_id'], WID)
        self.assertEqual(self.backend.starts, 1)

    def test_notifications_unavailable_does_not_block_start_or_retry(self):
        self.backend.notification_failure = ValueError('Existing unique authorized chat subscription required; filters unchanged')
        first = self.run_start()
        second = self.run_start()
        self.assertEqual(first['status'], 'started')
        self.assertEqual(first['chat']['status'], 'linked')
        self.assertEqual(first['notifications'], dict(status='unavailable', delivery='not_confirmed', reason='no_unique_active_authorized_subscription'))
        self.assertEqual(first['execution_process_id'], second['execution_process_id'])
        self.assertEqual(self.backend.starts, 1)
        self.assertTrue(first['chat_completed'] and first['assignment_verified'])

    def test_notification_error_after_launch_never_hides_receipt_or_secrets(self):
        self.backend.notification_failure = OSError('PRIVATE transport detail')
        result = self.run_start()
        self.assertEqual(result['status'], 'started')
        self.assertEqual(result['notifications']['reason'], 'notification_setup_unavailable')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_configured_notifications_do_not_claim_delivery(self):
        result = self.run_start()
        self.assertEqual(result['notifications']['status'], 'configured')
        self.assertEqual(result['notifications']['delivery'], 'not_confirmed')

    def test_dispatch_note_failure_does_not_hide_native_start(self):
        self.backend.note_failure = True
        result = self.run_start()
        self.assertEqual(result['status'], 'started')
        self.assertEqual(result['dispatch_note']['state'], 'unavailable')
        self.assertEqual(self.backend.starts, 1)

    def test_native_receipt_does_not_infer_notification_delivery(self):
        self.run_start()
        result = self.workflow.call('get_issue_workflow_receipt', dict(project_id=PID, request_id=RID))
        self.assertEqual(result['notifications']['status'], 'not_observed')
        self.assertEqual(result['notifications']['delivery'], 'not_confirmed')

    def test_notifications_outage_does_not_bypass_denied_project(self):
        self.backend.allowed = False
        self.backend.notification_failure = TimeoutError('outage')
        with self.assertRaises(w.Blocked):
            self.run_start()
        self.assertEqual(self.backend.posts, [])

    def test_relink_notifications_unavailable_retains_verified_link(self):
        self.backend.notification_failure = TimeoutError('outage')
        result = self.workflow.call('link_workspace_issue', self.link)
        self.assertEqual(result['status'], 'linked')
        self.assertEqual(result['notifications']['status'], 'unavailable')
        self.assertEqual(self.backend.starts, 0)

    def test_no_client_journal_poll_scan_or_legacy_launch(self):
        self.assertFalse(hasattr(w, 'Journal'))
        self.run_start()  # Backend.get raises on every unsupported path.
        self.assertFalse(any('/v1/' in path for path, _ in self.backend.posts))
        self.assertFalse(any(path.endswith('/start') for path, _ in self.backend.posts))

    def test_missing_backend_capability_means_zero_writes(self):
        self.backend.capabilities = {'version': 0}
        with self.assertRaises(w.Blocked):
            self.run_start()
        self.assertEqual(self.backend.posts, [])

    def test_invalid_missing_inputs_never_reach_backend(self):
        cases = [dict(self.start, project_id='bad'), dict(self.start, request_id=str(uuid.UUID(int=0))),
                 dict(self.start, prompt=''), dict(self.start, executor='CLAUDE_CODE'), dict(self.start, owner='forged'),
                 dict(self.start, repositories=[])]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(w.Blocked):
                self.workflow.call('create_issue_and_start_workspace', args)
        self.assertEqual(self.backend.posts, [])

    def test_revoked_permission_blocks_receipt_and_mutation(self):
        self.run_start()
        self.backend.allowed = False
        with self.assertRaises(w.Blocked):
            self.run_start()
        with self.assertRaises(w.Blocked):
            self.workflow.call('get_issue_workflow_receipt', dict(project_id=PID, request_id=RID))
        self.assertEqual(self.backend.starts, 1)

    def test_changed_input_server_receipt_binding_rejects(self):
        self.run_start()
        self.start['prompt'] = 'Different'
        with self.assertRaises(w.Blocked):
            self.run_start()
        self.assertEqual(self.backend.starts, 1)

    def test_timeout_after_reservation_reconciles_same_native_ids(self):
        self.backend.failure = '/api/issue-workflows:after'
        with self.assertRaises(TimeoutError):
            self.run_start()
        original = self.backend.row['issue_id'], self.backend.row['workspace_id'], self.backend.row['session_id']
        self.backend.failure = None
        r = self.run_start()
        self.assertEqual((r['issue_id'], r['workspace_id'], r['session_id']), original)
        self.assertEqual(self.backend.starts, 1)

    def test_local_chat_failure_keeps_native_reservation_and_no_launch(self):
        self.backend.chat_failure = True
        with self.assertRaises(w.Blocked):
            self.run_start()
        self.assertEqual(self.backend.starts, 0)
        self.assertEqual(self.backend.row['phase'], 'reserved')
        self.backend.chat_failure = False
        self.assertEqual(self.run_start()['status'], 'started')
        self.assertEqual(self.backend.starts, 1)

    def test_crashes_before_and_after_process_persistence_never_relaunch(self):
        for fault in ('crash_before_process', 'crash_after_process'):
            with self.subTest(fault=fault):
                self.backend = Backend()
                self.workflow = w.Workflow(self.backend)
                self.backend.failure = fault
                with self.assertRaises(TimeoutError):
                    self.run_start()
                self.backend.failure = None
                self.workflow = w.Workflow(self.backend)  # New connector process, same native receipt.
                r = self.run_start()
                self.assertEqual(r['status'], 'launch_unknown')
                self.assertEqual(self.backend.starts, 1)
                self.assertEqual(bool(r['executions']), fault == 'crash_after_process')

    def test_lost_success_response_reads_original_execution_receipt(self):
        self.backend.failure = '/api/issue-workflows/' + RID + '/launch:after'
        with self.assertRaises(TimeoutError):
            self.run_start()
        self.backend.failure = None
        r = self.run_start()
        self.assertEqual(r['status'], 'started')
        self.assertEqual(r['execution_process_id'], EID)
        self.assertEqual(self.backend.starts, 1)

    def test_changed_native_link_cannot_migrate_or_launch(self):
        self.run_start()
        self.backend.row['current_link'] = False
        with self.assertRaises(w.Blocked):
            self.run_start()
        self.assertEqual(self.backend.starts, 1)

    def test_assignment_revoked_after_reservation_blocks_launch(self):
        self.backend.failure = '/api/issue-workflows:after'
        with self.assertRaises(TimeoutError):
            self.run_start()
        self.backend.failure = None
        self.backend.row['assignment_verified'] = False
        with self.assertRaises(w.Blocked):
            self.run_start()
        self.assertEqual(self.backend.starts, 0)

    def test_relink_expected_native_revision_and_chat_catchup_pass_exactly(self):
        args = dict(self.link, chat_previous_issue_id=OLD)
        r = self.workflow.call('link_workspace_issue', args)
        self.assertEqual(r['status'], 'linked')
        self.assertEqual(self.backend.payload['link']['expected_link_revision'], 0)
        self.assertEqual(self.backend.payload['link']['chat_previous_issue_id'], OLD)
        self.assertEqual(self.backend.starts, 0)

    def test_existing_chat_conflict_rejects_before_native_mutation(self):
        self.backend.chat_failure = True
        with self.assertRaises(w.Blocked):
            self.workflow.call('link_workspace_issue', self.link)
        self.assertEqual(self.backend.posts, [])

    def test_create_dedicated_issue_for_existing_workspace_does_not_launch(self):
        args = dict(self.args, workspace_id=WID, expected_issue_id=OLD, expected_link_revision=0)
        r = self.workflow.call('create_issue_for_workspace', args)
        self.assertEqual(r['status'], 'linked')
        self.assertIsNone(self.backend.payload['link']['target_issue_id'])
        self.assertEqual(self.backend.starts, 0)

    def test_foreign_or_malformed_receipt_rejects(self):
        self.run_start()
        for key, value in [('project_id', OLD), ('request_id', OLD), ('assignment_verified', 'true'), ('phase', 'invented')]:
            with self.subTest(key=key):
                with self.assertRaises(w.Blocked):
                    w.receipt(dict(self.backend.row, **{key: value}), PID, RID)

    def test_source_uses_only_fixed_workflow_paths_for_mutations(self):
        adapter = Mock()
        runtime = w.Runtime.__new__(w.Runtime)
        runtime.adapter = adapter
        for path in ('/v1/issues', '/api/workspaces/start', '/api/sessions/' + SID + '/follow-up', '/api/issue-workflows/not-uuid/launch'):
            with self.assertRaises(w.Blocked):
                runtime.post(path, {})
