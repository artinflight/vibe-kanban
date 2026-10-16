import json
import sqlite3
import unittest
import uuid
import test_browser
from scope_rollout import build_plan,apply_plan


class ScopeRolloutTests(unittest.TestCase):
    def setUp(self):
        test_browser.BrowserTests.setUp(self)
        from events import Events
        Events(self.store,lambda *args:None)
        self.vibe=sqlite3.connect(':memory:')
        self.vibe.execute('CREATE TABLE projects(id BLOB,archived INTEGER)')
        self.vibe.execute('INSERT INTO projects VALUES (?,0)',(uuid.UUID(self.project).bytes,))
        self.other=str(uuid.uuid4())
        self.archived=str(uuid.uuid4())
        self.vibe.execute('INSERT INTO projects VALUES (?,0)',(uuid.UUID(self.other).bytes,))
        self.vibe.execute('INSERT INTO projects VALUES (?,1)',(uuid.UUID(self.archived).bytes,))
        self.plan=build_plan(self.store.db,self.vibe,now=self.now[0])

    def tearDown(self):
        self.vibe.close();test_browser.BrowserTests.tearDown(self)

    def test_plan_is_read_only_and_explicit_about_archived_and_future(self):
        before=self.store.db.total_changes
        self.assertEqual(2,len(self.plan['target_projects']))
        self.assertFalse(self.plan['future_projects'])
        self.assertEqual(3,len(build_plan(self.store.db,self.vibe,True,now=self.now[0])['target_projects']))
        self.assertEqual(before,self.store.db.total_changes)
        self.assertEqual([self.project],json.loads(self.api.auth.session(self.token)['projects']))

    def test_apply_changes_only_scope_and_preserves_session_credentials(self):
        before=dict(self.api.auth.session(self.token))
        result=apply_plan(self.store.db,self.vibe,self.plan,self.plan['plan_sha256'],now=self.now[0])
        after=dict(self.api.auth.session(self.token))
        self.assertEqual(0,result['subscriptions_changed'])
        self.assertEqual({self.project,self.other},set(json.loads(after.pop('projects'))))
        before.pop('projects');self.assertEqual(before,after)
        self.assertEqual(2,self.store.db.execute('SELECT count(*) FROM project_grants').fetchone()[0])

    def test_stale_session_or_revocation_rolls_back_without_grants(self):
        self.api.auth.revoke(self.session['id'])
        with self.assertRaises(ValueError):apply_plan(self.store.db,self.vibe,self.plan,self.plan['plan_sha256'],now=self.now[0])
        self.assertEqual(0,self.store.db.execute('SELECT count(*) FROM project_grants').fetchone()[0])

    def test_inventory_changes_expiry_and_wrong_digest_fail_closed(self):
        for digest,clock in [('wrong',self.now[0]),(self.plan['plan_sha256'],self.now[0]+3601)]:
            with self.assertRaises(ValueError):apply_plan(self.store.db,self.vibe,self.plan,digest,now=clock)
        self.vibe.execute('INSERT INTO projects VALUES (?,0)',(uuid.uuid4().bytes,))
        with self.assertRaises(ValueError):apply_plan(self.store.db,self.vibe,self.plan,self.plan['plan_sha256'],now=self.now[0])
        self.assertEqual(0,self.store.db.execute('SELECT count(*) FROM project_grants').fetchone()[0])

    def test_existing_subscription_retained_and_excluded_from_new_requests(self):
        from events import Events
        Events(self.store,lambda *args:None)
        self.store.db.execute('INSERT INTO sidechat_subscriptions VALUES (?,?,?,?,?,?,1,NULL,NULL)',
            ('fixture','owner',json.dumps({'project_id':self.project}),'https://fixture.invalid','fixture-key',self.now[0]+7200))
        plan=build_plan(self.store.db,self.vibe,now=self.now[0])
        before=[tuple(row) for row in self.store.db.execute('SELECT * FROM sidechat_subscriptions')]
        self.assertEqual([{'project_ids':[self.other]}],[r['arguments'] for r in plan['subscription_requests']])
        apply_plan(self.store.db,self.vibe,plan,plan['plan_sha256'],now=self.now[0])
        self.assertEqual(before,[tuple(row) for row in self.store.db.execute('SELECT * FROM sidechat_subscriptions')])


if __name__=='__main__':unittest.main()
