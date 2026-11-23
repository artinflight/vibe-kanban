from concurrent.futures import Future
from pathlib import Path
import hashlib
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import parallel_prepare as pp


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        rows=[dict(names=[str(i)],workspace=str(uuid.uuid4()),raw_and_sidecar_bytes=100*1024**2)for i in range(7)]
        self.rows=rows;self.worker=SimpleNamespace(C={'source_root':str(self.root)},readers=SimpleNamespace(check=lambda:None),progress=lambda *a:None)
        self.pool=pp.PreparationPool(self.worker,{'batches':rows},self.root,
            dict(preparations=str(self.root/'prep'),hosts=['desktop'],source_dir='fixture',log_module='fixture'))
        self.addCleanup(self.pool.close)

    def test_only_one_job_per_host_and_two_batch_lookahead(self):
        futures=[]
        def submit(*args):
            future=Future();futures.append(future);return future
        with patch.object(self.pool.executor,'submit',side_effect=submit):
            self.pool.schedule(0);self.pool.schedule(1)
        self.assertEqual(list(self.pool.jobs),[2]);self.assertEqual(len(futures),1)
        futures[0].set_result(None)

    def test_small_or_already_prepared_batches_stay_local(self):
        self.rows[2]['raw_and_sidecar_bytes']=1000
        (self.root/'batch-0003').mkdir()
        future=Future();future.set_result(None)
        with patch.object(self.pool.executor,'submit',return_value=future):self.pool.schedule(0)
        self.assertEqual(list(self.pool.jobs),[4])
        self.assertIsNone(self.pool.payload(self.root/'current',['0'],self.rows[0]['workspace']))

    def test_failed_remote_is_never_redispatched_and_preserves_local_fallback(self):
        future=Future();future.set_exception(OSError('unavailable'))
        with patch.object(self.pool.executor,'submit',return_value=future):self.pool.schedule(0)
        self.assertIsNone(self.pool.payload(self.root/'current',['2'],self.rows[2]['workspace']))
        self.assertIn('desktop',self.pool.disabled)
        with patch.object(self.pool.executor,'submit',side_effect=AssertionError('duplicate dispatch')):self.pool.schedule(1)
        self.assertTrue((self.root/'prep/unavailable-2.json').exists())

    def test_handoff_preserves_disabled_hosts_without_dispatch(self):
        config=dict(preparations=str(self.root/'disabled'),hosts=['desktop'],source_dir='fixture',
                    log_module='fixture',initially_disabled=['desktop'])
        pool=pp.PreparationPool(self.worker,{'batches':self.rows},self.root,config)
        self.addCleanup(pool.close)
        with patch.object(pool.executor,'submit',side_effect=AssertionError('disabled host dispatched')):
            pool.schedule(0)
        self.assertEqual(pool.jobs,{});self.assertEqual(pool.disabled,{'desktop'})

    def test_foreign_prepared_workspace_is_refused(self):
        future=Future();future.set_result(None)
        with patch.object(self.pool.executor,'submit',return_value=future):self.pool.schedule(0)
        with self.assertRaisesRegex(ValueError,'workspace'):self.pool.payload(self.root/'current',['2'],str(uuid.uuid4()))

    def completed_handoff(self):
        folder=self.root/'prior';folder.mkdir(mode=0o700);job=str(uuid.uuid4());body=b'completed copied output'
        (folder/'output.tar').write_bytes(body);digest=hashlib.sha256(body).hexdigest()
        rows={'SNAPSHOT.private.json':dict(job_id=job,workspace=self.rows[2]['workspace'],files=[{'path':'2'}]),
              'DISPATCH_INTENT.private.json':dict(job_id=job,host='desktop'),
              'RECEIVED.private.json':dict(job_id=job,host='desktop',output_sha256=digest),
              'RESULT.json':dict(job_id=job,complete=True,output_sha256=digest)}
        for name,value in rows.items():pp.atomic(folder/name,value)
        return folder,dict(preparations=str(self.root/'adopted'),hosts=['desktop'],source_dir='fixture',log_module='fixture',
                           adopt_completed=[dict(batch=2,host='desktop',folder=str(folder))])

    def test_terminal_returned_work_is_adopted_without_another_dispatch(self):
        folder,config=self.completed_handoff()
        with patch.object(pp.remote_dispatch,'dispatch',side_effect=AssertionError('duplicate dispatch')):
            adopted=pp.PreparationPool(self.worker,{'batches':self.rows},self.root,config)
            self.addCleanup(adopted.close);adopted.schedule(0)
        self.assertEqual(list(adopted.jobs),[2]);self.assertTrue(adopted.jobs[2]['future'].done())
        self.assertEqual(adopted.busy,{'desktop':2})

    def test_handoff_rejects_changed_output_or_wrong_selection(self):
        folder,config=self.completed_handoff();(folder/'output.tar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'match handoff'):pp.PreparationPool(self.worker,{'batches':self.rows},self.root,config)

    def test_handoff_refuses_already_imported_work(self):
        folder,config=self.completed_handoff();pp.atomic(folder/'IMPORTED.private.json',{})
        with self.assertRaisesRegex(ValueError,'match handoff'):pp.PreparationPool(self.worker,{'batches':self.rows},self.root,config)


if __name__=='__main__':unittest.main()
