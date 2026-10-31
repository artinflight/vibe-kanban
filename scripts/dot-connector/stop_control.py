"""Exact execution Stop. No workspace/process-shell/legacy Stop fallback."""
import json
import urllib.error

UUID = {"type": "string", "format": "uuid"}


def definition(name, description, properties, write=False):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties,
                            "required": list(properties), "additionalProperties": False},
            "annotations": {"readOnlyHint": not write, "destructiveHint": write,
                            "openWorldHint": False}}


IDENTITY = {"workspace_id": UUID, "session_id": UUID, "execution_id": UUID}
TOOLS = [definition("stop_agent_execution",
    "Stop only an explicitly selected running agent execution, for an owner request or "
    "CU-verified aggregate budget exhaustion. Requires exact workspace/session/execution IDs "
    "and one stable request_id UUID. Preserve it on retries; never resend an uncertain stop "
    "with a new ID. Does not stop a workspace, clear its queue, or enforce an account budget. "
    "CU must revoke scheduled leases and hold new admissions separately. Fails closed if "
    "the guarded backend capability is unavailable. stopped=true requires its durable receipt.",
    dict(IDENTITY, request_id=UUID, reason={"type": "string", "enum": ["user_request", "budget_exhausted"]}), True),
    definition("get_agent_execution_stop",
    "Read exact execution status, guarded stop capability and an optional matching stop receipt. "
    "Terminal database status alone does not prove a timed-out stop succeeded. Never stops anything.",
    dict(IDENTITY, request_id=UUID))]


def unwrap(value):
    if not isinstance(value, dict) or value.get("success") is not True or "data" not in value:
        raise ValueError("Invalid guarded stop response; no fallback is supported")
    return value["data"]


def identity(api, args, write=False):
    expected = set(IDENTITY) | {"request_id"} | ({"reason"} if write else set())
    if set(args) != expected:
        raise ValueError("Exact workspace/session/execution/request identity required")
    result = {k: api.valid_uuid(args[k]) for k in (*IDENTITY, "request_id")}
    if any(value == "00000000-0000-0000-0000-000000000000" for value in result.values()):
        raise ValueError("Non-nil UUIDs required")
    if write:
        if args["reason"] not in ("user_request", "budget_exhausted"):
            raise ValueError("Explicit stop reason required")
        result["reason"] = args["reason"]
    return result


def target(api, values):
    try:
        result = unwrap(api.http_get(f'/api/execution-processes/{values["execution_id"]}/stop-exact'))
    except urllib.error.HTTPError as error:
        if error.code in (404, 405):
            return None
        raise
    except json.JSONDecodeError:
        # Older Vibe serves the SPA HTML fallback for an unknown GET route.
        # There is no validated guarded capability and no write is permitted.
        return None
    if (not isinstance(result, dict) or result.get("version") != 1
            or any(result.get(k) != values[k] for k in IDENTITY)
            or result.get("status") not in ("ready", "not_running", "unsupported")
            or type(result.get("serialized_admission")) is not bool
            or not isinstance(result.get("expected_created_at"), str)
            or not result["expected_created_at"] or len(result["expected_created_at"]) > 64):
        raise ValueError("Stop target/capability mismatch; no stop sent")
    if result["status"] == "ready" and (result.get("execution_status") != "running"
            or result.get("run_reason") != "codingagent" or result.get("dropped") is not False
            or result["serialized_admission"] is not True):
        raise ValueError("Contradictory stop admission; no stop sent")
    return result


def receipt(api, values):
    value = unwrap(api.http_get(f'/api/execution-processes/{values["execution_id"]}/stop-requests?request_id={values["request_id"]}'))
    return None if value is None else validate_receipt(value, values)


def validate_receipt(value, values, expected_created_at=None):
    if not isinstance(value, dict) or any(value.get(k) != values[k] for k in (*IDENTITY, "request_id")):
        raise ValueError("Stop receipt identity mismatch; do not resend")
    if value.get("reason") not in ("user_request", "budget_exhausted") or (
            "reason" in values and value["reason"] != values["reason"]):
        raise ValueError("Stop request reason conflict; do not resend")
    if value.get("status") not in ("stopped", "not_running", "target_mismatch", "unknown"):
        raise ValueError("Invalid stop receipt; do not resend")
    expected = None if value["status"] == "unknown" else value["status"] == "stopped"
    if "stopped" not in value or value["stopped"] is not expected:
        raise ValueError("Contradictory stop receipt; do not resend")
    if not isinstance(value.get("expected_created_at"), str) or not 0 < len(value["expected_created_at"]) <= 64:
        raise ValueError("Invalid stop target creation identity")
    if expected_created_at is not None and value["expected_created_at"] != expected_created_at:
        # RFC3339 UTC may be serialized as Z or +00:00. Compare parsed instants.
        from datetime import datetime
        if datetime.fromisoformat(value["expected_created_at"]) != datetime.fromisoformat(expected_created_at):
            raise ValueError("Stop receipt target changed; do not resend")
    return {k: value[k] for k in (*IDENTITY, "request_id", "expected_created_at", "reason", "status", "stopped")}


def readback(api, args):
    values = identity(api, args)
    current = target(api, values)
    return api.result(dict(values, capability_available=current is not None,
                           target=current, receipt=receipt(api, values) if current is not None else None))


def stop(api, args):
    values = identity(api, args, write=True)
    current = target(api, values)
    if current is None:
        return api.result(dict(values, status="unsupported", stopped=False,
            message="Guarded backend stop capability is absent. No legacy/workspace Stop was called."))
    previous = receipt(api, values)
    if previous is not None:
        return api.result(previous)
    if current["status"] != "ready":
        return api.result(dict(values, status=current["status"], stopped=False,
                               message="No stop sent; existing work/queue unchanged."))
    payload = dict(values, expected_created_at=current["expected_created_at"])
    try:
        value = api.post_fixed(f'/api/execution-processes/{values["execution_id"]}/stop-exact', payload)
        return api.result(validate_receipt(value, values, current["expected_created_at"]))
    except Exception:
        # A failure can follow delivery. Reconcile reads only, never retry POST.
        try:
            previous = receipt(api, values)
            if previous is not None:
                return api.result(validate_receipt(previous, values, current["expected_created_at"]))
        except Exception:
            pass
        return api.result(dict(values, status="unknown", stopped=None,
            message="Stop outcome uncertain. Retain request_id and inspect readback; do not resend with another ID."))


HANDLERS = {"stop_agent_execution": stop, "get_agent_execution_stop": readback}
