import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_objects import ObjectClient
from vk_nightly_sql_point import capture_SQL_point


class SQLPointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source.sqlite';self.store=self.root/'objects';self.store.mkdir()
        with sqlite3.connect(self.source) as source:
            source.execute('create table retained(value)');source.execute("insert into retained values('saved')")
        folder=str(Path(__file__).parent)
        code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.store))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536,retained_SQL_root='+repr(str(self.root))+')'
        self.p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.close)
        self.client=ObjectClient(self.p.stdout,self.p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)

    def close(self):
        if not self.p.stdin.closed:self.p.stdin.close()
        if self.p.poll() is None:self.p.wait(timeout=5)
        self.p.stdout.close();self.p.stderr.close()

    def capture(self,retained=lambda sha,size:None,**overrides):
        args=dict(allowed_sources={str(self.source)},guard=lambda:None,retained_by_sha=retained,ram_root=self.root,
                  maximum_image_bytes=1024**2,chunk_bytes=4096,timeout_seconds=15)
        args.update(overrides);return capture_SQL_point(self.source,self.client,**args)

    def test_actual_SQL_API_chunked_B_restore_integrity_metadata_and_no_OS_staging(self):
        result=self.capture()
        self.assertEqual(result['status'],'consistent_SQL_point_verified')
        self.assertEqual(result['independent']['integrity'],'ok')
        self.assertTrue(result['independent']['independent_Linux_metadata_verified'])
        self.assertEqual(list(self.root.glob('nightly-sql-*.sqlite')),[])
        self.assertFalse(result['baseline_accepted'])

    def test_fresh_cohort_runs_API_but_reuses_identical_accepted_body_without_copy(self):
        import io,json
        first=self.capture(cohort_id='a'*64)
        second=self.capture(cohort_id='b'*64)
        self.assertEqual(first['SQL_cohort_id'],'a'*64);self.assertEqual(second['SQL_cohort_id'],'b'*64)
        self.assertGreaterEqual(second['original_source_API_point_at'],first['original_source_API_point_at'])
        self.assertEqual(first['sha256'],second['sha256'])
        self.assertEqual(second['new_B_encoded_payload_bytes'],0)
        self.assertEqual([s['selector'] for s in first['member']['segments']],[s['selector'] for s in second['member']['segments']])
        accepted=io.BytesIO();self.client.verify(second['B_acceptance_object'],accepted)
        self.assertEqual(json.loads(accepted.getvalue())['SQL_cohort_id'],'b'*64)

    def test_another_cohort_cannot_relabel_retained_API_or_durable_layout(self):
        saved={}
        def stop(value):
            saved.update(value)
            if 'layout' in value:raise RuntimeError('retained current API layout')
        with self.assertRaises(RuntimeError):self.capture(cohort_id='a'*64,on_prepared=stop)
        before=self.client.payload_bytes_sent
        for layout in (None,{k:saved[k] for k in ('layout','manifest')}):
            for another in ('b'*64,None):
                with self.assertRaisesRegex(ValueError,'another qualification cohort'):
                    self.capture(cohort_id=another,resume=saved['captured_RAM_point'],resume_layout=layout)
        self.assertEqual(self.client.payload_bytes_sent,before)
        self.assertTrue(Path(saved['captured_RAM_point']['working_RAM_path']).exists())
        result=self.capture(cohort_id='a'*64,resume=saved['captured_RAM_point'],resume_layout={k:saved[k] for k in ('layout','manifest')})
        self.assertEqual(result['SQL_cohort_id'],'a'*64)
        self.assertTrue(result['recovered_from_durable_B_layout']);self.assertEqual(result['new_B_encoded_payload_bytes'],0)

    def test_WAL_committed_rows_are_captured_through_SQL_API(self):
        live=sqlite3.connect(self.source);self.addCleanup(live.close)
        live.execute('pragma journal_mode=WAL');live.execute('pragma wal_autocheckpoint=0')
        live.execute("insert into retained values('only in WAL')");live.commit()
        result=self.capture()
        expected=self.root/'expected.sqlite'
        with sqlite3.connect(expected) as out:
            out.execute('pragma journal_mode=OFF');live.backup(out)
        self.assertEqual(result['sha256'],hashlib.sha256(expected.read_bytes()).hexdigest())
        self.assertEqual(result['independent']['integrity'],'ok')

    def test_exact_completed_image_is_probed_reused_without_new_SQL_payload(self):
        image=self.root/('sqlite-consistent-'+'a'*32+'.sqlite')
        with sqlite3.connect(self.source) as src,sqlite3.connect(image) as dst:
            dst.execute('pragma journal_mode=OFF');src.backup(dst)
        raw=image.read_bytes();sha=hashlib.sha256(raw).hexdigest();s=image.stat()
        proof=dict(sha256=sha,bytes=len(raw),integrity='ok')
        old=dict(sha256=sha,bytes=len(raw),name=image.name,native_path=str(image),
            file_identity=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns],proof={'native':proof,'Linux_reopen':proof})
        result=self.capture(lambda h,n:old if (h,n)==(sha,len(raw)) else None)
        self.assertTrue(result['independent']['reused_accepted_independent_SQL_image'])
        self.assertEqual(result['new_B_encoded_payload_bytes'],0)
        self.assertEqual(image.stat().st_ino,s.st_ino)

    def test_image_larger_than_actual_admission_creates_no_RAM_or_B_copy(self):
        result=self.capture(maximum_image_bytes=1)
        self.assertEqual(result['status'],'larger_SQL_working_window_required')
        self.assertEqual(list(self.root.glob('nightly-sql-*')),[])
        self.assertEqual(self.client.payload_bytes_sent,0)

    def test_source_substitution_after_API_is_not_accepted_as_the_original_source(self):
        replacement=self.root/'replacement.sqlite'
        with sqlite3.connect(replacement) as source:source.execute('create table different(value)')
        calls=0
        def guard():
            nonlocal calls
            calls+=1
            # The initial host check and backup progress precede the final
            # source-identity bracket. Replace only the fixture source.
            if calls==3:replacement.replace(self.source)
        with self.assertRaisesRegex(ValueError,'source inode/metadata replaced') as failed:
            self.capture(guard=guard)
        self.assertEqual(self.client.payload_bytes_sent,0)
        self.assertTrue(Path(failed.exception.nightly_SQL_working_path).exists())

    def test_interrupted_point_preserves_own_unaccepted_working_image(self):
        def fail(value):
            if 'layout' in value:raise RuntimeError('injected after B chunks/prepared manifest')
        with self.assertRaises(RuntimeError) as failed:self.capture(on_prepared=fail)
        self.assertTrue(Path(failed.exception.nightly_SQL_working_path).exists())
        self.assertGreater(len(list(self.store.glob('*.accepted.json'))),0)

    def test_resume_uses_retained_API_point_without_connecting_to_live_source_or_recopying_chunks(self):
        captured=[]
        def fail(value):
            if 'captured_RAM_point' in value:captured.append(value['captured_RAM_point'])
            if 'layout' in value:raise RuntimeError('stop after completed chunks')
        with self.assertRaises(RuntimeError):self.capture(on_prepared=fail)
        with sqlite3.connect(self.source) as source:source.execute("insert into retained values('later live write')")
        uploaded=self.client.payload_bytes_sent;connect=sqlite3.connect
        def checked(*args,**kwargs):
            if str(self.source) in str(args[0]):self.fail('resume recaptured live source')
            return connect(*args,**kwargs)
        with patch('vk_nightly_sql_point.sqlite3.connect',side_effect=checked):
            result=self.capture(resume=captured[0])
        self.assertTrue(result['resumed_retained_SQL_point'])
        self.assertEqual(result['sha256'],captured[0]['sha256'])
        self.assertEqual(result['new_B_encoded_payload_bytes'],0)

    def interrupted_layout(self):
        partial={}
        def stop(value):
            partial.update(value)
            if 'layout' in value:raise RuntimeError('simulated volatile scratch loss after durable B layout')
        with self.assertRaises(RuntimeError):self.capture(on_prepared=stop)
        # Only disposable fixture RAM is lost. Every B object/manifest remains.
        Path(partial['captured_RAM_point']['working_RAM_path']).unlink()
        return partial

    def test_lost_RAM_point_recovers_from_B_layout_without_source_access_or_duplicate_payload(self):
        partial=self.interrupted_layout();original=partial['captured_RAM_point'];self.source.unlink()
        connect=sqlite3.connect
        def no_source(*args,**kwargs):
            if str(self.source) in str(args[0]):self.fail('durable B recovery accessed later live source')
            return connect(*args,**kwargs)
        with patch('vk_nightly_sql_point.sqlite3.connect',side_effect=no_source), \
             patch.object(self.client,'health',wraps=self.client.health) as health:
            result=self.capture(resume=original,resume_layout={k:partial[k] for k in ('layout','manifest')})
        self.assertTrue(result['recovered_from_durable_B_layout'])
        self.assertEqual(result['sha256'],original['sha256']);self.assertEqual(result['source_API_image_bytes'],0)
        self.assertEqual(result['new_B_encoded_payload_bytes'],0)
        self.assertEqual(result['independent']['integrity'],'ok')
        self.assertTrue(result['independent']['independent_Linux_metadata_verified'])
        self.assertEqual(result['recovery_health_RPC_count'],health.call_count)
        self.assertLess(health.call_count,len(partial['layout']['segments'])+3)
        self.assertEqual(list(self.root.glob('nightly-sql-*')),[])

    def test_changed_durable_SQL_layout_is_rejected_without_source_or_new_scratch(self):
        partial=self.interrupted_layout();self.source.unlink();partial['layout']['sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'layout/original API proof differs'):
            self.capture(resume=partial['captured_RAM_point'],resume_layout={k:partial[k] for k in ('layout','manifest')})
        self.assertEqual(list(self.root.glob('nightly-sql-*')),[])

    def test_low_RAM_recovery_keeps_B_layout_and_can_resume_after_admission(self):
        from types import SimpleNamespace
        partial=self.interrupted_layout();self.source.unlink();args=dict(resume=partial['captured_RAM_point'],resume_layout={k:partial[k] for k in ('layout','manifest')})
        with patch('vk_nightly_sql_point.os.statvfs',return_value=SimpleNamespace(f_bavail=0,f_frsize=4096)):
            with self.assertRaisesRegex(OSError,'RAM independent SQL recovery scratch unavailable'):self.capture(**args)
        self.assertEqual(list(self.root.glob('nightly-sql-*')),[])
        self.assertTrue(self.capture(**args)['recovered_from_durable_B_layout'])


if __name__=='__main__':unittest.main()
