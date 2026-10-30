"""MCP Events on the existing authenticated single-owner tunnel only."""
import json
import os
from pathlib import Path
import subprocess

VERSION = "2026-07-28"
METHODS = frozenset(("events/list", "events/subscribe", "events/unsubscribe"))


def configured():
    return bool(os.environ.get("VK_APPROVAL_STATE") and
                os.environ.get("VK_APPROVAL_PRINCIPAL"))


def handle(message):
    method = message.get("method")
    if method == "server/discover":
        capabilities = {"tools": {}}
        if configured():
            capabilities["events"] = {}
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": {
            "resultType": "complete", "supportedVersions": [VERSION],
            "capabilities": capabilities}}
    if method not in METHODS:
        return None
    error = {"code": -32015, "message": "Approval events are unconfigured"}
    if configured():
        params = message.get("params", {})
        if not isinstance(params, dict) or len(json.dumps(params).encode()) > 16384:
            error = {"code": -32602, "message": "Invalid or oversized event parameters"}
        else:
            # Configuration is the authenticated single-owner binding. Caller
            # _meta never supplies an account or an executable/path/environment.
            env = {k: os.environ[k] for k in
                   ("PATH", "LANG", "VK_APPROVAL_STATE", "VK_APPROVAL_PRINCIPAL")
                   if k in os.environ}
            try:
                run = subprocess.run([
                    "/usr/bin/python3", "-B",
                    str(Path(__file__).with_name("approval_event_store.py"))],
                    input=json.dumps({"op": "rpc", "method": method,
                                      "params": params}) + "\n",
                    capture_output=True, text=True, timeout=30, env=env)
                if run.returncode or len(run.stdout.encode()) > 262144:
                    raise ValueError("Event engine unavailable")
                reply = json.loads(run.stdout)
                if not reply.get("ok"):
                    raise ValueError("Event operation rejected")
                return {"jsonrpc": "2.0", "id": message.get("id"),
                        "result": reply["result"]}
            except Exception:
                error = {"code": -32015,
                         "message": "Approval event operation failed",
                         "data": {"reason": "verification_or_validation_failed"}}
    return {"jsonrpc": "2.0", "id": message.get("id"), "error": error}
