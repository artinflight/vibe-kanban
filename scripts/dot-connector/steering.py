"""Explicit Codex steering; fixed URLs, identity fences, one POST, no fallback."""
import hashlib
import json

STATUSES = frozenset(("steered", "not_running", "not_ready", "unsupported_executor",
                      "target_mismatch", "scheduled_work", "blocked", "unknown"))


def tool(name, description, properties, write=False):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties,
                            "required": list(properties), "additionalProperties": False},
            "annotations": {"readOnlyHint": not write, "destructiveHint": False,
                            "openWorldHint": write}}


UUID = {"type": "string", "format": "uuid"}
TOOLS = [tool("steer_session_prompt",
              "Only call for an explicit user correction to the selected running CODEX execution. "
              "Provide its exact session_id/execution_id and a stable new request_id UUID. "
              "Retain request_id for reconciliation/retries; never retry an uncertain send with a new ID. "
              "Steers the current native turn without starting, stopping, queueing or changing settings. "
              "An existing queued follow-up is preserved. Only status=steered and delivered=true confirms delivery.",
              {"session_id": UUID, "execution_id": UUID, "request_id": UUID,
               "prompt": {"type": "string", "minLength": 1, "maxLength": 60000}}, True),
         tool("get_session_steering_receipt",
              "Read an exact steering request receipt; null/unknown does not prove non-delivery. "
              "Never resend an uncertain correction using another request_id.",
              {"session_id": UUID, "request_id": UUID})]


def unwrap(value):
    if not isinstance(value, dict) or value.get("success") is not True or "data" not in value:
        raise ValueError("Steering API unavailable or invalid; no fallback is supported")
    return value["data"]


def validate_receipt(value, sid, rid, eid=None, digest=None, binding=None):
    if not isinstance(value, dict) or value.get("session_id") != sid or value.get("request_id") != rid:
        raise ValueError("Steering receipt identity mismatch; do not resend")
    if value.get("status") not in STATUSES:
        raise ValueError("Invalid steering receipt; do not resend")
    expected = None if value["status"] == "unknown" else value["status"] == "steered"
    if "delivered" not in value or value["delivered"] is not expected:
        raise ValueError("Contradictory steering receipt; do not resend")
    if eid is not None and (value.get("execution_id") != eid or value.get("message_sha256") != digest):
        raise ValueError("request_id conflicts with another correction; no request sent")
    if not all(isinstance(value.get(k), str) and 0 < len(value[k]) <= 256
               for k in ("thread_id", "turn_id")):
        raise ValueError("Invalid steering target receipt; do not resend")
    if binding is not None and any(value[k] != binding[k] for k in ("thread_id", "turn_id")):
        raise ValueError("Steering target changed; do not resend")
    # Return only bounded admission metadata; never tool logs/configs/prompts.
    return {k: value[k] for k in ("session_id", "request_id", "execution_id",
                                 "thread_id", "turn_id", "status", "delivered", "message_sha256")}


def result(api, value):
    reply = api.result(value)
    reply["isError"] = value is not None and value.get("status") != "steered"
    return reply


def get_receipt(api, args):
    if set(args) != {"session_id", "request_id"}:
        raise ValueError("Exact session_id and request_id required")
    sid, rid = (api.valid_uuid(args[k]) for k in ("session_id", "request_id"))
    value = unwrap(api.http_get(f"/api/sessions/{sid}/steer/{rid}"))
    return api.result(None if value is None else validate_receipt(value, sid, rid))


def steer(api, args):
    if set(args) != {"session_id", "execution_id", "request_id", "prompt"}:
        raise ValueError("Exact session_id, execution_id, request_id and prompt required")
    sid, eid, rid = (api.valid_uuid(args[k]) for k in ("session_id", "execution_id", "request_id"))
    prompt = args["prompt"]
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 60000:
        raise ValueError("Explicit bounded correction required; no request sent")
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    path = f"/api/sessions/{sid}/steer"
    # Reconcile before inspecting a potentially completed/replaced native turn.
    previous = unwrap(api.http_get(f"{path}/{rid}"))
    if previous is not None:
        return result(api, validate_receipt(previous, sid, rid, eid, digest))
    target = unwrap(api.http_get(f"{path}/target?execution_id={eid}"))
    if not isinstance(target, dict) or target.get("session_id") != sid or target.get("execution_id") != eid:
        raise ValueError("Steering target identity mismatch; no request sent")
    if target.get("status") != "ready":
        if target.get("status") not in STATUSES - {"steered", "unknown"}:
            raise ValueError("Unrecognized steering admission; no request sent")
        return result(api, {"session_id": sid, "execution_id": eid, "request_id": rid,
                            "status": target["status"], "delivered": False,
                            "message": "No correction sent; no new execution or queued message created."})
    if not all(isinstance(target.get(k), str) and 0 < len(target[k]) <= 256
               for k in ("thread_id", "turn_id")):
        raise ValueError("Invalid active-turn binding; no request sent")
    payload = {"request_id": rid, "execution_id": eid, "message": prompt,
               "thread_id": target["thread_id"], "turn_id": target["turn_id"]}
    try:
        value = api.post_fixed(path, payload)  # exactly one attempt; never /queue or /follow-up
        return result(api, validate_receipt(value, sid, rid, eid, digest, target))
    except Exception:
        # A lost HTTP response/native error can follow delivery. Only a matching
        # durable receipt can resolve it, and this reconciliation is read-only.
        try:
            value = unwrap(api.http_get(f"{path}/{rid}"))
            if value is not None:
                return result(api, validate_receipt(value, sid, rid, eid, digest, target))
        except Exception:
            pass
        return result(api, {"session_id": sid, "execution_id": eid, "request_id": rid,
                            "status": "unknown", "delivered": None,
                            "message": "Delivery is uncertain. Inspect this request receipt; do not resend with a new request_id."})


HANDLERS = {"steer_session_prompt": steer, "get_session_steering_receipt": get_receipt}
