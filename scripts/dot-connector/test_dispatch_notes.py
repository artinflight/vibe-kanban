import dataclasses
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'dot-sidechat'))
from sidechat import Store, Principal, Rejected
import dispatch_notes as notes
from prepare_dispatch_notes import adapter_patch, assert_ast_preserved, status_patch, worker_patch


class DispatchNoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.chat, self.ledger, self.vibe = (self.root/n for n in ('chat.sqlite','receipts.sqlite','vibe.sqlite'))
        self.project, self.issue, self.workspace, self.session, self.execution = [str(uuid.uuid4()) for _ in range(5)]
        db = sqlite3.connect(self.vibe)
        db.executescript('''CREATE TABLE projects(id BLOB PRIMARY KEY);
            CREATE TABLE tasks(id BLOB PRIMARY KEY,project_id BLOB);
            CREATE TABLE workspaces(id BLOB PRIMARY KEY,task_id BLOB);
            CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB);
            CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,run_reason TEXT,dropped INTEGER,status TEXT);''')
        b = lambda x: uuid.UUID(x).bytes
        db.execute('INSERT INTO projects VALUES (?)',(b(self.project),))
        db.execute('INSERT INTO tasks VALUES (?,?)',(b(self.issue),b(self.project)))
        db.execute('INSERT INTO workspaces VALUES (?,?)',(b(self.workspace),b(self.issue)))
        db.execute('INSERT INTO sessions VALUES (?,?)',(b(self.session),b(self.workspace)))
        db.execute('INSERT INTO execution_processes VALUES (?,?,?,0,?)',(b(self.execution),b(self.session),'codingagent','running'))
        db.commit();db.close()
        store = Store(self.chat)
        store.db.execute('INSERT INTO project_grants VALUES (?,?)',('alice',self.project));store.close()
        test = self
        class FixtureRuntime(notes.Runtime):
            def __init__(self):
                self.owner = 'alice';self.journal = notes.Journal(test.ledger)
                self.native = notes.NativeReader(test.vibe);self.opened = lambda: notes.open_note_store(test.chat)
        self.factory = FixtureRuntime
        self.args = {'project_id':self.project,'issue_id':self.issue,'prompt':'SENSITIVE_PRIVATE_PROMPT_NEVER_COPY'}
        self.result = {'isError':False,'content':[{'type':'text','text':json.dumps({
            'workspace':{'id':self.workspace},'execution_process':{'id':self.execution,'session_id':self.session,
                'executor_action':{'prompt':self.args['prompt']}}})}]}

    def tearDown(self): self.temp.cleanup()

    def observe(self, **kw):
        return notes.observe('start_workspace',self.args,self.result,factory=self.factory,**kw)

    def receipt(self, result): return json.loads(result['content'][-1]['text'])['dispatch_note']

    def counts(self):
        store = Store(self.chat)
        try: return tuple(store.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('messages','outbox','scopes'))
        finally: store.close()

    def test_first_note_has_verified_execution_no_owner_event_or_forged_reply(self):
        before = hashlib.sha256(self.vibe.read_bytes()).hexdigest()
        result = self.observe();status = self.receipt(result)
        self.assertEqual('noted',status['state']);self.assertEqual(self.execution,status['execution_id'])
        self.assertEqual(self.result['content'][0],result['content'][0])
        store = Store(self.chat)
        try:
            context = {'thread_id':store.db.execute('SELECT id FROM threads WHERE owner=? AND project=? AND issue=?',('alice',self.project,self.issue)).fetchone()[0]}
            history = store.read(Principal('alice','dot'),context['thread_id'])
            self.assertEqual(1,len(history['messages']))
            message = history['messages'][0]
            self.assertEqual('dot',message['role']);self.assertIsNone(message['reply_to'])
            self.assertIn('begin the requested work',message['body']);self.assertIn(self.execution,message['body'])
            self.assertNotIn('SENSITIVE',message['body']);self.assertFalse(message['seen'])
            binding = store.db.execute('SELECT * FROM dispatch_notes').fetchone()
            self.assertEqual(self.execution,binding['execution']);self.assertEqual(self.session,binding['session'])
            summary = store.notifications(Principal('alice','owner'),[self.project])['issues'][0]
            self.assertEqual(1,summary['unread_count']);self.assertEqual(0,summary['needs_attention_count'])
            self.assertEqual((1,0,1),self.counts())
            # A later real owner message is still required for an ordinary reply.
            with self.assertRaises(Rejected):
                store.append(Principal('alice','dot'),history['thread']['id'],self.workspace,str(uuid.uuid4()),'fake',message['id'],'invented')
            owner = store.append(Principal('alice','owner'),history['thread']['id'],self.workspace,str(uuid.uuid4()),'Actual owner request')
            store.append(Principal('alice','dot'),history['thread']['id'],self.workspace,str(uuid.uuid4()),'Actual reply',owner['id'],'sidechat_'+owner['id'])
        finally: store.close()
        self.assertEqual(before,hashlib.sha256(self.vibe.read_bytes()).hexdigest())
        self.assertNotIn(b'SENSITIVE_PRIVATE_PROMPT_NEVER_COPY',self.ledger.read_bytes())
        self.assertNotIn(b'SENSITIVE_PRIVATE_PROMPT_NEVER_COPY',self.chat.read_bytes())

    def test_user_origin_failed_and_uncertain_dispatches_produce_no_note(self):
        factory = Mock(side_effect=AssertionError('Must not open state'))
        self.assertIs(self.result,notes.observe('start_workspace',self.args,self.result,origin='user',factory=factory))
        failed = {'isError':True,'content':[{'type':'text','text':'exact PR271 contract'}]}
        self.assertIs(failed,notes.observe('start_workspace',self.args,failed,factory=factory))
        def dispatch(): raise TimeoutError('unknown backend response')
        with self.assertRaises(TimeoutError): notes.observe('start_workspace',self.args,dispatch(),factory=factory)
        factory.assert_not_called();self.assertEqual((0,0,0),self.counts())

    def test_duplicate_receipts_restart_and_mcp_response_loss_have_one_note(self):
        first = self.receipt(self.observe())  # Simulate losing this MCP response.
        retry = self.receipt(self.observe())
        self.assertEqual(first,retry);self.assertEqual((1,0,1),self.counts())
        self.assertEqual([],notes.recover_pending(self.factory))
        self.assertEqual(0,self.ledger.stat().st_mode & 0o077)

    def test_note_commit_then_lost_journal_ack_reconciles_without_duplicate(self):
        runtime = self.factory();real_mark = runtime.journal.mark
        calls = [0]
        def mark(*a,**k):
            calls[0]+=1
            if calls[0]==1: raise OSError('lost acknowledgment after note persisted')
            return real_mark(*a,**k)
        runtime.journal.mark = mark
        result = notes.observe('start_workspace',self.args,self.result,factory=lambda:runtime)
        self.assertEqual('pending',self.receipt(result)['state']);self.assertEqual((1,0,1),self.counts())
        recovered = notes.recover_pending(self.factory)
        self.assertEqual('noted',recovered[0]['state']);self.assertEqual((1,0,1),self.counts())

    def test_accepted_receipt_recovers_when_chat_write_was_unavailable(self):
        runtime = self.factory();runtime.opened = Mock(side_effect=OSError('private unavailable details'))
        result = notes.observe('start_workspace',self.args,self.result,factory=lambda:runtime)
        self.assertEqual('pending',self.receipt(result)['state']);self.assertEqual((0,0,0),self.counts())
        self.assertNotIn('private',json.dumps(self.receipt(result)))
        self.assertEqual('noted',notes.recover_pending(self.factory)[0]['state'])
        self.assertEqual((1,0,1),self.counts())

    def test_followup_resolves_exact_session_workspace_and_safe_purpose(self):
        result = {'isError':False,'content':[{'type':'text','text':json.dumps({'session_id':self.session,
            'execution_id':self.execution,'execution':{'id':self.execution,'session_id':self.session}})}]}
        output = notes.observe('run_session_prompt',{'session_id':self.session,'prompt':'SENSITIVE'},result,factory=self.factory)
        self.assertEqual(self.workspace,self.receipt(output)['workspace_id'])
        store = Store(self.chat)
        try:self.assertIn('continue the requested work',store.db.execute('SELECT body FROM messages').fetchone()[0])
        finally:store.close()

    def test_bad_session_workspace_and_changed_issue_never_write(self):
        for kind in ('session','workspace','issue'):
            with self.subTest(kind=kind):
                journal=notes.Journal(self.ledger);journal.db.execute('DELETE FROM dispatch_receipts');journal.close()
                changed = json.loads(self.result['content'][0]['text'])
                args = dict(self.args)
                if kind=='session':changed['execution_process']['session_id']=str(uuid.uuid4())
                if kind=='workspace':changed['workspace']['id']=str(uuid.uuid4())
                if kind=='issue':args['issue_id']=str(uuid.uuid4())
                result = {'isError':False,'content':[{'type':'text','text':json.dumps(changed)}]}
                output = notes.observe('start_workspace',args,result,factory=self.factory)
                self.assertEqual('pending',self.receipt(output)['state']);self.assertEqual((0,0,0),self.counts())

    def test_capacity_queue_missing_receipt_and_setup_do_not_claim_agent_acceptance(self):
        for data in ({'status':'queued','execution_id':None,'session_id':self.session},{},
                     {'execution_process':{'id':'invalid'},'workspace':{'id':self.workspace}}):
            result={'isError':False,'content':[{'type':'text','text':json.dumps(data)}]}
            output=notes.observe('run_session_prompt',{'session_id':self.session},result,factory=self.factory)
            self.assertEqual('awaiting_execution_receipt',self.receipt(output)['state'])
        db=sqlite3.connect(self.vibe);db.execute("UPDATE execution_processes SET run_reason='setupscript'");db.commit();db.close()
        self.assertEqual('pending',self.receipt(self.observe())['state']);self.assertEqual((0,0,0),self.counts())

    def test_owner_isolation_and_existing_scope_cannot_be_relinked(self):
        runtime=self.factory();row=runtime.journal.accept('alice',notes.receipt_from_result('start_workspace',self.args,self.result))
        verified=runtime.native.verify(row);runtime.close()
        store=Store(self.chat)
        try:
            for principal in (Principal('bob','dispatch'),Principal('alice','owner'),Principal('alice','dot')):
                with self.assertRaises(Rejected):notes.record_dispatch_note(store,principal,verified)
            with self.assertRaises(Rejected):
                notes.record_dispatch_note(store,Principal('bob','dispatch'),dataclasses.replace(verified,owner='bob'))
            store.register_scope('alice',self.project,str(uuid.uuid4()),self.workspace)
            with self.assertRaises(Rejected):notes.record_dispatch_note(store,Principal('alice','dispatch'),verified)
            self.assertEqual(0,store.db.execute('SELECT count(*) FROM messages').fetchone()[0])
        finally:store.close()

    def test_concurrent_recovery_and_receipt_retries_insert_one_note(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.receipt(self.observe()),range(8)))
        self.assertEqual(1,len({r.get('message_id') for r in results if r['state']=='noted'}))
        notes.recover_pending(self.factory)
        self.assertEqual((1,0,1),self.counts())

    def test_recovery_batch_yields_to_existing_publisher_work(self):
        runtime=types.SimpleNamespace(owner='alice',journal=Mock(),deliver=Mock(return_value={'state':'pending'}),close=Mock())
        runtime.journal.pending.return_value=[{},{}]
        with patch.object(notes.time,'monotonic',side_effect=[0,0.1,0.6]):
            self.assertEqual([{'state':'pending'}],notes.recover_pending(lambda:runtime))
        runtime.deliver.assert_called_once();runtime.close.assert_called_once()

    def test_note_receipt_completion_is_monotonic(self):
        self.observe()
        runtime=self.factory()
        try:
            row=dict(runtime.journal.db.execute('SELECT * FROM dispatch_receipts').fetchone())
            runtime.journal.mark(row,error='late competing failure')
            after=dict(runtime.journal.db.execute('SELECT * FROM dispatch_receipts').fetchone())
            self.assertEqual('noted',after['state']);self.assertEqual(row['message'],after['message'])
        finally:runtime.close()

    def test_pending_recovery_is_fair_when_an_older_receipt_stays_blocked(self):
        runtime=self.factory()
        try:
            one=notes.receipt_from_result('start_workspace',self.args,self.result)
            first=runtime.journal.accept('alice',one)
            runtime.journal.accept('alice',dict(one,execution=str(uuid.uuid4())))
            self.assertEqual(first['execution'],runtime.journal.pending('alice',limit=1)[0]['execution'])
            runtime.journal.mark(first,error='still blocked')
            self.assertNotEqual(first['execution'],runtime.journal.pending('alice',limit=1)[0]['execution'])
        finally:runtime.close()

    def test_readonly_status_filters_owner_and_never_creates_or_recovers(self):
        connector=types.SimpleNamespace(ROOT=self.root,owner=lambda:'alice')
        with patch.dict(sys.modules,{'sidechat_connector':types.SimpleNamespace(),'connector':connector}):
            self.assertEqual('no_recorded_dispatch',notes.workspace_status(self.workspace)['status'])
            self.assertFalse((self.root/'dispatch-receipts.sqlite').exists())
        self.observe()
        connector.ROOT=self.root
        # Fixture journal uses an explicit test path; put it at the production name.
        runtime=self.factory();runtime.journal.db.execute('PRAGMA wal_checkpoint(TRUNCATE)');runtime.close()
        (self.root/'dispatch-receipts.sqlite').write_bytes(self.ledger.read_bytes())
        (self.root/'dispatch-receipts.sqlite').chmod(0o600)
        with patch.dict(sys.modules,{'sidechat_connector':types.SimpleNamespace(),'connector':connector}):
            self.assertEqual(1,len(notes.workspace_status(self.workspace)['receipts']))
            connector.owner=lambda:'bob'
            self.assertEqual([],notes.workspace_status(self.workspace)['receipts'])


if __name__=='__main__':unittest.main()
