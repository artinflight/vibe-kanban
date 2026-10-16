"""Authenticated sidechat events. Callback secrets stay in this private database."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time
from sidechat import Principal, Rejected, canonical
from publisher import publish_once


class Events:
    def __init__(self, store, sender, clock=time.time):
        self.store, self.sender, self.clock = store, sender, clock
        self.db = store.db
        self.db.execute("""CREATE TABLE IF NOT EXISTS sidechat_subscriptions(
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, filters TEXT NOT NULL,
            url TEXT NOT NULL, secret TEXT NOT NULL, expires REAL NOT NULL,
            active INTEGER NOT NULL, previous_secret TEXT, rotation_until REAL)""")

    def definition(self):
        return json.loads(Path(__file__).with_name("contracts.json").read_text())["events"][0]

    def _scope(self, principal, arguments):
        self.store._principal(principal, ("owner",))
        if not isinstance(arguments, dict) or set(arguments) not in ({"thread_id"}, {"project_id"}):
            raise Rejected("Exactly one thread_id or project_id is required")
        value = next(iter(arguments.values()))
        if not isinstance(value, str) or not 1 <= len(value) <= 200:
            raise Rejected("Invalid event scope")
        if "thread_id" in arguments:
            self.store._thread(principal, value)
        elif not (self.db.execute("SELECT 1 FROM scopes WHERE owner=? AND project=?",
                                  (principal.owner, value)).fetchone() or
                  self.db.execute("SELECT 1 FROM project_grants WHERE owner=? AND project=?",
                                  (principal.owner, value)).fetchone()):
            raise Rejected("Project unavailable")
        return canonical(arguments)

    def subscribe(self, principal, params, unsubscribe=False):
        if not isinstance(params, dict) or set(params) - {"name","arguments","delivery","cursor","ttlMs","_meta"}:
            raise Rejected("Invalid subscription request")
        if params.get("name") != self.definition()["name"] or params.get("cursor") is not None:
            raise Rejected("Unsupported event or replay cursor")
        filters = self._scope(principal, params.get("arguments"))
        delivery = params.get("delivery", {})
        if not isinstance(delivery, dict) or delivery.get("mode") != "webhook" or not isinstance(delivery.get("url"), str):
            raise Rejected("Verified webhook destination required")
        sid = "sidechat_sub_" + hashlib.sha256(canonical([principal.owner, delivery["url"], filters]).encode()).hexdigest()
        if unsubscribe:
            with self.store.transaction():
                self.db.execute("UPDATE sidechat_subscriptions SET active=0,secret='',previous_secret=NULL WHERE id=? AND owner=?", (sid,principal.owner))
                self.db.execute("UPDATE bindings SET active=0 WHERE subscription=?", (sid,))
            return {}
        ttl = params.get("ttlMs", 86400000)
        if type(ttl) is not int or not 60000 <= ttl <= 604800000:
            raise Rejected("Finite subscription lifetime of 1 minute to 7 days required")
        # The injected sender is the existing validating/signing transport. It validates
        # whsec_ shape, public HTTPS, DNS pinning, TLS and no redirects BEFORE sending.
        challenge = secrets.token_urlsafe(24)
        status, raw = self.sender(delivery["url"], delivery.get("secret"), sid,
                                  "verify_" + secrets.token_hex(12),
                                  {"type":"verification", "challenge":challenge})
        try:
            echoed=json.loads(raw).get("challenge")
        except (ValueError,AttributeError,TypeError):
            echoed=None
        if not 200 <= status < 300 or not isinstance(echoed,str) or not hmac.compare_digest(challenge,echoed):
            raise Rejected("Callback verification failed")
        expires=self.clock()+ttl/1000
        with self.store.transaction():
            old=self.db.execute("SELECT secret FROM sidechat_subscriptions WHERE id=? AND active=1",(sid,)).fetchone()
            previous=old["secret"] if old and old["secret"]!=delivery["secret"] else None
            self.db.execute("INSERT INTO sidechat_subscriptions VALUES (?,?,?,?,?,?,1,?,?) ON CONFLICT(id) DO UPDATE SET secret=excluded.secret,expires=excluded.expires,active=1,previous_secret=excluded.previous_secret,rotation_until=excluded.rotation_until",
                (sid,principal.owner,filters,delivery["url"],delivery["secret"],expires,previous,self.clock()+300 if previous else None))
        return {"id":sid,"refreshBefore":__import__("datetime").datetime.fromtimestamp(expires,__import__("datetime").timezone.utc).isoformat(),"cursor":None,"truncated":False}

    def _matches(self, sub, thread):
        filters=json.loads(sub["filters"])
        return filters.get("thread_id",thread["id"])==thread["id"] and filters.get("project_id",thread["project"])==thread["project"]

    def sync(self, owner):
        """Apply exact owner filters to existing and newly-created issue threads."""
        principal=Principal(owner,"owner")
        rows=self.db.execute("SELECT * FROM threads WHERE owner=?",(owner,)).fetchall()
        subscriptions=self.db.execute("SELECT * FROM sidechat_subscriptions WHERE owner=? AND active=1 AND expires>?",(owner,self.clock())).fetchall()
        for thread in rows:
            matches=[sub for sub in subscriptions if self._matches(sub,thread)]
            if len(matches)!=1:
                # No matches or overlapping destinations: fail closed, never double-publish.
                self.db.execute("UPDATE bindings SET active=0 WHERE thread=?",(thread["id"],))
                continue
            sub=matches[0]
            try:
                self.store._thread(principal,thread["id"])
            except Rejected:
                self.db.execute("UPDATE bindings SET active=0 WHERE thread=?",(thread["id"],))
                continue
            self.store.bind(principal,thread["id"],sub["id"],ttl=max(60,min(86400,int(sub["expires"]-self.clock()))))

    def deliver_one(self, owner):
        self.sync(owner)
        def deliver(subscription,event):
            sub=self.db.execute("SELECT * FROM sidechat_subscriptions WHERE id=? AND owner=? AND active=1 AND expires>?",
                                (subscription,owner,self.clock())).fetchone()
            if not sub:
                return 410
            scope=self.store._thread(Principal(owner,"owner"),event["data"]["thread_id"])
            if not self._matches(sub,scope):
                return 410
            keys=[sub["secret"],sub["previous_secret"]] if sub["previous_secret"] and sub["rotation_until"]>self.clock() else sub["secret"]
            # The legacy browser may still store per-thread cursors. This event
            # advertises no protocol replay, so every outgoing wire cursor is null.
            # Do not rewrite the immutable outbox or resend accepted deliveries.
            wire_event = dict(event, cursor=None)
            status,_=self.sender(sub["url"],keys,sub["id"],event["eventId"],wire_event)
            if status==410:
                self.db.execute("UPDATE sidechat_subscriptions SET active=0 WHERE id=?",(sub["id"],))
            return status
        return publish_once(self.store,owner,deliver)
