import hashlib,tempfile,unittest
from pathlib import Path
from vk_nightly_software_component import validate_request,qualify_sample
class SoftwareRequestTests(unittest.TestCase):
 def test_real_finite_source_hash_and_version_without_global_scope(self):
  with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
   p=Path(tmp)/'source';p.write_bytes(b'exact released software')
   r={'files':[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())]}
   s=qualify_sample(r,guard=lambda:None)
   self.assertEqual(s['files_sampled'],1);self.assertEqual(s['global_source_paths_scanned'],0)
   self.assertFalse(s['kernel_journal_coverage_claimed']);p.write_bytes(b'changed')
   with self.assertRaises(ValueError):qualify_sample(r,guard=lambda:None)
 def test_invalid_duplicate_symlink_and_oversize_scope_fail(self):
  with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
   p=Path(tmp)/'source';p.touch();l=Path(tmp)/'alias';l.symlink_to(p)
   row=dict(path=str(p),bytes=0,sha256=hashlib.sha256(b'').hexdigest())
   for files in [[],[row,row],[dict(row,path=str(l))],[dict(row,bytes=512*1024**2+1)],[dict(row,sha256='x'*64)]]:
    with self.subTest(files=files):
     with self.assertRaises(ValueError):validate_request({'files':files})
 def test_SQLite_retained_body_pair_lookup_uses_VALUES_rowset(self):
  import sqlite3
  with sqlite3.connect(':memory:')as db:
   db.execute('create table completed_file_carriers(sha256 text,bytes int,row blob,history_name text,history_version text)')
   db.execute("insert into completed_file_carriers values('a',7,X'01','old','version')")
   batch=[('a',7),('b',8)];place=','.join('(?,?)'for _ in batch)
   found=db.execute('select sha256,bytes,row,history_name,history_version from completed_file_carriers where (sha256,bytes) in (values '+place+')',tuple(v for pair in batch for v in pair)).fetchall()
   self.assertEqual(len(found),1);self.assertEqual(found[0][0:2],('a',7))
if __name__=='__main__':unittest.main()
