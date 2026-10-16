"""Prepared private browser API. Not installed or enabled by this module.

Only the trusted local CLI creates pairing grants. HTTP never accepts owner,
project, issue or role claims. HTTPS terminates at the existing Vibe proxy;
a non-loopback listener requires TLS and an exact trusted proxy address.
"""
import argparse
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import ipaddress
import os
from pathlib import Path
import secrets
import sqlite3
import ssl
import time
import urllib.parse
import uuid

from sidechat import Principal, Rejected, Store

PREFIX = "/api/dot-sidechat/"
COOKIE = "__Secure-vibe-dot"
MAX_BODY = 65000


class AuthRequired(Rejected):
    pass


def digest(value):
    if not isinstance(value, str) or not 20 <= len(value) <= 200:
        raise AuthRequired("Pair this browser to use private Dot chat")
    return hashlib.sha256(value.encode()).hexdigest()


class BrowserAuth:
    def __init__(self, store):
        self.store = store
        store.db.executescript("""
        CREATE TABLE IF NOT EXISTS browser_grants(
          id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, owner TEXT NOT NULL,
          projects TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS browser_sessions(
          id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, owner TEXT NOT NULL,
          projects TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL,
          revoked INTEGER NOT NULL DEFAULT 0);
        """)

    def grant(self, owner, projects):
        if not owner or not projects or len(projects) > 100:
            raise Rejected("Owner and explicit project allowlist required")
        projects = sorted({str(uuid.UUID(p)) for p in projects})
        token, grant = secrets.token_urlsafe(32), str(uuid.uuid4())
        self.store.db.execute("INSERT INTO browser_grants VALUES (?,?,?,?,?,0)",
            (grant, digest(token), owner, json.dumps(projects), self.store.clock()+600))
        return {"grant_id": grant, "pairing_code": token, "expires_in_seconds": 600,
                "projects": projects}

    def pair(self, code):
        token, sid, csrf = secrets.token_urlsafe(32), str(uuid.uuid4()), secrets.token_urlsafe(32)
        with self.store.transaction():
            grant = self.store.db.execute(
                "SELECT * FROM browser_grants WHERE token_hash=? AND used=0 AND expires>?",
                (digest(code), self.store.clock())).fetchone()
            if not grant:
                raise AuthRequired("Pairing code is invalid, expired or already used")
            self.store.db.execute("UPDATE browser_grants SET used=1 WHERE id=?", (grant["id"],))
            self.store.db.execute("INSERT INTO browser_sessions VALUES (?,?,?,?,?,?,0)",
                (sid, digest(token), grant["owner"], grant["projects"], csrf,
                 0))
        return token, self.session(token)

    def session(self, token):
        row = self.store.db.execute(
            "SELECT * FROM browser_sessions WHERE token_hash=? AND revoked=0 AND (expires=0 OR expires>?)",
            (digest(token), self.store.clock())).fetchone()
        if not row:
            raise AuthRequired("Pair this browser to use private Dot chat")
        return dict(row)

    def revoke(self, sid):
        self.store.db.execute("UPDATE browser_sessions SET revoked=1 WHERE id=?", (sid,))

    def revoke_all(self, owner):
        with self.store.transaction():
            self.store.db.execute("UPDATE browser_sessions SET revoked=1 WHERE owner=?", (owner,))
            self.store.db.execute("UPDATE browser_grants SET used=1 WHERE owner=?", (owner,))


class WorkspaceResolver:
    """Read-only authoritative local Vibe IDs; no copied or browser-supplied mapping."""
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)

    def __call__(self, workspace):
        wid = uuid.UUID(workspace)
        con = sqlite3.connect(self.path.as_uri()+"?mode=ro", uri=True, timeout=2)
        try:
            con.execute("PRAGMA query_only=ON")
            row = con.execute("""
                SELECT t.project_id,t.id,t.title,w.name
                FROM workspaces w JOIN tasks t ON t.id=w.task_id
                JOIN projects p ON p.id=t.project_id WHERE w.id=?
                """, (wid.bytes,)).fetchone()
        finally:
            con.close()
        if not row:
            raise Rejected("Workspace must be linked to an available issue")
        def uid(value):
            return str(uuid.UUID(bytes=value)) if isinstance(value, bytes) else str(uuid.UUID(value))
        return {"project": uid(row[0]), "issue": uid(row[1]), "workspace": str(wid),
                "issue_label": row[2], "workspace_label": row[3] or str(wid)}


class BrowserAPI:
    def __init__(self, store, resolver):
        self.store, self.resolver, self.auth = store, resolver, BrowserAuth(store)

    def scope(self, session, workspace):
        scope = self.resolver(str(uuid.UUID(workspace)))
        if scope["project"] not in json.loads(session["projects"]):
            raise Rejected("Workspace is outside this browser's project grant")
        owner = Principal(session["owner"], "owner")
        self.store.register_scope(owner.owner, scope["project"], scope["issue"], scope["workspace"])
        thread = self.store.resolve(owner, scope["project"], scope["issue"], scope["workspace"])
        return owner, thread, scope

    def page(self, session, workspace, after=0, through=None):
        owner, thread, scope = self.scope(session, workspace)
        page = self.store.read(owner, thread["id"], after=after, through=through, limit=50)
        page["scope"] = scope
        page["receipts"] = {m["id"]: self.store.receipt(owner, thread["id"], m["id"])
                            for m in page["messages"] if m["role"] == "owner"}
        return page

    def send(self, session, args):
        if set(args) != {"workspace", "request", "body"}:
            raise Rejected("Unexpected send argument")
        owner, thread, scope = self.scope(session, args["workspace"])
        return self.store.append(owner, thread["id"], scope["workspace"], args["request"], args["body"])


def handler(api, origin):
    parsed_origin = urllib.parse.urlsplit(origin)
    if parsed_origin.scheme != "https" or not parsed_origin.hostname or parsed_origin.path or parsed_origin.query or parsed_origin.fragment or parsed_origin.username:
        raise Rejected("Exact HTTPS browser origin required")
    host = parsed_origin.netloc
    failures = []

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Never log pairing codes, cookies, drafts, or transcript bodies.

        def output(self, status, data, cookie=None):
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(raw)))
            if cookie is None:
                cookie = getattr(self, "session_cookie", None)
            if cookie is not None:
                self.send_header("Set-Cookie", COOKIE+"="+cookie+"; Path=/api/dot-sidechat/; Secure; HttpOnly; SameSite=Strict; Max-Age="+("34560000" if cookie else "0"))
            self.end_headers()
            self.wfile.write(raw)

        def dispatch(self):
            if self.headers.get("Host") != host or self.headers.get("X-Dot-Request") != "1":
                raise Rejected("Same-origin browser request required")
            if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin"):
                raise Rejected("Cross-site request denied")
            request_origin = self.headers.get("Origin")
            if request_origin not in (None, origin) or (self.command == "POST" and request_origin != origin):
                raise Rejected("Exact Origin required")
            parsed = urllib.parse.urlsplit(self.path)
            if not parsed.path.startswith(PREFIX) or parsed.fragment:
                raise Rejected("Unsupported route")
            route = parsed.path[len(PREFIX):]
            args = {}
            if self.command == "POST":
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type") != "application/json":
                    raise Rejected("JSON request required")
                lengths = self.headers.get_all("Content-Length", [])
                if len(lengths) != 1 or not lengths[0].isdigit():
                    raise Rejected("Invalid body length")
                size = int(lengths[0])
                if not 0 < size <= MAX_BODY:
                    raise Rejected("Invalid body length")
                args = json.loads(self.rfile.read(size))
                if not isinstance(args, dict):
                    raise Rejected("Object required")
                if parsed.query:
                    raise Rejected("No query permitted on writes")
            if self.command == "POST" and route == "pair":
                if set(args) != {"code"}:
                    raise Rejected("Unexpected pairing argument")
                now = api.store.clock()
                failures[:] = [stamp for stamp in failures if stamp > now-60]
                if len(failures) >= 30:
                    return self.output(429, {"error": "Pairing rate limit; retry in one minute"})
                failures.append(now)
                token, session = api.auth.pair(args["code"])
                return self.output(200, {"csrf": session["csrf"], "expires": session["expires"] or None, "session_id": session["id"]}, token)
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            value = cookie.get(COOKIE)
            session = api.auth.session(value.value if value else "")
            self.session_cookie = value.value
            if self.command == "POST" and not secrets.compare_digest(self.headers.get("X-Dot-CSRF", ""), session["csrf"]):
                raise Rejected("CSRF check failed")
            if self.command == "GET" and route == "session" and not parsed.query:
                return self.output(200, {"csrf": session["csrf"], "expires": session["expires"] or None, "session_id": session["id"]})
            if self.command == "POST" and route == "logout" and not args:
                api.auth.revoke(session["id"])
                return self.output(200, {"revoked": True}, "")
            if self.command == "POST" and route == "send":
                return self.output(200, api.send(session, args))
            if self.command == "GET" and route == "thread":
                query = urllib.parse.parse_qs(parsed.query, strict_parsing=True)
                if set(query) - {"workspace", "after", "through"} or "workspace" not in query or any(len(v) != 1 for v in query.values()):
                    raise Rejected("Invalid history query")
                return self.output(200, api.page(session, query["workspace"][0],
                    int(query.get("after", ["0"])[0]),
                    int(query["through"][0]) if "through" in query else None))
            raise Rejected("Unsupported route")

        def do_GET(self):
            try:
                self.dispatch()
            except AuthRequired as exc:
                self.output(401, {"error": str(exc)})
            except (Rejected, ValueError, TypeError, KeyError, AttributeError):
                self.output(403, {"error": "Request denied; check pairing and issue/workspace access"})
            except Exception:
                self.output(503, {"error": "Chat unavailable; retained messages are unchanged"})
        do_POST = do_GET
    return Handler



def make_server(api, origin, listen, port, proxy=None, cert=None, key=None):
    address = ipaddress.ip_address(listen)
    if address.version != 4 or address.is_unspecified or not (address.is_private or address.is_loopback):
        raise Rejected("Private IPv4 listener required")
    if not address.is_loopback and not all((proxy, cert, key)):
        raise Rejected("Non-loopback listener requires TLS and an exact proxy address")
    context = None
    if cert or key:
        if not (cert and key):
            raise Rejected("Certificate and key are both required")
        key_path = Path(key)
        if key_path.is_symlink() or key_path.stat().st_mode & 0o077:
            raise Rejected("TLS private key must be owner-readable only")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
    allowed = str(ipaddress.ip_address(proxy)) if proxy else None

    class PrivateServer(HTTPServer):
        def get_request(self):
            connection, peer = super().get_request()
            if allowed and peer[0] != allowed:
                connection.close()
                raise OSError("Proxy peer denied")
            connection.settimeout(5)
            if context:
                try:
                    connection = context.wrap_socket(connection, server_side=True)
                except Exception:
                    connection.close()
                    raise
            return connection, peer

    return PrivateServer((str(address), port), handler(api, origin))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--vibe-db", required=True)
    serve.add_argument("--origin", required=True)
    serve.add_argument("--port", type=int, default=18974)
    serve.add_argument("--listen", default="127.0.0.1")
    serve.add_argument("--proxy-address")
    serve.add_argument("--tls-cert")
    serve.add_argument("--tls-key")
    pair = sub.add_parser("grant")
    pair.add_argument("--owner", required=True)
    pair.add_argument("--project", action="append", required=True)
    pair.add_argument("--output", required=True, help="New private file; never console/logs")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--owner", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    store = Store(Path(args.data).resolve(strict=True))
    auth = BrowserAuth(store)
    if args.command == "grant":
        # Reserve the private output before creating a grant; never overwrite.
        with open(args.output, "x", encoding="utf-8") as output:
            os.chmod(args.output, 0o600)
            json.dump(auth.grant(args.owner, args.project), output)
        print("One-use pairing grant saved privately; expires in ten minutes.")
    elif args.command == "revoke":
        auth.revoke_all(args.owner)
        print("Browser grants and sessions revoked; conversation history retained.")
    else:
        api = BrowserAPI(store, WorkspaceResolver(args.vibe_db))
        make_server(api, args.origin, args.listen, args.port,
                    args.proxy_address, args.tls_cert, args.tls_key).serve_forever()


if __name__ == "__main__":
    main()
