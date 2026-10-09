"""New lifecycle tests: owned Linux fixtures, no real B or production actions."""
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
from unittest.mock import patch

import test_vk_candidate_direct_b as fixtures
from test_vk_restart_safeguards import fixture_readback
from vk_archive_store import Archive
from vk_archive_stream import StreamingArchive
from vk_candidate_direct_b import DirectBProvider
from vk_change_journal import Journal, scope
from vk_direct_capture import capture
from vk_nightly_generation import MAX_INDEX, NightlyStore
import vk_nightly_lifecycle as lifecycle
from vk_nightly_lifecycle import NightlyJob
from vk_prep_common import identity


class NightlyLifecycle(fixtures.ContractTests):
    def setUp(self):
        super().setUp()
        self.normal = self.root/'normal-scope';self.normal.mkdir()
        self.nightly = self.normal/'store';self.nightly.mkdir()
        self.jobs = self.normal/'jobs';self.jobs.mkdir()
        self.store_job = NightlyStore(self.nightly,self.scope,lambda:self.root,independent_readback=fixture_readback)
        self.store_job.enroll_empty()
        self.job = NightlyJob(self.jobs,self.store_job,capture_limit_bytes=1024**2,changed_limit_bytes=1024**2)
        self.job.enroll_empty()
        self.parents=[];self.raw_inputs=[]
        self.reserve=MAX_INDEX+2*1024**2

    def make_capture(self,folder,register,seal,*,parent):
        self.parents.append(parent)
        plan={'sources':[str(self.inc)],'sqlite_snapshots':[str(self.db)],'excluded_rebuildable_directories':[]}
        journal=Journal(plan);journal.tree(self.inc);journal.ready=True
        def archive_factory(ref,*args,**kwargs):
            return Archive(ref,archive_directory=folder,desktop_only=False)
        def mirror(source):
            if isinstance(source,StreamingArchive):
                buffer=io.BytesIO();source.produce(buffer)
                raw=subprocess.run(['zstd','-T1','-3','-c'],input=buffer.getvalue(),capture_output=True,check=True).stdout
                source.sha256=hashlib.sha256(raw).hexdigest();source.bytes=len(raw);name=source.name
            else:
                raw=Path(source).read_bytes();name=Path(source).name
            if len(raw)>self.job.capture_limit:raise ValueError('fixture streaming capacity exceeded')
            target=folder/name
            with target.open('xb') as stream:
                register(target,stream.fileno());stream.write(raw);stream.flush();os.fsync(stream.fileno())
            seal(target);self.raw_inputs.append(target)
            return {'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                    'desktop_verified':True,'desktop_directory':'B:/vk-backups/lifecycle-fixture',
                    'direct_stream':isinstance(source,StreamingArchive)}
        try:
            with patch('vk_direct_capture.Archive',archive_factory):
                result=capture(plan,self.root/('metadata-'+os.urandom(4).hex()),journal.report,mirror,
                               parent=parent,publish=mirror,max_snapshot_bytes=64*1024)
        finally:journal.close()
        provider=DirectBProvider(self.scope,['home/state/state.sqlite'],archive_factory=archive_factory,fixture_only=True)
        provider.register('nightly',result,identity(plan),identity(scope(plan)),self.inc,origin_root_binding='fixture')
        return provider,'nightly',result

    def run_nightly(self):
        return self.job.run(self.make_capture,retention_adopted=True,reserve_bytes=self.reserve)

    def latest_rows(self):
        current=self.store_job.current();self.store_job.verify(current)
        row=current['entries']['home/state/state.sqlite']
        path=self.nightly/current['generation']/'objects'/row['sha256']
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            return db.execute('SELECT value FROM retained ORDER BY rowid').fetchall()

    def change(self):
        with sqlite3.connect(self.db) as db:db.execute("INSERT INTO retained VALUES('second')")

    def test_three_independent_captures_one_current_no_archive_chain(self):
        incident=self.root/'protected-incident';incident.write_bytes(b'protected evidence')
        fallback=self.root/'protected-fallback';fallback.write_bytes(b'protected fallback')
        self.assertTrue(self.run_nightly()['passed'])
        initial=self.store_job.current()
        note=initial['entries']['home/state/note']['sha256']
        inode=(self.nightly/initial['generation']/'objects'/note).stat().st_ino
        for number in range(2):
            with sqlite3.connect(self.db) as db:db.execute('INSERT INTO retained VALUES(?)',[str(number)])
            result=self.run_nightly();self.assertTrue(result['passed'],result)
            current=self.store_job.current();self.assertIsNone(current['parent'])
            self.assertEqual((self.nightly/current['generation']/'objects'/note).stat().st_ino,inode)
            self.assertEqual(len(self.store_job.inventory()),1)
            self.assertEqual({p.name for p in self.jobs.iterdir()},{'job-scope.json','job.lock'})
            self.assertFalse(any(p.exists() for p in self.raw_inputs))
        self.assertEqual(self.parents,[None,None,None])
        self.assertEqual(self.latest_rows(),[('before',),('0',),('1',)])
        self.assertEqual(incident.read_bytes(),b'protected evidence');self.assertEqual(fallback.read_bytes(),b'protected fallback')

    def crash(self,stage):
        self.assertTrue(self.run_nightly()['passed']);self.change()
        child=os.fork()
        if child==0:
            try:
                if stage=='before':
                    replace=os.replace
                    def hook(src,dst,**kwargs):
                        if Path(dst)==self.nightly/'current.json':os._exit(81)
                        return replace(src,dst,**kwargs)
                    with patch('os.replace',hook):self.run_nightly()
                elif stage=='candidate_objects_removed':
                    replace=os.replace
                    def before(src,dst,**kwargs):
                        if Path(dst)==self.nightly/'current.json':raise OSError('injected prepublication failure')
                        return replace(src,dst,**kwargs)
                    with patch('os.replace',before):
                        failure=self.run_nightly()
                    if failure['passed']:os._exit(90)
                    rmdir=Path.rmdir
                    candidate=self.nightly/self.job.read()['candidate']
                    def removed(path):
                        rmdir(path)
                        if path==candidate/'objects':os._exit(84)
                    with patch.object(Path,'rmdir',removed):
                        self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
                elif stage=='rename_before_fsync':
                    replace=os.replace;fsync=os.fsync;renamed=False
                    store_identity=lifecycle.directory_pin(self.nightly)
                    def renamed_pointer(src,dst,**kwargs):
                        nonlocal renamed
                        result=replace(src,dst,**kwargs)
                        if Path(dst)==self.nightly/'current.json':renamed=True
                        return result
                    def before_store_sync(fd):
                        if renamed and lifecycle.pin(os.fstat(fd))==store_identity:os._exit(85)
                        return fsync(fd)
                    with patch('os.replace',renamed_pointer),patch('os.fsync',before_store_sync):
                        self.run_nightly()
                elif stage=='after':
                    with patch.object(self.job,'_reconcile_held',lambda:os._exit(82)):self.run_nightly()
                else:
                    unlink=lifecycle.unlink_pinned
                    def hook(path,identity,**kwargs):
                        unlink(path,identity,**kwargs)
                        if Path(path).parent.name=='objects':os._exit(83)
                    with patch('vk_nightly_lifecycle.unlink_pinned',hook):self.run_nightly()
            except BaseException:os._exit(90)
            os._exit(91)
        deadline=time.monotonic()+15
        try:
            while True:
                pid,status=os.waitpid(child,os.WNOHANG)
                if pid:break
                if time.monotonic()>deadline:raise AssertionError('owned child exceeded fixture timeout')
                time.sleep(.05)
        finally:
            if not pid:os.kill(child,signal.SIGKILL);os.waitpid(child,0)
        self.assertEqual(os.waitstatus_to_exitcode(status),{'before':81,'after':82,'retention':83,'candidate_objects_removed':84,'rename_before_fsync':85}[stage])
        if stage=='candidate_objects_removed':
            candidate=self.nightly/self.job.read()['candidate']
            self.assertEqual(list(candidate.iterdir()),[])
            self.assertEqual(lifecycle.directory_pin(candidate),self.job.read()['candidate_directories'][0])
        blocked=self.run_nightly();self.assertEqual(blocked['status'],'reconciliation_required')
        if stage=='rename_before_fsync':
            previous=self.job.read()['previous']
            old=self.nightly/previous['generation']
            old_parents={tuple(previous['folder']),tuple(previous['objects'])}
            store_identity=lifecycle.directory_pin(self.nightly)
            fsync=os.fsync;unlink=os.unlink;events=[]
            def record_sync(fd):
                result=fsync(fd)
                if lifecycle.pin(os.fstat(fd))==store_identity:events.append('store_fsync')
                return result
            def record_unlink(path,*,dir_fd=None):
                if dir_fd is not None and tuple(lifecycle.pin(os.fstat(dir_fd))) in old_parents:
                    events.append('old_unlink')
                    self.assertIn('store_fsync',events,'old unlink preceded durable publication')
                return unlink(path,dir_fd=dir_fd)
            # A failed publication fsync must preserve the old generation.
            with patch('os.unlink',record_unlink), patch(
                    'vk_nightly_lifecycle.sync_directory',side_effect=OSError('injected store fsync failure')):
                with self.assertRaisesRegex(OSError,'store fsync failure'):
                    self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
            self.assertEqual(events,[])
            self.assertTrue(all((old/raw).exists() for raw in previous['files']))
            self.assertTrue((self.jobs/'attempt.json').exists())
            with patch('os.fsync',record_sync),patch('os.unlink',record_unlink):
                self.assertTrue(self.job.reconcile(retention_adopted=True,inputs_quiescent=True)['passed'])
            self.assertIn('old_unlink',events)
            self.assertLess(events.index('store_fsync'),events.index('old_unlink'))
        else:
            self.assertTrue(self.job.reconcile(retention_adopted=True,inputs_quiescent=True)['passed'])
        expected=[('before',)] if stage in ('before','candidate_objects_removed') else [('before',),('second',)]
        self.assertEqual(self.latest_rows(),expected)
        self.assertEqual(len(self.store_job.inventory()),1)
        self.assertFalse((self.jobs/'attempt.json').exists())
        self.assertTrue(self.run_nightly()['passed'])
        self.assertEqual(self.latest_rows(),[('before',),('second',)])

    def test_process_death_before_publication_reconciles_then_retries(self):self.crash('before')
    def test_process_death_after_publication_retires_recorded_previous(self):self.crash('after')
    def test_process_death_during_retention_resumes_missing_exact_objects(self):self.crash('retention')

    def test_candidate_cleanup_death_after_objects_rmdir_resumes_empty_recorded_folder(self):
        self.crash('candidate_objects_removed')

    def test_rename_before_fsync_recovery_durably_publishes_before_old_unlink(self):
        self.crash('rename_before_fsync')

    def test_missing_candidate_objects_rejects_nonempty_or_substituted_folder(self):
        self.assertTrue(self.run_nightly()['passed'])
        observe=self.job.observe
        def interrupted(event,value):
            observe(event,value)
            if event=='directories':raise OSError('injected empty candidate preparation failure')
        with patch.object(self.job,'observe',interrupted):
            self.assertFalse(self.run_nightly()['passed'])
        candidate=self.nightly/self.job.read()['candidate']
        (candidate/'objects').rmdir()
        unexpected=candidate/'unexpected-evidence';unexpected.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError,'remaining evidence'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertEqual(unexpected.read_bytes(),b'preserve')
        # Keep the recorded inode and its evidence; a new empty directory at
        # the same candidate name must never qualify for resumable cleanup.
        preserved=self.root/'preserved-recorded-candidate'
        candidate.rename(preserved);candidate.mkdir()
        with self.assertRaisesRegex(ValueError,'ownership not established'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertTrue(candidate.is_dir());self.assertTrue((preserved/'unexpected-evidence').exists())
        self.assertEqual(self.latest_rows(),[('before',)])

    def test_failed_partial_capture_reconciliation_and_gates(self):
        self.assertTrue(self.run_nightly()['passed'])
        def broken(folder,register,seal,*,parent):
            with (folder/'owned.partial').open('xb') as out:
                register(folder/'owned.partial',out.fileno());out.write(b'incomplete');out.flush();os.fsync(out.fileno())
            raise ValueError('injected receiver EOF')
        failure=self.job.run(broken,retention_adopted=True,reserve_bytes=self.reserve)
        self.assertIn('receiver EOF',failure['reason'])
        with self.assertRaises(ValueError):self.job.reconcile(retention_adopted=True)
        self.assertTrue(self.job.reconcile(retention_adopted=True,inputs_quiescent=True)['passed'])
        self.assertEqual(self.latest_rows(),[('before',)])
        with self.assertRaises(ValueError):self.job.run(self.make_capture,reserve_bytes=self.reserve)
        with self.assertRaises(ValueError):self.job.run(self.make_capture,retention_adopted=True,reserve_bytes=1)

    def test_unknown_input_symlink_substitution_and_chain_are_rejected(self):
        self.assertTrue(self.run_nightly()['passed'])
        def broken(folder,register,seal,*,parent):
            (folder/'unexpected-evidence').write_bytes(b'preserve')
            raise ValueError('adapter left unknown evidence')
        self.job.run(broken,retention_adopted=True,reserve_bytes=self.reserve)
        with self.assertRaisesRegex(ValueError,'unexpected transient'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        attempt=self.job.read();folder=self.jobs/attempt['input_name']
        self.assertEqual((folder/'unexpected-evidence').read_bytes(),b'preserve')
        self.assertEqual(self.latest_rows(),[('before',)])

    def test_capture_parent_and_unsealed_input_never_publish(self):
        self.assertTrue(self.run_nightly()['passed']);old=self.store_job.current()['generation']
        def chained(folder,register,seal,*,parent):
            provider,key,result=self.make_capture(folder,register,seal,parent=parent)
            return provider,key,{**result,'parent':{'forbidden_old_baseline':True}}
        failure=self.job.run(chained,retention_adopted=True,reserve_bytes=self.reserve)
        self.assertIn('retired archive parents',failure['reason'])
        self.assertEqual(self.store_job.current()['generation'],old)
        self.job.reconcile(retention_adopted=True,inputs_quiescent=True)

        def unsealed(folder,register,seal,*,parent):
            return self.make_capture(folder,register,lambda path:None,parent=parent)
        failure=self.job.run(unsealed,retention_adopted=True,reserve_bytes=self.reserve)
        self.assertIn('not sealed',failure['reason'])
        self.assertEqual(self.store_job.current()['generation'],old)
        self.job.reconcile(retention_adopted=True,inputs_quiescent=True)

    def test_symlink_input_rejects_cleanup_preserves_protected_fixture(self):
        self.assertTrue(self.run_nightly()['passed'])
        protected=self.root/'protected-evidence';protected.write_bytes(b'keep')
        def changed(folder,register,seal,*,parent):
            path=folder/'owned.partial'
            with path.open('xb') as stream:register(path,stream.fileno())
            path.unlink();path.symlink_to(protected)
            raise ValueError('injected substitution')
        self.job.run(changed,retention_adopted=True,reserve_bytes=self.reserve)
        with self.assertRaises(OSError):self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertEqual(protected.read_bytes(),b'keep')
        self.assertEqual(self.latest_rows(),[('before',)])

    def test_input_hardlink_substitution_and_traversal_intent_fail_closed(self):
        self.assertTrue(self.run_nightly()['passed'])
        protected=self.root/'protected-evidence';protected.write_bytes(b'keep')
        def changed(folder,register,seal,*,parent):
            path=folder/'owned.partial'
            with path.open('xb') as stream:register(path,stream.fileno())
            path.unlink();os.link(protected,path)
            raise ValueError('injected hardlink substitution')
        self.job.run(changed,retention_adopted=True,reserve_bytes=self.reserve)
        with self.assertRaisesRegex(ValueError,'input substituted'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        attempt=self.job.read();attempt['previous']['files']['../../protected-evidence']={'identity':[1,2],'sha256':'a'*64}
        self.job.save(attempt)
        with self.assertRaisesRegex(ValueError,'unsafe recorded retention path'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertEqual(protected.read_bytes(),b'keep')

    def test_progress_updates_are_constant_size_and_replay_rejected(self):
        self.assertTrue(self.run_nightly()['passed'])
        def broken(folder,register,seal,*,parent):
            raise ValueError('prepare only')
        self.job.run(broken,retention_adopted=True,reserve_bytes=self.reserve)
        attempt=self.job.read();attempt['expected_objects']={('%064x'%i):1 for i in range(10000)}
        self.job.save(attempt);self.job._active_intent=attempt
        with patch.object(self.job,'read',side_effect=AssertionError('must not reparse host-scale plan')):
            self.job.observe('directories',(self.nightly,self.nightly))
        self.job._active_intent=None
        self.assertLess((self.jobs/'progress.json').stat().st_size,16384)
        progress=json.loads((self.jobs/'progress.json').read_text());progress['candidate']='generation-'+'0'*32
        (self.jobs/'progress.json').write_text(json.dumps(progress))
        with self.assertRaisesRegex(ValueError,'replayed or substituted progress'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)

    def test_scripted_tick_reconciles_owned_partial_without_operator(self):
        self.assertTrue(self.run_nightly()['passed'])
        def broken(folder,register,seal,*,parent):
            with (folder/'owned.partial').open('xb') as out:
                register(folder/'owned.partial',out.fileno());out.write(b'incomplete')
            raise ValueError('closed owned receiver failed')
        self.job.run(broken,retention_adopted=True,reserve_bytes=self.reserve)
        active=self.job.tick(self.make_capture,lambda attempt:None,retention_adopted=True,reserve_bytes=self.reserve)
        self.assertEqual(active['status'],'input_producer_active')
        self.assertTrue((self.jobs/'attempt.json').exists())
        def closed(attempt):
            return {'candidate':attempt['candidate'],'input_name':attempt['input_name'],
                    'scope_sha256':self.scope,'quiescent':True}
        result=self.job.tick(self.make_capture,closed,retention_adopted=True,reserve_bytes=self.reserve)
        self.assertTrue(result['passed'],result)
        self.assertEqual(len(self.store_job.inventory()),1)
        self.assertFalse((self.jobs/'attempt.json').exists())
        self.assertEqual(self.latest_rows(),[('before',)])

    def test_actual_declared_db_count_and_first_capture_failure_are_bounded(self):
        def interrupted(folder,register,seal,*,parent):
            for number in range(71):
                path=folder/('snapshot-%03d'%number)
                with path.open('xb') as out:register(path,out.fileno())
                seal(path)
            raise ValueError('closed first capture interrupted')
        failed=self.job.run(interrupted,retention_adopted=True,reserve_bytes=self.reserve)
        self.assertIn('first capture interrupted',failed['reason'])
        result=self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertEqual(result['status'],'first_capture_retry_ready')
        self.assertIsNone(self.store_job.current())
        self.assertTrue(self.run_nightly()['passed'])


for name in list(dir(NightlyLifecycle)):
    if name.startswith('test_') and name not in NightlyLifecycle.__dict__:
        setattr(NightlyLifecycle,name,None)
