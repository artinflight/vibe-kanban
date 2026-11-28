import http.client
from http.server import HTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from server import handler, OWNER
from sidechat import Store


class HTTPContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.ready=threading.Event()
        def serve():
            self.store=Store(str(Path(self.tmp.name)/"fixture.sqlite"))
            self.store.register_scope(OWNER.owner,"fixture-project","fixture-issue","fixture-workspace")
            thread=self.store.resolve(OWNER,"fixture-project","fixture-issue","fixture-workspace")
            self.store.bind(OWNER,thread["id"],"fixture-only")
            self.http=HTTPServer(("127.0.0.1",0),handler(self.store,Path(__file__).parent/"dist",0))
            self.port=self.http.server_port
            self.http.RequestHandlerClass=handler(self.store,Path(__file__).parent/"dist",self.port)
            self.ready.set()
            self.http.serve_forever(poll_interval=0.05)
            self.store.close()
        self.worker=threading.Thread(target=serve)
        self.worker.start()
        self.ready.wait(5)

    def tearDown(self):
        self.http.shutdown()
        self.worker.join()
        self.http.server_close()
        self.tmp.cleanup()

    def call(self,path,body=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.port)
        h={"Content-Type":"application/json"}
        h.update(headers or {})
        conn.request("GET" if body is None else "POST",path,json.dumps(body) if body is not None else None,h)
        r=conn.getresponse()
        data=json.loads(r.read())
        conn.close()
        return r.status,data

    def test_owner_send_accept_reply_and_reload(self):
        key=str(uuid.uuid4())
        status,m=self.call("/__dot_fixture/send",{"request":key,"body":"Hello private fixture"})
        self.assertEqual(200,status)
        _,again=self.call("/__dot_fixture/send",{"request":key,"body":"Hello private fixture"})
        self.assertEqual(m["id"],again["id"])
        _,page=self.call("/__dot_fixture/thread")
        self.assertEqual("pending",page["receipts"][m["id"]]["state"])
        self.call("/__dot_fixture/accept",{})
        _,page=self.call("/__dot_fixture/thread")
        self.assertEqual("webhook_accepted",page["receipts"][m["id"]]["state"])
        self.assertFalse(page["receipts"][m["id"]]["reply_persisted"])
        self.call("/__dot_fixture/reply",{"request":str(uuid.uuid4()),"message":m["id"]})
        _,page=self.call("/__dot_fixture/thread")
        self.assertEqual(2,len(page["messages"]))
        self.assertTrue(page["receipts"][m["id"]]["reply_persisted"])

    def test_host_origin_and_identity_injection_denied(self):
        for headers in ({"Host":"evil.example"},{"Origin":"https://evil.example"}):
            status,_=self.call("/__dot_fixture/thread",headers=headers)
            self.assertEqual(400,status)
        status,_=self.call("/__dot_fixture/send",{"request":str(uuid.uuid4()),"body":"attack","owner":"real-user"})
        self.assertEqual(400,status)
        status,_=self.call("/api/sessions/anything/follow-up",{"prompt":"attack"})
        self.assertEqual(400,status)

if __name__=="__main__": unittest.main()
