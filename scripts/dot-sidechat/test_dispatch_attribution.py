"""Workspace presentation of verified notes; never infer dispatch from body text."""
import hashlib
from pathlib import Path
import uuid
import unittest
import test_browser
from sidechat import Principal, Rejected, Store
from browser_api import BrowserAPI


def uid(): return str(uuid.uuid4())


class DispatchAttribution(unittest.TestCase):
    setUp = test_browser.BrowserTests.setUp
    tearDown = test_browser.BrowserTests.tearDown

    def sibling(self):
        sibling = uid()
        target = self.workspace
        self.api.resolver = lambda workspace: dict(self.scope, workspace=workspace) if workspace in (target, sibling) else (_ for _ in ()).throw(Rejected('not found'))
        self.api.page(self.session, sibling)
        return sibling

    def note(self, workspace=None):
        workspace = workspace or self.workspace
        page = self.api.page(self.session, workspace)
        thread = page['thread']['id']
        message, execution = uid(), uid()
        body = 'Dot prompted this workspace\'s agent to continue the requested work.'
        with self.store.transaction():
            seq = self.store.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM messages WHERE thread=?', (thread,)).fetchone()[0]
            self.store.db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)', (message, thread, seq, 'dot', body, workspace, uid(), None, hashlib.sha256(body.encode()).hexdigest(), 1))
            self.store.db.execute('INSERT INTO dot_reply_state(message,updated) VALUES (?,?)', (message, 1))
            self.store.db.execute('INSERT INTO dispatch_notes VALUES (?,?,?,?,?,?,?)', ('owner', execution, workspace, uid(), 'run_session_prompt', thread, message))
        return message, thread

    def conversation(self, body='Shared actual reply', attention=None):
        owner = self.api.send(self.session, {'workspace':self.workspace, 'request':uid(), 'body':'Owner conversation'})
        thread = self.store.db.execute('SELECT thread FROM messages WHERE id=?', (owner['id'],)).fetchone()[0]
        reply = self.store.append(Principal('owner','dot'), thread, self.workspace, uid(), body, owner['id'], 'sidechat_'+owner['id'], attention=attention)
        return owner, reply

    def test_target_note_stays_unread_and_sibling_has_no_note_or_badge(self):
        sibling = self.sibling()
        note, thread = self.note()
        before = tuple(self.store.db.execute('SELECT * FROM dot_reply_state WHERE message=?', (note,)).fetchone())
        snapshot = self.api.notifications(self.session)
        issue = snapshot['issues'][0]
        self.assertEqual((1,0,0,0), tuple(issue[k] for k in ('unread_count','shared_unread_count','needs_attention_count','shared_needs_attention_count')))
        self.assertEqual([self.workspace], [r['workspace_id'] for r in snapshot['workspaces']])
        self.assertEqual([], self.api.page(self.session, sibling)['messages'])
        target = self.api.page(self.session, self.workspace)['messages'][0]
        self.assertEqual(note,target['id']);self.assertFalse(target['seen'])
        self.assertEqual(self.workspace,target['dispatch_note']['workspace_id'])
        self.assertIsNone(target['attention'])
        self.assertEqual(note, self.store.read(Principal('owner','dot'),thread)['messages'][0]['id'])
        self.assertEqual(before,tuple(self.store.db.execute('SELECT * FROM dot_reply_state WHERE message=?',(note,)).fetchone()))
        self.assertEqual(0,self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0])

    def test_shared_genuine_messages_stay_shared_and_are_not_detected_by_body(self):
        sibling = self.sibling(); note, _ = self.note()
        owner, reply = self.conversation(body="Dot prompted this workspace's agent to continue the requested work.", attention='question')
        self.assertEqual([owner['id'],reply['id']], [m['id'] for m in self.api.page(self.session,sibling)['messages']])
        notifications = self.api.notifications(self.session)
        self.assertEqual((2,0,0), tuple(notifications['issues'][0][k] for k in ('unread_count','shared_unread_count','shared_needs_attention_count')))
        self.api.seen(self.session,{'workspace':sibling,'messages':[reply['id']]})
        self.api.attention(self.session,{'workspace':sibling,'message':reply['id'],'action':'resolve'})
        self.assertEqual(1,self.api.notifications(self.session)['issues'][0]['unread_count'])
        self.assertFalse(self.api.page(self.session,self.workspace)['messages'][0]['seen'])
        self.assertEqual(3,self.store.db.execute('SELECT COUNT(*) FROM messages').fetchone()[0])

    def test_sibling_cannot_acknowledge_or_reclassify_foreign_dispatch(self):
        sibling = self.sibling(); note, _ = self.note(); _, reply = self.conversation()
        for operation, args in [(self.api.seen,{'workspace':sibling,'messages':[reply['id'],note]}),
                                (self.api.read_state,{'workspace':sibling,'message':note,'action':'read'}),
                                (self.api.attention,{'workspace':sibling,'message':note,'action':'action'})]:
            with self.assertRaises(Rejected): operation(self.session,args)
        self.assertEqual(2,self.api.notifications(self.session)['issues'][0]['unread_count'])
        self.api.seen(self.session,{'workspace':self.workspace,'messages':[note]})
        self.api.read_state(self.session,{'workspace':self.workspace,'message':note,'action':'unread'})
        self.assertTrue(self.api.page(self.session,self.workspace)['messages'][0]['manual_unread'])
        self.assertEqual([], [m for m in self.api.page(self.session,sibling)['messages'] if m['id']==note])

    def test_explicit_note_attention_remains_targeted_while_genuine_attention_is_shared(self):
        sibling=self.sibling();note,_=self.note();_,reply=self.conversation(attention='question')
        self.api.attention(self.session,{'workspace':self.workspace,'message':note,'action':'action'})
        snapshot=self.api.notifications(self.session)
        self.assertEqual(2,snapshot['issues'][0]['needs_attention_count'])
        self.assertEqual(0,snapshot['issues'][0]['shared_needs_attention_count'])
        self.assertEqual(2,snapshot['workspaces'][0]['needs_attention_count'])
        with self.assertRaises(Rejected):self.api.attention(self.session,{'workspace':sibling,'message':note,'action':'resolve'})
        self.api.attention(self.session,{'workspace':self.workspace,'message':note,'action':'resolve'})
        self.assertEqual(1,self.api.notifications(self.session)['issues'][0]['needs_attention_count'])
        self.assertFalse(next(m for m in self.api.page(self.session,sibling)['messages'] if m['id']==reply['id'])['attention']['resolved'])

    def test_both_targets_paginate_and_persist_without_losing_shared_history(self):
        sibling = self.sibling(); first, thread = self.note(); owner, reply = self.conversation(); second, _ = self.note(sibling)
        principal = Principal('owner','owner')
        ids=[]; after=0; through=None
        while True:
            page=self.store.read(principal,thread,after=after,through=through,limit=1,display_workspace=sibling)
            ids.extend(m['id'] for m in page['messages']);through=page['through']
            if page['next_after'] is None:break
            after=page['next_after']
        self.assertEqual([owner['id'],reply['id'],second],ids)
        self.store.close();self.store=Store(Path(self.temp.name)/"private.sqlite");self.api=BrowserAPI(self.store,self.api.resolver)
        self.assertEqual(2,len(self.api.notifications(self.session)['workspaces']))
        self.assertNotIn(first,[m['id'] for m in self.api.page(self.session,sibling)['messages']])
        self.assertEqual([],self.store.notifications(Principal('other','owner'),[self.scope['project']])['workspaces'])
        self.assertEqual([],self.store.notifications(principal,['ungranted'])['workspaces'])
