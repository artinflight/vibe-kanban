"""Read-only candidate validation against the current connector baseline."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

source=Path("/home/mcp/code/vibe-dot-connector")
candidate=Path(sys.argv[1])
sys.path.extend([str(source),str(Path(__file__).parent)])
import connector
sys.modules["sidechat_connector"]=connector
module=types.ModuleType("adapter")
sys.modules["adapter"]=module
raw=(source/"adapter.py").read_text()
changed=(candidate/"adapter.py").read_text()
before={node.name:ast.dump(node) for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef)}
after={node.name:ast.dump(node) for node in ast.parse(changed).body if isinstance(node,ast.FunctionDef)}
assert before==after,"Existing connector functions changed"
exec(compile(changed,"candidate-adapter.py","exec"),module.__dict__)
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in ("test_capacity_queue","test_recommend","test_status_reads"))
run=unittest.TextTestRunner(verbosity=2).run(suite)
if not run.wasSuccessful(): raise SystemExit(1)
upstream=Mock()
upstream.request.return_value={"result":{"tools":[]}}
facade=module.Adapter(upstream)
names={tool["name"] for tool in facade.handle({"jsonrpc":"2.0","id":1,"method":"tools/list"})["result"]["tools"]}
assert connector.NAMES <= names
assert "list_approval_notifications" in names
with patch.object(connector,"call",return_value={"verified":"fixture"}) as call:
    facade.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"read_sidechat_thread","arguments":{"thread":"fixture"}}})
    call.assert_called_once()
approval={"jsonrpc":"2.0","id":3,"result":{"events":[{"name":"vk.approval.pending"},{"name":"vk.approval.changed"}]}}
with patch.object(module.connector_events,"handle",return_value=approval):
    names=[x["name"] for x in facade.handle({"jsonrpc":"2.0","id":3,"method":"events/list"})["result"]["events"]]
    assert names==["vk.approval.pending","vk.approval.changed","vk.sidechat.owner_message.created"]
for name in ("shell","delete_workspace","stop_execution","generic_http"):
    try: facade.handle({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":name,"arguments":{}}})
    except ValueError: pass
    else: raise AssertionError("Forbidden tool exposed")
print(json.dumps({"existing_regressions_passed":run.testsRun,"discovery_dispatch_approval_preservation":"passed",
 "baseline_sha256":hashlib.sha256(raw.encode()).hexdigest(),"candidate_sha256":hashlib.sha256(changed.encode()).hexdigest(),"live_calls":0}))
