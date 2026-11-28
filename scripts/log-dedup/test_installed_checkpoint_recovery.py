import contextlib
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import checkpoint_control as cc
import controlled_conversion as driver
import installed_checkpoint_recovery as recovery
from test_checkpoint_control import CheckpointTests as Fixture


class InstalledRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.folder=self.root/'batch-0001';self.folder.mkdir(mode=0o700)
        (self.folder/'journal').mkdir();(self.folder/'archive').mkdir();(self.folder/'graph-recovery').mkdir()
        self.output=self.root/'recovery';self.output.mkdir()
        source=self.f.source/'next';source.write_bytes(b'installed manifest');s=source.stat()
        (self.folder/'archive/next').write_bytes(source.read_bytes())
        self.plan=dict(source_root=str(self.f.source),files=[dict(path='next',raw_bytes=100,sidecars=[])])
        digest=hashlib.sha256(cc.canonical(self.plan)).hexdigest()
        for name in recovery.NAMES:cc.atomic(self.folder/name,{})
        cc.atomic(self.folder/'PLAN.private.json',self.plan)
        cc.atomic(self.folder/'NONBENEFICIAL.private.json',[])
        self.cfg=dict(plan_sha256=digest)
        cc.atomic(self.folder/'OWNER_EFFECTIVE.private.json',self.cfg)
        cc.atomic(self.folder/'journal/state.json',dict(complete=True,outcome='installed',archive=str(self.folder/'archive'),
            plan_sha256=digest,files={'next':dict(state='installed',installed_identity=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns],manifest_sha256=driver.sha(source))}))
        cc.atomic(self.folder/'CONVERSION.private.json',dict(complete=True,outcome='installed',files=1))
        self.original=dict(independent_normal_B_full_EOF_hash_and_Linux_metadata_verified=True)
        self.dynamic=dict(checkpoint={'retained':'epoch'},actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True))
        cc.atomic(self.folder/'ORIGINAL_B_PROOF.private.json',self.original)
        cc.atomic(self.folder/'GRAPH_PROOF.private.json',dict(independent_backup_verified=True))
        cc.atomic(self.folder/'DYNAMIC_RECOVERY.private.json',self.dynamic)
        cc.atomic(self.folder/'graph-recovery/graph-checkpoint-0.json',dict(retained=True))
        cc.atomic(self.root/'FAILURE.private.json',dict(operation=self.f.committed['operation'],type='ValueError',error=recovery.ERROR,completed_batches=1))
        self.failure_sha=driver.sha(self.root/'FAILURE.private.json')

    def inspect(self):return recovery.inspect(self.root,self.failure_sha)

    def test_exact_fully_installed_tail_is_eligible_without_conversion(self):
        self.assertEqual(self.inspect()['files'],1)
        self.assertFalse((self.folder/'RESULT.private.json').exists())

    def test_changed_installed_manifest_is_rejected(self):
        (self.f.source/'next').write_bytes(b'new current data')
        with self.assertRaisesRegex(ValueError,'manifest changed'):self.inspect()

    def test_corrupt_prefix_is_not_hidden_by_tail_recovery(self):
        (self.f.source/'log').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'prefix qualification failed'):self.inspect()

    def test_any_retirement_start_or_later_preparation_requires_reconciliation(self):
        cc.atomic(self.folder/'STAGING_RETIREMENT_PLAN.private.json',{})
        with self.assertRaisesRegex(ValueError,'already started'):self.inspect()
        (self.folder/'STAGING_RETIREMENT_PLAN.private.json').unlink()
        (self.root/'batch-0002').mkdir()
        with self.assertRaisesRegex(ValueError,'later preparation'):self.inspect()

    def test_missing_original_or_dynamic_proof_refuses_recovery(self):
        cc.atomic(self.folder/'ORIGINAL_B_PROOF.private.json',dict(independent_normal_B_full_EOF_hash_and_Linux_metadata_verified=False))
        with self.assertRaisesRegex(ValueError,'proofs incomplete'):self.inspect()

    def test_incomplete_conversion_or_wrong_scope_is_rejected(self):
        cc.atomic(self.folder/'CONVERSION.private.json',dict(complete=False,outcome='installed',files=1))
        with self.assertRaisesRegex(ValueError,'not fully installed'):self.inspect()

    def fake_worker(self):
        before=dict(selected_log_allocated_bytes=1000,referenced_object_allocated_bytes=100,directory_allocated_bytes=10)
        cc.atomic(self.folder/'ALLOCATION_BEFORE.private.json',before)
        metadata=dict(mode=384,uid=1000,gid=1000,mtime_ns=1,xattrs={})
        cc.atomic(self.folder/'B_REQUEST.private.json',dict(files=[dict(bytes=100,normal_namespace_name='next',Linux_metadata=metadata)]))
        retained=SimpleNamespace(handle=SimpleNamespace(index=SimpleNamespace(entry=lambda _:metadata)),provider_placement={})
        custody=dict(reader_guard=lambda:None,recovery=retained,archive_recovery=object())
        worker=SimpleNamespace(online_owner=SimpleNamespace(admit_online=lambda *a,**k:contextlib.nullcontext(custody)),
            graph=SimpleNamespace(inventory=lambda *a:{},verify_provider=lambda *a,**k:dict(independent_backup_verified=True)),
            ReplayGroups=lambda *a:contextlib.nullcontext(SimpleNamespace(populate=lambda:None)),admit_ram=lambda _:None,
            support=SimpleNamespace(verify_restored_RAM=lambda *a:self.original,rust_readback=Mock()),
            C={'reader_probe':{'path':'probe','sha256':'hash'}},progress=lambda *a:None,
            hook=SimpleNamespace(verify_checkpoint=Mock(return_value=self.dynamic)),
            normal=dict(B_controls={},dependencies={},host_admission={}),
            retire_local_staging=Mock(return_value={'all_primary_objects_preserved':True}),
            physical_accounting=SimpleNamespace(measure=lambda *a,**k:{'allocated_bytes':80}),
            readers=SimpleNamespace(check=lambda:None),allocation_counts=lambda *a:dict(selected_log_allocated_bytes=40,referenced_object_allocated_bytes=30,directory_allocated_bytes=10))
        return worker

    def test_recovery_reopens_controls_and_uses_original_before_without_republication(self):
        worker=self.fake_worker();value=self.inspect();old={n:(self.folder/n).read_bytes() for n in recovery.NAMES}
        result=recovery.finish_batch(SimpleNamespace(w=worker),value,self.output)
        self.assertEqual(result['allocated_release_including_objects_and_directories'],1030)
        worker.support.rust_readback.assert_called_once();worker.retire_local_staging.assert_called_once()
        self.assertEqual(worker.hook.verify_checkpoint.call_args.args[4],self.dynamic['checkpoint'])
        for n,raw in old.items():self.assertEqual((self.folder/n).read_bytes(),raw)

    def test_failed_control_restore_cannot_retire_or_publish_success(self):
        worker=self.fake_worker();worker.hook.verify_checkpoint.side_effect=ValueError('B restore failed')
        with self.assertRaisesRegex(ValueError,'B restore failed'):
            recovery.finish_batch(SimpleNamespace(w=worker),self.inspect(),self.output)
        worker.retire_local_staging.assert_not_called()
        self.assertFalse((self.folder/'RESULT.private.json').exists())

    def test_freshly_changed_receipt_prevents_retirement(self):
        worker=self.fake_worker();value=self.inspect()
        cc.atomic(self.folder/'DYNAMIC_RECOVERY.private.json',dict(self.dynamic,changed=True))
        with self.assertRaisesRegex(ValueError,'source pin changed'):
            recovery.finish_batch(SimpleNamespace(w=worker),value,self.output)
        worker.retire_local_staging.assert_not_called()

if __name__=='__main__':unittest.main()
