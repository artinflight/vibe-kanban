import json
import sqlite3
import unittest
import uuid
import test_browser
from scope_rollout import build_plan,apply_plan,reconcile_projects


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

    def all_plan(self):
        return build_plan(self.store.db,self.vibe,now=self.now[0],future_projects=True)

    def test_all_projects_includes_archived_and_automatically_expands_legacy_browser(self):
        plan=self.all_plan()
        self.assertTrue(plan['future_projects']);self.assertTrue(plan['include_archived'])
        self.assertEqual(3,len(plan['target_projects']))
        apply_plan(self.store.db,self.vibe,plan,plan['plan_sha256'],now=self.now[0])
        future=str(uuid.uuid4())
        self.vibe.execute('INSERT INTO projects VALUES (?,1)',(uuid.UUID(future).bytes,))
        before=dict(self.api.auth.session(self.token));before.pop('projects')
        self.assertEqual(1,reconcile_projects(self.store.db,self.vibe,now=self.now[0])['sessions_updated'])
        session=self.api.auth.session(self.token)
        self.assertEqual({self.project,self.other,self.archived,future},set(json.loads(session['projects'])))
        session.pop('projects');self.assertEqual(before,session)
        # Exercise the unchanged browser's actual scope/read path for a project
        # created AFTER policy activation, without pairing or a browser restart.
        self.scope.update(project=future)
        page=self.api.page(self.api.auth.session(self.token),self.workspace)
        self.assertEqual(future,page['scope']['project'])
        self.assertEqual(0,reconcile_projects(self.store.db,self.vibe,now=self.now[0])['sessions_updated'])

    def test_future_policy_never_revives_or_expands_unreviewed_pairings(self):
        plan=self.all_plan();apply_plan(self.store.db,self.vibe,plan,plan['plan_sha256'],now=self.now[0])
        self.api.auth.revoke(self.session['id'])
        grant=self.api.auth.grant('owner',[self.project]);token,_=self.api.auth.pair(grant['pairing_code'])
        future=str(uuid.uuid4());self.vibe.execute('INSERT INTO projects VALUES (?,0)',(uuid.UUID(future).bytes,))
        reconcile_projects(self.store.db,self.vibe,now=self.now[0])
        self.assertEqual(1,self.store.db.execute('SELECT revoked FROM browser_sessions WHERE id=?',(self.session['id'],)).fetchone()[0])
        self.assertEqual([self.project],json.loads(self.api.auth.session(token)['projects']))
        self.store.db.execute('UPDATE owner_project_policies SET enabled=0')
        newest=str(uuid.uuid4());self.vibe.execute('INSERT INTO projects VALUES (?,0)',(uuid.UUID(newest).bytes,))
        reconcile_projects(self.store.db,self.vibe,now=self.now[0])
        self.assertIsNone(self.store.db.execute('SELECT 1 FROM project_grants WHERE project=?',(newest,)).fetchone())

    def test_wildcard_preserves_old_subscription_and_covers_future_without_duplicates(self):
        from events import Events
        from sidechat import Principal
        sent=[]
        def sender(url,key,sid,eid,body):
            if body.get('type')=='verification':return 200,json.dumps({'challenge':body['challenge']})
            sent.append((sid,body));return 200,''
        events=Events(self.store,sender,lambda:self.now[0])
        principal=Principal('owner','owner')
        def params(arguments):
            return {'name':'vk.sidechat.owner_message.created','arguments':arguments,
                    'delivery':{'mode':'webhook','url':'https://fixture.invalid/callback','secret':'fixture-key'}}
        # Existing subscription stays byte-for-byte unchanged, including its key.
        self.api.page(self.session,self.workspace)
        original=events.subscribe(principal,params({'project_id':self.project}))
        before=[tuple(row) for row in self.store.db.execute('SELECT * FROM sidechat_subscriptions')]
        plan=self.all_plan()
        self.assertEqual({'all_projects':True,'exclude_project_ids':[self.project]},plan['subscription_requests'][0]['arguments'])
        apply_plan(self.store.db,self.vibe,plan,plan['plan_sha256'],now=self.now[0])
        self.assertEqual(before,[tuple(row) for row in self.store.db.execute('SELECT * FROM sidechat_subscriptions')])
        broad=events.subscribe(principal,params(plan['subscription_requests'][0]['arguments']))
        first=self.api.send(self.api.auth.session(self.token),{'workspace':self.workspace,'request':str(uuid.uuid4()),'body':'old project'})
        self.assertIsNotNone(events.deliver_one('owner'));self.assertIsNone(events.deliver_one('owner'))
        future=str(uuid.uuid4());self.vibe.execute('INSERT INTO projects VALUES (?,1)',(uuid.UUID(future).bytes,))
        reconcile_projects(self.store.db,self.vibe,now=self.now[0])
        self.scope.update(project=future,issue=str(uuid.uuid4()),workspace=str(uuid.uuid4()))
        self.workspace=self.scope['workspace']
        second=self.api.send(self.api.auth.session(self.token),{'workspace':self.workspace,'request':str(uuid.uuid4()),'body':'future archived project'})
        self.assertIsNotNone(events.deliver_one('owner'));self.assertIsNone(events.deliver_one('owner'))
        self.assertEqual([original['id'],broad['id']],[row[0] for row in sent])
        self.assertEqual({first['id'],second['id']},{row[1]['data']['message_id'] for row in sent})
        self.assertEqual([1,1],[row[0] for row in self.store.db.execute('SELECT attempts FROM outbox')])

    def test_all_scope_requires_owner_policy_and_overlap_still_fails_closed(self):
        from events import Events
        from sidechat import Principal,Rejected
        def sender(url,key,sid,eid,body):return 200,json.dumps({'challenge':body.get('challenge')})
        events=Events(self.store,sender,lambda:self.now[0]);principal=Principal('owner','owner')
        def params(arguments):
            return {'name':'vk.sidechat.owner_message.created','arguments':arguments,
                    'delivery':{'mode':'webhook','url':'https://fixture.invalid/callback','secret':'fixture-key'}}
        with self.assertRaises(Rejected):events.subscribe(principal,params({'all_projects':True,'exclude_project_ids':[]}))
        plan=self.all_plan();apply_plan(self.store.db,self.vibe,plan,plan['plan_sha256'],now=self.now[0])
        with self.assertRaises(Rejected):events.subscribe(Principal('foreign','owner'),params({'all_projects':True,'exclude_project_ids':[]}))
        for arguments in [{'all_projects':False,'exclude_project_ids':[]},{'all_projects':True},{'all_projects':True,'exclude_project_ids':[self.project,self.project]}]:
            with self.assertRaises(Rejected):events.subscribe(principal,params(arguments))
        events.subscribe(principal,params({'all_projects':True,'exclude_project_ids':[]}))
        events.subscribe(principal,params({'project_id':self.project}))
        self.api.send(self.api.auth.session(self.token),{'workspace':self.workspace,'request':str(uuid.uuid4()),'body':'overlap'})
        self.assertIsNone(events.deliver_one('owner'))

    def test_destination_mismatch_cannot_starve_other_threads(self):
        from events import Events
        from sidechat import Principal
        events=Events(self.store,lambda *args:(200,''),lambda:self.now[0])
        self.api.page(self.session,self.workspace)
        thread=self.store.db.execute('SELECT id FROM threads').fetchone()[0]
        self.store.bind(Principal('owner','owner'),thread,'prior-destination')
        self.store.db.execute('INSERT INTO sidechat_subscriptions VALUES (?,?,?,?,?,?,1,NULL,NULL)',
            ('replacement','owner',json.dumps({'project_id':self.project}),'https://fixture.invalid','fixture-key',self.now[0]+7200))
        # Sync fails closed for this thread but returns normally for the worker.
        events.sync('owner')
        row=self.store.db.execute('SELECT subscription,active FROM bindings').fetchone()
        self.assertEqual(('prior-destination',0),tuple(row))


if __name__=='__main__':unittest.main()
