"""Explicit report-delivery events, durable holds, and fail-closed reconciliation.

This database contains connector receipts only, never Vibe read flags. No reads,
agent completions, silence, or fetched assistant text create delivery evidence.
"""
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import urllib.error
import urllib.request

import workspace_unread
from workspace_unread import workspace_id

PROTOCOL = "workspace-review-v1"
STATE = Path("/home/mcp/.config/vibe-dot-connector/report-receipts.sqlite")
HASH_VERSION = "utf8-sha256-v1"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def evidence(value):
    if not isinstance(value, dict) or set(value) != {"actor", "channel", "event_id", "evidence"}:
        raise ValueError("Exact delivery source evidence required")
    if value["actor"] not in ("root", "dot") or value["channel"] not in ("voice", "chat"):
        raise ValueError("Only root/dot voice/chat delivery evidence is supported")
    for key, limit in (("event_id", 200), ("evidence", 2000)):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > limit:
            raise ValueError("Missing or oversized source evidence")
    # Evidence must be a redacted delivery/transcript reference, never credentials.
    if re.search(r"\bBearer\s|\bsk-[A-Za-z0-9]|(?:password|api_key|access_token)\s*[=:]", value["evidence"], re.I):
        raise ValueError("Do not include credentials in delivery evidence")
    return dict(value)


def identity(args):
    keys = {"workspace_id", "execution_id", "session_id", "message_index", "reply_sha256",
            "hash_version", "execution_revision", "disposition", "source"}
    if set(args) != keys:
        raise ValueError("An exact reply identity and actual delivery evidence are required")
    out = dict(args)
    for key in ("workspace_id", "execution_id", "session_id"):
        out[key] = workspace_id(args[key])
    if type(args["message_index"]) is not int or not 0 <= args["message_index"] <= 10_000_000:
        raise ValueError("Invalid message index")
    if not isinstance(args["reply_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", args["reply_sha256"]):
        raise ValueError("Exact lowercase SHA256 required")
    if args["hash_version"] != HASH_VERSION:
        raise ValueError("Unsupported reply hash version")
    rev = args["execution_revision"]
    if not isinstance(rev, str) or len(rev) > 100:
        raise ValueError("Execution revision required")
    try:
        if datetime.datetime.fromisoformat(rev.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError("Timestamp execution revision required") from None
    if args["disposition"] not in ("delivered", "handled"):
        raise ValueError("Fetch/completion is not report delivery")
    out["source"] = evidence(args["source"])
    return out


class Store:
    def __init__(self, path=STATE):
        self.path = Path(path)

    @contextlib.contextmanager
    def locked(self):
        # Fixed existing writable config directory; no user-selected file path.
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.is_symlink():
                raise ValueError("Receipt store must not be a symlink")
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            os.chmod(self.path, 0o600)
            db = sqlite3.connect(self.path, timeout=15)
            db.row_factory = sqlite3.Row
            if db.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
                db.close()
                raise ValueError("Unsupported connector receipt ledger version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS holds (
                  workspace_id TEXT PRIMARY KEY, held INTEGER NOT NULL,
                  version INTEGER NOT NULL, source TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts (
                  receipt_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                  event_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
                  hold_version INTEGER NOT NULL, status TEXT NOT NULL,
                  detail TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  backend_intent_version INTEGER, proof TEXT);
                CREATE INDEX IF NOT EXISTS receipt_workspace ON receipts(workspace_id);
                CREATE TABLE IF NOT EXISTS hold_events (
                  event_key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)
            db.execute("PRAGMA user_version=1")
            try:
                yield db
                db.commit()
            finally:
                db.close()
        finally:
            os.close(lock)

    @staticmethod
    def hold(db, wid):
        row = db.execute("SELECT * FROM holds WHERE workspace_id=?", (wid,)).fetchone()
        return dict(row) if row else {"workspace_id": wid, "held": 0, "version": 0}

    def status(self, wid):
        with self.locked() as db:
            return {"workspace_id": wid, "hold": self.hold(db, wid),
                    "receipts": [dict(row) for row in db.execute(
                        "SELECT receipt_id,status,detail,hold_version,created_at,updated_at,payload,proof "
                        "FROM receipts WHERE workspace_id=? ORDER BY created_at LIMIT 100", (wid,))],
                    "automatic_marking": "requires_verified_atomic_backend",
                    "polling_interval_seconds": None,
                    "proof_origin": "receipt_ledger", "readback_fresh": False}


def verify_reply(api, payload):
    execution = api.http_get("/api/execution-processes/" + payload["execution_id"])
    session = api.http_get("/api/sessions/" + payload["session_id"])
    if execution.get("success") is not True or session.get("success") is not True:
        raise ValueError("Reply ownership unknown")
    ex, se = execution["data"], session["data"]
    if ex["session_id"] != payload["session_id"] or se["workspace_id"] != payload["workspace_id"]:
        raise ValueError("Reply does not belong to this workspace/session")
    if ex["status"] != "completed" or not ex.get("completed_at"):
        raise ValueError("Only a completed durable report can be acknowledged")
    if ex["updated_at"] != payload["execution_revision"]:
        raise ValueError("Execution revision changed")
    before = None
    for _ in range(10):
        path = "/api/execution-processes/" + payload["execution_id"] + "/log-history?limit=100"
        if before is not None:
            path += "&before=" + str(before)
        page = api.http_get(path)
        if page.get("success") is not True:
            raise ValueError("Durable reply history unavailable")
        for row in page["data"]["entries"]:
            if row["index"] != payload["message_index"]:
                continue
            entry = row["entry"]
            content = entry.get("content") or {}
            if entry.get("type") != "NORMALIZED_ENTRY" or (content.get("entry_type") or {}).get("type") != "assistant_message":
                raise ValueError("Identity is not an assistant reply")
            text = content.get("content")
            if not isinstance(text, str) or digest(text) != payload["reply_sha256"]:
                raise ValueError("Exact reply hash changed")
            return
        cursor = page["data"].get("next_before")
        if cursor is None:
            break
        if type(cursor) is not int or cursor < 0 or (before is not None and cursor >= before):
            raise ValueError("Ambiguous reply pagination")
        before = cursor
    raise ValueError("Exact durable reply not found in bounded history")


def backend(api, wid, suffix, method="GET", payload=None):
    # These three internal endpoints are the entire additional network surface.
    if suffix not in ("review-state", "review-receipts", "review-hold"):
        raise ValueError("Unsupported review route")
    path = api.BASE + "/api/workspaces/" + workspace_id(wid) + "/" + suffix
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    req = urllib.request.Request(path, method=method,
        data=canonical(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"} if payload is not None else {})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
        raw = response.read(api.MAX_BYTES + 1)
    if len(raw) > api.MAX_BYTES:
        raise ValueError("Review response exceeds limit; inspect receipt before retry")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("success") is not True or not isinstance(value.get("data"), dict):
        raise ValueError("Atomic review protocol unavailable")
    return value["data"]


def capabilities(api, wid):
    state = backend(api, wid, "review-state")
    if (state.get("protocol") != PROTOCOL or state.get("atomic_exact_reply") is not True
            or state.get("manual_intent_guard") is not True or type(state.get("intent_version")) is not int
            or type(state.get("held")) is not bool):
        raise ValueError("Atomic exact-reply/manual-intent protocol not verified")
    return state


def consume(api, store, receipt_id):
    # Never hold the local writer lock over HTTP: explicit hold events must be
    # able to reach the backend while immutable log replay is in progress there.
    with store.locked() as db:
        row = dict(db.execute("SELECT * FROM receipts WHERE receipt_id=?", (receipt_id,)).fetchone())
        hold = store.hold(db, row["workspace_id"])
    payload = json.loads(row["payload"])
    status, detail, proof, readback_fresh = "pending", "", None, False
    if row["status"] == "applied":
        return {"receipt_id": receipt_id, "status": "applied", "duplicate": True,
                "readback_fresh": False}
    if hold["held"]:
        status, detail = "held", "Explicit manual review hold"
    elif hold["version"] != row["hold_version"]:
        status, detail = "stale_intent", "Manual intent changed after this delivery; new evidence required"
    else:
        try:
            state = capabilities(api, row["workspace_id"])
            expected_intent = row["backend_intent_version"]
            # Receipts recorded before this protocol existed may only join the
            # initial epoch zero. They cannot silently adopt later manual intent.
            if expected_intent is None:
                expected_intent = 0
            if state["held"] or state["intent_version"] != expected_intent:
                status, detail = "stale_intent", "Backend manual intent changed; do not replay old delivery"
            else:
                with store.locked() as db:
                    latest_hold = store.hold(db, row["workspace_id"])
                if latest_hold["held"] or latest_hold["version"] != row["hold_version"]:
                    raise ValueError("Local hold/intent changed before atomic request")
                request = dict(payload, receipt_id=receipt_id, intent_version=expected_intent)
                proof = dict(backend(api, row["workspace_id"], "review-receipts", "POST", request))
                if (proof.get("protocol") != PROTOCOL or proof.get("receipt_id") != receipt_id
                        or proof.get("execution_id") != payload["execution_id"]
                        or proof.get("message_index") != payload["message_index"]
                        or proof.get("reply_sha256") != payload["reply_sha256"]
                        or proof.get("status") not in ("applied", "already_applied")):
                    raise ValueError("Atomic acknowledgement proof mismatch")
                status, detail = "applied", "Backend acknowledged only the exact reviewed turn"
                # Backend acknowledgement is historical/idempotent proof. Only
                # this separate summary request can establish a current flag.
                proof.pop("authoritative_readback", None)
                proof.pop("authoritative_readback_observed_at", None)
                rows = workspace_unread.request(api).get("summaries", [])
                flags = [r.get("has_unseen_turns") for r in rows if r.get("workspace_id") == row["workspace_id"]]
                proof["authoritative_readback"] = flags[0] if len(flags) == 1 and type(flags[0]) is bool else "unknown"
                proof["authoritative_readback_observed_at"] = now()
                readback_fresh = True
        except urllib.error.HTTPError as error:
            status = "blocked_backend" if error.code in (400, 404, 405) else "backend_conflict"
            detail = "Atomic backend route HTTP " + str(error.code) + "; no legacy /seen fallback"
        except (OSError, ValueError, KeyError):
            status, detail = "blocked_backend", "Atomic backend unavailable/uncertain; deduplicated retry only"
    with store.locked() as db:
        # Intent pins and immutable payload are NEVER updated on retry, including
        # a lost response after backend commit. NULL legacy intent stays NULL;
        # the epoch-zero fallback above is only a request value, not adoption.
        db.execute("UPDATE receipts SET status=?,detail=?,updated_at=?,proof=? WHERE receipt_id=? "
                   "AND (status <> 'applied' OR ? = 'applied')",
                   (status, detail, now(), canonical(proof) if proof is not None else None, receipt_id, status))
    return {"receipt_id": receipt_id, "workspace_id": row["workspace_id"], "status": status,
            "detail": detail, "proof": proof, "readback_fresh": readback_fresh}


def record(api, args, store=None):
    args = dict(args)
    guard_keys = {"expected_intent_version", "expected_hold_version"}
    pinned = bool(guard_keys & set(args))
    if pinned and not guard_keys <= set(args):
        raise ValueError("Both prepared delivery intent versions are required")
    guards = {k: args.pop(k) for k in guard_keys} if pinned else {}
    if any(type(v) is not int or not 0 <= v <= 9223372036854775807 for v in guards.values()):
        raise ValueError("Prepared intent versions must be non-negative integers")
    payload = identity(args)
    verify_reply(api, payload)
    store = store or Store()
    key = canonical([payload["workspace_id"], payload["source"]["actor"],
                     payload["source"]["channel"], payload["source"]["event_id"]])
    rid = digest(canonical(payload))
    epoch = guards.get("expected_intent_version")
    if not pinned:
        try:
            epoch = capabilities(api, payload["workspace_id"])["intent_version"]
        except (OSError, ValueError, KeyError):
            pass
    with store.locked() as db:
        old = db.execute("SELECT receipt_id,payload,backend_intent_version,hold_version FROM receipts WHERE event_key=?", (key,)).fetchone()
        if old and old["payload"] != canonical(payload):
            raise ValueError("Delivery event reused with a different reply/evidence")
        if old and pinned and (old["backend_intent_version"] != epoch
                or old["hold_version"] != guards["expected_hold_version"]):
            raise ValueError("Delivery event reused with different prepared intent")
        if not old:
            if db.execute("SELECT count(*) FROM receipts").fetchone()[0] >= 10_000:
                raise ValueError("Receipt ledger limit reached; no automatic pruning")
            hold = store.hold(db, payload["workspace_id"])
            db.execute("INSERT INTO receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rid, payload["workspace_id"], key, canonical(payload),
                 guards["expected_hold_version"] if pinned else hold["version"],
                 "pending", "Actual root/dot delivered/handled signal", now(), now(), epoch, None))
            # Durable receipt precedes the network operation. A crash can only
            # leave a pending receipt; backend receipt_id makes retry idempotent.
            db.commit()
    result = consume(api, store, rid)
    return dict(result, recorded=True, duplicate=bool(old))


def prepare(api, args, store=None):
    # Read-only preparation BEFORE presentation. It never creates a receipt.
    if set(args) != set(RECEIPT_PROPERTIES) - {"disposition", "source"}:
        raise ValueError("Exact complete durable reply identity required")
    checked = identity(dict(args, disposition="delivered", source={
        "actor": "root", "channel": "chat", "event_id": "identity-validation-only",
        "evidence": "Identity validation only; no delivery or receipt."}))
    identity_only = {k: checked[k] for k in args}
    verify_reply(api, identity_only)
    state = capabilities(api, identity_only["workspace_id"])
    hold = (store or Store()).status(identity_only["workspace_id"])["hold"]
    return {"delivery_context_version": 1, "identity": identity_only,
            "expected_intent_version": state["intent_version"],
            "expected_hold_version": hold["version"],
            "held": state["held"] or bool(hold["held"])}


def set_hold(api, args, store=None):
    if set(args) != {"workspace_id", "held", "source"} or type(args["held"]) is not bool:
        raise ValueError("One workspace, boolean held and explicit user-intent source required")
    wid, source = workspace_id(args["workspace_id"]), evidence(args["source"])
    store = store or Store()
    event = canonical([wid, source["actor"], source["channel"], source["event_id"]])
    payload = canonical(dict(args, workspace_id=wid, source=source))
    epoch = None
    try:
        epoch = capabilities(api, wid)["intent_version"]
    except (OSError, ValueError, KeyError):
        pass
    with store.locked() as db:
        previous = db.execute("SELECT payload FROM hold_events WHERE event_key=?", (event,)).fetchone()
        if previous:
            saved = json.loads(previous[0])
            # Read the original v1 seed format as an offline epoch-zero event.
            saved_args = saved.get("args", saved)
            if canonical(saved_args) != payload:
                raise ValueError("Hold event reused with conflicting intent")
            epoch = saved.get("backend_intent_version")
        if not previous:
            old = store.hold(db, wid)
            db.execute("INSERT OR REPLACE INTO holds VALUES (?,?,?,?,?)",
                       (wid, int(args["held"]), old["version"] + 1, canonical(source), now()))
            db.execute("INSERT INTO hold_events VALUES (?,?)", (event,
                canonical({"args": json.loads(payload), "backend_intent_version": epoch})))
            db.commit()
        # Hold events never invoke any read-marker endpoint. Backend mirroring
        # is fail closed, and ordinary UI /unread must register intent there.
        current = store.hold(db, wid)
    superseded = current["source"] != canonical(source) or bool(current["held"]) != args["held"]
    if superseded:
        return {"workspace_id": wid, "held": bool(current["held"]), "persisted": True,
                "backend_mirrored": False, "marks_sent": 0, "duplicate": bool(previous), "superseded": True}
    mirrored = False
    try:
        state = capabilities(api, wid)
        expected_epoch = epoch if epoch is not None else 0
        if state["intent_version"] == expected_epoch:
            proof = backend(api, wid, "review-hold", "PUT",
                {"held": args["held"], "event_id": event, "source": source,
                 "expected_intent_version": expected_epoch})
            mirrored = proof.get("held") == args["held"]
    except (OSError, ValueError, KeyError):
        pass
    return {"workspace_id": wid, "held": args["held"], "persisted": True,
            "backend_mirrored": mirrored, "marks_sent": 0, "duplicate": bool(previous)}


def reconcile(api, args, store=None):
    if set(args) != {"workspace_id"}:
        raise ValueError("Exactly one workspace_id required")
    wid, store = workspace_id(args["workspace_id"]), store or Store()
    with store.locked() as db:
        ids = [r[0] for r in db.execute("SELECT receipt_id FROM receipts WHERE workspace_id=? "
            "AND status NOT IN ('applied','stale_intent') ORDER BY created_at LIMIT 64", (wid,))]
    return {"workspace_id": wid, "results": [consume(api, store, rid) for rid in ids]}


def status(api, args, store=None):
    if set(args) != {"workspace_id"}:
        raise ValueError("Exactly one workspace_id required")
    wid = workspace_id(args["workspace_id"])
    result = (store or Store()).status(wid)
    if wid == 'PRIVATE_BINDING_265B9BBB95A88C2A':
        import credit_budget
        import usage_reporting
        result = dict(result, credit_budget=credit_budget.read_credit_budget(),
                      usage_report=usage_reporting.read_summary())
    # Additive private history lookup. Original delivery/CU readbacks retain their meaning.
    try:
        import sidechat_connector
        sidechat_context = sidechat_connector.workspace_context(wid)
    except Exception:
        sidechat_context = {"status": "unavailable", "workspace_id": wid}
    result = dict(result, sidechat=sidechat_context)
    try:
        import dispatch_notes
        result = dict(result, dispatch_notes=dispatch_notes.workspace_status(wid))
    except Exception:
        result = dict(result, dispatch_notes={"status": "unavailable", "receipts": []})
    return result


SOURCE = {"type": "object", "properties": {
    "actor": {"type": "string", "enum": ["root", "dot"]},
    "channel": {"type": "string", "enum": ["voice", "chat"]},
    "event_id": {"type": "string", "minLength": 1, "maxLength": 200},
    "evidence": {"type": "string", "minLength": 1, "maxLength": 2000}},
    "required": ["actor", "channel", "event_id", "evidence"], "additionalProperties": False}
ID = {"type": "string", "format": "uuid"}
RECEIPT_PROPERTIES = {"workspace_id": ID, "execution_id": ID, "session_id": ID,
    "message_index": {"type": "integer", "minimum": 0, "maximum": 10000000},
    "reply_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "hash_version": {"type": "string", "enum": [HASH_VERSION]},
    "execution_revision": {"type": "string", "maxLength": 100},
    "disposition": {"type": "string", "enum": ["delivered", "handled"]}, "source": SOURCE}


def tool(name, description, properties, read=False):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties, "required": list(properties), "additionalProperties": False},
        "annotations": {"readOnlyHint": read, "destructiveHint": False, "openWorldHint": False}}


TOOLS = [
    tool("record_workspace_report_delivery", "Root/dot: immediately AFTER actual voice/chat conveyance or explicit user handled acknowledgement, submit this exact durable report identity and redacted source-event evidence. This is the delivery caller; reading, fetching, completion, silence and an agent's own delivery claim are NOT delivery. Persists receipt, automatically invokes conditional exact-reply reconciliation; fails closed while the atomic backend is unavailable. Never clears unrelated/new/running reports or holds.", RECEIPT_PROPERTIES),
    tool("set_workspace_review_hold", "Record explicit user leave-unread/manual-review intent (held=true) or explicit release (held=false), durably across restarts. Root/dot must provide actual user voice/chat evidence. Does not change read flags; old receipts cannot override changed intent.", {"workspace_id": ID, "held": {"type": "boolean"}, "source": SOURCE}),
    tool("get_workspace_reconciliation_status", "Read this workspace's durable delivery receipts, holds and blocking reasons. Reading never submits delivery or clears badges.", {"workspace_id": ID}, True),
    tool("reconcile_workspace_reports", "Resume this workspace's already recorded, actually delivered reports after backend recovery. At most 64 receipts; idempotent conditional exact-reply backend only. No legacy mark-all fallback and no inferred delivery.", {"workspace_id": ID}),
]

# Optional for existing explicit callers; automatic delivery callers MUST pin
# both versions read before presentation. They are connector guards, not extra
# fields forwarded to the existing workspace-review-v1 backend.
TOOLS[0]["inputSchema"]["properties"] = dict(RECEIPT_PROPERTIES, **{
    k: {"type": "integer", "minimum": 0, "maximum": 9223372036854775807}
    for k in ("expected_intent_version", "expected_hold_version")})
TOOLS[0]["description"] += " Automatic delivery callers must first prepare the exact report and pass both prepared intent versions unchanged."
TOOLS.append(tool("prepare_workspace_report_delivery",
    "Read-only: verify the exact complete durable reply and snapshot backend/manual-review intent BEFORE presenting it. Returns immutable caller context, not delivery evidence. Pass both intent versions unchanged after actual conveyance. A held report remains unread; preparation never records or clears anything.",
    {k: v for k, v in RECEIPT_PROPERTIES.items() if k not in ("source", "disposition")}, True))

HANDLERS = {"record_workspace_report_delivery": record, "set_workspace_review_hold": set_hold,
            "get_workspace_reconciliation_status": status, "reconcile_workspace_reports": reconcile,
            "prepare_workspace_report_delivery": prepare}
