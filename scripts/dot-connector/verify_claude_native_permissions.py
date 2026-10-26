#!/usr/bin/env python3
"""Pinned Claude CLI acceptance with a synthetic loopback API; never an account.

All environment/config/history belongs to this disposable fixture. This proves
native permission evaluation, not model judgement or a deployed Vibe release.
"""
import argparse
import http.server
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
import uuid

PIN = "2.1.77"
MODEL = "claude-sonnet-4-5-20250929"
HISTORY_MARKER = "synthetic-prior-context-7f4c"
HOOKS = {"PreToolUse": [{"matcher": "^(ExitPlanMode|AskUserQuestion)$",
                         "hookCallbackIds": ["tool_approval"]},
                         {"matcher": "^(Write|Edit|MultiEdit|NotebookEdit)$",
                          "hookCallbackIds": ["workspace_edit_boundary"]}]}


class MockAPI(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        if not self.path.startswith("/v1/messages"):
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size < 2_000_000:
            self.send_error(413)
            return
        body = json.loads(self.rfile.read(size))
        if self.path.startswith("/v1/messages/count_tokens"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"input_tokens":100}')
            return
        fixture = self.server.fixture
        fixture["requests"].append(body)
        results = [block for message in body.get("messages", [])
                   if isinstance(message.get("content"), list)
                   for block in message["content"] if block.get("type") == "tool_result"
                   and block.get("tool_use_id") == "toolu_fixture"]
        fixture["results"] = results
        content = ([{"type": "text", "text": "synthetic fixture complete"}]
                   if results or fixture.get("text_only") else [{
                       "type": "tool_use", "id": "toolu_fixture",
                       "name": fixture["tool"], "input": fixture["input"]}])
        stop = "tool_use" if content[0]["type"] == "tool_use" else "end_turn"
        message = {"id": "msg_fixture", "type": "message", "role": "assistant",
                   "model": MODEL, "content": [], "stop_reason": None,
                   "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 10}}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        events = [("message_start", {"type": "message_start", "message": message})]
        for index, block in enumerate(content):
            empty = dict(block, **({"input": {}} if block["type"] == "tool_use" else {"text": ""}))
            delta = ({"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
                     if block["type"] == "tool_use" else {"type": "text_delta", "text": block["text"]})
            events += [("content_block_start", {"type": "content_block_start", "index": index, "content_block": empty}),
                       ("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta}),
                       ("content_block_stop", {"type": "content_block_stop", "index": index})]
        events += [("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 10}}),
                   ("message_stop", {"type": "message_stop"})]
        for name, event in events:
            self.wfile.write(("event: " + name + "\ndata: " + json.dumps(event) + "\n\n").encode())
            self.wfile.flush()


def run_case(node, cli, root, mode, tool, tool_input, *, rules=None, extra=(),
             resume=None, text_only=False, approve=False, hook_error=False, owner_error=False):
    fixture = {"tool": tool, "input": tool_input, "requests": [], "results": [], "text_only": text_only}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockAPI)
    server.daemon_threads = True
    server.fixture = fixture
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # An allowlisted environment prevents real credentials, plugins, proxies or
    # user policy from leaking into the fixture. No external provider is used.
    env = {"HOME": str(root), "PATH": str(Path(node).parent) + ":/usr/bin:/bin",
           "CLAUDE_CONFIG_DIR": str(root / "config"),
           "ANTHROPIC_API_KEY": "synthetic-fixture-only",
           "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
           "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1"}
    args = [node, str(cli), "-p", "--verbose", "--input-format=stream-json",
            "--output-format=stream-json", "--permission-mode=" + mode,
            "--permission-prompt-tool=stdio", "--setting-sources", "",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--model", MODEL, "--settings", json.dumps({"permissions": rules or {}})]
    session = resume or str(uuid.uuid4())
    args += ["--resume" if resume else "--session-id", session, *extra]
    process = subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    messages = queue.Queue()
    errors = []

    def reader(stream, target):
        for line in stream:
            target(line)

    threading.Thread(target=reader, args=(process.stdout, messages.put), daemon=True).start()
    threading.Thread(target=reader, args=(process.stderr, errors.append), daemon=True).start()

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    requests = []
    decisions = {}

    def owner_decision(request):
        call_id = request.get("tool_use_id")
        assert call_id, "No uncorrelated owner request"
        signature = (request["tool_name"], request["input"])
        if call_id in decisions:
            assert decisions[call_id] == signature, "Changed invocation reused a call ID"
        else:
            decisions[call_id] = signature
            requests.append(request)
        return ({"behavior": "allow", "updatedInput": request["input"]} if approve
                else {"behavior": "deny", "message": "Synthetic owner denial", "interrupt": False})

    final = None
    initialized = False
    qualified_runtime = False
    try:
        send({"type": "control_request", "request_id": "fixture-init",
              "request": {"subtype": "initialize", "hooks": HOOKS}})
        # Unlike Vibe's former startup bypass, argv already imposes the mode.
        send({"type": "user", "message": {"role": "user", "content": HISTORY_MARKER if text_only else "Run the synthetic fixture action then finish."}})
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                message = json.loads(messages.get(timeout=0.25))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if message.get("type") == "control_response":
                response = message["response"]
                if response.get("request_id") == "fixture-init":
                    assert response["subtype"] == "success", response
                    initialized = True
            if message.get("type") == "system" and message.get("subtype") == "init":
                qualified_runtime = message.get("claude_code_version") == PIN
                fixture["runtime_version"] = message.get("claude_code_version")
                assert message["session_id"] == session
                assert message["permissionMode"] == mode
                fixture["effective_model"] = message["model"]
                if MODEL.startswith("claude-"):
                    assert message["model"] == MODEL
            if message.get("type") == "control_request":
                request = message["request"]
                if request["subtype"] == "hook_callback":
                    fixture.setdefault("hook_events", []).append(request["input"])
                    callback = request["callback_id"]
                    if callback == "workspace_edit_boundary":
                        if hook_error:
                            send({"type":"control_response", "response":{"subtype":"error", "request_id":message["request_id"], "error":"Synthetic hook unavailable"}})
                            continue
                        event = request["input"]
                        tool_input = event.get("tool_input", {})
                        raw = tool_input.get("notebook_path" if event.get("tool_name") == "NotebookEdit" else "file_path")
                        try:
                            path = Path(raw)
                            requested = path if path.is_absolute() else root / path
                            resolved = requested.resolve()
                            allow = (qualified_runtime and event.get("permission_mode") == "default" and resolved.is_relative_to(root)
                                     and not any(part.lower() in {".git", ".claude", ".codex", ".agents", ".aws"} for part in resolved.parts))
                        except (TypeError, OSError, RuntimeError):
                            allow = False
                        response = ({"hookSpecificOutput": {"hookEventName":"PreToolUse", "permissionDecision":"allow",
                                    "permissionDecisionReason":"Synthetic authorized workspace edit"}} if allow else {})
                    else:
                        assert callback == "tool_approval"
                        response = {"hookSpecificOutput": {"hookEventName":"PreToolUse", "permissionDecision":"ask"}}
                else:
                    assert request["subtype"] == "can_use_tool"
                    assert request["tool_name"] == tool
                    assert request.get("tool_use_id"), "No uncorrelated approvals"
                    fixture["native_permission_requests"] = fixture.get("native_permission_requests", 0) + 1
                    if owner_error:
                        send({"type":"control_response", "response":{"subtype":"error", "request_id":message["request_id"], "error":"Synthetic owner unavailable"}})
                        continue
                    response = owner_decision(request)
                send({"type": "control_response", "response": {"subtype": "success", "request_id": message["request_id"], "response": response}})
            if message.get("type") == "result":
                final = message
                break
        assert initialized and final and not final.get("is_error"), "Native CLI did not complete the bounded fixture"
        process.stdin.close()
        assert process.wait(timeout=8) == 0
        assert fixture["requests"], "No mock API request observed"
        return requests, fixture, session
    finally:
        if process.poll() is None:
            # Only this disposable subprocess and its own tool children.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        for stream in [process.stdin, process.stdout, process.stderr]:
            stream.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main():
    global MODEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--legacy-cli", type=Path)
    args = parser.parse_args()
    package = json.loads((args.cli.parent / "package.json").read_text())
    assert package["name"] == "@anthropic-ai/claude-code" and package["version"] == PIN
    cases = [
        ("default-read", "default", "Bash", {"command": "ls"}, {}, False, False),
        ("default-scoped-allow", "default", "Bash", {"command": "printf fixture"}, {"allow": ["Bash(printf:*)"]}, False, False),
        ("default-ask", "default", "Bash", {"command": "ls"}, {"ask": ["Bash(ls)"]}, True, True),
        ("default-deny", "default", "Bash", {"command": "ls"}, {"deny": ["Bash(ls)"]}, False, True),
        ("default-ask-beats-allow", "default", "Bash", {"command": "ls"}, {"allow": ["Bash(ls)"], "ask": ["Bash(ls)"]}, True, True),
        ("default-deny-beats-allow", "default", "Bash", {"command": "ls"}, {"allow": ["Bash(ls)"], "deny": ["Bash(ls)"]}, False, True),
        ("auto-question", "default", "AskUserQuestion", {"questions": [{"question": "Synthetic choice?", "header": "Fixture", "options": [{"label": "A", "description": "Fixture A"}, {"label": "B", "description": "Fixture B"}], "multiSelect": False}]}, {"allow": ["AskUserQuestion"]}, True, True),
        ("plan-exit", "plan", "ExitPlanMode", {}, {"allow": ["ExitPlanMode"]}, True, True),
        ("supervised-workspace-edit", "default", "Write", {"content": "fixture"}, {}, False, False),
        ("auto-edit", "default", "Write", {"content": "fixture"}, {}, False, False),
        ("auto-ask", "default", "Write", {"content": "fixture"}, {"ask": ["Write"]}, True, True),
        ("auto-deny", "default", "Write", {"content": "fixture"}, {"deny": ["Write"]}, False, True),
        ("plan-read", "plan", "Bash", {"command": "ls"}, {}, False, False),
        ("plan-edit", "plan", "Write", {"content": "fixture"}, {}, True, True),
    ]
    passed = 0
    for name, mode, tool, value, rules, asks, denied in cases:
        with tempfile.TemporaryDirectory(prefix="vk-native-policy-") as temp:
            root = Path(temp)
            if tool == "Write":
                value = dict(value, file_path=str(root / "fixture.txt"))
            requests, fixture, _ = run_case(args.node, args.cli, root, mode, tool, value, rules=rules)
            assert bool(requests) == asks, f"{name}: unexpected manual approval count {len(requests)}"
            assert len(requests) <= 1, f"{name}: duplicate approval"
            assert len(fixture["results"]) == 1, f"{name}: missing or duplicate result"
            assert bool(fixture["results"][0].get("is_error")) == denied, f"{name}: wrong native outcome"
            if tool == "Write":
                assert (root / "fixture.txt").exists() != denied, f"{name}: unexpected file side effect"
            print(f"PASS {name}", flush=True)
            passed += 1
    for name in ["outside", "symlink", ".git", ".claude", ".codex", ".agents", ".aws"]:
        with tempfile.TemporaryDirectory(prefix="vk-native-file-boundary-") as temp:
            parent = Path(temp)
            root = parent / "work space"
            root.mkdir()
            if name == "outside":
                target = parent / "new.txt"
                actual = target
            elif name == "symlink":
                external = parent / "external"
                external.mkdir()
                (root / "linked").symlink_to(external, target_is_directory=True)
                target = root / "linked/new.txt"
                actual = external / "new.txt"
            else:
                target = root / name / "config"
                target.parent.mkdir()
                actual = target
            requests, fixture, _ = run_case(args.node, args.cli, root, "default", "Write",
                                              {"file_path": str(target), "content": "fixture"})
            assert len(requests) == 1 and fixture["results"][0].get("is_error"), name
            assert not actual.exists(), name
            print("PASS file-boundary-" + name, flush=True)
            passed += 1
    with tempfile.TemporaryDirectory(prefix="vk-native-external-allow-") as temp:
        parent = Path(temp)
        root = parent / "workspace"
        root.mkdir()
        target = parent / "explicit.txt"
        rule = "Edit(/" + target.as_posix() + ")"
        requests, fixture, _ = run_case(args.node, args.cli, root, "default", "Write",
                                          {"file_path": str(target), "content": "fixture"}, rules={"allow": [rule]})
        assert not requests and target.read_text() == "fixture"
        print("PASS existing-explicit-external-allow", flush=True)
        passed += 1
    with tempfile.TemporaryDirectory(prefix="vk-native-boundary-deny-") as temp:
        root = Path(temp)
        target = root / ".codex/config.toml"
        target.parent.mkdir()
        requests, fixture, _ = run_case(args.node, args.cli, root, "default", "Write",
                                          {"file_path": str(target), "content": "fixture"}, rules={"deny": ["Write"]}, approve=True)
        assert not requests and fixture["results"][0].get("is_error") and not target.exists()
        print("PASS native-deny-removes-tool-before-owner-request", flush=True)
        passed += 1
    for outcome in ["ask", "deny"]:
        with tempfile.TemporaryDirectory(prefix="vk-native-scoped-rule-") as temp:
            root = Path(temp)
            target = root / "scoped-file.txt"
            rule = "Edit(/" + target.as_posix() + ")"
            requests, fixture, _ = run_case(args.node, args.cli, root, "default", "Write",
                                              {"file_path": str(target), "content": "fixture"},
                                              rules={outcome: [rule]}, approve=True)
            assert len(requests) <= 1, "Duplicate owner request for hook/native fallback"
            if outcome == "ask":
                assert len(requests) == 1 and target.read_text() == "fixture"
            else:
                assert fixture["results"][0].get("is_error") and not target.exists()
            print("PASS scoped-native-" + outcome + "-with-boundary-owner-allow", flush=True)
            passed += 1
    for owner_unavailable in [False, True]:
        with tempfile.TemporaryDirectory(prefix="vk-native-hook-failure-") as temp:
            root = Path(temp)
            target = root / "new.txt"
            requests, fixture, _ = run_case(args.node, args.cli, root, "default", "Write",
                                              {"file_path": str(target), "content": "fixture"},
                                              hook_error=True, owner_error=owner_unavailable)
            assert fixture.get("native_permission_requests") == 1
            assert not target.exists() and fixture["results"][0].get("is_error")
            print("PASS hook-failure-requires-owner-" + ("unavailable" if owner_unavailable else "denied"), flush=True)
            passed += 1
    with tempfile.TemporaryDirectory(prefix="vk-native-resume-") as temp:
        root = Path(temp)
        _, _, session = run_case(args.node, args.cli, root, "default", "Bash", {}, text_only=True)
        requests, fixture, resumed = run_case(args.node, args.cli, root, "default", "Write",
                                              {"file_path": str(root / "fixture.txt"), "content": "fixture"},
                                              resume=session, approve=True, rules={"ask": ["Write"]})
        assert resumed == session and len(requests) == 1
        assert HISTORY_MARKER in json.dumps(fixture["requests"][0]["messages"]), "Resume lost prior context"
        assert (root / "fixture.txt").read_text() == "fixture"
        print("PASS resume-context-and-owner-approval", flush=True)
        passed += 1
    if args.legacy_cli:
        legacy_package = json.loads((args.legacy_cli.parent / "package.json").read_text())
        assert legacy_package["name"] == "@anthropic-ai/claude-code" and legacy_package["version"] == "2.1.62"
        with tempfile.TemporaryDirectory(prefix="vk-native-legacy-fallback-") as temp:
            root = Path(temp)
            target = root / "new.txt"
            requests, fixture, _ = run_case(args.node, args.legacy_cli, root, "default", "Write",
                                              {"file_path": str(target), "content": "fixture"})
            assert fixture["runtime_version"] == "2.1.62" and len(requests) == 1 and not target.exists()
            print("PASS legacy-runtime-keeps-native-owner-fallback", flush=True)
            passed += 1
        for first_cli, next_cli, name in [(args.legacy_cli, args.cli, "upgrade"), (args.cli, args.legacy_cli, "rollback")]:
            with tempfile.TemporaryDirectory(prefix="vk-native-version-resume-") as temp:
                root = Path(temp)
                _, _, session = run_case(args.node, first_cli, root, "default", "Bash", {}, text_only=True)
                requests, fixture, resumed = run_case(args.node, next_cli, root, "default", "Write",
                                                       {"file_path": str(root / "new.txt"), "content": "fixture"},
                                                       resume=session, rules={"ask": ["Write"]}, approve=True)
                assert resumed == session and len(requests) == 1 and (root / "new.txt").exists()
                assert HISTORY_MARKER in json.dumps(fixture["requests"][0]["messages"])
                print("PASS legacy-history-" + name + "-retains-context-and-owner-ask", flush=True)
                passed += 1
        original_model = MODEL
        try:
            for alias in ["sonnet", "opus", "haiku", "opus[1m]"]:
                MODEL = alias
                models = []
                for cli in [args.legacy_cli, args.cli]:
                    with tempfile.TemporaryDirectory(prefix="vk-native-model-preservation-") as temp:
                        _, fixture, _ = run_case(args.node, cli, Path(temp), "default", "Bash", {}, text_only=True)
                        models.append((fixture["effective_model"], fixture["requests"][0]["model"]))
                assert models[0] == models[1], f"Runtime update silently changes selected alias {alias}: {models}"
                print("PASS selected-model-alias-preserved-" + alias, flush=True)
                passed += 1
        finally:
            MODEL = original_model
    print(f"Verified {passed} pinned native Claude fixtures; no provider account or deployment exercised.")


if __name__ == "__main__":
    main()
