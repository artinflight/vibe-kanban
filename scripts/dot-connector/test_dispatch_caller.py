import json
import unittest

import test_dispatch_notes as fixtures
import dispatch_notes as notes
from dispatch_attribution import current_caller, caller_record, presentation, HISTORICAL
from sidechat import Store, Principal
from prepare_dispatch_attribution import adapter_patch, store_patch


class DispatchCallerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.DispatchNoteTests();self.fixture.setUp()

    def tearDown(self):self.fixture.tearDown()

    def test_transport_owner_name_target_and_caller_claims_cannot_identify_an_initiator(self):
        f=self.fixture
        f.args.update(origin='root_dot',caller={'name':'Dot','verified':True},manager='T18',owner_display_name='dot')
        result=f.observe(caller={'kind':'manager','name':'Manager','verification':'verified'})
        self.assertEqual('unknown',f.receipt(result)['caller']['kind'])
        self.assertFalse(f.receipt(result)['ownership_signal'])
        runtime=f.factory()
        try:
            row=runtime.journal.with_caller(runtime.journal.db.execute('SELECT * FROM dispatch_receipts').fetchone())
            self.assertEqual('unknown',runtime.native.verify(row).caller['kind'])
        finally:runtime.close()
        store=Store(f.chat)
        try:
            text=store.db.execute('SELECT body FROM messages').fetchone()[0]
            self.assertIn('The workspace agent was prompted',text);self.assertIn('Caller: unknown',text)
            self.assertIn(f.execution,text);self.assertNotIn('Dot prompted',text);self.assertNotIn('T18',text)
        finally:store.close()
        self.assertEqual(current_caller(),notes.current_caller())
        for actor in ('root_dot','manager','native_user'):
            self.assertEqual('unknown',caller_record({'kind':actor,'verification':'verified'})['kind'])

    def test_current_unknown_caller_is_durable_and_does_not_change_on_retry(self):
        f=self.fixture;first=f.receipt(f.observe())
        self.assertEqual(current_caller(),first['caller'])
        second=f.receipt(f.observe(caller={'kind':'root_dot','verification':'verified'}))
        self.assertEqual(first,second);self.assertEqual((1,0,1),f.counts())
        runtime=f.factory()
        try:
            metadata=runtime.journal.db.execute('SELECT caller FROM dispatch_receipt_callers').fetchone()[0]
            self.assertEqual(current_caller(),json.loads(metadata))
        finally:runtime.close()
        store=Store(f.chat)
        try:
            row=dict(store.db.execute('SELECT * FROM messages').fetchone())
            meta=presentation(store,Principal('alice','dot'),row)
            self.assertEqual(current_caller(),meta['caller']);self.assertFalse(meta['ownership_signal'])
            self.assertEqual(row['body'],meta['presentation']['body'])
        finally:store.close()

    def test_legacy_receipt_retry_never_backfills_caller_or_rewrites_a_note(self):
        f=self.fixture;f.observe()
        store=Store(f.chat)
        old_body='Dot prompted this workspace\'s agent to continue the requested work.'
        import hashlib
        store.db.execute('UPDATE messages SET body=?,hash=?',(old_body,hashlib.sha256(old_body.encode()).hexdigest()))
        store.db.execute('DROP TABLE dispatch_note_callers')
        store.db.execute('UPDATE dot_reply_state SET manual_unread=1,attention_kind=\'question\',resolved=0')
        before={table:[tuple(r) for r in store.db.execute('SELECT * FROM '+table)] for table in
                ('messages','dot_reply_state','dispatch_notes','scopes','threads','outbox')}
        store.close()
        runtime=f.factory();old_receipt=tuple(runtime.journal.db.execute('SELECT * FROM dispatch_receipts').fetchone())
        runtime.journal.db.execute('DROP TABLE dispatch_receipt_callers');runtime.close()
        result=f.receipt(f.observe())
        self.assertEqual(HISTORICAL,result['caller']['reason'])
        runtime=f.factory()
        try:
            self.assertEqual(old_receipt,tuple(runtime.journal.db.execute('SELECT * FROM dispatch_receipts').fetchone()))
            self.assertEqual(0,runtime.journal.db.execute('SELECT COUNT(*) FROM dispatch_receipt_callers').fetchone()[0])
        finally:runtime.close()
        store=Store(f.chat)
        try:
            thread=store.db.execute('SELECT id FROM threads').fetchone()[0]
            message=store.read(Principal('alice','dot'),thread,display_workspace=f.workspace)['messages'][0]
            self.assertEqual(old_body,message['body'])
            derived=message['dispatch_note']
            self.assertEqual(HISTORICAL,derived['caller']['reason'])
            self.assertIn('Caller: unknown',derived['presentation']['body'])
            self.assertEqual('Dispatch',derived['presentation']['author_label'])
            self.assertIn(f.execution,derived['presentation']['body'])
            self.assertTrue(message['manual_unread']);self.assertFalse(message['attention']['resolved'])
            self.assertEqual(before,{table:[tuple(r) for r in store.db.execute('SELECT * FROM '+table)] for table in before})
        finally:store.close()

    def test_pending_receipt_recovery_keeps_unknown_caller_and_exact_execution(self):
        f=self.fixture;runtime=f.factory()
        runtime.opened=lambda: (_ for _ in ()).throw(OSError('fixture unavailable'))
        output=notes.observe('start_workspace',f.args,f.result,caller=current_caller(),factory=lambda:runtime)
        self.assertEqual('pending',f.receipt(output)['state'])
        recovered=notes.recover_pending(f.factory)
        self.assertEqual('noted',recovered[0]['state']);self.assertEqual(current_caller(),recovered[0]['caller'])
        self.assertEqual(f.execution,recovered[0]['execution_id']);self.assertEqual((1,0,1),f.counts())

    def test_presentation_cannot_label_a_conversation_or_other_owner(self):
        f=self.fixture;f.observe();store=Store(f.chat)
        try:
            row=dict(store.db.execute('SELECT * FROM messages').fetchone())
            self.assertEqual({},presentation(store,Principal('bob','dot'),row))
            store.db.execute('DELETE FROM dispatch_notes')
            self.assertEqual({},presentation(store,Principal('alice','dot'),row))
        finally:store.close()

    def test_upgrade_patches_only_exact_old_hooks_and_preserves_shared_store_bytes(self):
        source='''class Adapter:
    def handle(self,name,args):
        if name=='follow':
            from dispatch_notes import observe
            return observe(name,args,local_followup(args))
        from dispatch_notes import observe
        return observe(name,args,dispatch_start(local_start,args))
'''
        result=adapter_patch(source)
        self.assertEqual(2,result.count('caller=current_caller()'))
        self.assertNotIn('_meta',result)
        with self.assertRaises(ValueError):adapter_patch(result)
        store='''class Store:
    def read(self):
        if True:
            if dispatch_workspace:
                message['dispatch_note']={'workspace_id':dispatch_workspace,'execution_id':dispatch_execution}
        return message
    def newer_owner_management(self):
        return 'explicit association preserved'
'''
        patched=store_patch(store)
        self.assertIn('def newer_owner_management',patched)
        with self.assertRaises(ValueError):store_patch(patched)


if __name__=='__main__':unittest.main()
