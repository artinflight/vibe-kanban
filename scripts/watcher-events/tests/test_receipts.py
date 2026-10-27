import copy
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from test_monitor import m, FakeBridge, sample


class ReceiptBridge(FakeBridge):
    def __init__(self):
        super().__init__()
        self.kind = 'accepted'
        self.durable = {}
        self.lookups = []

    def response(self, document, kind):
        return {'kind':kind, 'batch_id':document['batch_id'], 'intent_sha256':document['intent_sha256'],
                'execution_id':self.outcome, 'receipt_id':'fixture-durable-receipt',
                'definitely_not_admitted':kind in {'deferred','rejected'},
                'reason':{'accepted':'admitted','deferred':'native_capacity_hold','rejected':'scope_rejected'}[kind]}

    def send(self, document):
        self.calls.append(copy.deepcopy(document))
        if isinstance(self.outcome,Exception):raise self.outcome
        response=self.response(document,self.kind)
        self.durable[document['batch_id']]=response
        return response

    def lookup(self,bid,fingerprint,document=None):
        self.lookups.append((bid,fingerprint))
        return self.lookup_result


class Receipts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'state.db'
        self.s=m.Store(self.path);self.b=ReceiptBridge()

    def tearDown(self):
        self.s.close();self.temp.cleanup()

    def poll(self,values=None):
        values=self.b.samples if values is None else values
        self.s.observations(values,{},time.time())
        return self.s.dispatch(values,self.b,self.path)

    def restart(self):
        self.s.close();self.s=m.Store(self.path)

    def test_definite_capacity_hold_retries_same_batch_and_intent_after_restart(self):
        self.b.kind='deferred';self.assertEqual(self.poll(),'deferred')
        original=self.b.calls[0];self.restart();self.b.kind='accepted'
        self.assertEqual(self.poll(),'accepted')
        retry=self.b.calls[1]
        self.assertEqual(original['batch_id'],retry['batch_id'])
        self.assertEqual(original['intent'],retry['intent'])
        self.assertEqual(original['intent_sha256'],retry['intent_sha256'])
        self.assertNotEqual(original['attempt_id'],retry['attempt_id'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM batches').fetchone()[0],1)

    def test_definite_rejection_is_terminal_and_not_unknown(self):
        self.b.kind='rejected';self.assertEqual(self.poll(),'rejected');self.restart()
        self.assertEqual(self.poll(),'no_action');self.assertEqual(len(self.b.calls),1)
        self.assertEqual(self.s.db.execute('SELECT reason FROM batches').fetchone()[0],'scope_rejected')

    def test_transport_exception_stays_uncertain_across_restart(self):
        self.b.outcome=TimeoutError();self.assertEqual(self.poll(),'unknown');self.restart()
        self.assertEqual(self.poll(),'held_prior_delivery');self.assertEqual(len(self.b.calls),1)
        self.assertEqual(len(self.b.lookups),1)

    def test_positive_accepted_lookup_heals_uncertain_without_resend(self):
        self.b.outcome=TimeoutError();self.poll();original=self.b.calls[0]
        self.restart();self.b.outcome=str(uuid.uuid4())
        self.b.lookup_result=self.b.response(original,'accepted')
        self.assertEqual(self.poll(),'held_prior_delivery');self.assertEqual(len(self.b.calls),1)
        self.assertEqual(self.s.db.execute('SELECT status FROM batches').fetchone()[0],'accepted')
        self.b.status='completed';self.assertEqual(self.poll(),'no_action')

    def test_positive_no_admission_lookup_allows_same_key_retry(self):
        self.b.outcome=TimeoutError();self.poll();original=self.b.calls[0];self.restart()
        self.b.outcome=str(uuid.uuid4());self.b.lookup_result=self.b.response(original,'deferred')
        self.assertEqual(self.poll(),'accepted');self.assertEqual(len(self.b.calls),2)
        self.assertEqual(self.b.calls[1]['batch_id'],original['batch_id'])

    def test_not_found_and_unbound_or_unproved_responses_do_not_release_uncertainty(self):
        self.b.outcome=TimeoutError();self.poll();original=self.b.calls[0]
        invalid=[{'kind':'not_found'}, {'status':409},
                 {**self.b.response(original,'deferred'),'definitely_not_admitted':False},
                 {**self.b.response(original,'accepted'),'batch_id':str(uuid.uuid4())},
                 {**self.b.response(original,'rejected'),'intent_sha256':'0'*64}]
        for result in invalid:
            with self.subTest(result=result):
                self.b.lookup_result=result;self.restart()
                self.assertEqual(self.poll(),'held_prior_delivery')
        self.assertEqual(len(self.b.calls),1)

    def test_crash_after_send_before_response_can_reconcile_without_another_send(self):
        with patch.object(self.b,'send',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.poll()
        row=self.s.db.execute('SELECT * FROM batches').fetchone()
        self.restart()
        self.b.lookup_result={'kind':'accepted','batch_id':row['id'],'intent_sha256':row['fingerprint'],
                              'execution_id':str(uuid.uuid4()),'receipt_id':'positive-native-receipt'}
        self.assertEqual(self.poll(),'held_prior_delivery');self.assertFalse(self.b.calls)

    def test_recovery_does_not_erase_uncertain_receipt(self):
        self.b.outcome=TimeoutError();self.poll()
        self.assertEqual(self.poll({'os':sample(80),'ssd':sample(80)}),'held_prior_delivery')
        self.assertEqual(self.s.db.execute('SELECT status FROM batches').fetchone()[0],'unknown')

    def test_recovered_definite_deferral_is_retired_without_replaying_stale_incident(self):
        self.b.kind='deferred';self.poll();old=self.b.calls[0]['batch_id']
        self.b.kind='accepted';self.b.samples={'os':sample(80),'ssd':sample(98)}
        self.assertEqual(self.poll(),'accepted')
        new=self.b.calls[1]
        self.assertNotEqual(old,new['batch_id'])
        self.assertEqual([x['incident_id'] for x in new['intent']['incidents']],
                         [self.s.db.execute("SELECT id FROM incidents WHERE volume='ssd'").fetchone()[0]])
        self.assertEqual(self.s.db.execute('SELECT status FROM batches WHERE id=?',(old,)).fetchone()[0],
                         'cancelled_recovered')

    def test_ineligible_member_of_definite_deferral_does_not_block_other_verified_pressure(self):
        self.b.kind='deferred';self.poll();old=self.b.calls[0]['batch_id']
        self.b.kind='accepted';self.b.samples={'os':sample(84),'ssd':sample(98)}
        self.assertEqual(self.poll(),'accepted')
        self.assertEqual(len(self.b.calls[1]['intent']['incidents']),1)
        self.assertEqual(self.b.calls[1]['intent']['incidents'][0]['incident_id'],
                         self.s.db.execute("SELECT id FROM incidents WHERE volume='ssd'").fetchone()[0])
        self.assertEqual(self.s.db.execute('SELECT status FROM batches WHERE id=?',(old,)).fetchone()[0],
                         'cancelled_revalidation')
        self.assertIsNone(self.s.db.execute("SELECT recovered FROM incidents WHERE volume='os'").fetchone()[0])

    def test_unreviewed_production_adapter_cannot_send_even_with_activation_config(self):
        bridge=m.Bridge({'workspace_id':str(uuid.uuid4()),'session_id':str(uuid.uuid4()),
                         'activation_approved':True,'admission_protocol':'guessed_protocol'})
        self.s.observations(self.b.samples,{},time.time())
        self.assertEqual(self.s.dispatch(self.b.samples,bridge,self.path),'deferred')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM batches').fetchone()[0],0)


if __name__=='__main__':unittest.main()
