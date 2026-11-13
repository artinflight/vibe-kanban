import hashlib,json,sqlite3,tempfile,unittest,uuid
from datetime import datetime,timezone
from pathlib import Path
from vk_reconcile_orphaned_subagents import apply,validate_record

class ReconcileTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=self.root/'db.sqlite';self.plan=self.root/'plan.json'
  self.sid=uuid.uuid4();self.eid=uuid.uuid4();self.child=str(uuid.uuid4())
  self.row=dict(job=dict(execution_process_id=str(self.eid),session_id=str(self.sid),agent_id=self.child,nickname='fixture',status='running',created_at='2026-07-01T00:00:00Z'),parent_status='completed',parent_completed_at='2026-07-01T01:00:00Z',native_thread=dict(id=self.child,created_at_ms=1000,updated_at_ms=2000),rollout_exists=False,existing_rows=[])
  self.audit=dict(boot_UTC='2026-10-23T21:52:03+00:00',active_execution_count=0,matching_live_owners=[],records=[self.row])
  with sqlite3.connect(self.db)as d:
   d.executescript('CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,completed_at TEXT); CREATE TABLE subagent_jobs(id BLOB PRIMARY KEY,session_id BLOB,execution_process_id BLOB,agent_id TEXT,nickname TEXT,status TEXT,completed_at TEXT,created_at TEXT,updated_at TEXT,UNIQUE(execution_process_id,agent_id)); CREATE TABLE history(body TEXT); INSERT INTO history VALUES ("preserve original reply");')
   d.execute('INSERT INTO execution_processes VALUES(?,?,?,?)',(self.eid.bytes,self.sid.bytes,'completed',self.row['parent_completed_at']))
 def tearDown(self):self.temp.cleanup()
 def run_apply(self,guard=lambda _:None):
  raw=json.dumps(self.audit).encode();self.plan.write_bytes(raw)
  return apply(self.db,self.plan,verify_external=guard,expected_sha256=hashlib.sha256(raw).hexdigest())
 def test_failed_receipt_uses_boot_boundary_and_preserves_history(self):
  out=self.run_apply()
  self.assertEqual(len(out['changes']),1)
  with sqlite3.connect(self.db)as d:
   self.assertEqual(d.execute('select status,completed_at from subagent_jobs').fetchone(),('failed',self.audit['boot_UTC']))
   self.assertEqual(d.execute('select body from history').fetchone()[0],'preserve original reply')
  self.assertLess(datetime.fromisoformat(out['boot_boundary_UTC']),datetime.now(timezone.utc))
 def test_new_native_activity_and_new_parent_fail_closed(self):
  self.row['native_thread']['updated_at_ms']=datetime.now(timezone.utc).timestamp()*1000
  with self.assertRaises(ValueError):self.run_apply()
  self.row['native_thread']['updated_at_ms']=2000;self.row['parent_completed_at']='2026-10-29T00:00:00Z'
  with self.assertRaises(ValueError):self.run_apply()
 def test_concurrent_or_completed_records_are_not_overwritten(self):
  self.run_apply()
  with self.assertRaisesRegex(ValueError,'changed since audit'):self.run_apply()
  with sqlite3.connect(self.db)as d:self.assertEqual(d.execute('select count(*) from subagent_jobs').fetchone()[0],1)
 def test_owner_change_rolls_back_entire_transaction(self):
  calls=[]
  def guard(_):
   calls.append(True)
   if len(calls)==2:raise ValueError('new owner')
  with self.assertRaisesRegex(ValueError,'new owner'):self.run_apply(guard)
  with sqlite3.connect(self.db)as d:self.assertEqual(d.execute('select count(*) from subagent_jobs').fetchone()[0],0)
 def test_active_execution_blocks_reconciliation(self):
  with sqlite3.connect(self.db)as d:d.execute("update execution_processes set status='running'")
  with self.assertRaisesRegex(ValueError,'Active execution'):self.run_apply()
 def test_existing_receipt_retains_its_original_execution_binding(self):
  original=uuid.uuid4();jobid=uuid.uuid4()
  with sqlite3.connect(self.db)as d:
   d.row_factory=sqlite3.Row
   d.execute('INSERT INTO execution_processes VALUES(?,?,?,?)',(original.bytes,self.sid.bytes,'completed','2026-06-01T00:00:00Z'))
   d.execute('INSERT INTO subagent_jobs VALUES(?,?,?,?,?,?,?,?,?)',(jobid.bytes,self.sid.bytes,original.bytes,self.child,'fixture','running',None,'2026-05-01T00:00:00Z','2026-05-01T00:00:00Z'))
   from vk_reconcile_orphaned_subagents import encoded
   self.row['existing_rows']=[encoded(d.execute('select * from subagent_jobs').fetchone())]
   self.row['existing_parents']={original.hex:encoded(d.execute('select status,completed_at,session_id from execution_processes where id=?',(original.bytes,)).fetchone())}
  result=self.run_apply()
  self.assertEqual(result['changes'][0]['after']['execution_process_id'],original.hex)
  self.assertEqual(result['changes'][0]['after']['id'],jobid.hex)
  self.assertEqual(result['changes'][0]['after']['status'],'failed')
 def test_changed_audit_is_rejected_before_access(self):
  self.plan.write_text('{}')
  with self.assertRaisesRegex(ValueError,'plan changed'):apply(self.db,self.plan,verify_external=lambda _:None,expected_sha256='0'*64)

if __name__=='__main__':unittest.main()
