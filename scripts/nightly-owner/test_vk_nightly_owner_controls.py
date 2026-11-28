import hashlib,json,os,sqlite3,tempfile,unittest
from pathlib import Path
from vk_nightly_owner_controls import source_point,run,FORMAT
from vk_typed_recovery import checksum
class OwnerControlsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
  control=self.p/'actual-journal.json';control.write_bytes(b'{"actual_state":"before-switch"}\n');control.chmod(0o600)
  self.point,self.body=source_point(str(control),maximum_bytes=4096,guard=lambda:None)
  self.manifest=dict(operation='a'*32,plan_sha256='b'*64,files=[self.point]);root=self.p/'provider';root.mkdir();(root/'read.lease').touch();index=root/'checkpoint.sqlite'
  with sqlite3.connect(index)as db:
   db.execute('create table owner_control_manifest(sha256 text,row text)');db.execute('insert into owner_control_manifest values(?,?)',(checksum(self.manifest),json.dumps(self.manifest,sort_keys=True,separators=(',',':'))))
   db.execute('create table owner_control_files(source text,point text)');db.execute('insert into owner_control_files values(?,?)',(str(control),json.dumps(self.point,sort_keys=True,separators=(',',':'))))
   db.execute('create table owner_control_parts(source text,part int,data blob)');db.execute('insert into owner_control_parts values(?,?,?)',(str(control),0,self.body))
  st=root.stat();self.packet=dict(format=FORMAT,descriptor_sha256=checksum(self.manifest),checkpoint=dict(manifest=self.manifest,manifest_sha256=checksum(self.manifest),index_reference=dict(layer='nightly-controls-v1',selector=index.name,bytes=index.stat().st_size,sha256=hashlib.sha256(index.read_bytes()).hexdigest())),dependencies={'nightly-controls-v1':{'owner':'actual fixture'}},provider_placement=dict(roots={'nightly-controls-v1':str(root)},root_bindings={'nightly-controls-v1':[st.st_dev,st.st_ino]},lease_paths={'nightly-controls-v1':str(root/'read.lease')},expected_uid=os.getuid(),expected_gid=os.getgid()),scratch_parent=str(self.p))
 def test_normal_provider_checkpoint_full_restore_hash_and_Linux_metadata(self):
  r=run(self.packet,checksum(self.packet),guard=lambda:None)
  self.assertTrue(r['independent_owner_controls_restore_verified']);self.assertEqual(r['files'],1)
  self.assertTrue(r['actual_normal_reader_restore'][0]['Linux_metadata_verified']);self.assertFalse(r['current_baseline_accepted'])
 def test_source_admission_and_real_guard_errors_propagate(self):
  with self.assertRaisesRegex(ValueError,'finite'):source_point(self.point['source'],maximum_bytes=1,guard=lambda:None)
  def stop():raise OSError('real STOP')
  with self.assertRaisesRegex(OSError,'STOP'):run(self.packet,checksum(self.packet),guard=stop)
 def test_corrupt_or_wrong_checkpoint_not_accepted(self):
  with self.assertRaises(ValueError):run(self.packet,'0'*64,guard=lambda:None)
  self.packet['checkpoint']['index_reference']['sha256']='f'*64
  with self.assertRaisesRegex(ValueError,'hash'):run(self.packet,checksum(self.packet),guard=lambda:None)
 def test_multiframe_control_body_and_missing_tail_are_checked(self):
  control=Path(self.point['source']);body=b'final-review-journal\n'*60000;control.write_bytes(body)
  point,actual=source_point(str(control),maximum_bytes=2*1024**2,guard=lambda:None)
  self.manifest['files']=[point];self.packet['checkpoint']['manifest_sha256']=checksum(self.manifest)
  index=self.p/'provider/checkpoint.sqlite'
  with sqlite3.connect(index)as db:
   db.execute('delete from owner_control_manifest');db.execute('insert into owner_control_manifest values(?,?)',(checksum(self.manifest),json.dumps(self.manifest,sort_keys=True,separators=(',',':'))))
   db.execute('delete from owner_control_files');db.execute('insert into owner_control_files values(?,?)',(str(control),json.dumps(point,sort_keys=True,separators=(',',':'))))
   db.execute('delete from owner_control_parts')
   for part,start in enumerate(range(0,len(actual),1024**2)):db.execute('insert into owner_control_parts values(?,?,?)',(str(control),part,actual[start:start+1024**2]))
  ref=self.packet['checkpoint']['index_reference'];ref.update(bytes=index.stat().st_size,sha256=hashlib.sha256(index.read_bytes()).hexdigest())
  self.assertEqual(run(self.packet,checksum(self.packet),guard=lambda:None)['raw_bytes'],len(body))
  with sqlite3.connect(index)as db:db.execute('delete from owner_control_parts where part=1')
  ref.update(bytes=index.stat().st_size,sha256=hashlib.sha256(index.read_bytes()).hexdigest())
  with self.assertRaisesRegex(ValueError,'EOF'):run(self.packet,checksum(self.packet),guard=lambda:None)
 def test_outer_old_reader_namespace_cannot_replace_qualified_control_runner(self):
  import sys,types
  import vk_nightly_owner_controls as owner
  from unittest.mock import patch
  actual=owner.normal_restore;old=types.ModuleType('vk_nightly_remote_consumer');old.run=lambda *a,**k:None
  with patch.dict(sys.modules,{'vk_nightly_remote_consumer':old}):
   self.assertIs(owner.normal_restore,actual)
   self.assertIsNot(owner.normal_restore,old.run)
if __name__=='__main__':unittest.main()
