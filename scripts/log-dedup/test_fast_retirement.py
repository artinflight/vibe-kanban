import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import fast_retirement as fast
import log_dedup as logs
import reclaim


@unittest.skipUnless(os.environ.get('VK_DEDUP_TEST_ROOT'), 'requires owned mounted-SSD fixture root')
class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='retire-fixture-',dir=os.environ['VK_DEDUP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.archive=self.folder/'archive';self.primary=self.folder/'primary'
        session=str(uuid.uuid4());name=f'{session[:2]}/{session}/processes/{uuid.uuid4()}.jsonl'
        self.name=name;self.staging=self.archive/name;self.target=self.primary/name
        chunks=[];original=b'';created={}
        for target in [self.staging,self.target]:(target.parent/'.log-objects').mkdir(parents=True)
        for n in range(129):
            raw=('synthetic replica '+str(n)+'\\n').encode();original+=raw
            key=logs.sha(raw);chunks.append(dict(sha256=key,bytes=len(raw)))
            for target in [self.staging,self.target]:
                p=target.parent/'.log-objects'/(key+'.gz');p.write_bytes(gzip.compress(raw,mtime=0));p.chmod(0o600)
                if target==self.staging:created[str(p.relative_to(self.archive))]=logs.version(p.stat())
        body=logs.encode(dict(version=1,raw_bytes=len(original),sha256=logs.sha(original),chunks=chunks))
        self.staging.write_bytes(body);self.target.write_bytes(body)
        (self.folder/'STAGING_CREATED_IDENTITIES.private.json').write_text(json.dumps(created))
        self.plan={'files':[{'path':name}]};self.original=original;self.chunks=chunks
        self.kw=dict(complete_state={'complete':True,'outcome':'installed'},
            independent_B_proof={'independent_normal_B_full_EOF_hash_and_Linux_metadata_verified':True},
            normal_control_proof={'actual_independent_normal_restore':{'independent_owner_controls_restore_verified':True}})

    def run_retirement(self,guard=lambda:None):
        return fast.retire_new_staging_objects(self.plan,self.archive,self.primary,self.folder,guard,**self.kw)

    def objects(self):return list((self.staging.parent/'.log-objects').iterdir())

    def assert_primary(self):
        self.assertEqual(logs.reconstruct(self.target)['sha256'],logs.sha(self.original))
        self.assertEqual(len(list((self.target.parent/'.log-objects').iterdir())),129)

    def test_all_checks_remain_and_directory_flushes_precede_success(self):
        calls=[];original=reclaim.sync_directory
        def sync(path):calls.append(path);original(path)
        with patch.object(reclaim,'sync_directory',sync):result=self.run_retirement()
        self.assertEqual(result['duplicate_staging_objects_removed'],129)
        self.assertEqual(len(calls),3);self.assertEqual(self.objects(),[]);self.assert_primary()
        receipt=json.loads((self.folder/'STAGING_RETIREMENT_RESULT.private.json').read_text())
        self.assertTrue(receipt['complete'])

    def test_open_staging_consumer_prevents_its_deletion(self):
        path=self.staging.parent/'.log-objects'/(self.chunks[0]['sha256']+'.gz')
        with path.open('rb'):
            with self.assertRaises(BlockingIOError):self.run_retirement()
        self.assertEqual(len(self.objects()),129);self.assert_primary()

    def test_corrupt_primary_is_refused_before_deletion(self):
        path=self.target.parent/'.log-objects'/(self.chunks[0]['sha256']+'.gz');path.write_bytes(b'corrupt')
        with self.assertRaises((ValueError,OSError)):self.run_retirement()
        self.assertEqual(len(self.objects()),129)

    def test_valid_alternate_representation_is_retained_and_accounted(self):
        chunk=self.chunks[0];p=self.target.parent/'.log-objects'/(chunk['sha256']+'.gz')
        raw=gzip.decompress(p.read_bytes());p.write_bytes(gzip.compress(raw,mtime=1))
        staged=self.staging.parent/'.log-objects'/p.name;before=staged.read_bytes()
        result=self.run_retirement()
        self.assertEqual(result['duplicate_staging_objects_removed'],128)
        self.assertEqual(result['retained_alternate_representations'],1)
        self.assertEqual(result['retained_allocated_bytes'],staged.stat().st_blocks*512)
        self.assertEqual(staged.read_bytes(),before);self.assert_primary()
        plan=json.loads((self.folder/'STAGING_RETIREMENT_PLAN.private.json').read_text())
        self.assertNotIn(str(staged),[r['path'] for r in plan['objects']])
        self.assertEqual(plan['retained_objects'][0]['path'],str(staged))

    def test_corrupt_staging_is_not_retained_as_encoding_variant(self):
        p=self.objects()[0];p.write_bytes(b'corrupt')
        with self.assertRaises((ValueError,OSError)):self.run_retirement()
        self.assertEqual(len(self.objects()),129);self.assert_primary()

    def test_staging_hardlink_is_refused_before_retirement(self):
        os.link(self.objects()[0],self.folder/'foreign-link')
        with self.assertRaises(ValueError):self.run_retirement()
        self.assertEqual(len(self.objects()),129);self.assert_primary()

    def test_lost_custody_flushes_partial_removal_and_records_incomplete(self):
        calls=0
        def guard():
            nonlocal calls
            calls+=1
            if calls==136:raise ValueError('owner changed')
        with self.assertRaisesRegex(ValueError,'owner changed'):self.run_retirement(guard)
        receipt=json.loads((self.folder/'STAGING_RETIREMENT_RESULT.private.json').read_text())
        self.assertFalse(receipt['complete']);self.assertEqual(len(receipt['removed_paths']),6)
        self.assertEqual(len(self.objects()),123);self.assert_primary()

    def test_directory_sync_failure_cannot_publish_complete_receipt(self):
        with patch.object(reclaim,'sync_directory',side_effect=OSError('sync failed')):
            with self.assertRaisesRegex(OSError,'sync failed'):self.run_retirement()
        self.assertFalse((self.folder/'STAGING_RETIREMENT_RESULT.private.json').exists());self.assert_primary()

    def test_process_death_keeps_primary_and_no_false_success(self):
        child=os.fork()
        if child==0:
            calls=0
            def guard():
                nonlocal calls
                calls+=1
                if calls==136:os._exit(42)
            self.run_retirement(guard);os._exit(0)
        _,status=os.waitpid(child,0);self.assertEqual(os.waitstatus_to_exitcode(status),42)
        self.assertFalse((self.folder/'STAGING_RETIREMENT_RESULT.private.json').exists())
        self.assertTrue((self.folder/'STAGING_RETIREMENT_PLAN.private.json').exists())
        self.assert_primary();self.assertEqual(len(self.objects()),123)


if __name__=='__main__':unittest.main()
