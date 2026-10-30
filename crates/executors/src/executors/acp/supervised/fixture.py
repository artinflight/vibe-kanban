"""Synthetic ACP peer. No imports for networking, credentials or user projects."""
import json
import sys

scenario, trace_path = sys.argv[1:]
prompt_id = None
authenticated = False

def send(value):
    print(json.dumps({"jsonrpc": "2.0", **value}), flush=True)

def result(request, value):
    send({"id": request["id"], "result": value})

def error(request):
    send({"id": request["id"], "error": {"code": -32603, "message": "synthetic failure"}})

for line in sys.stdin:
    request = json.loads(line)
    with open(trace_path, "a", encoding="utf-8") as trace:
        trace.write(json.dumps(request) + "\n")
    method = request.get("method")
    if method == "initialize":
        if scenario == "malformed":
            print("invalid JSON", flush=True)
            break
        if scenario == "init-error":
            error(request)
            continue
        result(request, {"protocolVersion": 999 if scenario == "wrong-version" else 1,
                         "agentCapabilities": {"loadSession": scenario != "no-load"}, "authMethods": ([{"id": "oauth-personal", "name": "Personal", **({"type": "agent"} if scenario == "personal-agent" else {"type": "terminal"} if scenario == "personal-terminal" else {"type": "unsupported"} if scenario == "personal-unsupported" else {})}] if scenario.startswith("personal-") and scenario != "personal-missing" else [])})
    elif method == "authenticate":
        if request.get("params", {}).get("methodId") != "oauth-personal":
            error(request)
            continue
        if scenario == "personal-error":
            error(request)
            continue
        if scenario == "personal-eof":
            break
        if scenario == "personal-timeout":
            continue
        authenticated = True
        result(request, {})
        with open(trace_path, "a", encoding="utf-8") as trace:
            trace.write(json.dumps({"auth_ack": True}) + "\n")
    elif method in ("session/new", "session/load"):
        if scenario.startswith("personal-") and not authenticated:
            error(request)
            continue
        if scenario == "auth":
            send({"id": request["id"], "error": {"code": -32000, "message": "Authentication required"}})
            continue
        response = {"sessionId": "synthetic-1"} if method == "session/new" else {}
        if scenario != "no-models":
            response["models"] = {"currentModelId": "fixture-model", "availableModels": [{"modelId": "fixture-model", "name": "Fixture model"}]}
        result(request, response)
    elif method == "session/set_model":
        if scenario == "model-error":
            error(request)
        else:
            result(request, {})
    elif method == "session/prompt":
        prompt_id = request["id"]
        if scenario == "wait":
            continue
        if scenario == "prompt-error":
            error(request)
            continue
        if scenario == "approval":
            send({"id": 900, "method": "session/request_permission", "params": {
                "sessionId": "synthetic-1", "toolCall": {"toolCallId": "tool-1", "title": "synthetic tool"},
                "options": [{"optionId": "allow-once", "name": "Allow", "kind": "allow_once"},
                            {"optionId": "reject-once", "name": "Deny", "kind": "reject_once"}]}})
            continue
        send({"method": "session/update", "params": {"sessionId": "synthetic-1", "update": {
            "sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "fixture-ok"}}}})
        result(request, {"stopReason": "cancelled" if scenario == "cancelled" else "end_turn"})
    elif request.get("id") == 900:
        assert request["result"]["outcome"]["optionId"] == "reject-once", request
        send({"id": prompt_id, "result": {"stopReason": "end_turn"}})
    elif method == "session/cancel":
        if scenario == "wait":
            send({"id": prompt_id, "result": {"stopReason": "cancelled"}})
    else:
        raise AssertionError("Unexpected method: " + str(method))
