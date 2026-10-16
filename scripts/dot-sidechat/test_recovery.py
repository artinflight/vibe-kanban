import json
import unittest
from sidechat import Principal, Rejected
import test_sidechat
from events import Events


class RecoveryTests(unittest.TestCase):
    setUp = test_sidechat.Contracts.setUp
    tearDown = test_sidechat.Contracts.tearDown
    send = test_sidechat.Contracts.send
    reply = test_sidechat.Contracts.reply

    def pending(self, **args):
        return self.s.tool(self.dot, 'list_pending_sidechat_messages', args)

    def test_context_survives_context_free_wake_without_read_mutation(self):
        message = self.send()
        before = self.s.db.total_changes
        first = self.pending()['items'][0]
        self.assertEqual(before, self.s.db.total_changes)
        self.assertEqual(first, self.pending()['items'][0])
        data = first['event']['data']
        self.assertEqual((self.t, 'w', message['id'], message['hash']),
                         (data['thread_id'], data['workspace_id'], data['message_id'], data['message_sha256']))
        self.assertNotIn('body', json.dumps(first))
        self.assertEqual('pending', first['delivery']['state'])
        self.reply(message, request=first['reply_request'])
        self.assertEqual([], self.pending()['items'])
        with self.assertRaises(Rejected):
            self.reply(message)
        self.assertEqual(1, self.s.db.execute('SELECT count(*) FROM outbox').fetchone()[0])

    def test_scope_and_revoked_workspace_do_not_leak(self):
        self.send()
        self.assertEqual([], self.s.tool(Principal('bob', 'dot'), 'list_pending_sidechat_messages', {})['items'])
        for args in ({'owner':'alice'}, {'workspace':'w'}, {'limit':True}, {'through':999}, {'after':-1}):
            with self.assertRaises(Rejected): self.pending(**args)
        self.s.db.execute("DELETE FROM scopes WHERE workspace='w'")
        self.assertEqual([], self.pending()['items'])

    def test_snapshot_pagination_and_replied_holes(self):
        messages = [self.send() for _ in range(4)]
        first = self.pending(limit=1)
        self.reply(messages[1])
        self.send()
        second = self.pending(after=first['next_after'], through=first['through'])
        self.assertEqual([m['id'] for m in messages[2:]],
                         [i['event']['data']['message_id'] for i in second['items']])

    def test_corrupt_context_is_rejected(self):
        self.send()
        self.s.db.execute("UPDATE outbox SET payload='{}'")
        with self.assertRaises(Rejected): self.pending()

    def test_dispatch_preserves_complete_event_and_current_subscription(self):
        sent=[]
        def sender(url,key,sid,eid,body):
            if body.get('type')=='verification':return 200,json.dumps({'challenge':body['challenge']})
            sent.append((eid,body));return 200,''
        events=Events(self.s,sender,lambda:self.now)
        events.subscribe(self.owner,{'name':events.definition()['name'],
            'arguments':{'project_id':'p'},'delivery':{'mode':'webhook',
            'url':'https://fixture.invalid/callback','secret':'fixture-key'},'ttlMs':60000})
        message=self.send()
        expected=self.pending()['items'][0]['event']
        self.assertIsNone(expected['cursor'])
        events.deliver_one('alice')
        self.assertEqual([(expected['eventId'],expected)],sent)
        self.assertEqual('webhook_accepted',self.pending()['items'][0]['delivery']['state'])
        self.assertEqual(1,self.s.db.execute('SELECT count(*) FROM sidechat_subscriptions WHERE active=1').fetchone()[0])

    def test_legacy_cursor_is_normalized_without_rewriting_or_resending(self):
        sent=[]
        def sender(url,key,sid,eid,body):
            if body.get('type')=='verification':return 200,json.dumps({'challenge':body['challenge']})
            sent.append(body);return 200,''
        events=Events(self.s,sender,lambda:self.now)
        events.subscribe(self.owner,{'name':events.definition()['name'],'arguments':{'project_id':'p'},
            'delivery':{'mode':'webhook','url':'https://fixture.invalid/callback','secret':'fixture-key'},'ttlMs':60000})
        self.send()
        row=self.s.db.execute('SELECT event,payload FROM outbox').fetchone()
        legacy=json.loads(row['payload']);legacy['cursor']='1'
        raw=json.dumps(legacy)
        self.s.db.execute('UPDATE outbox SET payload=?',(raw,))
        events.deliver_one('alice')
        self.assertIsNone(sent[0]['cursor'])
        self.assertEqual(legacy['data'],sent[0]['data'])
        self.assertEqual(row['event'],sent[0]['eventId'])
        self.assertEqual(raw,self.s.db.execute('SELECT payload FROM outbox').fetchone()[0])
        self.assertIsNone(events.deliver_one('alice'))
        self.assertEqual(1,len(sent))

    def test_only_explicit_project_grants_allow_preparing_new_project(self):
        events=Events(self.s,lambda *args:None,lambda:self.now)
        with self.assertRaises(Rejected):events._scope(self.owner,{'project_id':'new'})
        self.s.db.execute("INSERT INTO project_grants VALUES ('alice','new')")
        self.assertEqual({'project_id':'new'},json.loads(events._scope(self.owner,{'project_id':'new'})))
        with self.assertRaises(Rejected):events._scope(Principal('bob','owner'),{'project_id':'new'})


if __name__=='__main__':unittest.main()
