import http.client
import json
from pathlib import Path
import sqlite3
import ssl
import subprocess
import os
import tempfile
import threading
import unittest
import uuid
from http.server import HTTPServer
from browser_api import BrowserAPI, BrowserAuth, AuthRequired, WorkspaceResolver, handler, COOKIE, make_server
from sidechat import Store, Rejected, Principal


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = [1000.]
        self.store = Store(Path(self.temp.name)/"private.sqlite", clock=lambda: self.now[0])
        self.project, self.issue, self.workspace = [str(uuid.uuid4()) for _ in range(3)]
        self.scope = {"project": self.project, "issue": self.issue, "workspace": self.workspace,
                      "issue_label": "Test issue", "workspace_label": "Test workspace"}
        self.api = BrowserAPI(self.store, lambda wid: self.scope if wid == self.workspace else (_ for _ in ()).throw(Rejected("not found")))
        self.grant = self.api.auth.grant("owner", [self.project])
        self.token, self.session = self.api.auth.pair(self.grant["pairing_code"])

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_one_use_expiry_and_revocation(self):
        with self.assertRaises(AuthRequired): self.api.auth.pair(self.grant["pairing_code"])
        self.api.auth.revoke(self.session["id"])
        with self.assertRaises(AuthRequired): self.api.auth.session(self.token)
        other = self.api.auth.grant("owner", [self.project])
        self.now[0] += 601
        with self.assertRaises(AuthRequired): self.api.auth.pair(other["pairing_code"])

    def test_session_expiry_and_revoke_pending_grants(self):
        self.now[0] += 86401
        with self.assertRaises(AuthRequired): self.api.auth.session(self.token)
        pending = self.api.auth.grant("owner", [self.project])
        self.api.auth.revoke_all("owner")
        with self.assertRaises(AuthRequired): self.api.auth.pair(pending["pairing_code"])

    def test_scope_is_server_owned_and_relinks_fail_closed(self):
        self.api.page(self.session, self.workspace)
        self.scope["issue"] = str(uuid.uuid4())
        with self.assertRaises(Rejected): self.api.page(self.session, self.workspace)
        self.scope["project"] = str(uuid.uuid4())
        with self.assertRaises(Rejected): self.api.page(self.session, self.workspace)

    def test_caller_cannot_inject_owner_or_reply(self):
        args = {"workspace": self.workspace, "request": str(uuid.uuid4()), "body": "hello"}
        with self.assertRaises(Rejected): self.api.send(self.session, dict(args, owner="other"))
        with self.assertRaises(Rejected): self.api.send(self.session, dict(args, reply_to="x"))
        first = self.api.send(self.session, args)
        again = self.api.send(self.session, args)
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_history_reply_receipts_and_snapshot_pagination(self):
        for n in range(51):
            self.api.send(self.session, {"workspace": self.workspace, "request": str(uuid.uuid4()), "body": str(n)})
        first = self.api.page(self.session, self.workspace)
        self.assertEqual(len(first["messages"]), 50)
        second = self.api.page(self.session, self.workspace, first["next_after"], first["through"])
        self.assertEqual(len(second["messages"]), 1)
        self.assertIsNone(second["next_after"])
        m = second["messages"][0]
        self.store.append(Principal("owner","dot"), first["thread"]["id"], self.workspace,
            str(uuid.uuid4()), "reply", m["id"], "sidechat_"+m["id"])
        current = self.api.page(self.session, self.workspace, 50)
        self.assertTrue(current["receipts"][m["id"]]["reply_persisted"])

    def test_read_only_authoritative_mapping(self):
        path = Path(self.temp.name)/"vibe.sqlite"
        con = sqlite3.connect(path)
        con.executescript("CREATE TABLE projects(id BLOB);CREATE TABLE tasks(id BLOB,project_id BLOB,title TEXT);CREATE TABLE workspaces(id BLOB,task_id BLOB,name TEXT);")
        con.execute("INSERT INTO projects VALUES (?)", (uuid.UUID(self.project).bytes,))
        con.execute("INSERT INTO tasks VALUES (?,?,?)", (uuid.UUID(self.issue).bytes,uuid.UUID(self.project).bytes,"Issue"))
        con.execute("INSERT INTO workspaces VALUES (?,?,?)", (uuid.UUID(self.workspace).bytes,uuid.UUID(self.issue).bytes,"Workspace"))
        con.commit(); con.close()
        before = path.read_bytes()
        result = WorkspaceResolver(path)(self.workspace)
        self.assertEqual(result["project"],self.project)
        self.assertEqual(path.read_bytes(), before)

    def test_remote_listener_requires_encrypted_exact_proxy_hop(self):
        with self.assertRaises(Rejected):
            make_server(self.api, "https://vibe.local", "10.0.0.129", 18974)
        with self.assertRaises(Rejected):
            make_server(self.api, "https://vibe.local", "0.0.0.0", 18974)
        with self.assertRaises(Rejected):
            handler(self.api, "http://vibe.local")

    def test_tls_verified_proxy_transport(self):
        cert, key = Path(self.temp.name)/"test.crt", Path(self.temp.name)/"test.key"
        subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes",
            "-keyout",str(key),"-out",str(cert),"-days","1","-subj","/CN=127.0.0.1",
            "-addext","subjectAltName=IP:127.0.0.1"],check=True,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        os.chmod(key,0o600)
        server=make_server(self.api,"https://vibe.local","127.0.0.1",0,
                           "127.0.0.1",str(cert),str(key))
        result=[]
        def client():
            context=ssl.create_default_context(cafile=str(cert))
            con=http.client.HTTPSConnection("127.0.0.1",server.server_port,context=context,timeout=3)
            con.request("GET","/api/dot-sidechat/session",headers={"Host":"vibe.local","X-Dot-Request":"1"})
            response=con.getresponse()
            result.append(response.status)
            response.read();con.close()
        thread=threading.Thread(target=client)
        try:
            thread.start();server.handle_request();thread.join()
            self.assertEqual(result,[401])
        finally: server.server_close()

    def test_http_auth_origin_csrf_cookie_and_fail_closed_routes(self):
        # Server dispatch runs on this test's SQLite owning thread. Client uses a worker.
        server = HTTPServer(("127.0.0.1",0), handler(self.api,"https://vibe.local"))
        def request(method,path,body=None,headers=None):
            result = []
            def client():
                con=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                hdr={"Host":"vibe.local","X-Dot-Request":"1", "Origin":"https://vibe.local"}
                hdr.update(headers or {})
                con.request(method,"/api/dot-sidechat/"+path,
                    json.dumps(body) if body is not None else None,
                    dict(hdr, **({"Content-Type":"application/json"} if body is not None else {})))
                res=con.getresponse()
                result.append((res.status,dict(res.getheaders()),json.loads(res.read())))
                con.close()
            thread=threading.Thread(target=client)
            thread.start(); server.handle_request(); thread.join()
            return result[0]
        try:
            self.assertEqual(request("GET","session")[0],401)
            code=self.api.auth.grant("owner",[self.project])["pairing_code"]
            status,headers,data=request("POST","pair",{"code":code})
            self.assertEqual(status,200)
            cookie=headers["Set-Cookie"]
            for attribute in ["Secure","HttpOnly","SameSite=Strict","Path=/api/dot-sidechat/"]:
                self.assertIn(attribute,cookie)
            auth={"Cookie":cookie.split(";")[0]}
            self.assertEqual(request("GET","session",headers=auth)[0],200)
            send={"workspace":self.workspace,"request":str(uuid.uuid4()),"body":"hello"}
            self.assertEqual(request("POST","send",send,auth)[0],403)
            auth["X-Dot-CSRF"]=data["csrf"]
            self.assertEqual(request("POST","send",send,dict(auth,Origin="https://evil.test"))[0],403)
            self.assertEqual(request("POST","send",send,auth)[0],200)
            self.assertEqual(request("GET","thread?workspace="+self.workspace,headers=dict(auth,Host="evil.test"))[0],403)
            self.assertEqual(request("POST","logout",{},auth)[0],200)
            self.assertEqual(request("GET","session",headers=auth)[0],401)
            self.assertEqual(request("POST","pair",{"code":code})[0],401)
        finally:
            server.server_close()


if __name__ == "__main__": unittest.main()
