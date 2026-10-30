import unittest,json,urllib.error
from unittest.mock import patch
import adapter,status_reads as s
SID="cdba0e6c-cfba-4fbe-bddf-1e3b92838c38";WID="fcf2fbbf-9dfd-4c2e-9588-7f3003ebb20d"
def row(i,status="completed",created="2026-10-04T10:00Z",completed="2026-10-04T11:00Z"):return dict(id=i,session_id=SID,status=status,created_at=created,completed_at=completed)
def page(text=None,cursor=None,index=9):return {"success":True,"data":{"entries":[] if text is None else [{"index":index,"entry":{"type":"NORMALIZED_ENTRY","content":{"entry_type":{"type":"assistant_message"},"content":text}}}],"next_before":cursor}}
class Tests(unittest.TestCase):
 def scope(self):return patch.object(s,"scope",return_value=(SID,WID,None))
 def test_ambiguous_workspace_no_guess(self):
  with patch.object(adapter,"http_get",return_value={"success":True,"data":[{"id":"a"},{"id":"b"}]}),patch.object(s,"snapshot") as snap:
   out=s.latest(adapter,{"workspace_id":WID});self.assertTrue(out["ambiguous"]);snap.assert_not_called()
 def test_interrupted_followup_does_not_mask_original(self):
  rows=[row("original",created="1",completed="4"),row("failed","failed",created="2",completed="3")]
  with self.scope(),patch.object(s,"snapshot",return_value=rows),patch.object(adapter,"http_get",return_value=page("finished")):
   out=s.latest(adapter,{"session_id":SID});self.assertEqual(out["latest_created_execution"]["id"],"failed");self.assertEqual(out["latest_successful_reply"]["execution"]["id"],"original")
 def test_later_failure_and_success_both_visible(self):
  rows=[row("original",created="1",completed="3"),row("failed","failed",created="2",completed="4")]
  with self.scope(),patch.object(s,"snapshot",return_value=rows),patch.object(adapter,"http_get",side_effect=[page("failure"),page("success")]):
   out=s.latest(adapter,{"session_id":SID});self.assertEqual(out["latest_durable_reply"]["text"],"failure");self.assertEqual(out["latest_successful_reply"]["text"],"success")
 def test_empty_page_follows_cursor(self):
  with patch.object(adapter,"http_get",side_effect=[page(cursor=10),page("last durable")]) as get:
   out=s.durable(adapter,row("e"),3);self.assertEqual(out["text"],"last durable");self.assertTrue(out["complete_message"]);self.assertIn("before=10",get.call_args.args[0])
 def test_empty_exhausted_not_completion(self):
  with patch.object(adapter,"http_get",return_value=page()):
   out=s.durable(adapter,row("e"),3);self.assertTrue(out["history_exhausted"]);self.assertIn("unknown",out["reason"])
 def test_bounded_history_cursor(self):
  with patch.object(adapter,"http_get",return_value=page(cursor=10)) as get:
   out=s.durable(adapter,row("e"),1);self.assertEqual(out["next_before"],"10");self.assertEqual(get.call_count,1)
 def test_running_separate_from_durable(self):
  rows=[row("live","running",created="3",completed=None),row("old",created="1",completed="2")]
  with self.scope(),patch.object(s,"snapshot",return_value=rows),patch.object(adapter,"http_get",return_value=page("durable")),patch.object(adapter,"replies",return_value=adapter.result({"messages":[{"text":"partial"}],"live":True})):
   out=s.latest(adapter,{"session_id":SID});self.assertTrue(out["current_running"]);self.assertFalse(out["live_reply"]["complete_message"]);self.assertEqual(out["latest_successful_reply"]["text"],"durable")
 def test_limits_and_unknowns(self):
  for args in [{"session_id":SID,"max_pages":11},{"session_id":SID,"max_executions":0},{"session_id":SID,"include_live":1},{"session_id":SID,"url":"evil"}]:
   with self.assertRaises(ValueError):s.latest(adapter,args)
 def test_scope_xor(self):
  for args in [{},{"session_id":SID,"workspace_id":WID}]:
   with self.assertRaises(ValueError):s.scope(adapter,args)
 def test_large_message_marked_incomplete(self):
  with patch.object(adapter,"http_get",return_value=page("a"*128001)):
   out=s.durable(adapter,row("e"),1);self.assertFalse(out["complete_message"]);self.assertEqual(len(out["text"]),128000)
 def test_metadata_listing_does_not_emit_configs(self):
  with self.scope(),patch.object(s,"snapshot",return_value=[row("a"),row("b")]):
   out=s.listing(adapter,{"session_id":SID,"limit":1});self.assertEqual(out["next_offset"],1);self.assertEqual(len(out["executions"]),1)
 def test_raw_tool_logs_not_returned(self):
  p=page();p["data"]["entries"]=[{"index":1,"entry":{"type":"NORMALIZED_ENTRY","content":{"entry_type":{"type":"tool_use"},"content":"SECRET_TOOL_TEXT"}}}]
  with patch.object(adapter,"http_get",return_value=p):self.assertNotIn("SECRET_TOOL_TEXT",str(s.durable(adapter,row("e"),1)))
 def test_no_executions_unknown(self):
  with self.scope(),patch.object(s,"snapshot",return_value=[]):
   out=s.latest(adapter,{"session_id":SID});self.assertIsNone(out["latest_durable_reply"]);self.assertEqual(out["task_completion"],"not_inferred")
 def test_409_not_empty_completed(self):
  with patch.object(adapter,"http_get",side_effect=urllib.error.HTTPError("",409,"",{},None)):
   out=s.durable(adapter,row("e"),1);self.assertFalse(out["history_available"])
if __name__=="__main__":unittest.main()
