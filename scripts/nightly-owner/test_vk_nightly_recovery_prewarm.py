import contextlib,fcntl,hashlib,io,os,unittest
from vk_nightly_recovery_prewarm import PrewarmedRecovery,SEALS

class Original:
 location='desktop:B:/vk-backups/test';prefix='sessions/'
 def __init__(self,data=b'a'*3145728):self.data=data;self.opens=0;self.checks=0;self.failed=False
 def check(self):
  self.checks+=1
  if self.failed:raise OSError('actual B STOP/lease failure')
 @contextlib.contextmanager
 def open_original(self,name,sha):
  self.check();self.opens+=1;yield io.BytesIO(self.data);self.check()

class PrewarmTests(unittest.TestCase):
 def request(self,o):return [dict(relative='original',bytes=len(o.data),sha256=hashlib.sha256(o.data).hexdigest())]
 def test_actual_B_only_once_then_sealed_RAM_replay_keeps_same_context_checks(self):
  o=Original();admitted=[]
  with PrewarmedRecovery(o,maximum_bytes=len(o.data),admit=admitted.append)as p:
   p.populate(self.request(o));fd=p.entries['original'][0]
   self.assertEqual(fcntl.fcntl(fd,fcntl.F_GET_SEALS)&SEALS,SEALS)
   for _ in range(2):
    with p.open_original('original',self.request(o)[0]['sha256'])as s:
     digest=hashlib.sha256()
     while block:=s.read(1048576):digest.update(block)
    self.assertEqual(digest.hexdigest(),self.request(o)[0]['sha256'])
   self.assertEqual(o.opens,1);self.assertEqual(admitted,[len(o.data)]);self.assertGreater(o.checks,10)
   # Linux may update timestamps even for a refused sealed-file write; such
   # tampering correctly invalidates subsequent replay identity checks.
   with self.assertRaises(OSError):os.pwrite(fd,b'X',0)
  with self.assertRaises(OSError):os.fstat(fd)
 def test_real_B_stop_still_blocks_cached_replay(self):
  o=Original(b'abc')
  with PrewarmedRecovery(o,maximum_bytes=3,admit=lambda _:None)as p:
   p.populate(self.request(o));o.failed=True
   with self.assertRaisesRegex(OSError,'STOP'):p.check()
 def test_bad_body_or_insufficient_admission_never_yields_ready(self):
  o=Original(b'abc')
  with PrewarmedRecovery(o,maximum_bytes=3,admit=lambda _:None)as p:
   r=self.request(o);r[0]['sha256']='0'*64
   with self.assertRaisesRegex(ValueError,'EOF'):p.populate(r)
   with self.assertRaisesRegex(ValueError,'incomplete'):
    with p.open_original('original','0'*64):pass
  with PrewarmedRecovery(o,maximum_bytes=2,admit=lambda _:None)as p:
   with self.assertRaisesRegex(ValueError,'peak'):p.populate(self.request(o))
  self.assertEqual(o.opens,1)
 def test_partial_replay_is_not_verified_and_wrong_version_rejected(self):
  o=Original(b'abc')
  with PrewarmedRecovery(o,maximum_bytes=3,admit=lambda _:None)as p:
   p.populate(self.request(o))
   with self.assertRaisesRegex(ValueError,'EOF'):
    with p.open_original('original',self.request(o)[0]['sha256'])as s:s.read(1)
   with self.assertRaisesRegex(ValueError,'version'):
    with p.open_original('original','0'*64):pass
if __name__=='__main__':unittest.main()
