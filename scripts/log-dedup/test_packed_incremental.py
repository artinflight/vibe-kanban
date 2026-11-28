"""Real SQL/files/kernel leases with explicitly isolated process/remote fixtures."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import automatic
import incremental
import log_dedup as logs
import packed_incremental as subject
import packed_objects as packed
from packed_live import Adapter as LiveAdapter
from packed_publication import PackedBatch
from packed_recovery import write_new
from scoped_fence import ClosedLogFence
import test_packed_forward_recovery as remote_fixture
import test_packed_publication as publication_fixture


class PackedDailyTests(unittest.TestCase):
    def setUp(self):
        self.t=publication_fixture.PublicationTests();self.t.setUp();self.addCleanup(self.t.doCleanups)
        self.remote=remote_fixture.ForwardRecoveryTests();self.remote.setUp();self.addCleanup(self.remote.doCleanups)
        self.state=self.t.base/'state';(self.state/'runs').mkdir(parents=True)
        self.cfg=dict(state_root=str(self.state),maximum_run_files=10,maximum_run_bytes=4*1024**2,
                      maximum_batch_files=2,maximum_batch_bytes=1024**2,maximum_run_seconds=60,minimum_closed_age_seconds=0)
        self.adapter=object.__new__(subject.Adapter)
        a=self.adapter;a.config=self.cfg;a.c=dict(reserve_bytes=3*1024**3,reader_artifacts={});a.root=self.t.root
        a.readers=SimpleNamespace(source=self.t.root,check=lambda:None);a.databases=dict(main=str(self.t.db),protected=str(self.t.db))
        a.catalog_pointer=self.state/'PACKED_CATALOG.private.json';a.index=self.remote.index;a.last_index=None
        a.started=None;a.recovery=self.remote.t.recovery;a.used=0
        def begin(folder,operation):a.folder=folder;a.operation=operation
        a.begin=begin
        self.fail_capture=None
        def capture(folder,rows,name):
            if name==self.fail_capture:raise RuntimeError('uncertain fixture capture')
            return self.remote.capture(rows,name)
        a.capture=capture
        t=self.t
        class FixtureLive(LiveAdapter):
            def __init__(self,readers,recovery,capture,**kwargs):
                self.readers,self.recovery,self.capture=readers,recovery,capture
            def convert(self,group,journal,progress):
                fence=ClosedLogFence(root=t.root,database=t.db,workspace_id=t.workspace,plan=group['plan'],roster=t.roster)
                batch=PackedBatch(group['plan'],group['prepared'],journal,fence,t.readers,self.recovery,reserve_bytes=0)
                with fence.held():
                    batch.publish(progress);self.verify_published(group,journal);return batch.retire(progress)
            def verify_published(self,group,journal):
                versions={}
                for r in group['plan']['files']:
                    path=t.root/r['path'];proof=packed.verify(path)
                    if (proof['sha256'],proof['raw_bytes'])!=(r['sha256'],r['raw_bytes']):raise ValueError('fixture EOF')
                    versions[str(path)]=logs.version(path.stat())
                proof=dict(plan_sha256=group['plan_sha256'],files=len(versions),versions=versions,full_EOF_verified=True)
                self._unchanged(group,proof);write_new(journal/'READER_EOF.json',proof);return proof
        self.patch=patch.object(subject,'LiveAdapter',FixtureLive);self.patch.start();self.addCleanup(self.patch.stop)
        self.third=self.t.root/self.t.names[2];self.third.with_suffix('.capture.json').write_text('{"capture_state":"pending"}')

    def run_daily(self):return incremental.execute(self.cfg,self.adapter)

    def test_real_publication_and_monitoring_then_reuse_without_body_capture(self):
        result=self.run_daily();proof=automatic.verify_run(Path(result['folder']))
        self.assertEqual(proof['converted_files'],2);self.t.exact()
        self.assertFalse(list(self.t.root.rglob('*.gz')))
        first_names=list(self.remote.captures);self.assertIn('PACKED_FORWARD_0000',first_names)
        self.third.with_suffix('.capture.json').write_text('{"capture_state":"closed"}')
        result=self.run_daily();self.assertEqual(automatic.verify_run(Path(result['folder']))['converted_files'],1)
        second_names=self.remote.captures[len(first_names):];self.assertNotIn('PACKED_FORWARD_0000',second_names)
        self.assertEqual(packed.verify(self.third)['raw_bytes'],len(self.t.raw))
        self.assertEqual(self.run_daily()['selected_files'],0)
        self.assertFalse((self.state/'ACTIVE.private.json').exists())

    def test_failed_result_recovery_keeps_review_hold_after_publication(self):
        self.fail_capture='BATCH_RESULT'
        with self.assertRaisesRegex(RuntimeError,'uncertain'):self.run_daily()
        self.t.exact();before=len(self.remote.captures)
        self.assertTrue((self.state/'ACTIVE.private.json').exists());self.assertFalse(self.adapter.catalog_pointer.exists())
        with self.assertRaisesRegex(ValueError,'no replay'):self.run_daily()
        self.assertEqual(len(self.remote.captures),before)

    def test_session_boundaries_survive_existing_workspace_batch_interface(self):
        rows=self.adapter.inventory()['eligible']
        other=json.loads(json.dumps(rows[0]));other['path']='zz/another-session/processes/another.jsonl'
        groups=subject.batches([rows[0],other],maximum_files=2,maximum_bytes=1024**2)
        self.assertEqual(len(groups),2);self.assertEqual({g['workspace']for g in groups},{self.t.workspace})


if __name__=='__main__':unittest.main()
