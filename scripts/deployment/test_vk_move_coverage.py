from pathlib import Path
import copy,os,unittest
from journal_compat import reconcile,MASK,recopy_cover,observed_move,source_removal
from unittest.mock import Mock
class Cases(unittest.TestCase):
 def move_fixture(self):
  path=Path('/protected/new/repo');source='/protected/old/repo'
  return path,Path('/protected/new'),{source:0x40000040},{Path('/protected')},lambda p:True,{str(path):source}
 def test_explicit_cross_parent_source_keeps_tombstones(self):
  args=self.move_fixture();events=dict(args[2]);source_removal(*args)
  self.assertEqual(events,args[2])
 def test_unmapped_cross_parent_move_rejected(self):
  args=list(self.move_fixture());args[-1]={}
  with self.assertRaises(AssertionError):source_removal(*args)
 def test_cross_parent_missing_source_event_rejected(self):
  args=list(self.move_fixture());args[2]={}
  with self.assertRaises(AssertionError):source_removal(*args)
 def test_cross_parent_source_outside_scope_rejected(self):
  args=list(self.move_fixture());args[-1]={str(args[0]):'/outside/repo'};args[2]={'/outside/repo':0x40000040}
  with self.assertRaises(AssertionError):source_removal(*args)
 def test_cross_parent_source_watch_missing_rejected(self):
  args=list(self.move_fixture());args[-2]=lambda p:False
  with self.assertRaises(AssertionError):source_removal(*args)
 def test_file_move_cannot_substitute_directory_source(self):
  args=list(self.move_fixture());args[2]={'/protected/old/repo':0x40}
  with self.assertRaises(AssertionError):source_removal(*args)
 def test_partial_deleted_watch_requires_recopy(self):
  v=self.fixture();p=Path(next(iter(v['events'])));v['events'][str(p)]=0x8400
  self.assertFalse(self.run_case(v)['ready'])
  self.assertTrue(reconcile(v,v,{Path('/protected')},lambda p:True,lambda p:False,lambda p:True)['ready'])
 def test_recopy_does_not_hide_unknown_watch_loss(self):
  v=self.fixture();v['events'][next(iter(v['events']))]=0x8000
  self.assertFalse(reconcile(v,v,{Path('/protected')},lambda p:True,lambda p:True,lambda p:True)['ready'])
 def test_deleted_move_requires_complete_evidence(self):
  p=Mock();p.exists.return_value=False;p.is_symlink.return_value=False
  observed_move(p,MASK|0x800)
  for missing in (0x200,0x400,0x800,0x8000):
   with self.assertRaises(AssertionError):observed_move(p,(MASK|0x800)&~missing)
 def test_recreated_move_requires_move_in(self):
  p=Mock();p.exists.return_value=True
  with self.assertRaises(AssertionError):observed_move(p,MASK|0x800)
  observed_move(p,0x40000880)
 def test_deleted_symlink_not_accepted(self):
  p=Mock();p.exists.return_value=False;p.is_symlink.return_value=True
  with self.assertRaises(AssertionError):observed_move(p,MASK|0x800)
 def test_nested_move_has_bounded_ancestor(self):
  self.assertEqual(recopy_cover(Path('/protected/tmp/deleted/repo'),{Path('/protected/tmp')},{Path('/protected')},lambda p:True),Path('/protected/tmp'))
 def test_move_outside_explicit_coverage_rejected(self):
  with self.assertRaises(AssertionError):recopy_cover(Path('/protected/other/repo'),{Path('/protected/tmp')},{Path('/protected')},lambda p:True)
 def test_whole_source_cannot_be_recopy_exception(self):
  with self.assertRaises(AssertionError):recopy_cover(Path('/protected/repo'),{Path('/protected')},{Path('/protected')},lambda p:True)
 def test_overlapping_coverage_rejected(self):
  with self.assertRaises(AssertionError):recopy_cover(Path('/protected/tmp/nested/repo'),{Path('/protected/tmp'),Path('/protected/tmp/nested')},{Path('/protected')},lambda p:True)
 def test_missing_covering_watch_rejected(self):
  with self.assertRaises(AssertionError):recopy_cover(Path('/protected/tmp/repo'),{Path('/protected/tmp')},{Path('/protected')},lambda p:False)
 def test_recopy_root_itself_moved_rejected(self):
  with self.assertRaises(AssertionError):recopy_cover(Path('/protected/tmp'),{Path('/protected/tmp')},{Path('/protected')},lambda p:True)
 def fixture(self):
  p='/protected/tmp/deleted'
  return {'instance':'a','scope_sha256':'x','ready':False,'errors':[{'watch_removed':p}],'events':{p:MASK},'changed':[p,'/protected/actual-data.sqlite']}
 def run_case(self,v,covered=lambda p:True):return reconcile(v,v,{Path('/protected')},covered,lambda p:False)
 def test_known_deletion_preserves_changes_and_original_errors(self):
  v=self.fixture();r=self.run_case(v);self.assertTrue(r['ready']);self.assertEqual(r['changed'],v['changed']);self.assertTrue(v['errors'])
 def test_missing_parent_event_rejected(self):
  v=self.fixture();v['events'][next(iter(v['events']))]&=~0x200;self.assertFalse(self.run_case(v)['ready'])
 def test_overflow_rejected(self):
  v=self.fixture();v['errors'].append({'coverage_lost':0x4000});self.assertFalse(self.run_case(v)['ready'])
 def test_outside_scope_rejected(self):
  v=self.fixture();v['errors']=[{'watch_removed':'/important'}];self.assertFalse(self.run_case(v)['ready'])
 def test_unwatched_ancestor_rejected(self):self.assertFalse(self.run_case(self.fixture(),lambda p:False)['ready'])
 def test_root_deletion_rejected(self):
  v=self.fixture();v['errors']=[{'watch_removed':'/protected'}];v['events']['/protected']=MASK;self.assertFalse(self.run_case(v)['ready'])
 def test_identity_change_rejected(self):
  v=self.fixture();other=copy.deepcopy(v);other['instance']='b'
  with self.assertRaises(AssertionError):reconcile(v,other,{Path('/protected')},lambda p:True,lambda p:True)
 def test_recreated_path_requires_all_watches(self):
  from tempfile import TemporaryDirectory
  with TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
   p=str(Path(d).resolve());v=self.fixture();v['errors']=[{'watch_removed':p}];v['events']={p:MASK}
   roots={Path(d).resolve().parent}
   self.assertFalse(reconcile(v,v,roots,lambda p:True,lambda p:False)['ready'])
   self.assertTrue(reconcile(v,v,roots,lambda p:True,lambda p:True)['ready'])
if __name__=='__main__':unittest.main()
