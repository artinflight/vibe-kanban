"""Test the prepared patch against a read-only live-source snapshot. No live calls."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from prepare_connector import patched
import steering


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    raw = (args.source / "adapter.py").read_bytes()
    candidate = patched(raw.decode())
    before = {node.name: ast.dump(node) for node in ast.parse(raw).body
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    after = {node.name: ast.dump(node) for node in ast.parse(candidate).body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert before == after, "Existing connector functions changed"
    sys.path.append(str(args.source))
    module = types.ModuleType("adapter")
    sys.modules["adapter"] = module
    exec(compile(candidate, "isolated-candidate-adapter.py", "exec"), module.__dict__)
    # The complete current capacity-policy tests execute against the candidate,
    # not the live adapter. Network/process interactions stay mocked.
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name)
                               for name in ("test_capacity_queue", "test_recommend"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    upstream = Mock()
    upstream.request.return_value = {"result": {"tools": [{"name":"run_session_prompt","description":"Existing follow-up tool","inputSchema":{"type":"object"}}]}}
    adapter = module.Adapter(upstream)
    tools = adapter.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert set(steering.HANDLERS) <= names
    followup = next(tool for tool in tools["result"]["tools"] if tool["name"] == "run_session_prompt")
    assert "steer_session_prompt" in followup["description"]
    mock = Mock(return_value=module.result({"status": "fixture"}))
    with patch.dict(steering.HANDLERS, {"steer_session_prompt": mock}):
        adapter.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "steer_session_prompt", "arguments": {"fixture": True}}})
    mock.assert_called_once_with(module, {"fixture": True})
    for name in ("shell", "stop_execution", "delete_workspace", "generic_http"):
        try:
            adapter.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name}})
        except ValueError:
            pass
        else:
            raise AssertionError("Unsupported tool was exposed")
    print(json.dumps({"baseline_sha256": hashlib.sha256(raw).hexdigest(),
                      "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                      "existing_regressions_passed": result.testsRun,
                      "new_discovery_dispatch_and_denied_tools": "passed",
                      "live_calls": 0, "live_files_modified": 0}))


if __name__ == "__main__":
    main()
