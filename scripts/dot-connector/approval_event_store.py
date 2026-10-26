"""Durable notification-only MCP Events bridge. Never resolves an approval.

Subscription destinations/keys come ONLY from the authenticated events/subscribe
request. No guessed wake API, credentials, agent launches or prompt mutations.
"""
import base64
import datetime as dt
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import ssl
import time
import urllib.parse
import uuid

import approval_preview

NAMES = ("vk.approval.pending", "vk.approval.changed")
TERMINAL = {"approved", "denied", "cancelled", "answered", "timed_out"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).isoformat()


def epoch(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def identifier(value):
    return str(uuid.UUID(value))


def summarize(row):
    """Persist only bounded redacted previews, never prompts/contents/credentials."""
    summary = {"approval_id": identifier(row["approval_id"]),
               "execution_id": identifier(row["execution_process_id"]),
               "tool": "review_in_vk", "targets": {},
               "is_question": bool(row.get("is_question")),
               "created_at": iso(epoch(row["created_at"])),
               "timeout_at": iso(epoch(row["timeout_at"]))}
    native_tool = row.get("tool_name", "")
    if isinstance(native_tool, str) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,120}", native_tool):
        summary["tool"] = native_tool
    params = {}
    consent = row.get("mcp_consent") or ""
    match = re.match(r"Tool: ([a-zA-Z0-9_.-]{1,120})\n", consent)
    if match:
        summary["tool"] = match[1]
    start = consent.find("Parameters (including target):\n")
    if start >= 0:
        try:
            params, _ = json.JSONDecoder().raw_decode(
                consent[start + len("Parameters (including target):\n"):].lstrip())
            if not isinstance(params, dict):
                raise ValueError("Invalid parameters")
            for key in ("session_id", "workspace_id", "execution_id", "issue_id", "project_id"):
                if key in params:
                    summary["targets"][key] = identifier(params[key])
            for key in ("repo_full_name", "pr_number"):
                v = params.get(key)
                if key == "repo_full_name" and isinstance(v, str) and re.fullmatch(r"[\w.-]+/[\w.-]+", v):
                    summary["targets"][key] = v
                elif key == "pr_number" and isinstance(v, int) and v > 0:
                    summary["targets"][key] = v
        except (ValueError, TypeError, KeyError):
            params = {}
    # IDs point to the normal supported approval presentation; no action URL is
    # invented, and a notification is never an approval instruction.
    summary["action"] = approval_preview.preview(params)
    return summary


def public_address(url):
    p = urllib.parse.urlsplit(url)
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.fragment or p.port not in (None, 443)):
        raise ValueError("Invalid callback destination")
    addresses = {x[4][0] for x in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global or
                            ipaddress.ip_address(a).is_multicast for a in addresses):
        raise ValueError("Callback destination is not public")
    return p, sorted(addresses)[0]


def signing_key(secret):
    if not isinstance(secret, str) or not secret.startswith("whsec_"):
        raise ValueError("Invalid signing secret")
    try:
        key = base64.b64decode(secret[6:], validate=True)
    except ValueError:
        raise ValueError("Invalid signing secret") from None
    if not 24 <= len(key) <= 64:
        raise ValueError("Invalid signing secret")
    return key


def webhook(url, secret, subscription_id, event_id, body):
    """Pin a validated public address; preserve TLS SNI; never redirect."""
    parsed, address = public_address(url)
    raw = canonical(body).encode()
    if len(raw) > 262144:
        raise ValueError("Event too large")
    stamp = str(int(time.time()))
    keys = secret if isinstance(secret, list) else [secret]
    signatures = ["v1," + base64.b64encode(hmac.new(signing_key(key),
        event_id.encode() + b"." + stamp.encode() + b"." + raw, hashlib.sha256).digest()).decode()
        for key in keys]
    conn = http.client.HTTPSConnection(parsed.hostname, 443, timeout=10)
    try:
        sock = socket.create_connection((address, 443), timeout=10)
        try:
            conn.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
        except Exception:
            sock.close()
            raise
        conn.request("POST", urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, "")),
            raw, {"Content-Type": "application/json", "webhook-id": event_id,
                  "webhook-timestamp": stamp, "webhook-signature": " ".join(signatures),
                  "X-MCP-Subscription-Id": subscription_id})
        response = conn.getresponse()
        result = response.read(262145)
        if len(result) > 262144:
            raise ValueError("Callback response too large")
        return response.status, result
    finally:
        conn.close()


class Store:
    def __init__(self, path, clock=time.time, sender=webhook):
        self.clock, self.sender = clock, sender
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.umask(0o077)
        self.db = sqlite3.connect(path, timeout=5)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, summary TEXT,
            state TEXT NOT NULL, observed REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, name TEXT, body TEXT);
          CREATE TABLE IF NOT EXISTS subscriptions(id TEXT PRIMARY KEY, principal TEXT,
            name TEXT, url TEXT, secret TEXT, expires REAL, active INTEGER NOT NULL,
            previous_secret TEXT, rotation_until REAL);
          CREATE TABLE IF NOT EXISTS deliveries(event_id TEXT, subscription_id TEXT,
            state TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0, next_try REAL DEFAULT 0,
            http_status INTEGER, PRIMARY KEY(event_id,subscription_id));
          CREATE TABLE IF NOT EXISTS health(key TEXT PRIMARY KEY, value TEXT);
        """)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(subscriptions)")}
        for name, kind in (("previous_secret", "TEXT"), ("rotation_until", "REAL")):
            if name not in columns:
                self.db.execute(f"ALTER TABLE subscriptions ADD COLUMN {name} {kind}")
        self.db.commit()

    def close(self):
        self.db.close()

    def health(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO health VALUES (?,?)", (key, canonical(value)))
        self.db.commit()

    def transition(self, summary, state):
        now, aid = self.clock(), summary["approval_id"]
        old = self.db.execute("SELECT state FROM requests WHERE id=?", (aid,)).fetchone()
        if old and old["state"] == state:
            return False
        if old and old["state"] in TERMINAL:
            return False  # Never resurrect a resolved request from stale replay.
        if old and old["state"] == "deadline_elapsed" and state == "pending" and epoch(summary["timeout_at"]) <= now:
            return False
        self.db.execute("INSERT OR REPLACE INTO requests VALUES (?,?,?,?)",
                        (aid, canonical(summary), state, now))
        name = NAMES[0] if state == "pending" else NAMES[1]
        eid = "evt_" + hashlib.sha256((aid + ":" + state).encode()).hexdigest()
        data = dict(summary, state=state)
        body = canonical({"eventId": eid, "name": name, "timestamp": iso(now),
                          "data": data, "cursor": None})
        self.db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?)", (eid, name, body))
        self.db.execute("""INSERT OR IGNORE INTO deliveries(event_id,subscription_id)
            SELECT ?,id FROM subscriptions WHERE active=1 AND name=?
            AND (expires IS NULL OR expires>?)""", (eid, name, now))
        self.db.commit()
        return True

    def snapshot(self, pending):
        # Called only for a complete successful snapshot, never for a disconnect.
        clean = [summarize(row) for row in pending.values()]
        ids = {x["approval_id"] for x in clean}
        for summary in clean:
            self.transition(summary, "pending")
        missing = self.db.execute("SELECT * FROM requests WHERE state IN ('pending','deadline_elapsed')").fetchall()
        for row in missing:
            if row["id"] not in ids:
                self.transition(json.loads(row["summary"]), "no_longer_pending")
        self.health("last_snapshot", iso(self.clock()))

    def outcome(self, aid, state):
        if state not in TERMINAL:
            raise ValueError("Unknown outcome")
        row = self.db.execute("SELECT summary FROM requests WHERE id=?", (identifier(aid),)).fetchone()
        if row:
            self.transition(json.loads(row[0]), state)

    def tick(self):
        now = self.clock()
        for row in self.db.execute("SELECT * FROM requests WHERE state='pending'").fetchall():
            summary = json.loads(row["summary"])
            if epoch(summary["timeout_at"]) <= now:
                # Deadline passage is not proof that the backend timed out.
                self.transition(summary, "deadline_elapsed")
        self.db.execute("UPDATE subscriptions SET active=0 WHERE expires IS NOT NULL AND expires<=?", (now,))
        self.db.execute("UPDATE subscriptions SET previous_secret=NULL,rotation_until=NULL WHERE rotation_until<=?", (now,))
        self.db.commit()

    def event_list(self):
        schema = {"type": "object", "properties": {
            "approval_id": {"type": "string"}, "execution_id": {"type": "string"},
            "tool": {"type": "string"}, "targets": {"type": "object"},
            "is_question": {"type": "boolean"}, "created_at": {"type": "string"},
            "timeout_at": {"type": "string"}, "state": {"type": "string"},
            "action": approval_preview.SCHEMA},
            "required": ["approval_id", "execution_id", "tool", "targets", "is_question",
                         "created_at", "timeout_at", "state"], "additionalProperties": False}
        return {"events": [{"name": name,
            "description": "VK approval notification, with IDs for per-request review. " +
                ("A request is pending." if name == NAMES[0] else
                 "Request state changed; no_longer_pending/deadline_elapsed have no proven outcome."),
            "delivery": ["webhook"], "inputSchema": {"type": "object", "properties": {},
            "additionalProperties": False}, "payloadSchema": schema} for name in NAMES]}

    def subscription(self, principal, params, unsubscribe=False):
        if not principal:
            raise ValueError("Authenticated principal required")
        if set(params) - {"name", "arguments", "delivery", "cursor", "ttlMs", "_meta"}:
            raise ValueError("Invalid subscription fields")
        if params.get("name") not in NAMES or params.get("arguments", {}) != {}:
            raise ValueError("Invalid event/filter")
        if params.get("cursor") is not None:
            raise ValueError("Historical replay cursors are unsupported")
        delivery = params.get("delivery", {})
        url = delivery.get("url")
        if delivery.get("mode") != "webhook" or not isinstance(url, str):
            raise ValueError("Webhook delivery required")
        sid = "sub_" + hashlib.sha256(canonical([principal, url, params["name"], {}]).encode()).hexdigest()
        if unsubscribe:
            self.db.execute("UPDATE subscriptions SET active=0,secret='',previous_secret=NULL,rotation_until=NULL WHERE id=? AND principal=?", (sid, principal))
            self.db.commit()
            return {}
        signing_key(delivery.get("secret"))
        ttl = params.get("ttlMs", 86400000)
        if ttl is not None and (type(ttl) is not int or not 60000 <= ttl <= 604800000):
            raise ValueError("Invalid lifetime")
        challenge = secrets.token_urlsafe(24)  # nonce only, never a credential
        body = {"type": "verification", "challenge": challenge}
        code, raw = self.sender(url, delivery["secret"], sid, "verify_" + secrets.token_hex(12), body)
        try:
            echo = json.loads(raw).get("challenge", "")
        except (ValueError, AttributeError):
            echo = ""
        if not 200 <= code < 300 or not isinstance(echo, str) or not hmac.compare_digest(echo, challenge):
            raise ValueError("Callback verification failed")
        expires = None if ttl is None else self.clock() + ttl / 1000
        previous = self.db.execute("SELECT secret,active FROM subscriptions WHERE id=?", (sid,)).fetchone()
        old_key = previous[0] if previous and previous[1] and previous[0] != delivery["secret"] else None
        self.db.execute("INSERT OR REPLACE INTO subscriptions VALUES (?,?,?,?,?,?,1,?,?)",
                        (sid, principal, params["name"], url, delivery["secret"], expires,
                         old_key, self.clock() + 300 if old_key else None))
        # Replay only current pending requests, never historical expired approvals.
        if params["name"] == NAMES[0]:
            for row in self.db.execute("SELECT id FROM requests WHERE state='pending'").fetchall():
                eid = "evt_" + hashlib.sha256((row["id"] + ":pending").encode()).hexdigest()
                self.db.execute("INSERT OR IGNORE INTO deliveries(event_id,subscription_id) VALUES (?,?)", (eid, sid))
        self.db.commit()
        return {"id": sid, "refreshBefore": iso(expires) if expires is not None else None,
                "cursor": None, "truncated": False}

    def deliver(self):
        self.tick()
        now = self.clock()
        rows = self.db.execute("""SELECT d.*,e.body,s.url,s.secret,s.previous_secret,s.rotation_until FROM deliveries d
            JOIN events e ON e.id=d.event_id JOIN subscriptions s ON s.id=d.subscription_id
            WHERE d.state='pending' AND d.next_try<=? AND s.active=1
            AND (s.expires IS NULL OR s.expires>?) ORDER BY e.rowid LIMIT 8""", (now, now)).fetchall()
        for row in rows:
            body = json.loads(row["body"])
            req = self.db.execute("SELECT state FROM requests WHERE id=?", (body["data"]["approval_id"],)).fetchone()
            if body["name"] == NAMES[0] and (not req or req[0] != "pending"):
                self.db.execute("UPDATE deliveries SET state='superseded' WHERE event_id=? AND subscription_id=?",
                                (row["event_id"], row["subscription_id"]))
                self.db.commit()
                continue
            try:
                keys = [row["secret"], row["previous_secret"]] if row["previous_secret"] and row["rotation_until"] > now else row["secret"]
                status, _ = self.sender(row["url"], keys, row["subscription_id"], row["event_id"], body)
            except Exception:
                status = 0  # Never log callback URLs, headers, secrets or bodies.
            attempts = row["attempts"] + 1
            retryable = status == 0 or status in (408, 425, 429) or 500 <= status < 600
            state = "acknowledged" if 200 <= status < 300 else (
                "pending" if retryable and attempts < 8 else "failed")
            if status == 410:
                self.db.execute("UPDATE subscriptions SET active=0 WHERE id=?", (row["subscription_id"],))
            self.db.execute("""UPDATE deliveries SET state=?,attempts=?,next_try=?,http_status=?
                WHERE event_id=? AND subscription_id=?""",
                (state, attempts, now + min(3600, 15 * 2 ** attempts), status,
                 row["event_id"], row["subscription_id"]))
            self.db.commit()
        return self.status()

    def status(self):
        count = lambda sql: self.db.execute(sql).fetchone()[0]
        return {"pending": count("SELECT count(*) FROM requests WHERE state='pending'"),
                "active_subscriptions": count("SELECT count(*) FROM subscriptions WHERE active=1"),
                "acknowledged_deliveries": count("SELECT count(*) FROM deliveries WHERE state='acknowledged'"),
                "failed_deliveries": count("SELECT count(*) FROM deliveries WHERE state='failed'"),
                "unconfigured": count("SELECT count(*) FROM subscriptions WHERE active=1") == 0,
                "health": {r[0]: json.loads(r[1]) for r in self.db.execute("SELECT * FROM health")}}

    def rpc(self, principal, method, params):
        if method == "events/list":
            return self.event_list()
        if method in ("events/subscribe", "events/unsubscribe"):
            return self.subscription(principal, params, method == "events/unsubscribe")
        raise ValueError("Unsupported event method")


def main():
    import sys
    path = os.environ["VK_APPROVAL_STATE"]
    store = Store(path)
    for line in sys.stdin:
        try:
            msg = json.loads(line)
            if msg["op"] == "snapshot":
                store.snapshot(msg["pending"])
                result = store.status()
            elif msg["op"] == "outcome":
                store.outcome(msg["approval_id"], msg["state"])
                result = {}
            elif msg["op"] == "tick":
                result = store.deliver()
            elif msg["op"] == "health":
                store.health(msg["key"], msg["value"])
                result = {}
            elif msg["op"] == "status":
                result = store.status()
            elif msg["op"] == "unresolved":
                result = [r[0] for r in store.db.execute(
                    "SELECT id FROM requests WHERE state IN ('no_longer_pending','deadline_elapsed') AND observed>=? ORDER BY observed", (store.clock() - 3600,))]
            elif msg["op"] == "rpc":
                result = store.rpc(os.environ["VK_APPROVAL_PRINCIPAL"], msg["method"], msg.get("params", {}))
            else:
                raise ValueError("Invalid operation")
            print(canonical({"ok": True, "result": result}), flush=True)
        except Exception:
            # Even validation errors can contain attacker-controlled values.
            print(canonical({"ok": False, "error": "approval_notification_operation_failed"}), flush=True)
    store.close()


if __name__ == "__main__":
    main()
