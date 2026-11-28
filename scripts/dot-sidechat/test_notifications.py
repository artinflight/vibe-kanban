import json
import unittest
import uuid
import http.client
import threading
from http.server import HTTPServer
import test_sidechat
import test_browser
from browser_api import handler
from sidechat import Principal, Rejected, Store


class NotificationContracts(unittest.TestCase):
    setUp=test_sidechat.Contracts.setUp
    tearDown=test_sidechat.Contracts.tearDown
    send=test_sidechat.Contracts.send
    reply=test_sidechat.Contracts.reply

    def counts(self):
        rows=self.s.notifications(self.owner,['p'])['issues']
        return (rows[0]['unread_count'],rows[0]['needs_attention_count']) if rows else (0,0)

    def test_read_and_attention_are_independent_and_durable(self):
        reply=self.reply(self.send(),attention='question')
        self.assertEqual((1,1),self.counts())
        self.s.read(self.owner,self.t)  # Fetching is not reading visible content.
        self.assertEqual((1,1),self.counts())
        self.s.seen_replies(self.owner,self.t,'w2',[reply['id']])
        self.assertEqual((0,1),self.counts())
        self.send(body='A follow-up does not resolve the question')
        self.assertEqual((0,1),self.counts())
        self.s.close();self.s=Store(self.path,lambda:self.now)
        self.assertEqual((0,1),self.counts())
        self.s.set_sidechat_attention(self.owner,self.t,'w2',reply['id'],'resolve')
        self.assertEqual((0,0),self.counts())
        self.s.close();self.s=Store(self.path,lambda:self.now)
        page=self.s.read(self.owner,self.t)
        dot=next(m for m in page['messages'] if m['id']==reply['id'])
        self.assertTrue(dot['seen']);self.assertTrue(dot['attention']['resolved'])
        self.s.tool(self.dot,'set_sidechat_attention',{'thread':self.t,'workspace':'w','message':reply['id'],'action':'reopen'})
        self.assertEqual(2,self.s.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0])
        self.assertEqual((0,1),self.counts())

    def test_resolve_does_not_mark_unread_reply_seen_and_plain_reply_can_be_flagged(self):
        reply=self.reply(self.send())
        self.assertEqual((1,0),self.counts())
        self.s.set_sidechat_attention(self.owner,self.t,'w',reply['id'],'action')
        self.assertEqual((1,1),self.counts())
        self.s.set_sidechat_attention(self.dot,self.t,'w',reply['id'],'resolve')
        self.assertEqual((1,0),self.counts())
        self.assertEqual(1,self.s.db.execute('SELECT count(*) FROM outbox').fetchone()[0])

    def test_exact_seen_ids_do_not_clear_a_new_reply_arriving_during_read(self):
        first=self.reply(self.send());second=self.reply(self.send())
        self.s.seen_replies(self.owner,self.t,'w',[first['id']])
        self.assertEqual((1,0),self.counts())
        self.assertFalse(next(m for m in self.s.read(self.owner,self.t)['messages'] if m['id']==second['id'])['seen'])

    def test_owner_scope_project_grants_and_atomic_batch_validation(self):
        owner_message=self.send();reply=self.reply(owner_message,attention='action')
        for principal in (Principal('bob','owner'),self.dot,self.publisher):
            with self.assertRaises(Rejected):self.s.seen_replies(principal,self.t,'w',[reply['id']])
        for messages in ([],[reply['id'],reply['id']],[reply['id'],owner_message['id']],[reply['id'],'missing']):
            with self.assertRaises(Rejected):self.s.seen_replies(self.owner,self.t,'w',messages)
        self.assertEqual((1,1),self.counts())
        self.assertEqual([],self.s.notifications(Principal('bob','owner'),['p'])['issues'])
        self.assertEqual([],self.s.notifications(self.owner,['other-project'])['issues'])
        with self.assertRaises(Rejected):self.s.set_sidechat_attention(self.owner,self.t,'missing',reply['id'],'resolve')
        with self.assertRaises(Rejected):self.s.set_sidechat_attention(self.dot,self.t,'w2',reply['id'],'resolve')
        with self.assertRaises(Rejected):self.s.set_sidechat_attention(self.owner,self.t,'w',owner_message['id'],'action')

    def test_reply_retry_preserves_seen_and_resolved_state_and_initial_annotation(self):
        message=self.send();request=str(uuid.uuid4())
        reply=self.reply(message,request=request,attention='question')
        self.s.seen_replies(self.owner,self.t,'w',[reply['id']])
        self.s.set_sidechat_attention(self.owner,self.t,'w',reply['id'],'action')
        self.s.set_sidechat_attention(self.owner,self.t,'w',reply['id'],'resolve')
        self.assertEqual(reply['id'],self.reply(message,request=request,attention='question')['id'])
        self.assertEqual((0,0),self.counts())
        with self.assertRaises(Rejected):self.reply(message,request=request,attention='action')
        self.assertEqual(1,self.s.db.execute("SELECT count(*) FROM messages WHERE role='dot'").fetchone()[0])

    def test_legacy_replies_become_unread_once_without_inventing_attention(self):
        reply=self.reply(self.send())
        self.s.db.execute('DROP TABLE dot_reply_state')
        self.s.close();self.s=Store(self.path,lambda:self.now)
        self.assertEqual((1,0),self.counts())
        self.s.seen_replies(self.owner,self.t,'w',[reply['id']])
        self.s.close();self.s=Store(self.path,lambda:self.now)
        self.assertEqual((0,0),self.counts())


class NotificationBrowserContracts(unittest.TestCase):
    setUp=test_browser.BrowserTests.setUp
    tearDown=test_browser.BrowserTests.tearDown

    def test_sibling_workspaces_share_state_and_relink_does_not_leak(self):
        owner=self.api.send(self.session,{'workspace':self.workspace,'request':str(uuid.uuid4()),'body':'Owner'})
        thread=self.store.db.execute('SELECT thread FROM messages WHERE id=?',(owner['id'],)).fetchone()[0]
        reply=self.store.append(Principal('owner','dot'),thread,self.workspace,str(uuid.uuid4()),'Question',owner['id'],'sidechat_'+owner['id'],attention='question')
        sibling=str(uuid.uuid4());original=self.workspace
        self.api.resolver=lambda wid:dict(self.scope,workspace=wid) if wid in (original,sibling) else (_ for _ in ()).throw(Rejected('not found'))
        self.assertEqual(1,self.api.notifications(self.session)['issues'][0]['unread_count'])
        self.api.seen(self.session,{'workspace':sibling,'messages':[reply['id']]})
        self.assertEqual(0,self.api.notifications(self.session)['issues'][0]['unread_count'])
        self.assertEqual(1,self.api.notifications(self.session)['issues'][0]['needs_attention_count'])
        self.api.attention(self.session,{'workspace':sibling,'message':reply['id'],'action':'resolve'})
        self.assertEqual([],self.api.notifications(self.session)['issues'])
        self.scope['issue']=str(uuid.uuid4())
        with self.assertRaises(Rejected):self.api.seen(self.session,{'workspace':sibling,'messages':[reply['id']]})

    def test_notification_http_auth_csrf_origin_and_no_agent_state_routes(self):
        owner=self.api.send(self.session,{'workspace':self.workspace,'request':str(uuid.uuid4()),'body':'Owner'})
        thread=self.store.db.execute('SELECT thread FROM messages WHERE id=?',(owner['id'],)).fetchone()[0]
        reply=self.store.append(Principal('owner','dot'),thread,self.workspace,str(uuid.uuid4()),'Action',owner['id'],'sidechat_'+owner['id'],attention='action')
        server=HTTPServer(('127.0.0.1',0),handler(self.api,'https://vibe.local'))
        def request(method,path,body=None,**changes):
            out=[]
            def client():
                c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                headers={'Host':'vibe.local','Origin':'https://vibe.local','X-Dot-Request':'1','Content-Type':'application/json','Cookie':'__Secure-vibe-dot='+self.token,'X-Dot-CSRF':self.session['csrf']};headers.update(changes)
                c.request(method,'/api/dot-sidechat/'+path,json.dumps(body) if body else None,headers)
                res=c.getresponse();out.append((res.status,json.loads(res.read())));c.close()
            t=threading.Thread(target=client);t.start();server.handle_request();t.join();return out[0]
        try:
            self.assertEqual(401,request('GET','notifications',Cookie='')[0])
            self.assertEqual(200,request('GET','notifications')[0])
            data={'workspace':self.workspace,'messages':[reply['id']]}
            self.assertEqual(403,request('POST','seen',data,**{'X-Dot-CSRF':''})[0])
            self.assertEqual(403,request('POST','seen',data,Origin='https://evil.test')[0])
            self.assertEqual(403,request('POST','seen',dict(data,owner='spoof'))[0])
            self.assertEqual(200,request('POST','seen',data)[0])
            self.assertEqual(1,request('GET','notifications')[1]['issues'][0]['needs_attention_count'])
            self.assertEqual(200,request('POST','attention',{'workspace':self.workspace,'message':reply['id'],'action':'resolve'})[0])
            self.assertEqual([],request('GET','notifications')[1]['issues'])
            self.assertEqual(403,request('POST','mark-workspace-seen',{})[0])
        finally:server.server_close()
