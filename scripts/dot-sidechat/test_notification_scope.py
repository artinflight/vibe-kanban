"""Synthetic recurrence after old notes were read; no live conversations opened."""
import unittest
import uuid

import notification_ack as ack
from sidechat import Principal, Rejected
import test_notification_ack as ack_tests


def uid():
    return str(uuid.uuid4())


class NotificationScopeTests(unittest.TestCase):
    setUp = ack_tests.NotificationAcknowledgementTests.setUp
    tearDown = ack_tests.NotificationAcknowledgementTests.tearDown
    note = ack_tests.NotificationAcknowledgementTests.note

    def clean_history(self):
        self.workspaces = [self.workspace, self.sibling] + [uid() for _ in range(3)]
        for workspace in self.workspaces[2:]:
            self.store.register_scope('alice', self.project, self.issue, workspace)
            note = self.note(workspace)
            self.store.seen_replies(self.owner, self.thread, workspace, [note])
        self.store.seen_replies(self.owner, self.thread, self.workspace, [self.first, self.conversation])
        self.store.seen_replies(self.owner, self.thread, self.sibling, [self.other])
        self.assertEqual([], self.store.notifications(self.owner, [self.project])['issues'])

    def reply(self, workspace=None, thread=None, attention=None):
        workspace = workspace or self.workspace
        thread = thread or self.thread
        owner = self.store.append(self.owner, thread, workspace, uid(), 'Synthetic owner message')
        return self.store.append(self.dot, thread, workspace, uid(), 'Substantive manager answer',
                                 owner['id'], 'sidechat_' + owner['id'], attention=attention)['id']

    def inventory(self, workspace):
        return ack.call(self.path, self.dot, ack.INVENTORY, {'workspace_id':workspace})['notifications']

    def snapshot(self):
        return list(self.store.db.iterdump())

    def assert_target_counts(self, unread, attention):
        result = self.store.notifications(self.owner, [self.project])
        self.assertEqual([], result['projects'])
        expected = [{'project_id':self.project, 'issue_id':self.issue, 'workspace_id':self.workspace,
                     'unread_count':unread, 'needs_attention_count':attention}] if unread or attention else []
        self.assertEqual(expected, result['workspaces'])
        if expected:
            self.assertEqual((unread, attention, 0, 0), tuple(result['issues'][0][k] for k in
                ('unread_count','needs_attention_count','shared_unread_count','shared_needs_attention_count')))

    def test_new_substantive_A_reply_after_cleanup_badges_only_A_but_history_stays_shared(self):
        self.clean_history()
        message = self.reply()
        before = self.snapshot()
        self.assert_target_counts(1, 0)
        for workspace in self.workspaces:
            history = self.store.read(self.owner, self.thread, display_workspace=workspace)
            self.assertIn(message, [m['id'] for m in history['messages']])
            rows = self.inventory(workspace)
            self.assertEqual(workspace == self.workspace, message in [r['message_id'] for r in rows])
            self.assertTrue(all(r['workspace_id'] == workspace for r in rows))
        self.assertEqual(before, self.snapshot(), 'Metadata/history reads change no state')
        row = next(r for r in self.inventory(self.workspace) if r['message_id'] == message)
        self.assertEqual('genuine_conversation', row['protected_reason'])
        result = ack.call(self.path, self.dot, ack.ACKNOWLEDGE, {'workspace_id':self.workspace,
            'items':[{k:row[k] for k in ('thread_id','message_id','state_token')}]})
        self.assertEqual('genuine_conversation', result['outcomes'][0]['outcome'])
        with self.assertRaises(Rejected):
            ack.call(self.path, self.dot, ack.ACKNOWLEDGE, {'workspace_id':self.sibling,
                'items':[{k:row[k] for k in ('thread_id','message_id','state_token')}]})
        self.assertEqual(before, self.snapshot())

    def test_manual_read_and_explicit_attention_are_independent_and_never_fan_out(self):
        self.clean_history()
        message = self.reply(attention='question')
        self.assert_target_counts(1, 1)
        for _ in range(3):
            self.store.set_reply_read_state(self.owner, self.thread, self.workspace, message, 'unread')
            self.assertEqual([], self.store.seen_replies(self.owner, self.thread, self.sibling, [message])['seen'])
            self.assert_target_counts(1, 1)
        self.store.set_sidechat_attention(self.owner, self.thread, self.workspace, message, 'resolve')
        self.assert_target_counts(1, 0)
        self.store.set_sidechat_attention(self.owner, self.thread, self.workspace, message, 'reopen')
        self.store.set_reply_read_state(self.owner, self.thread, self.workspace, message, 'read')
        self.assert_target_counts(0, 1)
        for workspace in self.workspaces[1:]:
            self.assertNotIn(message, [r['message_id'] for r in self.inventory(workspace)])
        from sidechat import Store
        self.store.close()
        self.store = Store(self.path, lambda:self.now)
        self.assert_target_counts(0, 1)
        self.store.set_reply_read_state(self.owner, self.thread, self.workspace, message, 'unread')
        self.assert_target_counts(1, 1)

    def test_project_reply_and_manual_attention_badge_only_project_even_with_legacy_workspace_value(self):
        self.clean_history()
        context = 'project:' + self.project
        self.store.register_scope('alice', self.project, context, context)
        thread = self.store.resolve(self.owner, self.project, context, context)['id']
        message = self.reply(context, thread, 'action')
        self.store.set_reply_read_state(self.owner, thread, context, message, 'unread')
        for legacy_workspace in (context, self.workspace):
            # Simulate older stored data; the project thread remains authoritative.
            self.store.db.execute('UPDATE messages SET workspace=? WHERE id=?', (legacy_workspace, message))
            before = self.snapshot()
            result = self.store.notifications(self.owner, [self.project])
            self.assertEqual([], result['issues'])
            self.assertEqual([], result['workspaces'])
            self.assertEqual([{'project_id':self.project,'unread_count':1,'needs_attention_count':1}], result['projects'])
            for workspace in self.workspaces:
                self.assertNotIn(message, [r['message_id'] for r in self.inventory(workspace)])
            self.assertEqual(before, self.snapshot())

    def test_unknown_legacy_scope_stays_issue_metadata_without_assigning_any_workspace(self):
        self.clean_history()
        message = self.reply(attention='question')
        self.store.set_reply_read_state(self.owner, self.thread, self.workspace, message, 'unread')
        for unknown in ('', 'legacy-unknown', uid()):
            self.store.db.execute('UPDATE messages SET workspace=? WHERE id=?', (unknown, message))
            before = self.snapshot()
            result = self.store.notifications(self.owner, [self.project])
            self.assertEqual([], result['workspaces'])
            self.assertEqual([], result['projects'])
            self.assertEqual((1,1,1,1), tuple(result['issues'][0][k] for k in
                ('unread_count','needs_attention_count','shared_unread_count','shared_needs_attention_count')))
            for workspace in self.workspaces:
                self.assertNotIn(message, [r['message_id'] for r in self.inventory(workspace)])
                self.assertIn(message, [r['id'] for r in self.store.read(self.owner, self.thread, display_workspace=workspace)['messages']])
            self.assertEqual(before, self.snapshot())
        self.assertEqual([], self.store.notifications(Principal('bob','owner'), [self.project])['workspaces'])
        self.assertEqual([], self.store.notifications(self.owner, ['not-granted'])['issues'])
