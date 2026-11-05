"""Loopback fixture only. Never mounts production data or calls external services."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import urllib.parse
import uuid
from sidechat import Store, Principal, Rejected

OWNER=Principal("fixture-owner", "owner")
DOT=Principal("fixture-owner", "dot")
PUBLISHER=Principal("fixture-owner", "publisher")


def handler(store, static, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def output(self, status, body, kind="application/json"):
            raw=json.dumps(body).encode() if kind=="application/json" else body
            self.send_response(status)
            self.send_header("Content-Type",kind)
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def dispatch(self):
            host=self.headers.get("Host","")
            if host not in (f"127.0.0.1:{port}",f"localhost:{port}"):
                raise Rejected("Loopback fixture Host required")
            origin=self.headers.get("Origin")
            if origin and origin != "http://"+host:
                raise Rejected("Cross-origin fixture request denied")
            parsed=urllib.parse.urlsplit(self.path)
            if self.command=="GET" and parsed.path in ("/","/app.js","/app.css"):
                file=static/({"/":"index.html","/app.js":"app.js","/app.css":"app.css"}[parsed.path])
                kind={"html":"text/html; charset=utf-8","js":"text/javascript; charset=utf-8","css":"text/css; charset=utf-8"}[file.suffix[1:]]
                return self.output(200,file.read_bytes(),kind)
            if self.command=="GET" and parsed.path=="/__dot_fixture/thread":
                thread=store.resolve(OWNER,"fixture-project","fixture-issue","fixture-workspace")
                page=store.read(OWNER,thread["id"],limit=100)
                after=page["next_after"]
                while after:
                    next_page=store.read(OWNER,thread["id"],after=after,through=page["through"],limit=100)
                    page["messages"]+=next_page["messages"]
                    after=next_page["next_after"]
                page["next_after"]=None
                page["complete"]=True
                page["receipts"]={m["id"]:store.receipt(OWNER,thread["id"],m["id"]) for m in page["messages"] if m["role"]=="owner"}
                return self.output(200,page)
            if self.command!="POST" or self.headers.get("Content-Type")!="application/json":
                raise Rejected("Unsupported fixture request")
            length=int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 65000: raise Rejected("Invalid body length")
            args=json.loads(self.rfile.read(length))
            if not isinstance(args,dict): raise Rejected("Object required")
            thread=store.resolve(OWNER,"fixture-project","fixture-issue","fixture-workspace")["id"]
            if parsed.path=="/__dot_fixture/send":
                if set(args)!={"request","body"}: raise Rejected("Unexpected argument")
                return self.output(200,store.append(OWNER,thread,"fixture-workspace",**args))
            if parsed.path=="/__dot_fixture/accept":
                if args: raise Rejected("Unexpected argument")
                job=store.claim(PUBLISHER)
                if job: store.acknowledge(PUBLISHER,job["event"]["eventId"],job["attempt"],202)
                return self.output(200,{"fixture":True,"accepted":bool(job)})
            if parsed.path=="/__dot_fixture/reply":
                if set(args)!={"message","request"}: raise Rejected("Unexpected argument")
                return self.output(200,store.append(DOT,thread,"fixture-workspace",args["request"],
                    "Fixture reply: keep one private conversation for this issue, with the current workspace attached as context. Nothing has been sent to a coding agent.",
                    reply_to=args["message"],event_id="sidechat_"+args["message"]))
            raise Rejected("Unsupported fixture route")

        def do_GET(self):
            try: self.dispatch()
            except (Rejected,ValueError,TypeError,KeyError) as exc: self.output(400,{"error":str(exc)})
            except Exception: self.output(500,{"error":"Fixture operation failed"})

        do_POST=do_GET
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",required=True)
    parser.add_argument("--port",type=int,default=18973)
    args=parser.parse_args()
    path=Path(args.data).resolve()
    if path.name!="fixture.sqlite": raise SystemExit("Use an isolated fixture.sqlite")
    os.umask(0o077)
    path.parent.mkdir(parents=True,exist_ok=True)
    store=Store(path)
    store.register_scope(OWNER.owner,"fixture-project","fixture-issue","fixture-workspace")
    thread=store.resolve(OWNER,"fixture-project","fixture-issue","fixture-workspace")
    store.bind(OWNER,thread["id"],"fixture-only-no-webhook")
    static=Path(__file__).parent/"dist"
    print(f"Fixture only: http://127.0.0.1:{args.port}",flush=True)
    HTTPServer(("127.0.0.1",args.port),handler(store,static,args.port)).serve_forever()

if __name__=="__main__": main()
