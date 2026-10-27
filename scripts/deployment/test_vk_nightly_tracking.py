"""Durable queue, real inotify and bounded consumer tests on tiny RAM fixtures."""
import copy
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

from vk_nightly_tracking import TrackingStore, FORMAT, request, serve,source_bindings,discard_committed
from vk_nightly_tracked_delta import select, ReconciliationRequired


class TrackingTests(unittest.TestCase):
    def test_B_commit_discards_only_durable_path_and_mask_generations(self):
        from types import SimpleNamespace
        journal=SimpleNamespace(changed={'old':4,'same-file':7,'new':8},
            events={'old':{8:4},'same-file':{8:5,4:7},'new':{8:8}})
        discard_committed(journal,5)
        self.assertEqual(journal.changed,{'same-file':7,'new':8})
        self.assertEqual(journal.events,{'same-file':{4:7},'new':{8:8}})

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'tracking.sqlite'
        self.binding=dict(format=FORMAT,instance='one',scope_sha256='a'*64,plan_sha256='b'*64,owner_pid=os.getpid())

    def report(self,sequence,events=None,errors=None):
        events=events or {}
        return dict(instance='one',sequence=sequence,scope_sha256='a'*64,ready=not errors,
                    changed=list(events),events=events,errors=errors or [])

    def test_reopen_reuses_committed_queue_and_new_epoch_invalidates_old(self):
        with TrackingStore.held(self.path) as store:
            store.start(self.binding);store.commit(self.report(4,{'/source/a':8}))
        with TrackingStore.held(self.path) as store:
            self.assertEqual(store.report('one',0)['changed'],['/source/a'])
            store.start(dict(self.binding,instance='two'))
            self.assertFalse(store.report('one',0)['ready'])
            self.assertFalse(store.report('two',0)['ready'])
            with self.assertRaises(ValueError):store.report('three',0)

    def test_persistent_fault_cannot_be_erased_by_later_clean_report(self):
        with TrackingStore.held(self.path) as store:
            store.start(self.binding);store.commit(self.report(1,errors=[{'coverage_lost':16384}]))
            store.commit(self.report(2,{'/source/b':8}))
            value=store.report('one',1)
            self.assertFalse(value['ready']);self.assertEqual(value['errors'],[{'coverage_lost':16384}])

    def test_failure_reason_and_committed_cursor_survive_cleanup_and_reopen(self):
        with TrackingStore.held(self.path) as store:
            store.start(self.binding);store.commit(self.report(9,{'/source/preserved':8}))
            store.terminate('one','actual SSD floor reached')
            store.terminate('one','owner terminal; new observer requires explicit reconciliation')
        with TrackingStore.held(self.path) as store:
            value=store.report('one',0)
            self.assertFalse(value['ready']);self.assertEqual(value['sequence'],9)
            self.assertEqual(value['changed'],['/source/preserved'])
            self.assertEqual(value['terminal'],'actual SSD floor reached')

    def test_bound_and_future_cursor_fail_without_truncating_or_mutating(self):
        with TrackingStore.held(self.path) as store:
            store.start(self.binding);store.commit(self.report(2,{'/source/a':8,'/source/b':8}))
            with self.assertRaises(ValueError):store.report('one',0,maximum_paths=1)
            with self.assertRaises(ValueError):store.report('one',3)
            self.assertEqual(len(store.report('one',0)['changed']),2)

    def test_backwards_commit_and_competing_owner_refused(self):
        with TrackingStore.held(self.path) as store:
            store.start(self.binding);store.commit(self.report(5))
            with self.assertRaises(ValueError):store.commit(self.report(4))
            with self.assertRaises(BlockingIOError):
                with TrackingStore.held(self.path):pass
            self.assertEqual(store.report('one',0)['sequence'],5)

    def test_real_daemon_commits_change_and_serves_complete_bounded_query(self):
        source=self.root/'source';source.mkdir();endpoint=self.root/'queue.sock';status=self.root/'status.json'
        stop=threading.Event();errors=[]
        def worker():
            try:serve({'sources':[str(source)]},self.path,endpoint,guard=lambda:None,status_path=status,stop=stop)
            except BaseException as e:errors.append(e)
        thread=threading.Thread(target=worker);thread.start()
        try:
            import json
            deadline=time.monotonic()+10
            while not endpoint.exists():
                if errors:raise errors[0]
                if time.monotonic()>deadline:self.fail('tiny daemon did not enroll')
                time.sleep(.01)
            binding=json.loads(status.read_text());instance=binding['instance']
            (source/'new').write_text('fixture')
            while True:
                value=request(endpoint,instance,0)
                if str(source/'new') in value['changed']:break
                if time.monotonic()>deadline:self.fail('new file not durably observed')
                time.sleep(.02)
            self.assertTrue(value['ready']);self.assertEqual(value['source_payload_bytes_read'],0)
            from vk_nightly_observer_barrier import flush
            before=value['sequence'];(source/'last-before-barrier').write_text('fixture')
            value=flush(endpoint,instance,before,guard=lambda:None)
            self.assertIn(str(source/'last-before-barrier'),value['changed'])
            self.assertEqual(value['barrier']['durable_sequence'],value['sequence'])
            with self.assertRaises(ValueError):request(endpoint,'other',0)
        finally:stop.set();thread.join(timeout=10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        with TrackingStore.held(self.path) as store:self.assertFalse(store.report(instance,0)['ready'])

    def test_buffered_inode_daemon_barrier_covers_burst_behind_processing_lock(self):
        from vk_nightly_inode_journal import Journal,require_full_coverage
        from vk_nightly_observer_barrier import flush
        import json
        limit=int(Path('/proc/sys/fs/inotify/max_queued_events').read_text())
        if limit>65536:self.skipTest('host FIFO exceeds bounded fixture')
        source=self.root/'inode-source';source.mkdir()
        files=[source/str(i) for i in range(4)]
        for f in files:f.write_bytes(b'x')
        endpoint=self.root/'inode.sock';status=self.root/'inode-status.json'
        stop=threading.Event();errors=[];journals=[]
        def factory(plan):
            journal=Journal(plan);journals.append(journal);return journal
        def worker():
            try:serve({'sources':[str(source)]},self.path,endpoint,guard=lambda:None,
                      status_path=status,stop=stop,journal_factory=factory)
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=worker);thread.start()
        try:
            deadline=time.monotonic()+10
            while not endpoint.exists():
                if errors:raise errors[0]
                if time.monotonic()>deadline:self.fail('inode daemon did not enroll')
                time.sleep(.01)
            binding=json.loads(status.read_text())
            with journals[0].lock:
                for i in range(limit+1024):
                    os.utime(files[i%4],ns=(i+1,i+1))
                    if i%256==0:time.sleep(.001)
            report=flush(endpoint,binding['instance'],0,guard=lambda:None)
            require_full_coverage(report)
            self.assertEqual(set(report['changed']),set(map(str,files)))
            self.assertGreater(report['sequence'],limit)
            self.assertEqual(report['barrier']['durable_sequence'],report['sequence'])
            self.assertEqual(report['source_payload_bytes_read'],0)
            self.assertEqual(report['source_paths_scanned'],0)
        finally:stop.set();thread.join(timeout=10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertFalse(journals[0].raw_reader.is_alive())

    def test_required_alias_retarget_is_detected_without_scanning_source_contents(self):
        one=self.root/'one';two=self.root/'two';one.mkdir();two.mkdir();alias=self.root/'alias';alias.symlink_to(one)
        plan={'sources':[str(alias)]};before=source_bindings(plan)
        (one/'ordinary-change').write_text('no root substitution')
        self.assertEqual(source_bindings(plan),before)
        alias.unlink();alias.symlink_to(two)
        self.assertNotEqual(source_bindings(plan),before)


class TrackedDeltaTests(unittest.TestCase):
    def setUp(self):
        self.anchor=dict(baseline_accepted=True,instance='one',scope_sha256='a'*64,plan_sha256='b'*64,sequence=10,sources=['/source'])
        self.report=dict(ready=True,errors=[],terminal=None,instance='one',scope_sha256='a'*64,plan_sha256='b'*64,
                         since=10,sequence=11,changed=[],events={},barrier=True,coverage_model='all-selected-inodes-v1')

    def delta(self,enumerate_subtree=lambda _:(),maximum_paths=10):
        return select(self.anchor,self.report,required_sql=['/source/db.sqlite'],maximum_paths=maximum_paths,enumerate_subtree=enumerate_subtree)

    def events(self,events):self.report.update(changed=list(events),events=events)

    def test_unchanged_workspaces_do_not_walk_stat_hash_or_copy(self):
        def forbidden(_):raise AssertionError('unchanged workspace walked')
        result=self.delta(forbidden)
        self.assertEqual(result['paths'],[]);self.assertEqual(result['unchanged_paths_scanned'],0)

    def test_critical_SQL_dependency_requires_API_even_without_main_inode_events(self):
        self.anchor['always_SQL_API_sources']=['/source/db.sqlite']
        result=self.delta(lambda _:self.fail('unchanged workspace walked'))
        self.assertEqual(result['SQLite_API_sources'],['/source/db.sqlite'])
        self.assertEqual(result['unchanged_paths_scanned'],0)
        for paths in (['/outside'],['/source/not-declared.sqlite']):
            self.anchor['always_SQL_API_sources']=paths
            with self.assertRaises(ReconciliationRequired):self.delta()

    def test_new_nested_subtree_is_enumerated_once_and_SQL_sidecars_select_API(self):
        self.events({'/source/new':0x40000100,'/source/new/inside':0x40000080,'/source/db.sqlite-wal':8})
        seen=[]
        def enumerate_(root):seen.append(root);return [root+'/file']
        result=self.delta(enumerate_)
        self.assertEqual(seen,['/source/new']);self.assertEqual(result['SQLite_API_sources'],['/source/db.sqlite'])
        self.assertNotIn('/source/db.sqlite-wal',result['paths'])

    def test_epoch_fault_scope_or_wrong_query_cursor_requires_reconciliation(self):
        for updates in (dict(instance='new'),dict(errors=[{'coverage_lost':16384}]),dict(ready=False),dict(since=9),
                        dict(coverage_model='directory-namespace-only-v1'),dict(barrier=False)):
            old=copy.deepcopy(self.report);self.report.update(updates)
            with self.assertRaises(ReconciliationRequired):self.delta()
            self.report=old

    def test_delta_budget_and_subtree_escape_never_yield_partial_acceptance(self):
        self.events({'/source/new':0x40000100})
        with self.assertRaises(ReconciliationRequired):self.delta(lambda r:[r+'/a',r+'/b'],maximum_paths=1)
        with self.assertRaises(ValueError):self.delta(lambda r:['/outside'])


if __name__=='__main__':unittest.main()
