import types,unittest
import test_vk_nightly_sql_point as fixtures
from vk_nightly_owner_sql import capture
class OwnedSQLTests(unittest.TestCase):
 def test_real_SQL_API_and_same_existing_object_protocol(self):
  fixture=fixtures.SQLPointTests('test_explicit_owner_until_verified_mode_retains_SQL_API_and_restore');fixture.setUp();self.addCleanup(fixture.doCleanups)
  events=[];checks=[];recovery=types.SimpleNamespace(native_SQL_client=fixture.client,native_SQL_guard=lambda:None,check=lambda:checks.append(True))
  result=capture(recovery,[str(fixture.source)],maximum_image_bytes=1024**2,chunk_bytes=65536,memory_floor_bytes=0,timeout_seconds=None,save=lambda source,value:events.append(value))
  self.assertEqual(result[0]['independent']['integrity'],'ok');self.assertTrue(result[0]['independent']['independent_Linux_metadata_verified']);self.assertTrue(result[0]['B_acceptance_object']);self.assertGreater(len(checks),1);self.assertTrue(any('accepted'in e for e in events))
if __name__=='__main__':unittest.main()
