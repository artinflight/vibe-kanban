import gzip
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import uuid

import log_dedup as logs
import remote_pack
import remote_preparation as prep


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('VK_DEDUP_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.root=self.base/'sessions';self.root.mkdir();session=str(uuid.uuid4())
        self.names=[f'{session[:2]}/{session}/processes/{uuid.uuid4()}.jsonl' for _ in range(2)]
        self.raw=b'{"Stdout":"copied closed history\\n"}\n'*12000
        for name in self.names:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(self.raw);p.chmod(0o600)
            p.with_suffix('.capture.json').write_text('{"capture_state":"closed"}\n')
        self.job=self.base/'job';self.workspace=str(uuid.uuid4())
        self.snapshot=prep.snapshot(self.root,self.names,self.workspace,self.job,lambda:None)
        self.destination=self.base/'archive'

    def remote(self):
        return remote_pack.run(self.job,self.snapshot['request_sha256'],minimum_free=0)

    def rewrite_output(self,mutate):
        rows=[]
        with tarfile.open(self.job/'output.tar') as t:
            for m in t:rows.append((m.name,t.extractfile(m).read()))
        with tarfile.open(self.job/'output.tar','w') as t:
            for name,data in mutate(rows):remote_pack.member(t,name,data)
        result=json.loads((self.job/'RESULT.json').read_text());result['output_sha256']=remote_pack.digest(self.job/'output.tar')
        (self.job/'RESULT.json').write_text(json.dumps(result))

    def test_remote_round_trip_matches_existing_local_plan(self):
        self.remote();expected=logs.scan(self.root,self.names)
        actual=prep.import_archive(self.job,self.destination,lambda:None)
        self.assertEqual(actual,expected)
        for name in self.names:self.assertEqual(logs.reconstruct(self.destination/name)['sha256'],logs.sha(self.raw))
        self.assertTrue(json.loads((self.job/'IMPORTED.private.json').read_text())['all_bodies_verified'])

    def test_existing_primary_physical_bytes_are_preserved_even_if_encoding_differs(self):
        self.remote()
        block=next(logs.chunks(io.BytesIO(self.raw)));key=logs.sha(block)
        primary=(self.root/self.names[0]).parent/'.log-objects'/(key+'.gz');primary.parent.mkdir();primary.write_bytes(gzip.compress(block,compresslevel=9,mtime=17))
        before=primary.read_bytes();prep.import_archive(self.job,self.destination,lambda:None)
        self.assertEqual(primary.read_bytes(),before)
        self.assertEqual(((self.destination/self.names[0]).parent/'.log-objects'/primary.name).read_bytes(),before)

    def test_source_change_with_restored_mtime_is_refused(self):
        self.remote();p=self.root/self.names[0];st=p.stat();p.write_bytes(b'x'+self.raw[1:]);os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'identity changed'):prep.import_archive(self.job,self.destination,lambda:None)
        self.assertFalse(self.destination.exists())

    def test_sidecar_change_is_refused(self):
        self.remote();(self.root/self.names[0]).with_suffix('.capture.json').write_text('{"capture_state":"pending"}')
        with self.assertRaisesRegex(ValueError,'sidecars changed'):prep.import_archive(self.job,self.destination,lambda:None)

    def test_remote_output_checksum_corruption_is_refused(self):
        self.remote()
        with (self.job/'output.tar').open('r+b') as f:f.write(b'bad')
        with self.assertRaisesRegex(ValueError,'transfer checksum'):prep.import_archive(self.job,self.destination,lambda:None)

    def test_remote_path_traversal_is_refused_without_external_write(self):
        self.remote();self.rewrite_output(lambda rows:[('../outside',b'bad')]+rows)
        with self.assertRaisesRegex(ValueError,'unexpected remote member'):prep.import_archive(self.job,self.destination,lambda:None)
        self.assertFalse((self.base/'outside').exists())

    def test_duplicate_remote_member_is_refused(self):
        self.remote();self.rewrite_output(lambda rows:rows+[rows[0]])
        with self.assertRaisesRegex(ValueError,'duplicate'):prep.import_archive(self.job,self.destination,lambda:None)

    def test_remote_chunk_corruption_is_refused_even_with_new_transfer_hash(self):
        self.remote();self.rewrite_output(lambda rows:[(rows[0][0],gzip.compress(b'wrong bytes'))]+rows[1:])
        with self.assertRaisesRegex(ValueError,'invalid remote object'):prep.import_archive(self.job,self.destination,lambda:None)

    def test_preparation_cannot_be_replayed_or_overwrite_a_destination(self):
        self.remote()
        with self.assertRaises(FileExistsError):self.remote()
        prep.import_archive(self.job,self.destination,lambda:None)
        with self.assertRaises((FileExistsError,ValueError)):prep.import_archive(self.job,self.destination,lambda:None)

    def test_disk_admission_refuses_before_starting(self):
        with self.assertRaisesRegex(ValueError,'free-space'):remote_pack.run(self.job,self.snapshot['request_sha256'],minimum_free=10**20)
        self.assertFalse((self.job/'STARTED.json').exists())


if __name__=='__main__':unittest.main()
