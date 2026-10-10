"""Root/dot delivery boundary, using the existing restricted connector tools.

This module owns prepared presentation context and an immutable event outbox.
The connector and workspace-review-v1 backend own receipts and all read flags.
No transport playback or user acknowledgement is inferred here.
"""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys


IDENTITY_KEYS = {
    "workspace_id", "execution_id", "session_id", "message_index",
    "reply_sha256", "hash_version", "execution_revision",
}
GUARD_KEYS = {"expected_intent_version", "expected_hold_version"}
CONTEXT_KEYS = IDENTITY_KEYS | GUARD_KEYS
CONFIRMED = {
    "chat_delivered": ("chat", "delivered"),
    "voice_playback_completed": ("voice", "delivered"),
    "user_handled": (None, "handled"),
}
NOT_DELIVERED = {"cancelled", "partial", "failed", "fetched", "completed"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def require_prepared_guards(request):
    if any(type(request.get(k)) is not int or not 0 <= request[k] <= 9223372036854775807
           for k in GUARD_KEYS):
        raise ValueError("Automatic delivery requires both prepared intent versions")


def cached_result(saved):
    # A receipt remains applied; its old flag observation is not current state.
    value = dict(saved, duplicate=True, result_origin="outbox_cache", readback_fresh=False)
    if isinstance(saved.get("proof"), dict):
        proof = dict(saved["proof"])
        if "authoritative_readback" in proof:
            value["historical_readback"] = {
                "has_unseen_turns": proof.pop("authoritative_readback"),
                "observed_at": proof.pop("authoritative_readback_observed_at", None),
                "fresh": False,
            }
        value["proof"] = proof
    return value


class Caller:
    def __init__(self, path, tools):
        self.path = Path(path)
        self.tools = tools

    @contextlib.contextmanager
    def database(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS presentations (
                  token TEXT PRIMARY KEY, context TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                  token TEXT PRIMARY KEY REFERENCES presentations(token),
                  event_key TEXT NOT NULL UNIQUE, request TEXT NOT NULL,
                  result TEXT);
            """)
            yield db
            db.commit()
        finally:
            db.close()

    def prepare(self, identity):
        if not isinstance(identity, dict) or set(identity) != IDENTITY_KEYS:
            raise ValueError("Exact full durable reply identity required")
        value = self.tools.call("prepare_workspace_report_delivery", identity)
        if (value.get("delivery_context_version") != 1
                or value.get("identity") != identity or type(value.get("held")) is not bool
                or any(type(value.get(k)) is not int or not 0 <= value[k] <= 9223372036854775807
                       for k in GUARD_KEYS)):
            raise ValueError("Prepared delivery context unavailable; do not acknowledge")
        if value["held"]:
            return {"prepared": False, "held": True}
        context = dict(identity, **{k: value[k] for k in GUARD_KEYS})
        token = digest(context)
        with self.database() as db:
            db.execute("INSERT OR IGNORE INTO presentations VALUES (?,?)",
                       (token, canonical(context)))
        return {"prepared": True, "token": token, "context": context}

    def confirm(self, token, confirmation):
        # Only the presentation owner may attest a real channel completion.
        # A worker's report content is never passed as confirmation.
        if (not isinstance(confirmation, dict)
                or set(confirmation) != {"outcome", "actor", "channel", "event_id", "evidence"}):
            raise ValueError("Actual channel completion or explicit handled event required")
        outcome = confirmation["outcome"]
        if outcome in NOT_DELIVERED:
            return {"recorded": False, "reason": "Report was not delivered"}
        if outcome not in CONFIRMED:
            raise ValueError("Unknown channel event; unread preserved")
        channel, disposition = CONFIRMED[outcome]
        if channel and confirmation["channel"] != channel:
            raise ValueError("Confirmation does not match its channel")
        source = {k: confirmation[k] for k in ("actor", "channel", "event_id", "evidence")}
        # Reuse the installed connector's exact evidence validator locally.
        self.tools.validate_source(source)
        with self.database() as db:
            row = db.execute("SELECT context FROM presentations WHERE token=?", (token,)).fetchone()
            if not row:
                raise ValueError("No prepared presentation for this delivery")
            request = dict(json.loads(row[0]), disposition=disposition, source=source)
            # One real narration/chat event may convey several exact reports.
            # Match the connector's per-workspace event scope, without a sweep.
            event_key = canonical([request["workspace_id"], source["actor"],
                                   source["channel"], source["event_id"]])
            existing = db.execute("SELECT token,request FROM events WHERE token=? OR event_key=?",
                                  (token, event_key)).fetchall()
            if any(r["token"] != token or r["request"] != canonical(request) for r in existing):
                raise ValueError("Delivery event or presentation reused with changed evidence")
            db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,NULL)",
                       (token, event_key, canonical(request)))
            # Commit BEFORE invoking the existing receipt tool. Uncertain calls
            # can only be retried from this identical prepared context/event.
        return self.retry(token)

    def retry(self, token):
        with self.database() as db:
            row = db.execute("SELECT request,result FROM events WHERE token=?", (token,)).fetchone()
            if not row:
                raise ValueError("No confirmed event; preparation is not delivery")
            request = json.loads(row["request"])
            require_prepared_guards(request)
            saved = json.loads(row["result"]) if row["result"] else None
            if saved and saved.get("status") == "applied":
                return cached_result(saved)
        value = self.tools.call("record_workspace_report_delivery", request)
        if not isinstance(value, dict) or not value.get("recorded"):
            raise ValueError("Delivery receipt result unavailable; reconcile identical event only")
        with self.database() as db:
            # A slower uncertain duplicate cannot downgrade a successful result.
            current = db.execute("SELECT result FROM events WHERE token=?", (token,)).fetchone()[0]
            if current and json.loads(current).get("status") == "applied":
                return cached_result(json.loads(current))
            db.execute("UPDATE events SET result=? WHERE token=?", (canonical(value), token))
        return value


class LocalTools:
    """The already-supported MCP-local Root dispatcher, with a fixed allowlist."""
    def __init__(self):
        sys.path.insert(0, "/home/mcp/code/vibe-dot-connector")
        import adapter
        import report_reconciliation
        self.adapter = adapter
        self.reconciliation = report_reconciliation

    def call(self, name, args):
        if name not in {"prepare_workspace_report_delivery", "record_workspace_report_delivery",
                        "list_workspace_unread_summaries"}:
            raise ValueError("Unsupported delivery integration tool")
        if name == "record_workspace_report_delivery":
            require_prepared_guards(args)
        response = self.adapter.Adapter(None).handle({
            "jsonrpc": "2.0", "id": "root-delivery", "method": "tools/call",
            "params": {"name": name, "arguments": args}})
        if "error" in response or response.get("result", {}).get("isError"):
            raise ValueError("Scoped connector tool unavailable; unread preserved")
        return json.loads(response["result"]["content"][0]["text"])

    def validate_source(self, source):
        self.reconciliation.evidence(source)

    def verify(self, workspace_id):
        # Real installed discovery, not a saved tool-schema snapshot. The
        # read-only upstream child is closed; no service or agent is started.
        upstream = self.adapter.Upstream()
        try:
            response = self.adapter.Adapter(upstream).handle({
                "jsonrpc": "2.0", "id": "delivery-discovery", "method": "tools/list"})
            tools = response["result"]["tools"]
        finally:
            upstream.close()
        state = self.reconciliation.capabilities(self.adapter, workspace_id)
        unread = self.call("list_workspace_unread_summaries", {"limit": 1})
        record = next(t for t in tools if t["name"] == "record_workspace_report_delivery")
        properties = record["inputSchema"]["properties"]
        return {"server_tools": sorted(t["name"] for t in tools),
                "server_tool_count": len(tools), "review_state": state,
                "unread_summary_read_succeeded": isinstance(unread.get("summaries"), list),
                "guarded_delivery_supported": GUARD_KEYS <= set(properties)
                    and any(t["name"] == "prepare_workspace_report_delivery" for t in tools),
                "delivery_callback_observed": False, "marks_sent": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "prepare", "confirm", "retry"))
    parser.add_argument("--workspace-id")
    parser.add_argument("--input", type=Path, help="Identity or genuine channel confirmation JSON")
    parser.add_argument("--token")
    parser.add_argument("--state", type=Path,
                        default=Path("/mnt/vk-storage/vk-report-delivery/outbox.sqlite"))
    args = parser.parse_args()
    tools = LocalTools()
    if args.action == "verify":
        if not args.workspace_id:
            parser.error("verify requires --workspace-id")
        value = tools.verify(args.workspace_id)
    else:
        if not os.path.ismount("/mnt/vk-storage") or not args.state.resolve().is_relative_to("/mnt/vk-storage"):
            parser.error("Delivery outbox requires mounted /mnt/vk-storage")
        caller = Caller(args.state, tools)
        if args.action == "prepare":
            if not args.input:
                parser.error("prepare requires --input")
            value = caller.prepare(json.loads(args.input.read_text()))
        elif args.action == "confirm":
            if not args.input or not args.token:
                parser.error("confirm requires --input and --token")
            value = caller.confirm(args.token, json.loads(args.input.read_text()))
        else:
            if not args.token:
                parser.error("retry requires --token")
            value = caller.retry(args.token)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
