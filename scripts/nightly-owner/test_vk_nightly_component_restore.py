import copy,hashlib,json,os,sqlite3,tempfile,unittest,zlib
from pathlib import Path
from vk_nightly_component_restore import run,FORMAT
from vk_nightly_current_map import encode_member,FORMAT as MAP
from vk_typed_recovery import checksum

class ComponentRestoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
  self.p=Path(self.tmp.name);root=self.p/'provider';root.mkdir();(root/'read.lease').touch();raw=b'exact software byte version\n'*10000
  encoded=zlib.compress(raw);(root/'body.zlib').write_bytes(encoded);h=lambda b:hashlib.sha256(b).hexdigest()
  row=dict(kind='file',bytes=len(raw),sha256=h(raw),uid=os.getuid(),gid=os.getgid(),mode=0o555,mtime_ns=1790000000000000000,xattrs={},segments=[dict(layer='objects',selector='body.zlib',encoding='zlib',bytes=len(raw),sha256=h(raw),encoded_bytes=len(encoded),encoded_sha256=h(encoded))])
  path=root/'component.sqlite'
  with sqlite3.connect(path)as db:
   db.execute('create table metadata(format text,binding text,last_name text,complete integer)');db.execute('insert into metadata values(?,?,?,1)',(MAP,'{}',''))
   db.execute('create table members(name text primary key,state text,row blob)');db.execute('insert into members values(?,?,?)',('software/reader','verified-file',encode_member(dict(member=row))))
   db.execute('create table SQL_sources(path text primary key)')
  st=root.stat();self.packet=dict(format=FORMAT,descriptor_sha256='a'*64,files={'/software/reader':dict(bytes=len(raw),sha256=h(raw),Linux_metadata={k:row[k]for k in ('mode','uid','gid','mtime_ns','xattrs')})},dependencies={'objects':{'actual':'pinned fixture'}},provider_placement=dict(roots={'objects':str(root)},root_bindings={'objects':[st.st_dev,st.st_ino]},lease_paths={'objects':str(root/'read.lease')},expected_uid=os.getuid(),expected_gid=os.getgid()),index_reference=dict(format='vk-nightly-current-member-map-v1',layer='objects',selector=path.name,sha256=h(path.read_bytes()),bytes=path.stat().st_size),maximum_readback_bytes=len(raw),maximum_scratch_bytes=len(raw)+16*1024**2,memory_floor_bytes=0,swap_floor_bytes=0,scratch_parent=str(self.p))
 def test_real_normal_provider_immutable_index_decode_hash_metadata_full_restore(self):
  proof=run(self.packet,checksum(self.packet),guard=lambda:None)
  self.assertTrue(proof['independent_software_component_restore_verified']);self.assertNotIn('independent_composed_restore_verified',proof)
  self.assertFalse(proof['current_baseline_accepted']);self.assertEqual(proof['raw_bytes'],280000)
  self.assertTrue(proof['actual_normal_reader_restore'][0]['Linux_metadata_verified']);self.assertEqual(list(self.p.glob('nightly-software-*')),[])
 def test_exact_missing_and_changed_manifest_rejected(self):
  for mutate in [lambda p:p['files']['/software/reader'].update(sha256='f'*64),lambda p:p['files'].update({'/software/missing':copy.deepcopy(p['files']['/software/reader'])})]:
   p=copy.deepcopy(self.packet);mutate(p);p['maximum_readback_bytes']=1000000
   with self.assertRaises(ValueError):run(p,checksum(p),guard=lambda:None)
 def test_corrupt_B_content_and_changed_provider_lease_fail(self):
  (self.p/'provider/body.zlib').write_bytes(b'bad')
  with self.assertRaises((ValueError,zlib.error)):run(self.packet,checksum(self.packet),guard=lambda:None)
 def test_hash_or_peak_admission_fail_before_restore(self):
  with self.assertRaises(ValueError):run(self.packet,'0'*64,guard=lambda:None)
  p=copy.deepcopy(self.packet);p['maximum_scratch_bytes']=1
  with self.assertRaisesRegex(ValueError,'scratch'):run(p,checksum(p),guard=lambda:None)
if __name__=='__main__':unittest.main()
