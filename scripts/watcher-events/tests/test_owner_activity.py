import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import owner_activity as a
import monitor
import pressure
import t26_watch


def no_processes(config, ids):
    return {'process_ids': [], 'process_limit': False,
            'unattributed_process_count': 0, 'unattributed_processes': []}


class AssignedOwner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.wid, self.sid, self.other_wid, self.other_sid = [uuid.uuid4() for _ in range(4)]
        self.cfg = {'workspace_id': str(self.wid), 'session_id': str(self.sid),
                    'vibe_db': str(self.root/'vibe.sqlite'), 'owner_roots': [str(self.root)],
                    'delegation_journal_dir': str(self.root)}
        self.db = sqlite3.connect(self.cfg['vibe_db'])
        self.db.executescript('''CREATE TABLE sessions(id BLOB,workspace_id BLOB);
          CREATE TABLE execution_processes(id BLOB,session_id BLOB,status TEXT,run_reason TEXT,created_at TEXT);
          CREATE TABLE watcher_job_leases(workspace_id BLOB,closed_at TEXT);
          CREATE TABLE coding_agent_turns(execution_process_id BLOB,agent_session_id TEXT);''')
        self.db.executemany('INSERT INTO sessions VALUES(?,?)', [(self.sid.bytes,self.wid.bytes),(self.other_sid.bytes,self.other_wid.bytes)])
        self.db.commit()
        self.jobs = {}; self.queues = {}
    def tearDown(self):
        self.db.close(); self.tmp.cleanup()
    def insert(self, status='running', sid=None, reason='codingagent'):
        eid = uuid.uuid4()
        self.db.execute('INSERT INTO execution_processes VALUES(?,?,?,?,?)', (eid.bytes, (sid or self.sid).bytes, status, reason, str(time.time_ns())))
        self.db.commit(); return eid
    def api(self, path):
        if path.endswith('/queue'):
            return self.queues.get(path.split('/')[3], {'status': 'empty'})
        sid = path.split('session_id=')[-1]
        return self.jobs.get(sid, [])
    def read(self, config=None, reader=no_processes, api=None):
        return a.inspect(config or self.cfg, api_get=api or self.api, process_reader=reader)
    def test_current_turn_is_exact_and_unrelated_running_owner_does_not_hold(self):
        old = self.insert('completed'); self.insert(sid=self.other_sid)
        out = self.read()
        self.assertEqual(out['current_turn']['execution_id'], str(old))
        self.assertEqual(out['turn_state'], 'idle'); self.assertEqual(out['state'], 'idle')
        self.assertFalse(a.busy(out))
    def test_busy_to_idle_has_no_cached_running_turn(self):
        eid = self.insert(); out = self.read()
        self.assertEqual(out['turn_state'], 'running'); self.assertIn(str(eid), out['coding_or_script_turns'])
        self.db.execute("UPDATE execution_processes SET status='completed'"); self.db.commit()
        out = self.read(); self.assertEqual(out['current_turn']['status'], 'completed')
        self.assertEqual(out['state'], 'idle'); self.assertFalse(a.busy(out))
    def test_running_agent_turn_wins_over_later_completed_script(self):
        eid=self.insert()
        self.insert('completed',reason='cleanupscript')
        out=self.read()
        self.assertEqual(out['current_turn']['execution_id'],str(eid))
        self.assertEqual(out['turn_state'],'running');self.assertTrue(a.busy(out))
        self.db.execute("UPDATE execution_processes SET status='completed'");self.db.commit()
        self.assertEqual(self.read()['current_turn']['execution_id'],str(eid))

    def test_other_session_of_same_workspace_holds_assigned_owner(self):
        sid = uuid.uuid4(); self.db.execute('INSERT INTO sessions VALUES(?,?)', (sid.bytes,self.wid.bytes)); self.db.commit()
        eid = self.insert(sid=sid); out = self.read()
        self.assertIn(str(eid),out['coding_or_script_turns']); self.assertTrue(a.busy(out))
    def test_devserver_is_not_a_coding_turn(self):
        self.insert(reason='devserver'); self.assertEqual(self.read()['state'], 'idle')
    def test_unfamiliar_turn_status_holds_only_its_assigned_target(self):
        self.insert(status='future-provider-state')
        out = self.read(); self.assertTrue(out['inventory_unknown'])
        self.assertEqual(out['turn_state'], 'unknown')
        cfg = {**self.cfg, 'workspace_id':str(self.other_wid), 'session_id':str(self.other_sid)}
        self.assertEqual(self.read(cfg)['state'],'idle')
    def test_unfamiliar_job_status_is_scoped_and_preserved_pending(self):
        self.jobs[str(self.sid)] = [{'id':'child-job','status':'future-child-state'}]
        out = self.read(); self.assertTrue(a.busy(out))
        self.assertEqual(out['owner_uncertainties'][0]['component'], 'jobs')
        cfg = {**self.cfg,'workspace_id':str(self.other_wid),'session_id':str(self.other_sid)}
        self.assertFalse(a.busy(self.read(cfg)))
    def test_unknown_and_running_independent_jobs_hold_after_parent_finishes(self):
        self.insert('completed')
        for status in ('running','unresolved','not_found'):
            self.jobs[str(self.sid)] = [{'id':'child','status':status}]
            self.assertTrue(a.busy(self.read()))
        self.jobs[str(self.sid)] = [{'id':'child','status':'completed'}]
        self.assertFalse(a.busy(self.read()))
    def test_wrong_job_session_is_not_idle(self):
        self.jobs[str(self.sid)] = [{'id':'child','status':'completed','session_id':str(self.other_sid)}]
        self.assertTrue(a.busy(self.read()))
    def test_queue_holds_without_claiming_running_turn(self):
        self.queues[str(self.sid)] = {'status':'queued'}
        out = self.read(); self.assertEqual(out['state'],'queued'); self.assertEqual(out['turn_state'],'idle')
        self.assertTrue(a.busy(out))
    def test_api_failure_does_not_erase_known_current_turn(self):
        eid = self.insert()
        def fail(_):raise ValueError('no response')
        out = self.read(api=fail); self.assertEqual(out['current_turn']['execution_id'],str(eid))
        self.assertEqual(out['turn_state'],'running'); self.assertTrue(a.busy(out))
    def test_missing_binding_and_database_hold_only_this_target(self):
        for change in ({'session_id':str(uuid.uuid4())},{'vibe_db':str(self.root/'missing')}):
            out = self.read({**self.cfg,**change})
            self.assertTrue(a.busy(out)); self.assertEqual(out['turn_state'],'unknown')
        self.assertFalse(a.busy(self.read()))
    def test_turn_arrives_during_inventory_is_detected_by_final_read(self):
        invoked=[]
        def api(path):
            if not invoked:invoked.append(self.insert())
            return self.api(path)
        out = self.read(api=api)
        self.assertIn(str(invoked[0]),out['coding_or_script_turns'])
        self.assertEqual(out['turn_state'],'running'); self.assertTrue(a.busy(out))
    def test_turn_finishes_during_read_holds_until_next_consistent_read(self):
        self.insert()
        def api(path):
            self.db.execute("UPDATE execution_processes SET status='completed'");self.db.commit()
            return self.api(path)
        out=self.read(api=api)
        self.assertEqual(out['current_turn']['status'],'completed')
        self.assertTrue(a.busy(out));self.assertFalse(a.busy(self.read()))
    def test_open_lease_and_unsettled_journal_are_target_scoped(self):
        self.db.execute('INSERT INTO watcher_job_leases VALUES(?,NULL)',(self.wid.bytes,));self.db.commit()
        self.assertTrue(a.busy(self.read()))
        cfg={**self.cfg,'workspace_id':str(self.other_wid),'session_id':str(self.other_sid)}
        self.assertFalse(a.busy(self.read(cfg)))
        self.db.execute("UPDATE watcher_job_leases SET closed_at='confirmed'");self.db.commit()
        eid=self.insert('completed')
        self.db.execute('INSERT INTO coding_agent_turns VALUES(?,?)',(eid.bytes,'root-thread'));self.db.commit()
        (self.root/'root-thread.json').write_text(json.dumps({'child':{'status':'interrupted_unconfirmed'}}))
        self.assertTrue(a.busy(self.read()))
        (self.root/'root-thread.json').write_text(json.dumps({'child':{'status':'completed'}}))
        self.assertFalse(a.busy(self.read()))
    def test_scanner_failure_is_component_scoped_not_idle(self):
        def fail(*_):raise OSError()
        out=self.read(reader=fail)
        self.assertTrue(a.busy(out));self.assertEqual(out['turn_state'],'idle')
        self.assertEqual(out['owner_uncertainties'][0]['component'],'process')
    def test_chrome_restart_unreadable_process_does_not_poison_owner_turn(self):
        for pid in (101,202,303,404):
            def reader(cfg,ids):
                return a.classify_processes([{'pid':pid,'ppid':1,'name':'chrome','start_ticks':'12000',
                    'cgroup':'0::/user.slice/unrelated-browser.service',
                    'unreadable':True}], ids)
            out=self.read(reader=reader)
            self.assertFalse(out['inventory_unknown']);self.assertEqual(out['state'],'idle')
            self.assertEqual(out['unattributed_process_count'],1)
            self.assertEqual(out['unattributed_processes'][0]['pid'],pid)


class ProcessAttribution(unittest.TestCase):
    def test_unfamiliar_owned_process_and_full_descendant_chain_hold(self):
        rows=[{'pid':1,'ppid':0,'start_ticks':'1','references_owner':True}]
        rows += [{'pid':i,'ppid':i-1,'start_ticks':str(i),'unreadable':True,'name':'unfamiliar'} for i in range(2,12)]
        self.assertEqual(a.classify_processes(rows,[])['process_ids'],list(range(1,12)))
    def test_native_execution_unit_is_positive_target_attribution(self):
        eid=str(uuid.uuid4())
        rows=[{'pid':7,'ppid':0,'start_ticks':'2','unreadable':True,
               'cgroup':'0::/app.slice/vk-capacity-'+uuid.UUID(eid).hex+'.service'}]
        self.assertEqual(a.classify_processes(rows,[eid])['process_ids'],[7])
        self.assertEqual(a.classify_processes(rows,[])['process_ids'],[])
    def test_pid_reuse_cannot_invent_parentage(self):
        rows=[{'pid':1,'ppid':0,'start_ticks':'100','references_owner':True},
              {'pid':2,'ppid':1,'start_ticks':'20','unreadable':True}]
        out=a.classify_processes(rows,[])
        self.assertEqual(out['process_ids'],[1]);self.assertEqual(out['unattributed_process_count'],1)
    def test_unfamiliar_name_is_not_a_privileged_browser_allowlist(self):
        for name in ('chrome','python','future-program'):
            rows=[{'pid':7,'ppid':0,'start_ticks':'1','name':name,'unreadable':True}]
            self.assertEqual(a.classify_processes(rows,[])['process_ids'],[])
            rows[0]['references_owner']=True
            self.assertEqual(a.classify_processes(rows,[])['process_ids'],[7])
    def test_diagnostics_are_bounded(self):
        rows=[{'pid':i,'unreadable':True,'name':'unknown'} for i in range(200)]
        out=a.classify_processes(rows,[])
        self.assertEqual(out['unattributed_process_count'],200);self.assertEqual(len(out['unattributed_processes']),16)
    def test_arguments_are_not_retained_and_path_substrings_are_not_owner_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);proc=root/'123';proc.mkdir()
            (proc/'stat').write_text('123 (fake) S 1 '+'0 '*17+'42 0')
            (proc/'comm').write_text('future-program\n');(proc/'cgroup').write_text('0::/other.service')
            (proc/'cwd').symlink_to(root)
            (proc/'cmdline').write_bytes(b'program\0--secret=DO_NOT_RETAIN\0--path=/owner-prefix-extra\0')
            with patch.object(a.os,'getpid',return_value=999):row=a.read_process(proc,['/owner-prefix'])
            self.assertFalse(row['references_owner']);self.assertNotIn('DO_NOT_RETAIN',json.dumps(row))


class BusyPendingMigration(unittest.TestCase):
    def test_only_definitely_unadmitted_covered_incidents_rearm_same_id(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'incidents.sqlite';store=monitor.Store(path)
            for bid,status in [('deferred','deferred'),('accepted','accepted'),('unknown','unknown')]:
                store.db.execute('INSERT INTO batches(id,status) VALUES(?,?)',(bid,status))
            for iid,bid in [('unsubmitted',None),('refused','deferred'),('admitted','accepted'),('uncertain','unknown')]:
                store.db.execute("INSERT INTO incidents(id,volume,delivery,batch) VALUES(?,?,'covered_active_owner',?)",(iid,iid,bid))
            store.db.commit();store.close();store=monitor.Store(path)
            got=dict(store.db.execute('SELECT id,delivery FROM incidents'))
            self.assertEqual(got,{'unsubmitted':'pending','refused':'pending','admitted':'covered_active_owner','uncertain':'covered_active_owner'})
            self.assertEqual(store.db.execute("SELECT count(*) FROM audit WHERE kind='restored_busy_pending'").fetchone()[0],2)
            store.close();store=monitor.Store(path)
            self.assertEqual(store.db.execute("SELECT count(*) FROM audit WHERE kind='restored_busy_pending'").fetchone()[0],2)
            store.close()


class PendingCadence(unittest.TestCase):
    def test_busy_wait_does_not_grow_transport_failure_backoff(self):
        from test_t26 import sample
        with tempfile.TemporaryDirectory() as d:
            store=monitor.Store(Path(d)/'incidents.sqlite')
            config={'state_file':str(Path(d)/'incidents.sqlite'),'native_transport':{'enabled':True}}
            owner={'inventory_unknown':False,'coding_or_script_turns':['active']}
            meta={}
            for now in range(1000,1900,60):
                meta,out=t26_watch.cycle(store,config,{'ssd':sample('ssd',1,now)},{},owner,meta,now)
                self.assertEqual(out['status'],'pending_owner_busy_or_inventory_unknown')
                self.assertEqual(meta.get('failures',0),0)
                self.assertEqual(meta.get('next_attempt',0),0)
            self.assertEqual(store.db.execute('select count(*) from incidents').fetchone()[0],1)
            self.assertEqual(store.db.execute('select count(*) from attempts').fetchone()[0],0)
            store.close()
    def test_legacy_real_receipt_backoff_is_preserved(self):
        from test_t26 import sample
        with tempfile.TemporaryDirectory() as d:
            store=monitor.Store(Path(d)/'incidents.sqlite')
            store.db.execute("INSERT INTO batches(id,status) VALUES('old','unknown')");store.db.commit()
            cfg={'state_file':str(Path(d)/'incidents.sqlite'),'native_transport':{'enabled':True}}
            meta,out=t26_watch.cycle(store,cfg,{'ssd':sample('ssd',1)},{},{'inventory_unknown':False},
                                      {'next_attempt':2000,'failures':4},1000)
            self.assertEqual(out['status'],'backoff');self.assertEqual(meta['next_attempt'],2000)
            self.assertEqual(meta['failures'],4);store.close()
