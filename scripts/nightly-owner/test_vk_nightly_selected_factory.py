import unittest
from vk_nightly_selected_factory import build_rows
class FactoryTests(unittest.TestCase):
 def values(self):
  meta=dict(mode=0o664,uid=1000,gid=1000,mtime_ns=100,xattrs={});body=dict(kind='file',bytes=3,sha256='a'*64,segments=[dict(layer='actual-retained',selector='body',bytes=3,sha256='a'*64)],**meta)
  files=[dict(relative=str(i),normal_namespace_name='root/'+str(i),bytes=3,sha256='a'*64,Linux_metadata=dict(meta,mtime_ns=i))for i in range(60)]
  return dict(source_root='/root',files=files),{('a'*64,3):body},{'actual-retained':{'independent':'prior real body'}}
 def test_sixty_requested_names_reuse_retained_body_and_distinct_metadata(self):
  request,carriers,deps=self.values();r=build_rows(request,carriers,deps)
  self.assertTrue(r['complete']);self.assertEqual(len(r['rows']),60);self.assertEqual(r['body_bytes_read'],0)
  self.assertEqual(r['rows']['root/59']['member']['mtime_ns'],59)
  self.assertTrue(r['rows']['root/59']['supplemental_metadata_epoch']['original_archive_name_inclusion_not_claimed'])
 def test_missing_exact_version_or_provider_is_reported_not_relabelled(self):
  r,c,d=self.values();self.assertFalse(build_rows(r,{},d)['complete']);self.assertFalse(build_rows(r,c,{})['complete'])

 def test_exact_map_carrier_without_incremental_history_is_reusable(self):
  from vk_nightly_selected_factory import retained_map_candidate
  from vk_nightly_current_map import encode_member
  r,c,d=self.values();m=c[('a'*64,3)];wanted=r['files'][0]
  v=dict(member=m,qualification=dict(state='qualified-retained-body',source='/root/0',row=m))
  self.assertEqual(retained_map_candidate('root/0',wanted,('verified-file',encode_member(v))),m)
  self.assertIsNone(retained_map_candidate('root/0',wanted,('file-needs-capture',encode_member(v))))
  self.assertIsNone(retained_map_candidate('root/0',dict(wanted,sha256='b'*64),('verified-file',encode_member(v))))
  v['qualification']['source']='/other'
  self.assertIsNone(retained_map_candidate('root/0',wanted,('verified-file',encode_member(v))))



class MissingVersionTests(unittest.TestCase):
 def setUp(self):
  import sqlite3,types
  import test_vk_nightly_sql_point as fixtures
  self.fixture=fixtures.SQLPointTests('test_actual_SQL_API_chunked_B_restore_integrity_metadata_and_no_OS_staging')
  self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
  self.client=self.fixture.client;self.root=self.fixture.root
  self.db=sqlite3.connect(':memory:',isolation_level=None);self.addCleanup(self.db.close)
  self.recovery=types.SimpleNamespace(native_SQL_client=self.client,check=lambda:None)
  self.dependencies={'nightly-objects-v1':{'actual_fixture':True}}
 def request(self,values):
  import hashlib,stat
  from vk_nightly_file_version import attributes
  files=[]
  for name,body in values:
   p=self.root/name;p.write_bytes(body);st=p.stat()
   files.append(dict(relative=name,normal_namespace_name=str(p)[1:],bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),Linux_metadata=dict(mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,xattrs=attributes(p))))
  return dict(source_root=str(self.root),files=files)
 def run_capture(self,request,carriers=None,maximum=65536):
  from vk_nightly_selected_factory import capture_missing
  return capture_missing(self.recovery,request,{}if carriers is None else carriers,self.dependencies,self.db,maximum_source_bytes=maximum,chunk_bytes=4096)
 def test_native_readback_completed_resume_does_not_reopen_source(self):
  from unittest.mock import patch
  r=self.request([('raw',b'x'*9000),('sidecar',b'{}')]);first=self.run_capture(r)
  self.assertEqual(first['source_bytes_captured'],9002)
  self.assertEqual(self.client.independent_readback_bytes,9002)
  sent=self.client.payload_bytes_sent
  with patch('vk_nightly_selected_factory.capture_version',side_effect=AssertionError('completed source reopened')):
   second=self.run_capture(r,maximum=0)
  self.assertEqual(second['source_bytes_captured'],0);self.assertEqual(second['completed_request_points_reused'],2)
  self.assertEqual(self.client.payload_bytes_sent,sent)
 def test_interruption_retains_first_point_then_captures_only_missing(self):
  from unittest.mock import patch
  from vk_nightly_file_version import capture_version
  r=self.request([('first',b'a'*5000),('second',b'b'*5000)]);calls=[]
  def fail_second(path,*args,**kwargs):
   calls.append(path)
   if path.endswith('/second'):raise OSError('actual STOP')
   return capture_version(path,*args,**kwargs)
  with patch('vk_nightly_selected_factory.capture_version',side_effect=fail_second):
   with self.assertRaisesRegex(OSError,'actual STOP'):self.run_capture(r)
  self.assertEqual(self.db.execute('select count(*) from selected_captured_versions').fetchone(),(1,))
  calls=[]
  def recorded(path,*a,**kw):calls.append(path);return capture_version(path,*a,**kw)
  with patch('vk_nightly_selected_factory.capture_version',side_effect=recorded):result=self.run_capture(r)
  self.assertEqual(calls,[str(self.root/'second')]);self.assertEqual(result['completed_request_points_reused'],1)
 def test_wrong_current_version_is_never_accepted(self):
  r=self.request([('raw',b'old')]);(self.root/'raw').write_bytes(b'new')
  with self.assertRaisesRegex(ValueError,'source differs'):self.run_capture(r)
  self.assertEqual(self.db.execute('select count(*) from selected_captured_versions').fetchone(),(0,))
 def test_budget_rejects_before_any_body_upload(self):
  r=self.request([('raw',b'abcd')])
  with self.assertRaisesRegex(ValueError,'exceed admission'):self.run_capture(r,maximum=3)
  self.assertEqual(self.client.payload_bytes_sent,0)
 def test_path_escape_and_duplicate_names_rejected(self):
  from vk_nightly_selected_factory import validate_request
  r=self.request([('raw',b'a')]);r['files'][0]['relative']='../escape'
  with self.assertRaises(ValueError):validate_request(r)
  r=self.request([('raw',b'a')]);r['files'].append(dict(r['files'][0]))
  with self.assertRaises(ValueError):validate_request(r)
 def test_empty_file_and_retained_carrier_need_no_new_body_copy_on_reuse(self):
  from vk_nightly_current_map import decode_member
  from unittest.mock import patch
  r=self.request([('empty',b'')]);self.run_capture(r)
  member=decode_member(self.db.execute('select row from selected_captured_versions').fetchone()[0])
  with patch('vk_nightly_selected_factory.capture_version',side_effect=AssertionError('reopened')):
   result=self.run_capture(r,{(member['sha256'],member['bytes']):member},maximum=0)
  self.assertEqual(result['source_bytes_captured'],0)

if __name__=='__main__':unittest.main()
