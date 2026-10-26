"""Durable queue, real inotify and bounded consumer tests on tiny RAM fixtures."""
import copy
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

from vk_nightly_tracking import TrackingStore, FORMAT, request, serve,source_bindings
from vk_nightly_tracked_delta import select, ReconciliationRequired


class TrackingTests(unittest.TestCase):
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
            with self.assertRaises(ValueError):request(endpoint,'other',0)
        finally:stop.set();thread.join(timeout=10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        with TrackingStore.held(self.path) as store:self.assertFalse(store.report(instance,0)['ready'])

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
                         since=10,sequence=11,changed=[],events={})

    def delta(self,enumerate_subtree=lambda _:(),maximum_paths=10):
        return select(self.anchor,self.report,required_sql=['/source/db.sqlite'],maximum_paths=maximum_paths,enumerate_subtree=enumerate_subtree)

    def events(self,events):self.report.update(changed=list(events),events=events)

    def test_unchanged_workspaces_do_not_walk_stat_hash_or_copy(self):
        def forbidden(_):raise AssertionError('unchanged workspace walked')
        result=self.delta(forbidden)
        self.assertEqual(result['paths'],[]);self.assertEqual(result['unchanged_paths_scanned'],0)

    def test_new_nested_subtree_is_enumerated_once_and_SQL_sidecars_select_API(self):
        self.events({'/source/new':0x40000100,'/source/new/inside':0x40000080,'/source/db.sqlite-wal':8})
        seen=[]
        def enumerate_(root):seen.append(root);return [root+'/file']
        result=self.delta(enumerate_)
        self.assertEqual(seen,['/source/new']);self.assertEqual(result['SQLite_API_sources'],['/source/db.sqlite'])
        self.assertNotIn('/source/db.sqlite-wal',result['paths'])

    def test_epoch_fault_scope_or_wrong_query_cursor_requires_reconciliation(self):
        for updates in (dict(instance='new'),dict(errors=[{'coverage_lost':16384}]),dict(ready=False),dict(since=9)):
            old=copy.deepcopy(self.report);self.report.update(updates)
            with self.assertRaises(ReconciliationRequired):self.delta()
            self.report=old

    def test_delta_budget_and_subtree_escape_never_yield_partial_acceptance(self):
        self.events({'/source/new':0x40000100})
        with self.assertRaises(ReconciliationRequired):self.delta(lambda r:[r+'/a',r+'/b'],maximum_paths=1)
        with self.assertRaises(ValueError):self.delta(lambda r:['/outside'])


if __name__=='__main__':unittest.main()
