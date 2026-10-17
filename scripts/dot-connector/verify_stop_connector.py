"""Check the stop overlay against installed source; all writes stay mocked."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from prepare_stop_connector import patched
import stop_control


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    raw = (args.source / "adapter.py").read_text()
    candidate = patched(raw)
    def functions(source):
        return {node.name: ast.dump(node) for node in ast.parse(source).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert functions(raw) == functions(candidate), "Existing policy/read/write functions changed"
    sys.path.append(str(args.source))
    module = types.ModuleType("adapter")
    sys.modules["adapter"] = module
    exec(compile(candidate, "isolated-stop-adapter.py", "exec"), module.__dict__)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name)
        for name in ("test_capacity_queue", "test_recommend", "test_status_reads"))
    tests = unittest.TextTestRunner(verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise SystemExit(1)
    upstream = Mock()
    upstream.request.return_value = {"result": {"tools": []}}
    facade = module.Adapter(upstream)
    tools = facade.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert set(stop_control.HANDLERS) <= names
    assert module.sidechat_connector.NAMES <= names
    for name in stop_control.HANDLERS:
        mock = Mock(return_value=module.result({"fixture": True}))
        with patch.dict(stop_control.HANDLERS, {name: mock}):
            facade.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": name, "arguments": {"fixture": "isolated"}}})
        mock.assert_called_once_with(module, {"fixture": "isolated"})
    for name in ("stop_execution", "stop_workspace", "shell", "delete_workspace", "generic_http"):
        try:
            facade.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name}})
        except ValueError:
            pass
        else:
            raise AssertionError("Broad/unsupported control exposed")
    print(json.dumps({"existing_regressions_passed": tests.testsRun,
        "stop_discovery_dispatch": "passed", "sidechat_preserved": True,
        "broad_stop_shell_admin_denied": True, "live_writes": 0,
        "baseline_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
