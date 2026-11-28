import contextlib,hashlib,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from vk_nightly_owner_callback import make_callback
class CallbackTests(unittest.TestCase):
 def test_same_actual_context_reused_and_real_control_proof_not_relabelled(self):
  with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
   p=Path(tmp)/'journal';p.write_bytes(b'current durable state');digest=hashlib.sha256(p.read_bytes()).hexdigest();checks=[];opened=[]
   recovery=types.SimpleNamespace(check=lambda:checks.append(True));expected=dict(path=str(p),sha256=digest,bytes=p.stat().st_size)
   def acquire():opened.append(True);return recovery
   def checkpoint(actual,**kw):
    self.assertIs(actual,recovery)
    points=[dict(source=n,member=dict(bytes=Path(n).stat().st_size,sha256=hashlib.sha256(Path(n).read_bytes()).hexdigest()))for n in kw['paths']]
    return dict(manifest=dict(files=points),manifest_sha256='b'*64,index_reference=dict(selector='c'*64+'.sqlite'))
   proof=dict(format='vk-nightly-owner-controls-restore-acceptance-v1',independent_owner_controls_restore_verified=True)
   sdk=types.SimpleNamespace(checkpoint=checkpoint,verify_checkpoint=lambda *a,**k:dict(actual_independent_normal_restore=proof))
   callback,state=make_callback(sdk=sdk,acquire_recovery=acquire,controls={'B_root':'B:/vk-backups/test'},provider_placement={},dependencies={},resource_admission={},plan_sha256='a'*64,seed_checkpoint_sha256='d'*64,output_folder=tmp)
   request=dict(format='vk-reader-final-quiet-checkpoint-request-v1',operation='a'*32,files=[expected])
   with patch.object(Path,'is_relative_to',return_value=True),patch('vk_nightly_owner_callback.os.path.ismount',return_value=True):
    for _ in range(2):ref=callback(request)
   self.assertEqual(len(opened),1);self.assertIs(state['recovery'],recovery)
   receipt=json.loads(Path(ref['path']).read_bytes());self.assertTrue(receipt['actual_independent_normal_restore']['independent_owner_controls_restore_verified'])
   self.assertNotIn('independent_software_component_restore_verified',receipt['actual_independent_normal_restore'])
 def test_changed_quiet_file_refuses_before_opening_context(self):
  with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
   p=Path(tmp)/'journal';p.write_bytes(b'later state')
   def never():raise AssertionError('no context may be opened for stale input')
   callback,_=make_callback(sdk=None,acquire_recovery=never,controls={},provider_placement={},dependencies={},resource_admission={},plan_sha256='a'*64,seed_checkpoint_sha256='b'*64,output_folder=tmp)
   with self.assertRaisesRegex(ValueError,'changed'):callback(dict(format='vk-reader-final-quiet-checkpoint-request-v1',operation='a'*32,files=[dict(path=str(p),sha256='f'*64,bytes=1)]))
 def test_requested_SQL_cannot_be_silently_relabelled_as_control_metadata(self):
  with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
   p=Path(tmp)/'control';p.write_bytes(b'current')
   recovery=types.SimpleNamespace(check=lambda:None)
   cb,_=make_callback(sdk=None,acquire_recovery=lambda:recovery,controls={},provider_placement={},dependencies={},resource_admission={},plan_sha256='a'*64,seed_checkpoint_sha256='b'*64,output_folder=tmp)
   with self.assertRaisesRegex(ValueError,'SQL API callback'):cb(dict(format='vk-reader-final-quiet-checkpoint-request-v1',operation='a'*32,SQL_sources=['/actual/main.sqlite'],files=[dict(path=str(p),bytes=7,sha256=hashlib.sha256(b'current').hexdigest())]))
if __name__=='__main__':unittest.main()
