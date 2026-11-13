import json
import unittest
import test_sidechat
from events import Events
from sidechat import Principal, Rejected

class EventContracts(unittest.TestCase):
    setUp = test_sidechat.Contracts.setUp
    tearDown = test_sidechat.Contracts.tearDown
    send = test_sidechat.Contracts.send
    reply = test_sidechat.Contracts.reply

    def engine(self):
        self.sent=[]
        def sender(url,key,sid,eid,body):
            self.sent.append((sid,body))
            if body.get("type")=="verification":
                return 200,json.dumps({"challenge":body["challenge"]})
            return 202,""
        return Events(self.s,sender,lambda:self.now)

    def params(self,arguments):
        return {"name":"vk.sidechat.owner_message.created","arguments":arguments,
                "delivery":{"mode":"webhook","url":"https://fixture.invalid/callback","secret":"fixture-key"},
                "ttlMs":60000}

    def test_project_routes_new_threads_without_bot_loops(self):
        events=self.engine()
        sub=events.subscribe(self.owner,self.params({"project_id":"p"}))
        first=self.send()
        self.s.register_scope("alice","p","second-issue","third-workspace")
        thread=self.s.resolve(self.owner,"p","second-issue","third-workspace")["id"]
        import uuid
        second=self.s.append(self.owner,thread,"third-workspace",str(uuid.uuid4()),"second issue")
        self.assertIsNotNone(events.deliver_one("alice"))
        self.assertIsNotNone(events.deliver_one("alice"))
        self.assertIsNone(events.deliver_one("alice"))
        self.assertEqual({first["id"],second["id"]},{x[1]["data"]["message_id"] for x in self.sent if "data" in x[1]})
        self.reply(first)
        self.assertIsNone(events.deliver_one("alice"))

    def test_scope_and_expiry(self):
        events=self.engine()
        with self.assertRaises(Rejected): events.subscribe(Principal("bob","owner"),self.params({"thread_id":self.t}))
        with self.assertRaises(Rejected): events.subscribe(self.owner,self.params({"thread_id":self.t,"project_id":"p"}))
        events.subscribe(self.owner,self.params({"thread_id":self.t}))
        self.send()
        self.now+=61
        self.assertIsNone(events.deliver_one("alice"))

    def test_overlap_fails_closed_and_unsubscribe_preserves_other_scopes(self):
        events=self.engine()
        events.subscribe(self.owner,self.params({"project_id":"p"}))
        events.subscribe(self.owner,self.params({"thread_id":self.t}))
        self.send()
        self.assertIsNone(events.deliver_one("alice"))
        events.subscribe(self.owner,self.params({"thread_id":self.t}),unsubscribe=True)
        self.assertIsNotNone(events.deliver_one("alice"))

    def test_verification_failure_does_not_store_subscription(self):
        engine=Events(self.s,lambda *args:(200,'{"challenge":"wrong"}'),lambda:self.now)
        with self.assertRaises(Rejected): engine.subscribe(self.owner,self.params({"thread_id":self.t}))
        self.assertEqual(0,self.s.db.execute("SELECT count(*) FROM sidechat_subscriptions").fetchone()[0])
