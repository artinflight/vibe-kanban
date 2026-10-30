"""Workspace read state via two fixed, loopback-only Vibe endpoints."""
import datetime
import json
import re
import urllib.request
import uuid


def workspace_id(value):
    # Require canonical hyphenated UUIDs; no paths, queries, URLs or URNs.
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
    ):
        raise ValueError("workspace_id must be a hyphenated UUID")
    return str(uuid.UUID(value))


def request(api, wid=None):
    """No caller-controlled URL, method, headers or payload; never retry."""
    if wid is None:
        path, method, body = "/api/workspaces/summaries", "POST", b'{"archived":false}'
    else:
        path, method, body = "/api/workspaces/" + workspace_id(wid) + "/seen", "PUT", None

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    req = urllib.request.Request(
        api.BASE + path, data=body, method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
        raw = response.read(api.MAX_BYTES + 1)
    if len(raw) > api.MAX_BYTES:
        raise ValueError("Workspace response exceeds limit; inspect state before retrying")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError("Workspace request failed; inspect state before retrying")
    return data.get("data")


def summaries(api, args):
    if set(args) - {"limit", "offset", "unread_only"}:
        raise ValueError("Unknown workspace summary argument")
    limit, offset = args.get("limit", 50), args.get("offset", 0)
    unread_only = args.get("unread_only", False)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("offset must be 0..10000")
    if type(unread_only) is not bool:
        raise ValueError("unread_only must be boolean")
    data = request(api)
    rows = data.get("summaries") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Workspace summaries unavailable; unread state unknown")
    states = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("has_unseen_turns")) is not bool:
            raise ValueError("Invalid workspace summary; unread state unknown")
        states.append({"workspace_id": workspace_id(row.get("workspace_id")),
                       "has_unseen_turns": row["has_unseen_turns"]})
    total_unread = sum(row["has_unseen_turns"] for row in states)
    total_workspaces = len(states)
    if unread_only:
        states = [row for row in states if row["has_unseen_turns"]]
    states.sort(key=lambda row: row["workspace_id"])
    return {
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "archived": False, "summaries": states[offset:offset + limit],
        "total": len(states), "total_workspaces": total_workspaces, "total_unread": total_unread,
        "next_offset": offset + limit if offset + limit < len(states) else None,
        "note": "Vibe has_unseen_turns, not inferred from execution status. Fresh snapshot per call; pagination may shift. Reads never mark seen.",
    }


def mark_read(api, args):
    if set(args) != {"workspace_id"}:
        raise ValueError("Exactly one workspace_id required")
    wid = workspace_id(args["workspace_id"])
    request(api, wid)
    return {
        "workspace_id": wid, "marked_read": True,
        "note": "Vibe accepted marking this workspace's existing turns seen. New turns can make it unread again; refresh summaries. No other workspace was requested.",
    }


TOOLS = [
    {
        "name": "list_workspace_unread_summaries",
        "description": "Read actual has_unseen_turns for non-archived Vibe workspaces. Does not mark anything read or infer unread state from agent status. UUIDs can be matched with list_workspaces. Bounded pages use a fresh snapshot; unread_only filters to unread workspaces.",
        "inputSchema": {"type": "object", "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
            "offset": {"type": "integer", "minimum": 0, "maximum": 10000, "default": 0},
            "unread_only": {"type": "boolean", "default": False},
        }, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "mark_workspace_read",
        "description": "Only call when the user requests marking this individual workspace read. Marks its existing coding-agent turns seen using Vibe's normal per-workspace semantics; later turns may become unread. Changes read state, does not stop an agent or acknowledge task completion. Requires one hyphenated workspace UUID; no bulk or per-turn action.",
        "inputSchema": {"type": "object", "properties": {
            "workspace_id": {"type": "string", "format": "uuid", "pattern": "^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$"},
        }, "required": ["workspace_id"], "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
]
