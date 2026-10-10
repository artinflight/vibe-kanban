"""Read-only discovery/readiness for the already installed explicit clear tools.

There is deliberately no mark-read command. Run this before client metadata
refresh; successful stdio discovery does not prove the client catalog refreshed.
"""
import hashlib
import json
from pathlib import Path
import sys


def verify(client):
    listing = client.handle({"jsonrpc": "2.0", "id": "explicit-discovery", "method": "tools/list"})
    tools = listing["result"]["tools"]
    by_name = {tool["name"]: tool for tool in tools}
    mark = by_name["mark_workspace_read"]
    schema = mark["inputSchema"]
    annotations = mark["annotations"]
    if (schema.get("required") != ["workspace_id"]
            or set(schema.get("properties", {})) != {"workspace_id"}
            or schema.get("additionalProperties") is not False
            or schema["properties"]["workspace_id"].get("format") != "uuid"
            or annotations.get("readOnlyHint") is not False
            or annotations.get("openWorldHint") is not False
            or by_name["list_workspace_unread_summaries"]["annotations"].get("readOnlyHint") is not True):
        raise ValueError("Explicit clear contract differs; review before publication")
    response = client.handle({"jsonrpc": "2.0", "id": "explicit-readiness", "method": "tools/call",
                              "params": {"name": "list_workspace_unread_summaries", "arguments": {"limit": 1}}})
    result = response["result"]
    if result.get("isError"):
        raise ValueError("Unread read unavailable; client readiness unknown")
    value = json.loads(result["content"][0]["text"])
    if (not isinstance(value.get("summaries"), list) or not value.get("observed_at")
            or any(type(row.get("has_unseen_turns")) is not bool for row in value["summaries"])):
        raise ValueError("Unread read unavailable; client readiness unknown")
    return {"server_tool_names": sorted(by_name), "server_tool_count": len(tools),
            "explicit_mark_metadata": mark, "unread_read_succeeded": True,
            "summary_observed_at": value["observed_at"],
            "mark_requests": 0, "client_refresh_verified": False}


def main():
    # Fixed installed dispatcher: no caller-provided URLs, keys or permissions.
    sys.path.insert(0, "/home/mcp/code/vibe-dot-connector")
    import adapter
    upstream = adapter.Upstream()
    try:
        value = verify(adapter.Adapter(upstream))
        value["installed_adapter_sha256"] = hashlib.sha256(
            Path("/home/mcp/code/vibe-dot-connector/adapter.py").read_bytes()).hexdigest()
        print(json.dumps(value, indent=2))
    finally:
        upstream.close()


if __name__ == "__main__":
    main()
