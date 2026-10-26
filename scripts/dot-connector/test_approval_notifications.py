import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import approval_event_store as events
import approval_notifications as notifications
import approval_preview


class ApprovalNotificationTests(unittest.TestCase):
    def row(self, params=None, tool='Bash'):
        row = {'approval_id': str(uuid.uuid4()), 'execution_process_id': str(uuid.uuid4()),
               'tool_name': tool, 'is_question': False,
               'created_at': '2026-10-26T15:34:38Z', 'timeout_at': '2026-10-27T01:34:38Z'}
        if params is not None:
            row['mcp_consent'] = 'Tool: '+tool+'\nParameters (including target):\n'+json.dumps(params)+'\nPreview only'
        return row

    def test_native_tool_and_complete_command_survive_to_notification_read(self):
        command = "find ./art-candidates -type f -name '*.svg' | head -50"
        row = self.row({'command': command, 'prompt': 'private instructions', 'content': 'private body'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'notifications.sqlite'
            store = events.Store(path, clock=lambda: dt.datetime(2026, 10, 26, 16, tzinfo=dt.timezone.utc).timestamp(), sender=lambda *a: self.fail('No network'))
            store.snapshot({row['approval_id']: row})
            before = [row[0] for row in store.db.execute('SELECT body FROM events')]
            with patch.dict(os.environ, {'VK_APPROVAL_STATE': str(path), 'VK_APPROVAL_PRINCIPAL': 'fixture-owner'}):
                value = notifications.listing({'state': 'pending'})
            item = value['notifications'][0]
            self.assertEqual(item['tool'], 'Bash')
            self.assertEqual(item['action'], {'command': command, 'status': 'available'})
            self.assertEqual(item['approval_id'], row['approval_id'])
            self.assertEqual(item['execution_id'], row['execution_process_id'])
            self.assertEqual(item['state'], 'pending')
            self.assertEqual(before, [row[0] for row in store.db.execute('SELECT body FROM events')])
            self.assertNotIn('private instructions', json.dumps(before))
            self.assertNotIn('private body', json.dumps(before))
            self.assertFalse(value['delivery_verified'])
            store.close()

    def test_legacy_requests_truthfully_have_no_command(self):
        native = events.summarize(self.row())
        self.assertEqual(native['tool'], 'Bash')
        self.assertEqual(native['action'], {'status': 'unavailable'})
        native.pop('action')
        self.assertEqual(notifications.clean_summary(json.dumps(native))['action'], {'status': 'unavailable'})

    def test_secrets_long_commands_and_controls_are_not_retained(self):
        for command in ["curl -H 'Authorization: Bearer hidden' https://example.test", 'echo API_KEY=hidden',
                        'curl https://user:pass@example.test', 'x'*4097, 'echo hidden\nnext', 'echo \u202ehidden',
                        'curl https://example.test?X-Amz-Signature=hidden', 'curl --data @credentials.json']:
            with self.subTest(command=command[:30]):
                summary = events.summarize(self.row({'command': command}))
                self.assertEqual(summary['action'], {'status': 'withheld'})
                self.assertNotIn(command, json.dumps(summary))

    def test_modified_unsafe_event_fails_closed_at_read_boundary(self):
        summary = events.summarize(self.row({'command': 'ls ./docs'}))
        for action in [{'status': 'available', 'command': 'echo secret=hidden'},
                       {'status': 'available', 'prompt': 'private'},
                       {'status': 'unavailable', 'command': 'ls ./docs'},
                       {'status': 'approved', 'command': 'ls ./docs'}]:
            with self.assertRaises(ValueError):
                notifications.clean_summary(json.dumps(dict(summary, action=action)))

    def test_mcp_targets_preserved_but_prompts_and_grants_are_never_previewed(self):
        sid = str(uuid.uuid4())
        row = self.row({'session_id': sid, 'prompt': 'private target instructions', 'updatedPermissions': ['allow everything']}, tool='run_session_prompt')
        summary = events.summarize(row)
        self.assertEqual(summary['targets'], {'session_id': sid})
        self.assertEqual(summary['action'], {'status': 'unavailable'})
        self.assertNotIn('private target instructions', json.dumps(summary))
        self.assertNotIn('allow everything', json.dumps(summary))

    def test_event_schema_and_outcomes_remain_request_bound(self):
        row = self.row({'command': 'ls ./docs'})
        with tempfile.TemporaryDirectory() as directory:
            store = events.Store(Path(directory)/'events.sqlite', clock=lambda: dt.datetime(2026, 10, 26, 16, tzinfo=dt.timezone.utc).timestamp(), sender=lambda *a: self.fail('No network'))
            store.snapshot({row['approval_id']: row})
            store.snapshot({row['approval_id']: row})
            self.assertEqual(store.db.execute('SELECT count(*) FROM events').fetchone()[0], 1)
            store.outcome(row['approval_id'], 'denied')
            store.snapshot({row['approval_id']: row})
            self.assertEqual(store.db.execute('SELECT state FROM requests').fetchone()[0], 'denied')
            schema = store.event_list()['events'][0]['payloadSchema']
            for event in store.db.execute('SELECT body FROM events'):
                value = json.loads(event[0])
                self.assertIn('action', schema['properties'])
                self.assertTrue(set(schema['required']) <= set(value['data']))
                self.assertTrue(set(value['data']) <= set(schema['properties']))
                self.assertEqual(value['data']['approval_id'], row['approval_id'])
                self.assertEqual(value['data']['action']['command'], 'ls ./docs')
            store.close()

    def test_aggregate_budget_never_sends_partial_command(self):
        result = approval_preview.preview({'command': '\U0001f600'*1024, 'path': 'y'*4096})
        self.assertEqual(result, {'status': 'withheld'})
        with self.assertRaises(ValueError):
            approval_preview.validate({'status': 'available', 'command': '\U0001f600'*1024, 'path': 'y'*4096})


if __name__ == '__main__':
    unittest.main()
