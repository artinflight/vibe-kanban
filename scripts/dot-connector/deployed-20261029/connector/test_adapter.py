import unittest
from unittest.mock import patch
import adapter
class Fake:
 def __init__(self): self.calls=[]
 def request(self,m):
  self.calls.append(m)
  return {"jsonrpc":"2.0","id":m.get("id"),"result":{"tools":[{"name":x,"inputSchema":{"type":"object"}} for x in ["list_sessions","start_workspace","delete_workspace","stop_execution","shell","update_setup_script"]]}}
class Tests(unittest.TestCase):
 def setUp(self): self.up=Fake(); self.a=adapter.Adapter(self.up)
 def call(self,n,args=None): return self.a.handle({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":n,"arguments":args or {}}})
 def test_discovery_filter(self):
  r=self.a.handle({"jsonrpc":"2.0","id":1,"method":"tools/list"})
  self.assertEqual({x["name"] for x in r["result"]["tools"]},{"list_sessions","start_workspace","get_agent_replies","list_session_executions","get_latest_agent_reply"})
 def test_optional_list_metadata(self):
  for params in ({"_meta":{}},{"cursor":None},{"cursor":"","_meta":{"progressToken":"mock"}}):
   r=self.a.handle({"jsonrpc":"2.0","id":2,"method":"tools/list","params":params})
   self.assertIn("result",r)
   self.assertEqual(self.up.calls[-1]["params"],{})
 def test_repeated_init_independent(self):
  for i in range(2):
   r=self.a.handle({"jsonrpc":"2.0","id":i,"method":"initialize","params":{"protocolVersion":"2025-03-26"}})
   self.assertEqual(r["result"]["serverInfo"]["name"],"vibe-dot-connector")
  self.assertEqual(self.up.calls,[])
 def test_forbidden_not_forwarded(self):
  for n in ["delete_workspace","stop_execution","shell","merge","update_setup_script","../../anything"]:
   with self.assertRaises(ValueError): self.call(n)
  self.assertEqual(self.up.calls,[])
 def test_protocol_bypass_denied(self):
  for m in ["resources/read","prompts/get","execute","tools/call/extra"]:
   with self.assertRaises(ValueError): self.a.handle({"jsonrpc":"2.0","id":1,"method":m})
  self.assertEqual(self.up.calls,[])
 def test_prompt_required(self):
  for n in ["start_workspace","run_session_prompt"]:
   with self.assertRaises(ValueError): self.call(n)
  self.assertEqual(self.up.calls,[])
 def test_writes_only_mocked(self):
  with patch.object(adapter,"local_followup",return_value=adapter.result({"mock":True})) as mock:
   self.call("run_session_prompt",{"session_id":"example","prompt":"mock only"})
   mock.assert_called_once()
  self.assertEqual(self.up.calls,[])
 def test_log_rejects_path_and_limits(self):
  for args in [{"execution_id":"../../config"},{"execution_id":"00000000-0000-0000-0000-000000000000","limit":101},{"execution_id":"00000000-0000-0000-0000-000000000000","url":"http://evil"}]:
   with self.assertRaises(ValueError): adapter.replies(args)
 def test_running_history_uses_bounded_stream(self):
  import urllib.error,subprocess,json
  uid="00000000-0000-0000-0000-000000000000"
  error=urllib.error.HTTPError("http://localhost",409,"running",{},None)
  completed=subprocess.CompletedProcess([],0,json.dumps({"messages":[{"text":"mock reply"}],"live":True}),"")
  with patch.object(adapter,"http_get",side_effect=error),patch.object(adapter.subprocess,"run",return_value=completed) as mock:
   r=adapter.replies({"execution_id":uid,"limit":3})
   self.assertTrue(json.loads(r["content"][0]["text"])["live"])
   self.assertEqual(mock.call_args.kwargs["timeout"],6)
 def test_running_cursor_does_not_launch_stream(self):
  import urllib.error
  with patch.object(adapter,"http_get",side_effect=urllib.error.HTTPError("http://localhost",409,"running",{},None)),patch.object(adapter.subprocess,"run") as mock:
   adapter.replies({"execution_id":"00000000-0000-0000-0000-000000000000","before":"cursor"})
   mock.assert_not_called()
 def test_local_start_payload_mocked(self):
  import json
  class Response:
   def __enter__(self): return self
   def __exit__(self,*a): pass
   def read(self,n): return b'{"success":true,"data":{"workspace":{"id":"mock"}}}'
  uid="00000000-0000-0000-0000-000000000000"
  with patch.object(adapter.urllib.request,"build_opener") as mock:
   mock.return_value.open.return_value=Response()
   adapter.local_start({"name":"mock","prompt":"mock only","executor":"CODEX","repositories":[{"repo_id":uid,"branch":"integration/example"}],"issue_id":uid,"project_id":uid})
   req=mock.return_value.open.call_args.args[0]
   self.assertEqual(req.full_url,adapter.BASE+"/api/workspaces/start")
   self.assertEqual(json.loads(req.data)["repos"][0]["target_branch"],"integration/example")
 def test_local_issue_scope(self):
  uid="00000000-0000-0000-0000-000000000000"
  with patch.object(adapter,"http_get",return_value={"issues":[{"id":uid,"title":"mock"}]}):
   self.assertFalse(adapter.local_issues({"project_id":uid,"issue_id":uid},True)["isError"])
 def test_logs_only_assistant_bounded(self):
  page={"success":True,"data":{"entries":[{"entry":{"type":"NORMALIZED_ENTRY","content":{"entry_type":{"type":"tool_use"},"content":"DO NOT EXPOSE"}}},{"entry":{"type":"NORMALIZED_ENTRY","content":{"entry_type":{"type":"assistant_message"},"content":"a"*65000}}}],"next_before":"cursor"}}
  with patch.object(adapter,"http_get",return_value=page):
   r=adapter.replies({"execution_id":"00000000-0000-0000-0000-000000000000"})
  self.assertNotIn("DO NOT EXPOSE",str(r)); self.assertIn('"truncated": true',r["content"][0]["text"])
if __name__=="__main__": unittest.main()
