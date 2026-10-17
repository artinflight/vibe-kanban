"""Isolated sidechat contracts. No credentials, network transport or agent actions.

Auth is supplied by a trusted adapter, never by tool arguments. The demo adapter
uses fixed fixture identities on loopback; it is NOT production authentication.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

EVENT = "vk.sidechat.owner_message.created"


@dataclass(frozen=True)
class Principal:
    owner: str
    role: str  # owner, dot or publisher, supplied by trusted host


class Rejected(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        db_path = Path(path)
        if db_path.is_symlink():
            raise Rejected("Private database cannot be a symlink")
        try:
            fd = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            if db_path.stat().st_mode & 0o077:
                raise Rejected("Private database must be owner-readable only")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS scopes(
          owner TEXT, project TEXT, issue TEXT, workspace TEXT,
          PRIMARY KEY(owner,workspace));
        CREATE TABLE IF NOT EXISTS project_grants(
          owner TEXT NOT NULL, project TEXT NOT NULL,
          PRIMARY KEY(owner,project));
        CREATE TABLE IF NOT EXISTS owner_project_policies(
          owner TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS all_project_sessions(
          owner TEXT NOT NULL, session TEXT NOT NULL,
          PRIMARY KEY(owner,session));
        CREATE TABLE IF NOT EXISTS threads(
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
          issue TEXT NOT NULL, created REAL NOT NULL,
          UNIQUE(owner,project,issue));
        CREATE TABLE IF NOT EXISTS messages(
          id TEXT PRIMARY KEY, thread TEXT NOT NULL REFERENCES threads(id),
          seq INTEGER NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL,
          workspace TEXT NOT NULL, request TEXT NOT NULL, reply_to TEXT,
          hash TEXT NOT NULL, created REAL NOT NULL,
          UNIQUE(thread,seq), UNIQUE(thread,role,request), UNIQUE(reply_to));
        CREATE TABLE IF NOT EXISTS dot_reply_state(
          message TEXT PRIMARY KEY REFERENCES messages(id),
          seen INTEGER NOT NULL DEFAULT 0,
          attention_kind TEXT CHECK(attention_kind IN ('question','action')),
          initial_attention_kind TEXT CHECK(initial_attention_kind IN ('question','action')),
          resolved INTEGER NOT NULL DEFAULT 0,
          updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS bindings(
          thread TEXT PRIMARY KEY REFERENCES threads(id),
          subscription TEXT NOT NULL, active INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(
          event TEXT PRIMARY KEY, message TEXT UNIQUE NOT NULL REFERENCES messages(id),
          thread TEXT NOT NULL REFERENCES threads(id), payload TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
          next_try REAL NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
          subscription TEXT, http_status INTEGER, updated REAL NOT NULL);
        """)

        # Legacy Dot replies become unread once. Reopening never resets state.
        self.db.execute("INSERT OR IGNORE INTO dot_reply_state(message,updated) SELECT id,created FROM messages WHERE role='dot'")

        # Only prototype schema evolution; existing fixtures retain all messages.
        if "expires" not in {r[1] for r in self.db.execute("PRAGMA table_info(bindings)")} :
            self.db.execute("ALTER TABLE bindings ADD COLUMN expires REAL NOT NULL DEFAULT 0")

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()

    def _principal(self, principal, roles):
        if not isinstance(principal.owner, str) or not principal.owner or principal.role not in roles:
            raise Rejected("Unauthorized role")

    def _thread(self, principal, thread):
        self._principal(principal, ("owner", "dot", "publisher"))
        row = self.db.execute("SELECT * FROM threads WHERE id=? AND owner=? AND EXISTS (SELECT 1 FROM scopes s WHERE s.owner=threads.owner AND s.project=threads.project AND s.issue=threads.issue)",
                              (thread, principal.owner)).fetchone()
        if not row:
            raise Rejected("Thread unavailable")
        return row

    def register_scope(self, owner, project, issue, workspace):
        """Trusted provisioning only. Never exposed as a tool or HTTP endpoint."""
        if not all(isinstance(v, str) and 0 < len(v) <= 200 for v in (owner, project, issue, workspace)):
            raise Rejected("Invalid scope")
        with self.transaction():
            old = self.db.execute("SELECT * FROM scopes WHERE owner=? AND workspace=?",
                                  (owner, workspace)).fetchone()
            if old and (old["project"], old["issue"]) != (project, issue):
                raise Rejected("Relinking requires explicit migration; history is retained")
            self.db.execute("INSERT OR IGNORE INTO scopes VALUES (?,?,?,?)",
                            (owner, project, issue, workspace))

    def resolve(self, principal, project, issue, workspace):
        self._principal(principal, ("owner",))
        with self.transaction():
            scope = self.db.execute("SELECT 1 FROM scopes WHERE owner=? AND project=? AND issue=? AND workspace=?",
                                    (principal.owner, project, issue, workspace)).fetchone()
            if not scope:
                raise Rejected("Workspace is not authorized for this issue")
            self.db.execute("INSERT OR IGNORE INTO threads VALUES (?,?,?,?,?)",
                            (str(uuid.uuid4()), principal.owner, project, issue, self.clock()))
            return dict(self.db.execute("SELECT * FROM threads WHERE owner=? AND project=? AND issue=?",
                                        (principal.owner, project, issue)).fetchone())

    def _workspace(self, principal, row, workspace):
        if not self.db.execute("SELECT 1 FROM scopes WHERE owner=? AND project=? AND issue=? AND workspace=?",
                               (principal.owner, row["project"], row["issue"], workspace)).fetchone():
            raise Rejected("Workspace is not authorized for this thread")

    def append(self, principal, thread, workspace, request, body, reply_to=None, event_id=None, attention=None):
        self._principal(principal, ("owner", "dot"))
        if not isinstance(body, str) or not body.strip() or len(body.encode()) > 60000:
            raise Rejected("Message must contain 1..60000 UTF-8 bytes")
        try:
            uuid.UUID(request)
        except (ValueError, TypeError, AttributeError):
            raise Rejected("Request must be a UUID")
        if attention not in (None,'question','action') or (principal.role!='dot' and attention is not None):
            raise Rejected('Only Dot replies can flag a question or action')
        with self.transaction():
            scope = self._thread(principal, thread)
            self._workspace(principal, scope, workspace)
            if principal.role == "owner" and (reply_to is not None or event_id is not None):
                raise Rejected("Owner messages cannot impersonate replies")
            if principal.role == "dot":
                target = self.db.execute("SELECT m.*,o.event FROM messages m JOIN outbox o ON o.message=m.id WHERE m.id=? AND m.thread=? AND m.role='owner'",
                                         (reply_to, thread)).fetchone()
                if not target or target["event"] != event_id or target["workspace"] != workspace:
                    raise Rejected("Reply must match the exact owner message/event/workspace")
            digest = hashlib.sha256(body.encode()).hexdigest()
            old = self.db.execute("SELECT * FROM messages WHERE thread=? AND role=? AND request=?",
                                  (thread, principal.role, request)).fetchone()
            if old:
                if (old["hash"], old["workspace"], old["reply_to"]) != (digest, workspace, reply_to):
                    raise Rejected("Idempotency key conflict")
                # Idempotency compares the original annotation, not subsequently
                # resolved state. A retry cannot reopen an action or mark it unread.
                initial=self.db.execute('SELECT initial_attention_kind FROM dot_reply_state WHERE message=?',(old['id'],)).fetchone()
                if principal.role=='dot' and (not initial or initial[0]!=attention):
                    raise Rejected('Idempotency key conflict')
                return dict(old)
            if reply_to and self.db.execute("SELECT 1 FROM messages WHERE reply_to=?", (reply_to,)).fetchone():
                raise Rejected("Owner message already has a final reply")
            seq = self.db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM messages WHERE thread=?", (thread,)).fetchone()[0]
            mid, now = str(uuid.uuid4()), self.clock()
            self.db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (mid, thread, seq, principal.role, body, workspace, request, reply_to, digest, now))
            if principal.role=='dot':
                self.db.execute('INSERT INTO dot_reply_state(message,attention_kind,initial_attention_kind,updated) VALUES (?,?,?,?)',(mid,attention,attention,now))
            if principal.role == "owner":
                eid = "sidechat_" + mid
                payload = {"eventId": eid, "name": EVENT, "timestamp": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                           "data": {"thread_id": thread, "project_id": scope["project"],
                                    "issue_id": scope["issue"], "workspace_id": workspace,
                                    "message_id": mid, "sequence": seq,
                                    "author_type": "authenticated_owner",
                                    "intent": "sidechat_reply_requested",
                                    "reply_scope": "same_thread_only",
                                    "message_sha256": digest}, "cursor": None}
                self.db.execute("INSERT INTO outbox(event,message,thread,payload,updated) VALUES (?,?,?,?,?)",
                                (eid, mid, thread, canonical(payload), now))
            return dict(self.db.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone())

    def read(self, principal, thread, after=0, limit=50, through=None):
        self._principal(principal, ("owner", "dot"))
        scope = self._thread(principal, thread)
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise Rejected("Invalid pagination")
        high = self.db.execute("SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread=?", (thread,)).fetchone()[0]
        if through is None:
            through = high
        if type(through) is not int or through < after or through > high:
            raise Rejected("Invalid snapshot")
        rows = [dict(r) for r in self.db.execute("SELECT * FROM messages WHERE thread=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?",
                                                (thread, after, through, limit + 1))]
        more = len(rows) > limit
        rows = rows[:limit]
        for message in rows:
            if message['role']=='dot':
                state=self.db.execute('SELECT seen,attention_kind,resolved FROM dot_reply_state WHERE message=?',(message['id'],)).fetchone()
                message['seen']=bool(state and state['seen'])
                message['attention']={'kind':state['attention_kind'],'resolved':bool(state['resolved'])} if state and state['attention_kind'] else None
            if message["role"] == "owner":
                message["owner_intent"] = {
                    "intent": "sidechat_reply_requested",
                    "reply_scope": "same_thread_only",
                    "thread_id": thread, "message_id": message["id"],
                    "message_sha256": message["hash"],
                    "coding_agent_action_authorized": False,
                    "platform_review_bypass": False,
                }
        return {"thread": dict(scope), "messages": rows, "through": through,
                "next_after": rows[-1]["seq"] if more else None, "complete": not more}

    def notifications(self, principal, projects):
        """Owner-only metadata. A GET never acknowledges reading or resolves work."""
        self._principal(principal,('owner',))
        allowed=set(projects)
        rows=self.db.execute("""SELECT t.project,t.issue,
          SUM(CASE WHEN s.seen=0 THEN 1 ELSE 0 END) AS unread_count,
          SUM(CASE WHEN s.attention_kind IS NOT NULL AND s.resolved=0 THEN 1 ELSE 0 END) AS needs_attention_count
          FROM threads t JOIN messages m ON m.thread=t.id AND m.role='dot'
          JOIN dot_reply_state s ON s.message=m.id WHERE t.owner=?
          GROUP BY t.project,t.issue""",(principal.owner,)).fetchall()
        return {'issues':[{'project_id':r['project'],'issue_id':r['issue'],
          'unread_count':r['unread_count'],'needs_attention_count':r['needs_attention_count']}
          for r in rows if r['project'] in allowed and (r['unread_count'] or r['needs_attention_count'])]}

    def seen_replies(self, principal, thread, workspace, messages):
        self._principal(principal,('owner',))
        if not isinstance(messages,list) or not 1<=len(messages)<=100 or any(not isinstance(m,str) for m in messages) or len(set(messages))!=len(messages):
            raise Rejected('Bounded distinct visible reply IDs required')
        with self.transaction():
            scope=self._thread(principal,thread);self._workspace(principal,scope,workspace)
            for message in messages:
                if not self.db.execute("SELECT 1 FROM messages WHERE id=? AND thread=? AND role='dot'",(message,thread)).fetchone():
                    raise Rejected('Visible reply unavailable')
            for message in messages:
                self.db.execute('UPDATE dot_reply_state SET seen=1,updated=? WHERE message=? AND seen=0',(self.clock(),message))
        return {'seen':messages}

    def set_sidechat_attention(self, principal, thread, workspace, message, action):
        self._principal(principal,('owner','dot'))
        if action not in ('question','action','resolve','reopen'):
            raise Rejected('Explicit attention action required')
        with self.transaction():
            scope=self._thread(principal,thread);self._workspace(principal,scope,workspace)
            row=self.db.execute("SELECT m.workspace,s.attention_kind,s.resolved FROM messages m JOIN dot_reply_state s ON s.message=m.id WHERE m.id=? AND m.thread=? AND m.role='dot'",(message,thread)).fetchone()
            if not row or (principal.role=='dot' and row['workspace']!=workspace):
                raise Rejected('Dot reply unavailable in this scope')
            if action in ('resolve','reopen') and not row['attention_kind']:
                raise Rejected('Reply has no question or action to resolve')
            kind=action if action in ('question','action') else row['attention_kind']
            resolved=action=='resolve'
            self.db.execute('UPDATE dot_reply_state SET attention_kind=?,resolved=?,updated=? WHERE message=?',(kind,int(resolved),self.clock(),message))
        return {'message':message,'attention':{'kind':kind,'resolved':resolved}}

    def pending(self, principal, after=0, limit=20, through=None):
        """Read-only recovery when the platform wake omits its event context.

        Snapshot cursors never acknowledge, claim, resend or manufacture an event.
        Only registered exact owner/workspace scopes and unanswered messages appear.
        """
        self._principal(principal, ("dot",))
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise Rejected("Invalid pagination")
        high = self.db.execute("SELECT COALESCE(MAX(m.rowid),0) FROM messages m JOIN threads t ON t.id=m.thread WHERE t.owner=?", (principal.owner,)).fetchone()[0]
        if through is None:
            through = high
        if type(through) is not int or not after <= through <= high:
            raise Rejected("Invalid snapshot")
        rows = self.db.execute("""
          SELECT m.rowid AS position,m.id,m.thread,m.workspace,m.seq,m.hash,
                 t.project,t.issue,o.event,o.payload
          FROM messages m JOIN threads t ON t.id=m.thread JOIN outbox o ON o.message=m.id
          WHERE t.owner=? AND m.role='owner' AND m.rowid>? AND m.rowid<=?
          AND NOT EXISTS(SELECT 1 FROM messages r WHERE r.reply_to=m.id)
          AND EXISTS(SELECT 1 FROM scopes s WHERE s.owner=t.owner AND s.project=t.project
                     AND s.issue=t.issue AND s.workspace=m.workspace)
          ORDER BY m.rowid LIMIT ?
          """, (principal.owner,after,through,limit+1)).fetchall()
        more = len(rows)>limit
        rows = rows[:limit]
        items = []
        for row in rows:
            event = json.loads(row["payload"])
            expected = {"thread_id":row["thread"],"project_id":row["project"],
                        "issue_id":row["issue"],"workspace_id":row["workspace"],
                        "message_id":row["id"],"sequence":row["seq"],
                        "message_sha256":row["hash"],"author_type":"authenticated_owner",
                        "intent":"sidechat_reply_requested","reply_scope":"same_thread_only"}
            if event.get("eventId")!=row["event"] or event.get("name")!=EVENT or event.get("data")!=expected:
                raise Rejected("Stored event context is inconsistent; do not guess a reply target")
            items.append({"event":event,
                          "reply_request":str(uuid.uuid5(uuid.NAMESPACE_URL,"vibe-sidechat:"+row["event"])),
                          "delivery":self.receipt(principal,row["thread"],row["id"])})
        return {"items":items,"through":through,
                "next_after":rows[-1]["position"] if more else None,
                "complete":not more}

    def bind(self, principal, thread, subscription, ttl=3600):
        """Trusted events/subscribe adapter AFTER callback verification only."""
        self._principal(principal, ("owner",))
        if not isinstance(subscription, str) or not 1 <= len(subscription) <= 200 or type(ttl) is not int or not 60 <= ttl <= 86400:
            raise Rejected("Invalid verified subscription")
        with self.transaction():
            self._thread(principal, thread)
            old = self.db.execute("SELECT * FROM bindings WHERE thread=?", (thread,)).fetchone()
            if old and old["subscription"] != subscription:
                raise Rejected("Explicit destination migration required")
            self.db.execute("INSERT INTO bindings VALUES (?,?,1,?) ON CONFLICT(thread) DO UPDATE SET active=1,expires=excluded.expires",
                            (thread, subscription, self.clock() + ttl))

    def unbind(self, principal, thread):
        self._principal(principal, ("owner",))
        with self.transaction():
            self._thread(principal, thread)
            self.db.execute("UPDATE bindings SET active=0 WHERE thread=?", (thread,))

    def claim(self, principal):
        self._principal(principal, ("publisher",))
        with self.transaction():
            row = self.db.execute("""
              SELECT o.*,b.subscription AS destination FROM outbox o
              JOIN threads t ON t.id=o.thread JOIN bindings b ON b.thread=o.thread
              JOIN messages m ON m.id=o.message
              JOIN scopes s ON s.owner=t.owner AND s.project=t.project AND s.issue=t.issue AND s.workspace=m.workspace
              WHERE t.owner=? AND b.active=1 AND b.expires>? AND o.state IN ('pending','inflight')
              AND o.next_try<=? AND o.lease_until<=? ORDER BY o.rowid LIMIT 1
              """, (principal.owner, self.clock(), self.clock(), self.clock())).fetchone()
            if not row:
                return None
            attempt = row["attempts"] + 1
            self.db.execute("UPDATE outbox SET state='inflight',attempts=?,lease_until=?,subscription=?,updated=? WHERE event=?",
                            (attempt, self.clock() + 30, row["destination"], self.clock(), row["event"]))
            return {"event": json.loads(row["payload"]), "subscription": row["destination"], "attempt": attempt}

    def acknowledge(self, principal, event, attempt, status):
        self._principal(principal, ("publisher",))
        if type(status) is not int or not 0 <= status <= 599:
            raise Rejected("Invalid HTTP status")
        with self.transaction():
            row = self.db.execute("SELECT o.* FROM outbox o JOIN threads t ON t.id=o.thread WHERE o.event=? AND t.owner=?",
                                  (event, principal.owner)).fetchone()
            if not row or row["state"] != "inflight" or row["attempts"] != attempt:
                raise Rejected("Stale delivery attempt")
            transient = status == 0 or status in (408, 425, 429) or 500 <= status <= 599
            state = "webhook_accepted" if 200 <= status < 300 else (
                "pending" if transient and attempt < 8 else "failed")
            self.db.execute("UPDATE outbox SET state=?,http_status=?,next_try=?,lease_until=0,updated=? WHERE event=?",
                            (state, status, self.clock() + min(3600, 2 ** attempt), self.clock(), event))
            if status == 410:
                self.db.execute("UPDATE bindings SET active=0 WHERE thread=?", (row["thread"],))

    def receipt(self, principal, thread, message):
        self._principal(principal, ("owner", "dot"))
        self._thread(principal, thread)
        row = self.db.execute("SELECT event,state,attempts,http_status,updated FROM outbox WHERE thread=? AND message=?",
                              (thread, message)).fetchone()
        if not row:
            raise Rejected("Receipt unavailable")
        reply = self.db.execute("SELECT id,seq,hash FROM messages WHERE reply_to=? AND thread=?", (message, thread)).fetchone()
        return {**dict(row), "reply_persisted": reply is not None,
                "reply": dict(reply) if reply else None, "seen": None}

    def tool(self, principal, name, args):
        """Minimal allowlisted adapter contract: no owner/role argument accepted."""
        allowed = {
            "list_pending_sidechat_messages": ({"after", "limit", "through"}, self.pending),
            "read_sidechat_thread": ({"thread", "after", "limit", "through"}, self.read),
            "append_dot_reply": ({"thread", "workspace", "request", "body", "reply_to", "event_id", "attention"}, self.append),
            "set_sidechat_attention": ({"thread","workspace","message","action"}, self.set_sidechat_attention),
            "get_sidechat_delivery": ({"thread", "message"}, self.receipt),
        }
        self._principal(principal, ("dot",))
        if name not in allowed or not isinstance(args, dict) or set(args) - allowed[name][0]:
            raise Rejected("Unknown tool or argument")
        return allowed[name][1](principal, **args)
