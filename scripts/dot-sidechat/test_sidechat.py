import os
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from sidechat import Store, Principal, Rejected


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "private.sqlite")
        self.now = 1000
        self.s = Store(self.path, lambda: self.now)
        self.owner = Principal("alice", "owner")
        self.dot = Principal("alice", "dot")
        self.publisher = Principal("alice", "publisher")
        self.s.register_scope("alice", "p", "i", "w")
        self.s.register_scope("alice", "p", "i", "w2")
        self.t = self.s.resolve(self.owner, "p", "i", "w")["id"]

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def send(self, **changes):
        args = dict(thread=self.t, workspace="w", request=str(uuid.uuid4()), body="Owner text")
        args.update(changes)
        return self.s.append(self.owner, **args)

    def reply(self, message, **changes):
        args = dict(thread=self.t, workspace="w", request=str(uuid.uuid4()), body="Dot reply",
                    reply_to=message["id"], event_id="sidechat_" + message["id"])
        args.update(changes)
        return self.s.tool(self.dot, "append_dot_reply", args)

    def test_scope_and_owner_isolation(self):
        self.assertEqual(self.t, self.s.resolve(self.owner, "p", "i", "w2")["id"])
        for p in (Principal("bob","owner"), Principal("bob","dot")):
            with self.assertRaises(Rejected): self.s.read(p,self.t)
            with self.assertRaises(Rejected): self.s.append(p,self.t,"w",str(uuid.uuid4()),"attack")
        with self.assertRaises(Rejected): self.s.resolve(self.owner,"other","i","w")
        with self.assertRaises(Rejected): self.send(workspace="unknown")
        with self.assertRaises(Rejected): self.s.register_scope("alice","p","changed","w")

    def test_atomic_owner_message_and_outbox(self):
        self.s.db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(Exception): self.send()
        self.assertEqual([],self.s.read(self.owner,self.t)["messages"])

    def test_message_idempotency_conflict(self):
        key=str(uuid.uuid4())
        first=self.send(request=key)
        self.assertEqual(first,self.send(request=key))
        with self.assertRaises(Rejected): self.send(request=key,body="changed")
        self.assertEqual(1,self.s.db.execute("SELECT count(*) FROM outbox").fetchone()[0])

    def test_reply_idempotency_no_loop_and_receipt(self):
        m=self.send()
        key=str(uuid.uuid4())
        r=self.reply(m,request=key)
        self.assertEqual(r,self.reply(m,request=key))
        with self.assertRaises(Rejected): self.reply(m)
        with self.assertRaises(Rejected): self.reply(m,request=key,body="different")
        self.assertEqual(1,self.s.db.execute("SELECT count(*) FROM outbox").fetchone()[0])
        receipt=self.s.receipt(self.owner,self.t,m["id"])
        self.assertEqual("pending",receipt["state"])
        self.assertTrue(receipt["reply_persisted"])
        self.assertEqual(r["hash"],receipt["reply"]["hash"])
        self.assertIsNone(receipt["seen"])

    def test_reply_target_fencing(self):
        m=self.send()
        for change in ({"workspace":"w2"},{"event_id":"wrong"},{"reply_to":"wrong"}):
            with self.assertRaises(Rejected): self.reply(m,**change)
        with self.assertRaises(Rejected): self.send(reply_to=m["id"])
        with self.assertRaises(Rejected):
            self.s.tool(self.dot,"append_dot_reply",{"owner":"alice"})
        with self.assertRaises(Rejected): self.s.tool(self.dot,"run_session_prompt",{})

    def test_snapshot_pagination_retains_complete_thread(self):
        for i in range(7): self.send(body=str(i))
        page=self.s.read(self.dot,self.t,limit=3)
        self.send(body="new after snapshot")
        bodies=[m["body"] for m in page["messages"]]
        while page["next_after"] is not None:
            page=self.s.read(self.dot,self.t,after=page["next_after"],through=page["through"],limit=3)
            bodies += [m["body"] for m in page["messages"]]
        self.assertEqual(list(map(str,range(7))),bodies)
        self.assertEqual(8,len(self.s.read(self.dot,self.t)["messages"]))

    def test_delivery_is_not_reply_and_survives_restart(self):
        m=self.send()
        self.assertIsNone(self.s.claim(self.publisher))
        self.s.bind(self.owner,self.t,"fixture-sub")
        job=self.s.claim(self.publisher)
        self.s.acknowledge(self.publisher,job["event"]["eventId"],job["attempt"],202)
        self.s.close()
        self.s=Store(self.path,lambda:self.now)
        r=self.s.receipt(self.owner,self.t,m["id"])
        self.assertEqual("webhook_accepted",r["state"])
        self.assertFalse(r["reply_persisted"])
        self.assertIsNone(self.s.claim(self.publisher))

    def test_lease_recovery_stable_event_stale_ack_rejected(self):
        self.send()
        self.s.bind(self.owner,self.t,"fixture-sub")
        first=self.s.claim(self.publisher)
        self.assertIsNone(self.s.claim(self.publisher))
        self.now +=31
        second=self.s.claim(self.publisher)
        self.assertEqual(first["event"],second["event"])
        with self.assertRaises(Rejected): self.s.acknowledge(self.publisher,first["event"]["eventId"],1,200)
        self.s.acknowledge(self.publisher,second["event"]["eventId"],2,200)

    def test_retry_backoff_expiration_and_revocation(self):
        m=self.send()
        self.s.bind(self.owner,self.t,"fixture-sub")
        job=self.s.claim(self.publisher)
        self.s.acknowledge(self.publisher,job["event"]["eventId"],1,503)
        self.assertIsNone(self.s.claim(self.publisher))
        self.now +=3
        job=self.s.claim(self.publisher)
        self.s.acknowledge(self.publisher,job["event"]["eventId"],2,410)
        self.now +=100
        self.assertIsNone(self.s.claim(self.publisher))
        self.assertEqual("failed",self.s.receipt(self.owner,self.t,m["id"])["state"])

    def test_subscription_owner_and_destination_fences(self):
        with self.assertRaises(Rejected): self.s.bind(Principal("bob","owner"),self.t,"evil")
        self.s.bind(self.owner,self.t,"first")
        with self.assertRaises(Rejected): self.s.bind(self.owner,self.t,"second")
        self.send()
        self.s.unbind(self.owner,self.t)
        self.assertIsNone(self.s.claim(self.publisher))

    def test_concurrent_duplicate_writers(self):
        key=str(uuid.uuid4())
        def append(_):
            s=Store(self.path)
            try: return s.append(self.owner,self.t,"w",key,"same")["id"]
            finally: s.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(append,range(8)))
        self.assertEqual(1,len(set(ids)))
        self.assertEqual(1,len(self.s.read(self.owner,self.t)["messages"]))

    def test_expired_subscription_and_revoked_scope(self):
        self.send()
        self.s.bind(self.owner,self.t,"fixture-sub",ttl=60)
        self.now += 61
        self.assertIsNone(self.s.claim(self.publisher))
        self.s.bind(self.owner,self.t,"fixture-sub",ttl=60)
        self.s.db.execute("DELETE FROM scopes WHERE owner=?",("alice",))
        self.assertIsNone(self.s.claim(self.publisher))
        with self.assertRaises(Rejected): self.s.read(self.dot,self.t)

    def test_unicode_limit_and_invalid_pagination(self):
        with self.assertRaises(Rejected): self.send(body="😀"*16000)
        with self.assertRaises(Rejected): self.s.read(self.dot,self.t,limit=1000)
        with self.assertRaises(Rejected): self.s.read(self.dot,self.t,after=-1)

if __name__=="__main__": unittest.main()
