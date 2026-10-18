import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from sidechat import Store, Principal, Rejected
import notification_ack as ack


class NotificationAcknowledgementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'threads.sqlite'
        self.now = 1000
        self.owner = Principal('alice', 'owner')
        self.dot = Principal('alice', 'dot')
        self.project, self.issue, self.workspace, self.sibling = [str(uuid.uuid4()) for _ in range(4)]
        self.store = Store(self.path, lambda: self.now)
        for workspace in (self.workspace, self.sibling):
            self.store.register_scope('alice', self.project, self.issue, workspace)
        self.thread = self.store.resolve(self.owner, self.project, self.issue, self.workspace)['id']
        self.store.db.execute('CREATE TABLE coding_agent_flags(id TEXT,unread INTEGER)')
        self.store.db.execute("INSERT INTO coding_agent_flags VALUES ('retained',1)")
        self.first = self.note(self.workspace)
        self.other = self.note(self.sibling)
        request = self.store.append(self.owner, self.thread, self.workspace, str(uuid.uuid4()), 'PRIVATE OWNER TEXT')
        self.conversation = self.store.append(self.dot, self.thread, self.workspace, str(uuid.uuid4()),
            'PRIVATE CONVERSATION', request['id'], 'sidechat_'+request['id'])['id']

    def tearDown(self):
        self.assertEqual(1, self.store.db.execute('SELECT unread FROM coding_agent_flags').fetchone()[0])
        self.store.close()
        self.temp.cleanup()

    def note(self, workspace, owner='alice', thread=None):
        thread = thread or self.thread
        mid, execution, session = [str(uuid.uuid4()) for _ in range(3)]
        seq = self.store.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM messages WHERE thread=?', (thread,)).fetchone()[0]
        self.store.db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)',
            (mid,thread,seq,'dot','Safe dispatch note',workspace,str(uuid.uuid4()),None,'fixture_hash',self.now))
        self.store.db.execute('INSERT INTO dot_reply_state(message,updated) VALUES (?,?)', (mid,self.now))
        self.store.db.execute('INSERT INTO dispatch_notes VALUES (?,?,?,?,?,?,?)',
            (owner,execution,workspace,session,'run_session_prompt',thread,mid))
        return mid

    def inventory(self, **extra):
        return ack.call(self.path,self.dot,ack.INVENTORY,dict(workspace_id=self.workspace,**extra))

    def selection(self, message=None):
        row = next(r for r in self.inventory()['notifications'] if r['message_id'] == (message or self.first))
        return {k:row[k] for k in ('thread_id','message_id','state_token')}

    def acknowledge(self, items=None):
        return ack.call(self.path,self.dot,ack.ACKNOWLEDGE,{'workspace_id':self.workspace,'items':items or [self.selection()]})

    def state(self, message):
        return dict(self.store.db.execute('SELECT * FROM dot_reply_state WHERE message=?',(message,)).fetchone())

    def test_inventory_is_readonly_body_free_owner_and_workspace_scoped(self):
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        before = self.path.read_bytes()
        with patch.object(Store,'__init__',side_effect=AssertionError('No schema/backfill writes')):
            page = self.inventory()
        self.assertEqual(before,self.path.read_bytes())
        self.assertEqual({self.first,self.conversation},{r['message_id'] for r in page['notifications']})
        self.assertNotIn('PRIVATE',json.dumps(page));self.assertNotIn('Safe dispatch',json.dumps(page))
        reader=ack.opened(self.path)
        try:
            with self.assertRaises(sqlite3.OperationalError): reader.db.execute('UPDATE dot_reply_state SET seen=1')
        finally: reader.close()
        self.assertFalse(self.state(self.first)['seen'])
        for principal in (Principal('bob','dot'),self.owner,Principal('alice','publisher')):
            with self.assertRaises(Rejected):ack.call(self.path,principal,ack.INVENTORY,{'workspace_id':self.workspace})

    def test_exact_note_only_conversation_and_sibling_flags_and_events_unchanged(self):
        before = self.state(self.other),self.state(self.conversation)
        events = list(self.store.db.execute('SELECT * FROM outbox'))
        rows = list(self.store.db.execute('SELECT * FROM messages'))
        result = self.acknowledge()
        self.assertEqual('acknowledged',result['outcomes'][0]['outcome'])
        self.assertTrue(result['outcomes'][0]['seen'])
        self.assertEqual(before,(self.state(self.other),self.state(self.conversation)))
        self.assertEqual(events,list(self.store.db.execute('SELECT * FROM outbox')))
        self.assertEqual(rows,list(self.store.db.execute('SELECT * FROM messages')))
        self.assertEqual('selected_ids_only',result['scope'])

    def test_sibling_wrong_owner_or_non_dot_selection_rejects_entire_batch(self):
        selected=self.selection()
        bob_project,bob_issue,bob_workspace=[str(uuid.uuid4()) for _ in range(3)]
        self.store.register_scope('bob',bob_project,bob_issue,bob_workspace)
        bob_thread=self.store.resolve(Principal('bob','owner'),bob_project,bob_issue,bob_workspace)['id']
        bob_note=self.note(bob_workspace,owner='bob',thread=bob_thread)
        for bad in (dict(selected,message_id=bob_note),dict(selected,message_id=self.other),dict(selected,thread_id=bob_thread),
                    dict(selected,message_id=str(uuid.uuid4())),
                    dict(selected,message_id=self.store.db.execute("SELECT id FROM messages WHERE role='owner'").fetchone()[0])):
            with self.assertRaises(Rejected):self.acknowledge([selected,bad])
            self.assertFalse(self.state(self.first)['seen'])
        with self.assertRaises(Rejected):ack.call(self.path,Principal('bob','dot'),ack.ACKNOWLEDGE,
            {'workspace_id':self.workspace,'items':[selected]})

    def test_unresolved_question_or_action_is_preserved_even_after_inventory(self):
        for attention in ('question','action'):
            selected=self.selection();self.store.set_sidechat_attention(self.dot,self.thread,self.workspace,self.first,attention)
            before=self.state(self.first)
            result=self.acknowledge([selected])['outcomes'][0]
            self.assertEqual('unresolved_attention',result['outcome']);self.assertFalse(result['seen'])
            self.assertEqual(before,self.state(self.first))
            self.store.set_sidechat_attention(self.dot,self.thread,self.workspace,self.first,'resolve')
        selected=self.selection();result=self.acknowledge([selected])['outcomes'][0]
        self.assertEqual('acknowledged',result['outcome']);self.assertTrue(result['attention']['resolved'])

    def test_manual_unread_before_or_after_inventory_and_lost_response_retry(self):
        selected=self.selection()
        self.assertEqual('acknowledged',self.acknowledge([selected])['outcomes'][0]['outcome'])
        self.store.set_reply_read_state(self.owner,self.thread,self.workspace,self.first,'unread')
        before=self.state(self.first)
        for selection in (selected,self.selection()):
            result=self.acknowledge([selection])['outcomes'][0]
            self.assertEqual('manual_unread',result['outcome']);self.assertFalse(result['seen'])
            self.assertEqual(before,self.state(self.first))

    def test_genuine_conversation_is_protected_even_if_explicitly_selected(self):
        before=self.state(self.conversation)
        result=self.acknowledge([self.selection(self.conversation)])['outcomes'][0]
        self.assertEqual('genuine_conversation',result['outcome'])
        self.assertEqual(before,self.state(self.conversation))

    def test_duplicate_calls_do_not_rewrite_timestamp_or_swallow_new_message(self):
        selected=self.selection()
        first=self.acknowledge([selected]);before=self.state(self.first)
        self.now+=10;new=self.note(self.workspace)
        retry=self.acknowledge([selected])
        self.assertEqual('already_seen',retry['outcomes'][0]['outcome'])
        self.assertEqual(before,self.state(self.first));self.assertFalse(self.state(new)['seen'])
        self.assertGreater(retry['through'],first['through'])

    def test_new_message_between_inventory_and_ack_remains_unread(self):
        selected=self.selection();new=self.note(self.workspace)
        result=self.acknowledge([selected])
        self.assertEqual([self.first],[r['message_id'] for r in result['outcomes']])
        self.assertFalse(self.state(new)['seen'])

    def test_stale_state_token_does_not_ack_changed_item(self):
        selected=self.selection();self.store.db.execute('UPDATE dot_reply_state SET updated=updated+1 WHERE message=?',(self.first,))
        before=self.state(self.first)
        result=self.acknowledge([selected])['outcomes'][0]
        self.assertEqual('state_changed',result['outcome']);self.assertEqual(before,self.state(self.first))

    def test_exact_bounds_no_wildcards_extra_auth_or_duplicate_ids(self):
        selection=self.selection()
        for items in ([],[selection]*2,[selection]*51,[{}],
                      [dict(selection,owner='alice')],[dict(selection,state_token='*')],
                      [dict(selection,message_id='*')]):
            with self.assertRaises(Rejected):ack.call(self.path,self.dot,ack.ACKNOWLEDGE,{'workspace_id':self.workspace,'items':items})
        for args in ({'workspace_id':'*'},{'workspace_id':self.workspace,'owner':'alice'},
                     {'workspace_id':self.workspace,'all':True}):
            with self.assertRaises(Rejected):ack.call(self.path,self.dot,ack.INVENTORY,args)
        self.assertFalse(self.state(self.first)['seen'])

    def test_inventory_pagination_has_fixed_upper_sequence_and_does_not_mark_seen(self):
        page=self.inventory(limit=1);self.assertIsNotNone(page['next_after'])
        new=self.note(self.workspace)
        second=self.inventory(after=page['next_after'],through=page['through'],limit=1)
        self.assertEqual([self.conversation],[r['message_id'] for r in second['notifications']])
        self.assertIsNone(second['next_after']);self.assertFalse(self.state(new)['seen'])
        self.assertFalse(self.state(self.first)['seen'])

    def test_malformed_dispatch_workspace_binding_never_authorizes_ack(self):
        selected=self.selection()
        self.store.db.execute('UPDATE dispatch_notes SET workspace=? WHERE message=?',(self.sibling,self.first))
        result=self.acknowledge([selected])['outcomes'][0]
        self.assertEqual('genuine_conversation',result['outcome']);self.assertFalse(result['seen'])

    def test_incompatible_read_state_schema_fails_closed_without_migration(self):
        self.store.db.execute('ALTER TABLE dot_reply_state RENAME COLUMN manual_unread TO legacy_manual')
        with self.assertRaises(sqlite3.OperationalError):self.inventory()
        self.assertFalse(self.state(self.first)['seen'])
        columns={r[1] for r in self.store.db.execute('PRAGMA table_info(dot_reply_state)')}
        self.assertNotIn('manual_unread',columns)

    def test_connector_registration_dispatch_and_unchanged_browser_owner_boundary(self):
        import connector
        with patch.object(connector,'ROOT',self.path.parent),patch.object(connector,'owner',return_value='alice'),\
             patch.object(connector,'opened',side_effect=AssertionError('Do not open mutable normal Store')):
            self.assertIn(ack.INVENTORY,connector.NAMES);self.assertIn(ack.ACKNOWLEDGE,connector.NAMES)
            result=connector.call(ack.INVENTORY,{'workspace_id':self.workspace})
            self.assertEqual(self.thread,result['thread_id'])
            selection=self.selection()
            self.assertEqual('acknowledged',connector.call(ack.ACKNOWLEDGE,{'workspace_id':self.workspace,'items':[selection]})['outcomes'][0]['outcome'])
        with self.assertRaises(Rejected):self.store.seen_replies(self.dot,self.thread,self.workspace,[self.first])


if __name__=='__main__':unittest.main()
