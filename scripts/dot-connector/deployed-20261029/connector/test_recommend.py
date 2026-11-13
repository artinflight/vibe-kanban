import unittest,json,urllib.error
from unittest.mock import patch
import adapter
SID="cdba0e6c-cfba-4fbe-bddf-1e3b92838c38"
CFG={"executor":"CODEX","model_id":"gpt-6.1-sol","reasoning_id":"high","permission_policy":"AUTO","routing":{"mode":"auto","floor":"frontier","denied_models":["blocked"],"allow_escalation":False}}
class Tests(unittest.TestCase):
 def test_preserves_every_field_except_mode(self):
  c=adapter.recommend_config(CFG);self.assertEqual(c["routing"]["mode"],"shadow")
  c["routing"]["mode"]="auto";self.assertEqual(c,CFG)
 def test_default_and_manual_always_shadow(self):
  for c in ({"executor":"CODEX"},{"executor":"CODEX","routing":{"mode":"manual","floor":"routine","denied_models":[],"allow_escalation":True}}):self.assertEqual(adapter.recommend_config(c)["routing"]["mode"],"shadow")
 def test_unsupported_executor_fails(self):
  with self.assertRaises(ValueError):adapter.recommend_config({"executor":"OTHER"})
 def test_unknown_policy_fails(self):
  with self.assertRaises(ValueError):adapter.recommend_config({"executor":"CODEX","routing":{"future":True}})
 def test_followup_payload_no_generation(self):
  with patch.object(adapter,"resolve_followup_config",return_value=adapter.recommend_config(CFG)),patch.object(adapter,"post_fixed",return_value={"id":"mock"}) as post:
   adapter.local_followup({"session_id":SID,"prompt":"mock only"})
   payload=post.call_args.args[1];self.assertEqual(payload["executor_config"]["routing"]["mode"],"shadow");self.assertEqual(payload["executor_config"]["model_id"],CFG["model_id"]);self.assertIsNone(payload["retry_process_id"])
 def test_resolution_failure_never_posts(self):
  with patch.object(adapter,"resolve_followup_config",side_effect=ValueError()),patch.object(adapter,"post_fixed") as post:
   with self.assertRaises(ValueError):adapter.local_followup({"session_id":SID,"prompt":"mock"})
   post.assert_not_called()
 def test_no_mode_bypass(self):
  with self.assertRaises(ValueError):adapter.local_followup({"session_id":SID,"prompt":"mock","routing":{"mode":"auto"}})
 def test_draft_wins_and_retains_limits(self):
  draft=dict(CFG,model_id="owner-model",reasoning_id="xhigh")
  responses=[{"success":True,"data":{"executor":"CODEX"}},{"success":True,"data":{"payload":{"data":{"executor_config":draft}}}}]
  with patch.object(adapter,"http_get",side_effect=responses),patch.object(adapter,"session_configs",return_value=[{"config":CFG}]):
   c=adapter.resolve_followup_config(SID);self.assertEqual(c["model_id"],"owner-model");self.assertEqual(c["routing"]["denied_models"],["blocked"])
 def test_new_start_payload_shadow(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):return b'{"success":true,"data":{}}'
  with patch.object(adapter.urllib.request,"build_opener") as op:
   op.return_value.open.return_value=Response();adapter.local_start({"name":"mock","prompt":"mock","executor":"CODEX","model_id":"chosen","reasoning_id":"high","repositories":[{"repo_id":SID,"branch":"main"}]})
   c=json.loads(op.return_value.open.call_args.args[0].data)["executor_config"];self.assertEqual(c["routing"]["mode"],"shadow");self.assertEqual(c["model_id"],"chosen");self.assertEqual(c["reasoning_id"],"high")
if __name__=="__main__":unittest.main()
