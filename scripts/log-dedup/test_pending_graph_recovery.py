import hashlib
from pathlib import Path
import unittest

import checkpoint_control as cc
import controlled_conversion as driver
import pending_graph_recovery as recovery
from test_checkpoint_control import CheckpointTests

class PendingTests(unittest.TestCase):
    def setUp(self):
        self.f=CheckpointTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.folder=self.root/'batch-0001';self.folder.mkdir(mode=0o700)
        (self.folder/'graph-recovery').mkdir(mode=0o700)
        source=self.f.source/'next';source.write_text('original bytes');st=source.stat()
        plan=dict(source_root=str(self.f.source),files=[dict(path='next',sha256=driver.sha(source),
            identity=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns])])
        for name in ['PLAN.private.json','PLAN_ALL.private.json']:cc.atomic(self.folder/name,plan)
        for name in ['PREPARED.private.json','PREPARATION_COMPLETE.private.json','CONFIGURATION.private.json','B_REQUEST.private.json']:
            cc.atomic(self.folder/name,{})
        cc.atomic(self.folder/'NONBENEFICIAL.private.json',[])
        owner=dict(plan_sha256=hashlib.sha256(cc.canonical(plan)).hexdigest())
        cc.atomic(self.folder/'OWNER.private.json',owner)
        cc.atomic(self.folder/'OWNER_RESUME3.private.json',dict(owner,archive_resume_attempt='recovery1'))
        cc.atomic(self.folder/'graph-recovery/graph-checkpoint-0.json',{'retained':True})
        self.proof=recovery.evidence(self.root,1)

    def test_default_refuses_partial_but_exact_proof_preserves_committed_prefix(self):
        with self.assertRaisesRegex(ValueError,'unreconciled'):driver.checkpoint(self.root,True)
        cp=driver.checkpoint(self.root,True,pending_graph=self.proof)
        self.assertEqual(cp['next_batch'],1);self.assertEqual(cp['completed_files'],2)
        self.assertEqual(cp['checkpoint_sha256'],driver.checkpoint(self.root,trusted_prefix=cp,pending_graph=self.proof)['checkpoint_sha256'])

    def test_no_existing_installation_can_be_adopted(self):
        (self.folder/'journal').mkdir()
        with self.assertRaisesRegex(ValueError,'publication'):recovery.inspect(self.root,self.proof)

    def test_changed_sources_receipts_or_consumed_suffix_are_refused(self):
        (self.f.source/'next').write_text('changed')
        with self.assertRaisesRegex(ValueError,'identity'):recovery.inspect(self.root,self.proof)

    def test_new_receipt_or_prior_resume_carrier_is_not_replayed(self):
        (self.folder/'graph-recovery/pack-1-recovery1').mkdir()
        with self.assertRaisesRegex(ValueError,'already exists'):recovery.inspect(self.root,self.proof)

    def test_owner_mutation_is_refused_even_with_rebuilt_proof(self):
        owner=cc.read(self.folder/'OWNER_RESUME3.private.json');owner['database']='other'
        cc.atomic(self.folder/'OWNER_RESUME3.private.json',owner)
        with self.assertRaisesRegex(ValueError,'more than'):recovery.evidence(self.root,1)

if __name__=='__main__':unittest.main()
