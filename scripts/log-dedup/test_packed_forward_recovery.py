import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest

import log_dedup as logs
from nightly_graph import canonical
from packed_forward_recovery import recover
import reclaim
import test_packed_admission as fixtures


class ForwardRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.t=fixtures.AdmissionTests();self.t.setUp();self.addCleanup(self.t.doCleanups)
        self.root=self.t.folder.parent;self.prepared=self.root/'forward';shutil.copytree(self.t.folder,self.prepared)
        self.group=copy.deepcopy(self.t.sealed);self.group['prepared']=str(self.prepared)
        self.group['plan']=dict(source_root='/fixture-only')
        self.outcome=dict(beneficial=True,group=self.group)
        old=self.root/'old-proof.json';old.write_bytes(canonical(self.t.proof))
        self.index=copy.deepcopy(self.t.index);self.index['checkpoints'][0].update(path=str(old),sha256=reclaim.file_hash(old))
        self.remote={'1'*64:(self.t.cp,self.t.bodies)};self.captures=[]
        def connect(name,reference,readonly):
            self.assertTrue(readonly);cp,bodies=self.remote[reference];return fixtures.RemoteFixture(cp,bodies)
        self.t.recovery.handle.db.client.connect=connect
    def capture(self,rows,name):
        self.captures.append(name);points=[];bodies={};back=[]
        for row in rows:
            path=Path(row['path']);body=path.read_bytes();self.assertEqual(logs.sha(body),row['sha256']);bodies[str(path)]=body
            member=dict(kind='file',bytes=len(body),sha256=logs.sha(body),**reclaim.metadata_for(path))
            points.append(dict(source=str(path),member=member));back.append(dict(source=str(path),bytes=len(body),sha256=logs.sha(body),Linux_metadata_verified=True))
        manifest=dict(files=points,operation='fixture',plan_sha256='0'*64);h=logs.sha(canonical(manifest));cp=dict(manifest=manifest,manifest_sha256=h,index_reference=dict(sha256=h))
        self.remote[h]=(cp,bodies)
        return dict(checkpoint=cp,actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True,normal_leased_consumer_entrypoint_verified=True,manifest_sha256=h,files=len(rows),raw_bytes=sum(r['bytes']for r in rows),actual_normal_reader_restore=back))
    def run_it(self):
        return recover(self.outcome,self.root/'recovery',self.index,'fixture',self.t.recovery,self.capture,guard=lambda:None)
    def test_identical_bodies_are_read_from_prior_B_without_recapture(self):
        adapter,proof=self.run_it();self.assertEqual(self.captures,['FORWARD_MAPPING'])
        self.assertEqual(proof['new_body_files'],0);self.assertEqual(proof['reused_body_files'],2)
        self.assertTrue(proof['admission']['actual_current_normal_B_bytes_verified']);self.assertFalse(proof['admission']['local_body_fallback'])
        self.assertEqual({k:v for k,v in adapter.mapping['prepared_metadata'][0]['metadata'].items()if k!='atime_ns'}, {k:v for k,v in reclaim.metadata_for(Path(adapter.mapping['prepared_metadata'][0]['path'])).items()if k!='atime_ns'})
        with self.assertRaises(FileExistsError):self.run_it()
        self.assertEqual(self.captures,['FORWARD_MAPPING'])
    def test_corrupt_existing_remote_body_cannot_use_good_local_alias(self):
        self.t.bodies[str(self.t.path)]=b'x'*len(self.t.bodies[str(self.t.path)])
        with self.assertRaisesRegex(ValueError,'EOF differs'):self.run_it()
        self.assertEqual(reclaim.file_hash(self.prepared/'history.jsonl'),self.group['files'][0]['packed_sha256'])
        self.assertFalse((self.root/'recovery/RECOVERED.json').exists())
    def test_nonbeneficial_original_never_starts_capture(self):
        self.outcome['beneficial']=False
        with self.assertRaisesRegex(ValueError,'Nonbeneficial'):self.run_it()
        self.assertEqual(self.captures,[])
    def test_new_manifest_is_captured_but_unchanged_pack_is_reused(self):
        # Equivalent logical history with a different valid JSON representation.
        p=self.prepared/'history.jsonl';raw=p.read_bytes();p.write_bytes(raw.replace(b'"version":2',b'"version": 2'))
        self.group['files'][0]['packed_sha256']=reclaim.file_hash(p)
        _,proof=self.run_it();self.assertEqual(self.captures,['PACKED_FORWARD_0000','FORWARD_MAPPING'])
        self.assertEqual(proof['new_body_files'],1);self.assertEqual(proof['reused_body_files'],1)


if __name__=='__main__':unittest.main()
