"""Owner quote links are separate from Dot delivery/continuation reply_to."""
import json
import sqlite3
import unittest
import uuid
from pathlib import Path
import tempfile
from sidechat import Store, Principal, Rejected
import test_project_collaboration as projects
from publisher import publish_once


def uid():
    return str(uuid.uuid4())


class OwnerReplies(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'private.sqlite'
        self.store = Store(self.path)
        self.owner = Principal('owner', 'owner')
        self.dot = Principal('owner', 'dot')
        for w, issue in [('target', 'issue'), ('sibling', 'issue'), ('other', 'other')]:
            self.store.register_scope('owner', 'project', issue, w)
        self.thread = self.store.resolve(self.owner, 'project', 'issue', 'target')['id']
        self.original = self.send('Question')
        self.answer = self.store.append(self.dot, self.thread, 'target', uid(), 'Exact answer\n<untrusted context>', self.original['id'], 'sidechat_' + self.original['id'], attention='question')
        self.store.set_reply_read_state(self.owner, self.thread, 'target', self.answer['id'], 'unread')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def send(self, body, target=None, request=None, workspace='target'):
        return self.store.append(self.owner, self.thread, workspace, request or uid(), body, in_reply_to=target)

    def test_multiple_replies_history_reopen_dot_receipt_and_event_recovery(self):
        before = self.store.notifications(self.owner, ['project'])
        key = uid()
        message = self.send('Follow up', self.answer['id'], key)
        self.assertEqual(message, self.send('Follow up', self.answer['id'], key))
        second = self.send('Another follow up', self.answer['id'])
        # Both links can point at the same message. Dot still replies to each owner event.
        dot_answer = self.store.append(self.dot, self.thread, 'target', uid(), 'Follow-up answer', message['id'], 'sidechat_' + message['id'])
        self.assertTrue(self.store.receipt(self.owner, self.thread, message['id'])['reply_persisted'])
        self.assertEqual(dot_answer['reply_to'], message['id'])
        self.store.close(); self.store = Store(self.path)
        history = self.store.read(self.dot, self.thread, after=second['seq'] - 1, limit=1)
        ref = history['messages'][0]['reply_reference']
        self.assertEqual(ref['id'], self.answer['id'])
        self.assertEqual(ref['excerpt'], self.answer['body'])
        self.assertEqual(ref['created'], self.answer['created'])
        pending = self.store.pending(self.dot)['items']
        recovered = next(p for p in pending if p['event']['data']['message_id'] == second['id'])
        self.assertEqual(recovered['event']['data']['in_reply_to'], self.answer['id'])
        self.assertNotIn('body', recovered['event']['data'])
        # Link creation did not change the original manual unread or unresolved attention.
        state = next(m for m in self.store.read(self.owner, self.thread)['messages'] if m['id'] == self.answer['id'])
        self.assertFalse(state['seen']); self.assertTrue(state['manual_unread']); self.assertFalse(state['attention']['resolved'])
        self.assertEqual(before['issues'][0]['needs_attention_count'], 1)
        self.assertEqual(self.store.notifications(self.owner, ['project'])['issues'][0]['needs_attention_count'], 1)

    def test_target_is_part_of_idempotency_and_invalid_targets_are_atomic(self):
        key = uid(); self.send('Follow up', self.answer['id'], key)
        for target in [None, self.original['id']]:
            with self.assertRaisesRegex(Rejected, 'Idempotency'):
                self.send('Follow up', target, key)
        other_thread = self.store.resolve(self.owner, 'project', 'other', 'other')['id']
        other = self.store.append(self.owner, other_thread, 'other', uid(), 'Unrelated')
        self.store.register_scope('foreign', 'project', 'issue', 'foreign')
        foreign_owner = Principal('foreign', 'owner')
        foreign_thread = self.store.resolve(foreign_owner, 'project', 'issue', 'foreign')['id']
        foreign = self.store.append(foreign_owner, foreign_thread, 'foreign', uid(), 'Private')
        before = self.store.db.total_changes
        for target in ['', [], {}, 7, 'missing', other['id'], foreign['id']]:
            with self.assertRaises(Rejected): self.send('Invalid', target)
        self.assertEqual(before, self.store.db.total_changes)
        with self.assertRaises(Rejected):
            self.store.append(self.dot, self.thread, 'target', uid(), 'Forged', self.original['id'], 'sidechat_' + self.original['id'], in_reply_to=self.answer['id'])

    def test_dispatch_target_only_and_shared_real_conversation(self):
        # Dispatch binding is trusted metadata; this note belongs only to target.
        self.store.db.execute('INSERT INTO dispatch_notes VALUES (?,?,?,?,?,?,?)', ('owner', uid(), 'target', uid(), 'dispatch', self.thread, self.answer['id']))
        with self.assertRaises(Rejected): self.send('Wrong workspace', self.answer['id'], workspace='sibling')
        linked = self.send('Target reply', self.answer['id'])
        sibling = self.store.read(self.owner, self.thread, display_workspace='sibling')['messages']
        self.assertNotIn(self.answer['id'], [m['id'] for m in sibling])
        sibling_ref = next(m for m in sibling if m['id'] == linked['id'])['reply_reference']
        self.assertTrue(sibling_ref['unavailable']); self.assertEqual(sibling_ref['excerpt'], '')
        self.assertNotIn(self.answer['body'], json.dumps(sibling))
        dot_ref = next(m for m in self.store.read(self.dot, self.thread)['messages'] if m['id'] == linked['id'])['reply_reference']
        self.assertEqual(dot_ref['excerpt'], self.answer['body'])
        shared = self.send('Shared actual conversation', self.original['id'], workspace='sibling')
        ref = next(m for m in self.store.read(self.owner, self.thread, display_workspace='target')['messages'] if m['id'] == shared['id'])['reply_reference']
        self.assertEqual(ref['id'], self.original['id']); self.assertFalse(ref['unavailable'])
        self.assertEqual(self.store.notifications(self.owner, ['project'])['workspaces'][0]['workspace_id'], 'target')

    def test_atomic_message_link_outbox_and_bounded_context(self):
        self.store.db.execute("CREATE TRIGGER reject_link BEFORE INSERT ON owner_reply_targets BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        before = self.store.db.execute('SELECT count(*) FROM messages').fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError): self.send('Fail', self.original['id'])
        self.assertEqual(before, self.store.db.execute('SELECT count(*) FROM messages').fetchone()[0])
        self.store.db.execute('DROP TRIGGER reject_link')
        self.store.db.execute("CREATE TRIGGER reject_event BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.send('Fail', self.original['id'])
        self.assertEqual(0, self.store.db.execute('SELECT count(*) FROM owner_reply_targets').fetchone()[0])
        self.store.db.execute('DROP TRIGGER reject_event')
        long = self.send('x' * 2000)
        reply = self.send('Quote', long['id'])
        ref = self.store.read(self.owner, self.thread, after=reply['seq'] - 1)['messages'][0]['reply_reference']
        self.assertEqual(len(ref['excerpt']), 1000); self.assertTrue(ref['truncated'])

    def test_publisher_preserves_exact_target_and_does_not_create_dot_events(self):
        message = self.send('Deliver exact context', self.answer['id'])
        self.store.bind(self.owner, self.thread, 'verified-fixture-subscription')
        delivered = []
        for _ in range(3):
            publish_once(self.store, 'owner', lambda subscription, event: (delivered.append(event), 202)[1])
        event = next(e for e in delivered if e['data']['message_id'] == message['id'])
        self.assertEqual(event['data']['in_reply_to'], self.answer['id'])
        self.assertEqual(2, len(delivered))
        self.assertEqual(2, self.store.db.execute('SELECT count(*) FROM outbox').fetchone()[0])
        state = self.store.db.execute('SELECT seen,manual_unread,resolved FROM dot_reply_state WHERE message=?', (self.answer['id'],)).fetchone()
        self.assertEqual((0, 1, 0), tuple(state))

    def test_corrupt_target_event_recovery_fails_closed(self):
        message = self.send('Do not guess', self.answer['id'])
        raw = self.store.db.execute('SELECT payload FROM outbox WHERE message=?', (message['id'],)).fetchone()[0]
        payload = json.loads(raw); payload['data']['in_reply_to'] = self.original['id']
        self.store.db.execute('UPDATE outbox SET payload=? WHERE message=?', (json.dumps(payload), message['id']))
        with self.assertRaisesRegex(Rejected, 'inconsistent'):
            self.store.pending(self.dot)

    def test_upgrade_preserves_existing_history_and_notifications(self):
        before = self.store.read(self.owner, self.thread)
        notices = self.store.notifications(self.owner, ['project'])
        self.store.db.execute('DROP TABLE owner_reply_targets')
        self.store.close(); self.store = Store(self.path)
        self.assertEqual(before, self.store.read(self.owner, self.thread))
        self.assertEqual(notices, self.store.notifications(self.owner, ['project']))
        self.send('New reply after upgrade', self.answer['id'])
        self.assertEqual([], self.store.db.execute('PRAGMA foreign_key_check').fetchall())


class BrowserOwnerReplies(unittest.TestCase):
    setUp = projects.ProjectTests.setUp
    tearDown = projects.ProjectTests.tearDown
    pair = projects.ProjectTests.pair
    # Use the existing isolated authoritative project/issue resolver fixture.
    def test_browser_send_linked_replies_issue_project_and_cross_scope_rejection(self):
        for target in [{'workspace':self.workspace}, {'project':self.project}]:
            args = {**target, 'request':uid(), 'body':'First'}
            original = self.api.send(self.session, args)
            request = {**target, 'request':uid(), 'body':'Exact reply', 'in_reply_to':original['id']}
            message = self.api.send(self.session, request)
            self.assertEqual(message, self.api.send(self.session, request))
            page = self.api.page(self.session, self.workspace) if 'workspace' in target else self.api.project_page(self.session, self.project)
            self.assertTrue(page['capabilities']['message_replies'])
            ref = next(m for m in page['messages'] if m['id'] == message['id'])['reply_reference']
            self.assertEqual(ref['id'], original['id'])
            with self.assertRaises(Rejected): self.api.send(self.session, {**request, 'in_reply_to':message['id']})
            other = {'project':self.other, 'request':uid(), 'body':'Cross project', 'in_reply_to':original['id']}
            with self.assertRaises(Rejected): self.api.send(self.session, other)
            for invalid in [None, [], {}, 7, '']:
                with self.assertRaises(Rejected): self.api.send(self.session, {**target, 'request':uid(), 'body':'Invalid target', 'in_reply_to':invalid})
            for injected in [{'owner':'foreign'}, {'reply_to':original['id']}, {'event_id':'forged'}, {'reply_reference':{'excerpt':'forged'}}]:
                with self.assertRaises(Rejected): self.api.send(self.session, {**request, **injected})
