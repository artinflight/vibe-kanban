import json, unittest
from unittest.mock import patch
import adapter
SID="d703d0fe-4c95-4b3d-ba11-7fa5b1a920ce"
class Tests(unittest.TestCase):
 def invoke(self, envelope):
  class Response:
   def __enter__(self): return self
   def __exit__(self,*args): pass
   def read(self,n): return json.dumps(envelope).encode()
  with patch.object(adapter,"resolve_followup_config",return_value={"executor":"CODEX"}), patch.object(adapter.urllib.request,"build_opener") as op:
   op.return_value.open.return_value=Response()
   answer=adapter.local_followup({"session_id":SID,"prompt":"mock only"})
   self.assertEqual(op.return_value.open.call_count,1)
   return json.loads(answer["content"][0]["text"])
 def queued(self):
  return {"success":False,"error_data":{"status":"queued","message":{"session_id":SID,"wait_for_capacity":True,"queued_at":"now","messages":[{"message":"PRIVATE PROMPT"}]}}}
 def test_capacity_is_accepted_without_replay_or_prompt_echo(self):
  result=self.invoke(self.queued())
  self.assertEqual(result["status"],"queued")
  self.assertIsNone(result["execution_id"])
  self.assertNotIn("PRIVATE PROMPT",json.dumps(result))
 def test_actual_execution_unchanged(self):
  self.assertEqual(self.invoke({"success":True,"data":{"id":"execution"}})["execution_id"],"execution")
 def test_generic_failure_not_accepted(self):
  with self.assertRaises(ValueError): self.invoke({"success":False,"error_data":None})
 def test_wrong_session_not_accepted(self):
  data=self.queued();data["error_data"]["message"]["session_id"]="wrong"
  with self.assertRaises(ValueError): self.invoke(data)
 def test_non_capacity_queue_not_accepted(self):
  data=self.queued();data["error_data"]["message"]["wait_for_capacity"]=False
  with self.assertRaises(ValueError): self.invoke(data)
if __name__=="__main__": unittest.main()
