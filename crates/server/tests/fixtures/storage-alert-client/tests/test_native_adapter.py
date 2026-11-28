"""Codec and durable-client regressions; these are NOT native integration evidence."""
import copy
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
import native_integration as driver
from pathlib import Path

from test_monitor import m, FakeBridge, sample
import native_adapter as n


def response(document, kind='accepted', execution=None):
    return {'protocol': n.PROTOCOL, 'outcome': kind, 'reason': 'fixture_reason',
            'no_admission': kind != 'accepted', 'automatic_launch_queued': False, 'replay': False,
            'execution_status': 'running' if kind == 'accepted' else None,
            'receipt': {'batch_id': document['batch_id'], **{k:document['intent'][k] for k in ('workspace_id','session_id')},
                        'intent_sha256': document['intent_sha256'], 'attempt_id': document['attempt_id'],
                        'state': kind, 'reason': 'fixture_reason',
                        'execution_id': (execution or str(uuid.uuid4())) if kind == 'accepted' else None}}


class NativeCodec(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'state.db'
        self.store=m.Store(self.path); self.fake=FakeBridge()
        self.store.observations(self.fake.samples,{},time.time())
        self.store.dispatch(self.fake.samples,self.fake,self.path)
        self.doc=self.fake.calls[0]

    def tearDown(self):
        self.store.close(); self.temp.cleanup()

    def decode(self, body):
        return n.decode(body,self.doc,self.doc['known_attempt_ids'])

    def test_exact_v2_wire_shape_and_unicode_canonical_binding(self):
        wire=n.request(self.doc)
        self.assertEqual(set(wire), {'protocol','batch_id','attempt_id','intent_sha256','intent','validation'})
        self.assertEqual(set(wire['intent']), {'workspace_id','session_id','executor_config_sha256','incidents','receipt_ref','prompt'})
        self.assertEqual(set(wire['validation']), {'observed_at','eligible_incident_ids','evidence_sha256'})
        self.assertNotIn('observations',n.canonical(wire))
        self.assertEqual(n.canonical({'z':'é','a':{'x':'雪'}}), '{"a":{"x":"雪"},"z":"é"}')
        self.assertEqual(n.canonical({'z':[{'b':2,'a':'é'}],'a':None}), '{"a":null,"z":[{"a":"é","b":2}]}')
        self.assertEqual(n.utc(1), '1970-01-01T00:00:01Z')
        self.assertEqual(n.utc(1.123), '1970-01-01T00:00:01.123Z')
        self.assertEqual(n.utc(1.123456), '1970-01-01T00:00:01.123456Z')
        changed=copy.deepcopy(self.doc);changed['intent']['prompt']+='changed'
        with self.assertRaises(ValueError):n.request(changed)

    def test_all_positive_outcomes_validate_full_native_binding(self):
        for kind in ('accepted','deferred','rejected'):
            self.assertEqual(self.decode(response(self.doc,kind))['kind'],kind)

    def test_corrupt_or_unproved_native_receipt_never_grants_retry(self):
        cases=[]
        for key,value in [('protocol','v1'),('no_admission',False),('automatic_launch_queued',True),
                          ('outcome','uncertain'),('replay',1),('reason','raw sensitive error!'),('execution_status','completed')]:
            body=response(self.doc,'deferred');body[key]=value;cases.append(body)
        for key,value in [('batch_id',str(uuid.uuid4())),('workspace_id',str(uuid.uuid4())),
                          ('session_id',str(uuid.uuid4())),('intent_sha256','0'*64),
                          ('attempt_id',str(uuid.uuid4())),('state','accepted'),('execution_id',str(uuid.uuid4()))]:
            body=response(self.doc,'deferred');body['receipt'][key]=value;cases.append(body)
        cases += [{},None,{'status':409}, {'outcome':'uncertain','receipt':None}]
        for body in cases:
            with self.subTest(body=body):self.assertEqual(self.decode(body)['kind'],'unknown')

    def test_previous_deferral_cannot_release_newer_uncertain_attempt(self):
        body=response(self.doc,'deferred');old=body['receipt']['attempt_id']
        self.doc['attempt_id']=str(uuid.uuid4());self.doc['known_attempt_ids'].append(self.doc['attempt_id'])
        self.assertEqual(self.decode(body)['kind'],'unknown')
        body=response(self.doc);body['receipt']['attempt_id']=old
        self.assertEqual(self.decode(body)['kind'],'accepted')

    def test_missing_execution_status_retains_accepted_binding(self):
        body=response(self.doc);body['execution_status']=None
        self.assertEqual(self.decode(body)['kind'],'accepted')
        body['receipt']['execution_id']=None
        self.assertEqual(self.decode(body)['kind'],'unknown')

    def test_failed_live_revalidation_breaks_debounce_and_leaves_private_failure_evidence(self):
        # A failure between periodic samples cannot count toward recovery.
        self.store.close();self.path=Path(self.temp.name)/'mount-failure.db';self.store=m.Store(self.path)
        self.store.observations(self.fake.samples,{},time.time())
        with self.store.db:
            self.store.db.execute('UPDATE volume_state SET state=?',
                (m.accounting.canonical({'critical_count':2,'recovery_count':2,'latched':True}),))
        self.fake.observe=lambda key: (_ for _ in ()).throw(ValueError('synthetic mount loss'))
        self.assertEqual(self.store.dispatch(self.fake.samples,self.fake,self.path),'recovered_or_invalid_before_admission')
        state=__import__('json').loads(self.store.db.execute('SELECT state FROM volume_state LIMIT 1').fetchone()[0])
        self.assertEqual((state['critical_count'],state['recovery_count']),(0,0))
        self.assertTrue(state['latched'])
        evidence=self.store.db.execute("SELECT detail FROM audit WHERE kind='observation_deferred'").fetchall()
        self.assertEqual(len(evidence),2)
        self.assertTrue(all('live_revalidation_unavailable' in row[0] for row in evidence))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM attempts').fetchone()[0],0)

    def test_adapter_rejects_saved_binding_drift_before_transport(self):
        calls=[]
        adapter=n.NativeAdapter(self.fake.binding(),lambda *args:calls.append(args),self.fake.observe,30)
        self.doc['intent']['executor_config_sha256']='0'*64
        self.doc['intent_sha256']=n.digest(self.doc['intent'])
        with self.assertRaises(ValueError):adapter.send(self.doc)
        self.assertEqual(calls,[])

    def test_same_and_regressed_observation_cannot_retry_after_deferral(self):
        self.store.close();self.path=Path(self.temp.name)/'fresh.db';self.store=m.Store(self.path)
        captured=time.time()
        self.fake.observe=lambda key: {**sample(), 'at':captured}
        self.fake.send=lambda doc: {'kind':'deferred','batch_id':doc['batch_id'],
            'intent_sha256':doc['intent_sha256'],'receipt_id':'fixture','definitely_not_admitted':True}
        self.store.observations(self.fake.samples,{},captured)
        self.assertEqual(self.store.dispatch(self.fake.samples,self.fake,self.path),'deferred')
        for stamp in (captured,captured-0.001):
            self.fake.observe=lambda key: {**sample(), 'at':stamp}
            self.assertEqual(self.store.dispatch(self.fake.samples,self.fake,self.path),'deferred_fresh_validation_required')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM attempts').fetchone()[0],1)

    def test_native_adapter_uncertain_reconciliation_uses_GET_only_after_restart(self):
        self.store.close();self.path=Path(self.temp.name)/'native.db';self.store=m.Store(self.path)
        calls=[];durable={}
        def transport(method,path,body):
            calls.append(method)
            if method=='POST':
                durable['reply']=response(body);raise TimeoutError('discard actual receipt fixture')
            return durable['reply']
        adapter=n.NativeAdapter(self.fake.binding(),transport,self.fake.observe,30)
        self.store.observations(self.fake.samples,{},time.time())
        self.assertEqual(self.store.dispatch(self.fake.samples,adapter,self.path),'unknown')
        self.store.close();self.store=m.Store(self.path)
        self.assertEqual(self.store.dispatch(self.fake.samples,adapter,self.path),'held_prior_delivery')
        self.assertEqual(calls,['POST','GET'])
        durable['reply']['execution_status']='completed'
        self.assertEqual(self.store.dispatch(self.fake.samples,adapter,self.path),'no_action')
        self.assertEqual(calls,['POST','GET','GET'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],2)


class NativeDriverBootstrap(unittest.TestCase):
    def test_driver_reaches_stdlib_HTTP_without_module_shadowing(self):
        # No response/body stub is native acceptance. This guards the exact
        # bootstrap failure observed in hosted native run39142867234.
        with tempfile.TemporaryDirectory() as root:
            descriptor={'fixture_protocol':'storage-native-fixture-v1','phase':'initial',
                'base_url':'http://127.0.0.1:49152/api','control_url':'http://127.0.0.1:49152/__fixture',
                'state_file':str(Path(root)/'journal.json'),
                'binding':FakeBridge().binding(),'max_validation_age_seconds':60}
            with patch.object(driver.http.client,'HTTPConnection') as connection:
                connection.return_value.request.side_effect=RuntimeError('fixture_connection_reached')
                with self.assertRaisesRegex(RuntimeError,'fixture_connection_reached'):
                    driver.run(descriptor)
                connection.assert_called_once_with('127.0.0.1',49152,timeout=30)

    def test_driver_rejects_live_port_or_non_fixture_before_transport(self):
        for url in ('http://127.0.0.1:4720/api','https://example.invalid/api'):
            with patch.object(driver.http.client,'HTTPConnection') as connection:
                with self.assertRaises(ValueError):
                    driver.run({'fixture_protocol':'storage-native-fixture-v1','base_url':url,
                                'control_url':url.replace('/api','/__fixture')})
                connection.assert_not_called()


if __name__=='__main__': unittest.main()
