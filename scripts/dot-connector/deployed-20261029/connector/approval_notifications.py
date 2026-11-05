"""Bounded, genuinely read-only view of the notification ledger, not VK DB."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

STATES = frozenset(("pending", "approved", "denied", "cancelled", "answered",
                    "timed_out", "deadline_elapsed", "no_longer_pending"))
TOOLS = [{"name": "list_approval_notifications", "description":
          "Read retained VK approval notifications and observed outcomes across agents. "
          "Does not acknowledge, approve, reject or consume requests. Returns sanitized "
          "tool/target IDs only; exact action review stays in VK. Unknown disappearance "
          "and elapsed deadlines are not owner rejection or confirmed timeout. "
          "Disconnected watcher data may be stale; no guaranteed replay for requests "
          "created and resolved entirely during an upstream outage.",
          "inputSchema": {"type": "object", "properties": {
              "state": {"type": "string", "enum": ["pending", "outcomes", "all"],
                        "default": "pending"},
              "after": {"type": "integer", "minimum": 0, "maximum": 9223372036854775807},
              "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}},
              "additionalProperties": False},
          "annotations": {"readOnlyHint": True, "destructiveHint": False,
                          "openWorldHint": False}}]


def clean_summary(raw):
    if len(raw.encode()) > 8192:
        raise ValueError("Notification summary exceeds bound")
    value = json.loads(raw)
    clean = {key: str(uuid.UUID(value[key])) for key in ("approval_id", "execution_id")}
    tool = value.get("tool", "")
    clean["tool"] = tool if isinstance(tool, str) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,120}", tool) else "review_in_vk"
    clean["targets"] = {}
    targets = value.get("targets", {})
    if not isinstance(targets, dict):
        raise ValueError("Damaged notification targets")
    for key in ("session_id", "workspace_id", "execution_id", "issue_id", "project_id"):
        if key in targets:
            clean["targets"][key] = str(uuid.UUID(targets[key]))
    repo = targets.get("repo_full_name")
    if isinstance(repo, str) and len(repo) <= 250 and re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        clean["targets"]["repo_full_name"] = repo
    number = targets.get("pr_number")
    if type(number) is int and 0 < number <= 9223372036854775807:
        clean["targets"]["pr_number"] = number
    clean["is_question"] = bool(value.get("is_question"))
    for key in ("created_at", "timeout_at"):
        stamp = value[key]
        if not isinstance(stamp, str) or len(stamp) > 64:
            raise ValueError("Damaged notification timestamp")
        clean[key] = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).isoformat()
    return clean


def listing(args):
    if not isinstance(args, dict) or set(args) - {"state", "after", "limit"}:
        raise ValueError("Unknown notification argument")
    state, after, limit = args.get("state", "pending"), args.get("after", 0), args.get("limit", 50)
    if state not in ("pending", "outcomes", "all") or type(after) is not int or not 0 <= after <= 9223372036854775807 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid notification pagination/filter")
    path = os.environ.get("VK_APPROVAL_STATE")
    if not path or not os.environ.get("VK_APPROVAL_PRINCIPAL"):
        raise ValueError("Approval notification integration is unconfigured")
    # No directory/file creation, Store constructor, schema migration, chmod,
    # tick, delivery, receipt or state update. Existing WAL remains visible.
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        # Events are append-only. Requests use INSERT OR REPLACE, whose rowid
        # can be reused, so a request-row cursor would skip an outcome update.
        where = {"pending": "e.name='vk.approval.pending' AND r.state='pending'",
                 "outcomes": "e.name='vk.approval.changed'", "all": "1=1"}[state]
        rows = db.execute(f"SELECT e.rowid,e.id,e.name,e.body,r.state AS current_state FROM events e LEFT JOIN requests r ON r.id=json_extract(e.body,'$.data.approval_id') WHERE e.rowid>? AND ({where} OR r.id IS NULL) ORDER BY e.rowid LIMIT ?", (after, limit + 1)).fetchall()
        notifications = []
        for row in rows[:limit]:
            if len(row["body"].encode()) > 16384:
                raise ValueError("Notification event exceeds bound")
            event = json.loads(row["body"])
            data = event["data"]
            if data["state"] not in STATES or row["current_state"] not in STATES:
                raise ValueError("Unknown recorded approval state")
            summary = clean_summary(json.dumps(data))
            event_id = "evt_" + hashlib.sha256((summary["approval_id"] + ":" + data["state"]).encode()).hexdigest()
            name = "vk.approval.pending" if data["state"] == "pending" else "vk.approval.changed"
            if event_id != row["id"] or event_id != event["eventId"] or name != row["name"] or name != event["name"]:
                raise ValueError("Notification identity mismatch")
            if not isinstance(event["timestamp"], str) or len(event["timestamp"]) > 64:
                raise ValueError("Damaged event timestamp")
            dt.datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            summary.update(state=data["state"], current_state=row["current_state"],
                           observed_at=event["timestamp"], event_id=event_id, event_name=name)
            notifications.append(summary)
        health = {}
        for row in db.execute("SELECT key,value FROM health WHERE key IN ('stream','last_snapshot','started_at','last_error','owner_workspace')"):
            if len(row["value"].encode()) > 256:
                raise ValueError("Damaged watcher health")
            value = json.loads(row["value"])
            if row["key"] == "stream" and value not in ("connected", "disconnected"):
                value = "unknown"
            elif row["key"] == "last_error":
                value = "watcher_operation_failed" if value else None
            elif row["key"] == "owner_workspace":
                value = str(uuid.UUID(value))
            elif row["key"] != "stream":
                if not isinstance(value, str) or len(value) > 64:
                    raise ValueError("Damaged watcher health")
                dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            health[row["key"]] = value
        active = db.execute("SELECT count(*) FROM subscriptions WHERE active=1 AND (expires IS NULL OR expires>?)", (time.time(),)).fetchone()[0]
        count = db.execute("SELECT count(*) FROM requests WHERE state='pending'").fetchone()[0]
        return {"notifications": notifications, "pending_count": count,
                "next_after": rows[limit - 1]["rowid"] if len(rows) > limit else None,
                "last_returned_after": rows[min(limit, len(rows)) - 1]["rowid"] if rows else after,
                "observation_time": dt.datetime.now(dt.timezone.utc).isoformat(),
                "watcher": health, "active_subscriptions": active,
                "delivery_verified": False,
                "coverage": "Retained watcher observations; upstream has no durable outage replay. Querying is not delivery or acknowledgement."}
    finally:
        db.close()
