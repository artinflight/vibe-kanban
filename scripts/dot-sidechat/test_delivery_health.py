import datetime
import json
import unittest
import test_sidechat
from sidechat import Principal, Rejected
from events import Events
from delivery_health import registration_health


class DeliveryHealthTests(unittest.TestCase):
    setUp=test_sidechat.Contracts.setUp
    tearDown=test_sidechat.Contracts.tearDown

    def subscribe(self, **extra):
        params={'name':'vk.sidechat.owner_message.created','arguments':{'project_id':'p'},
                'delivery':{'mode':'webhook','url':'https://fixture.invalid/callback','secret':'fixture-key'},'ttlMs':60000}
        params.update(extra)
        return Events(self.s,lambda *args:(200,json.dumps({'challenge':args[-1]['challenge']})),lambda:self.now).subscribe(self.owner,params)

    def health(self, principal=None):
        return registration_health(self.s,principal or self.dot,{'thread_id':self.t},self.now)

    def test_renewal_deadline_precedes_actual_expiry_without_changing_finite_limit(self):
        for ttl in (60000,86400000,604800000):
            result=self.subscribe(ttlMs=ttl)
            renew=datetime.datetime.fromisoformat(result['refreshBefore']).timestamp()
            expiry=self.s.db.execute('SELECT expires FROM sidechat_subscriptions WHERE id=?',(result['id'],)).fetchone()[0]
            self.assertEqual(self.now+ttl/1000,expiry)
            self.assertLess(self.now,renew);self.assertLess(renew,expiry)
        with self.assertRaises(Rejected):self.subscribe(ttlMs=0)

    def test_expiry_health_is_readonly_and_not_an_agent_permission(self):
        self.subscribe();self.now+=61
        before=self.s.db.total_changes
        self.s.db.execute('PRAGMA query_only=ON')
        result=self.health()
        self.assertEqual('expired',result['status']);self.assertFalse(result['agent_prompt_dependency'])
        self.assertEqual(before,self.s.db.total_changes)
        self.assertNotIn('secret',json.dumps(result));self.assertNotIn('https://',json.dumps(result))

    def test_registered_due_missing_overlap_and_wrong_owner_are_distinct(self):
        self.assertEqual('unavailable',self.health()['status'])
        self.subscribe();result=self.health()
        self.assertEqual('registered',result['status']);self.assertTrue(result['renewal_due'])
        self.assertEqual('not_confirmed',result['delivery'])
        self.subscribe(arguments={'thread_id':self.t})
        self.assertEqual('ambiguous',self.health()['status'])
        with self.assertRaises(Rejected):self.health(Principal('bob','dot'))
