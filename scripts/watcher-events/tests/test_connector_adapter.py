import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import connector_adapter as c
import monitor
import native_adapter as n

class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.sid=str(uuid.uuid4());self.wid=str(uuid.uuid4());self.bid=str(uuid.uuid4());self.aid=str(uuid.uuid4())
        self.saved={'executor':'CODEX','model_id':'existing-model','reasoning_id':'high','routing':{'mode':'shadow'}}
        self.config={'workspace_id':self.wid,'session_id':self.sid,'state_file':str(self.root/'incidents.sqlite'),
                     'vibe_db':str(self.root/'vibe.sqlite'),'activation_approved':True,'dispatch_transport':c.TRANSPORT,
                     'native_transport':{'enabled':False},'connector_transport':{'enabled':True,'executor_config_sha256':n.digest(self.saved),
                     'max_validation_age_seconds':30,'delegation_journal_dir':str(self.root)}}
        self.db=sqlite3.connect(self.config['vibe_db'])
        self.db.execute('CREATE TABLE execution_processes(id BLOB,session_id BLOB,status TEXT,executor_action TEXT,created_at TEXT)');self.db.commit()
        self.bridge=c.ConnectorBridge(self.config)
        intent={**self.bridge.binding(),'prompt':'[storage-response '+self.bid+'] read-only delivery verification','incidents':[]}
        self.doc={'batch_id':self.bid,'attempt_id':self.aid,'intent':intent,'intent_sha256':n.digest(intent),'validation':{'observed_at':n.utc(time.time())},'known_attempt_ids':[self.aid]}
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def insert(self,prompt=None,config=None,sid=None):
        eid=str(uuid.uuid4())
        self.db.execute('INSERT INTO execution_processes VALUES(?,?,?,?,datetime(\'now\'))',(uuid.UUID(eid).bytes,uuid.UUID(sid or self.sid).bytes,'running',json.dumps({'typ':{'prompt':prompt or self.doc['intent']['prompt'],'executor_config':config or self.saved}})))
        self.db.commit();return eid
    def result(self,eid=None,queued=False):
        data={'session_id':self.sid,'execution_id':eid}
        if queued:data['status']='queued'
        return types.SimpleNamespace(stdout=json.dumps({'id':self.aid,'result':{'content':[{'type':'text','text':json.dumps(data)}]}}),returncode=0)
    def send(self,fn):
        with patch.object(self.bridge,'ready',return_value=True),patch.object(c.subprocess,'run',side_effect=fn) as call:
            out=self.bridge.send(self.doc)
        return out,call.call_count
    def test_verified_execution_and_no_duplicate_after_reopen(self):
        def launch(*a,**kw):
            msg=json.loads(kw['input']);self.assertEqual(msg['params']['name'],'run_session_prompt')
            self.assertEqual(msg['params']['arguments'],{'session_id':self.sid,'prompt':self.doc['intent']['prompt']})
            return self.result(self.insert())
        out,count=self.send(launch);self.assertEqual(out['kind'],'accepted');self.assertEqual(count,1)
        self.bridge=c.ConnectorBridge(self.config)
        with patch.object(c.subprocess,'run',side_effect=AssertionError('duplicate')):
            self.assertEqual(self.bridge.send(self.doc)['execution_id'],out['execution_id'])
    def test_lost_ack_reconciles_exact_execution(self):
        def launch(*a,**kw):self.insert();raise TimeoutError()
        out,count=self.send(launch);self.assertEqual(out['kind'],'accepted');self.assertEqual(count,1)
    def test_lost_ack_without_execution_never_retries(self):
        out,count=self.send(lambda *a,**kw: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(out['kind'],'unknown');self.assertEqual(count,1)
        with patch.object(c.subprocess,'run',side_effect=AssertionError('resend')):
            self.assertEqual(c.ConnectorBridge(self.config).send(self.doc)['kind'],'unknown')
    def test_capacity_queue_remains_uncertain_then_reconciles(self):
        out,_=self.send(lambda *a,**kw:self.result(queued=True))
        self.assertEqual(out['reason'],'connector_queued_no_retry')
        eid=self.insert()
        self.assertEqual(self.bridge.lookup(self.bid,self.doc['intent_sha256'],self.doc)['execution_id'],eid)
    def test_busy_refusal_is_before_any_write(self):
        with patch.object(self.bridge,'ready',return_value=False),patch.object(c.subprocess,'run') as run:
            out=self.bridge.send(self.doc)
        self.assertEqual(out['kind'],'deferred');self.assertTrue(out['definitely_not_admitted']);run.assert_not_called();self.assertFalse(self.bridge.root.exists())
    def test_stale_refusal_is_before_any_write(self):
        self.doc['validation']['observed_at']=n.utc(time.time()-60)
        out,count=self.send(lambda *a,**kw:None)
        self.assertEqual(out['kind'],'deferred');self.assertEqual(count,0)
    def test_wrong_session_does_not_certify_delivery(self):
        out,_=self.send(lambda *a,**kw:self.result(self.insert(sid=str(uuid.uuid4()))))
        self.assertEqual(out['kind'],'unknown')
    def test_wrong_saved_config_does_not_certify_delivery(self):
        out,_=self.send(lambda *a,**kw:self.result(self.insert(config={**self.saved,'model_id':'changed'})))
        self.assertEqual(out['kind'],'unknown')
    def test_prompt_substring_is_not_exact_receipt(self):
        out,_=self.send(lambda *a,**kw:self.result(self.insert(prompt='Other '+self.doc['intent']['prompt'])))
        self.assertEqual(out['kind'],'unknown')
    def test_duplicate_matching_execution_fails_closed(self):
        def launch(*a,**kw):self.insert();return self.result(self.insert())
        out,_=self.send(launch);self.assertEqual(out['kind'],'unknown')
    def test_reported_execution_must_match_persisted_execution(self):
        def launch(*a,**kw):self.insert();return self.result(str(uuid.uuid4()))
        out,_=self.send(launch);self.assertEqual(out['reason'],'connector_execution_mismatch')
    def test_corrupted_intent_is_rejected_without_call(self):
        self.doc['intent']['prompt']+=' changed'
        with patch.object(c.subprocess,'run') as run:
            with self.assertRaises(ValueError):self.bridge.send(self.doc)
        run.assert_not_called()
    def test_reopen_after_outbox_commit_before_send_holds(self):
        self.bridge.root.mkdir()
        (self.bridge.root/(self.bid+'.json')).write_text(json.dumps({'transport':c.TRANSPORT,'batch_id':self.bid,'intent_sha256':self.doc['intent_sha256'],'attempt_id':self.aid,'not_before':time.time(),'state':'dispatching'}))
        with patch.object(c.subprocess,'run',side_effect=AssertionError('resend')):
            self.assertEqual(self.bridge.send(self.doc)['kind'],'unknown')
    def test_disabled_has_no_native_fallback(self):
        self.config['connector_transport']['enabled']=False
        with self.assertRaises(ValueError):monitor.Bridge(self.config)
        self.assertFalse(monitor.transport_enabled(self.config))
    def test_unknown_transport_rejected(self):
        self.config['dispatch_transport']='typo'
        with self.assertRaises(ValueError):monitor.Bridge(self.config)
    def test_owner_busy_prevents_config_resolution(self):
        with patch.object(c,'owner_idle',return_value=False),patch.object(c,'load_connector') as loader:
            self.assertFalse(self.bridge.ready());loader.assert_not_called()
    def test_config_drift_and_recommend_policy_hold(self):
        module=types.SimpleNamespace(http_get=lambda path:{'success':True,'data':{'workspace_id':self.wid,'executor':'CODEX'}},resolve_followup_config=lambda sid:{**self.saved,'model_id':'changed'})
        with patch.object(c,'owner_idle',return_value=True),patch.object(c,'load_connector',return_value=module):self.assertFalse(self.bridge.ready())
    def test_terminal_execution_read_is_bound_to_session(self):
        eid=self.insert();self.db.execute("UPDATE execution_processes SET status='completed'");self.db.commit()
        self.assertEqual(self.bridge.execution(eid),'completed')
        with self.assertRaises(ValueError):self.bridge.execution(str(uuid.uuid4()))


    def probe(self,expires=None):
        path=self.root/'connector-probe.json'
        path.write_text(json.dumps({'state':'pending','document':self.doc,'expires_at':expires if expires is not None else time.time()+100}))
        return path
    def test_probe_waits_for_idle_without_send(self):
        path=self.probe()
        with patch.object(c,'ConnectorBridge',return_value=self.bridge),patch.object(self.bridge,'ready',return_value=False),patch.object(self.bridge,'send') as send:
            self.assertEqual(c.process_probe(self.config),'pending_owner_busy_or_config_hold');send.assert_not_called()
        self.assertEqual(json.loads(path.read_text())['state'],'pending')
    def test_probe_expiry_never_sends(self):
        path=self.probe(time.time()-1)
        with patch.object(c,'ConnectorBridge',return_value=self.bridge),patch.object(self.bridge,'send') as send:
            self.assertEqual(c.process_probe(self.config),'expired');send.assert_not_called()
    def test_probe_send_then_lookup_only(self):
        path=self.probe()
        result={'kind':'accepted','execution_id':str(uuid.uuid4())}
        with patch.object(c,'ConnectorBridge',return_value=self.bridge),patch.object(self.bridge,'ready',return_value=True),patch.object(self.bridge,'send',return_value=result) as send,patch.object(self.bridge,'lookup',return_value=result),patch.object(self.bridge,'execution',return_value='completed'):
            self.assertEqual(c.process_probe(self.config),'accepted')
            self.assertEqual(c.process_probe(self.config),'completed')
            self.assertEqual(c.process_probe(self.config),'completed')
            self.assertEqual(send.call_count,1)

class OwnerInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.wid, self.sid, self.eid = (uuid.uuid4() for _ in range(3))
        self.config = {'workspace_id': str(self.wid), 'vibe_db': str(self.root/'db.sqlite'),
                       'connector_transport': {'delegation_journal_dir': str(self.root)}}
        self.db = sqlite3.connect(self.config['vibe_db'])
        self.db.executescript("CREATE TABLE watcher_job_leases(workspace_id BLOB, closed_at TEXT);"
                             "CREATE TABLE sessions(id BLOB, workspace_id BLOB);"
                             "CREATE TABLE execution_processes(id BLOB, session_id BLOB);"
                             "CREATE TABLE coding_agent_turns(execution_process_id BLOB, agent_session_id TEXT);")
        self.db.execute('INSERT INTO sessions VALUES(?,?)', (self.sid.bytes, self.wid.bytes))
        self.db.execute('INSERT INTO execution_processes VALUES(?,?)', (self.eid.bytes, self.sid.bytes))
        self.db.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (self.eid.bytes, 'fixture-thread'))
        self.db.commit()
        self.journal = self.root/'fixture-thread.json'
        self.inventory = patch('t26_watch.owner_status', return_value={'inventory_unknown': False})
        self.inventory.start()
    def tearDown(self):
        self.inventory.stop(); self.db.close(); self.tmp.cleanup()
    def test_unclosed_lease_holds_until_terminal_evidence(self):
        self.db.execute('INSERT INTO watcher_job_leases VALUES(?,NULL)', (self.wid.bytes,)); self.db.commit()
        self.assertFalse(c.owner_idle(self.config))
        self.db.execute("UPDATE watcher_job_leases SET closed_at='confirmed'"); self.db.commit()
        self.assertTrue(c.owner_idle(self.config))
    def test_unsettled_child_and_unknown_journal_hold(self):
        for status in ('running', 'unknown', None):
            self.journal.write_text(json.dumps({'child': {'status': status}}))
            self.assertFalse(c.owner_idle(self.config))
        self.journal.write_text(json.dumps({'child': {'status': 'completed'}}))
        self.assertTrue(c.owner_idle(self.config))
    def test_symlink_or_missing_journal_custody_is_not_idle(self):
        target = self.root/'empty.json'; target.write_text('{}')
        self.journal.symlink_to(target)
        self.assertFalse(c.owner_idle(self.config))
        self.config['connector_transport']['delegation_journal_dir'] = str(self.root/'absent')
        self.assertFalse(c.owner_idle(self.config))
    def test_busy_inventory_cannot_reach_database(self):
        with patch('t26_watch.owner_status', return_value={'inventory_unknown': True}), patch.object(c, 'database') as db:
            self.assertFalse(c.owner_idle(self.config)); db.assert_not_called()

class InfrastructureIdentityTests(unittest.TestCase):
    def test_only_complete_reviewed_identity_may_resolve_permission_hold(self):
        import t26_watch as w
        p = Path('/proc/123')
        identity = {'pid': 123, 'start_ticks': '456', 'boot_id': 'boot', 'name': 'sshd', 'cgroup': 'scope'}
        config = {'reviewed_infrastructure_processes': [{**identity, 'reason': 'reviewed transport broker'}]}
        with patch.object(w, 'process_identity', return_value=identity):
            self.assertTrue(w.reviewed_infrastructure(p, config))
            self.assertFalse(w.reviewed_infrastructure(p, {}))
        for key, changed in (('start_ticks', '457'), ('boot_id', 'newboot'), ('cgroup', 'other'), ('name', 'agent')):
            with patch.object(w, 'process_identity', return_value={**identity, key: changed}):
                self.assertFalse(w.reviewed_infrastructure(p, config))
        with patch.object(w, 'process_identity', side_effect=PermissionError):
            self.assertFalse(w.reviewed_infrastructure(p, config))

class SSHBrokerTests(unittest.TestCase):
    def test_only_root_owned_transport_ancestry_is_excluded(self):
        import t26_watch as w
        child = {'pid': 123, 'start_ticks': '10', 'name': 'sshd', 'parent': 12, 'uids': [os.getuid()]*4,
                 'cgroup': '0::/user.slice/user-'+str(os.getuid())+'.slice/session-1.scope'}
        parent = {'pid': 12, 'name': 'sshd', 'parent': 1, 'uids': [0]*4}
        with patch.object(w, 'ssh_broker_metadata', side_effect=[child,parent,child]):
            self.assertTrue(w.protected_ssh_broker(Path('/proc/123')))
        with patch.object(w, 'ssh_broker_metadata', side_effect=[child,{**parent,'uids':[os.getuid()]*4}]):
            self.assertFalse(w.protected_ssh_broker(Path('/proc/123')))
        with patch.object(w, 'ssh_broker_metadata', return_value={**child,'name':'python3'}):
            self.assertFalse(w.protected_ssh_broker(Path('/proc/123')))
        with patch.object(w, 'ssh_broker_metadata', side_effect=[child,parent,{**child,'start_ticks':'11'}]):
            self.assertFalse(w.protected_ssh_broker(Path('/proc/123')))

if __name__=='__main__':unittest.main()
