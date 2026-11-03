"""Expiry proposal tests use isolated generated source and fixture-only stores."""
import hashlib
import os
import shutil
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prepare_delivery_expiry import PATCHES, prepare


BOOT = r'''
import json
from pathlib import Path
import sys
import tempfile
import uuid
sys.path.insert(0, sys.argv[1])
from sidechat import Store, Principal, Rejected
from events import Events
from scope_migration import delivery_binding
from delivery_health import registration_health
workspace = tempfile.TemporaryDirectory()
now = [1000.]
s = Store(Path(workspace.name) / 'chat.sqlite', clock=lambda: now[0])
owner = Principal('owner', 'owner')
s.register_scope('owner', 'project', 'issue', 'workspace')
t = s.resolve(owner, 'project', 'issue', 'workspace')['id']
calls = []
def sender(url, key, subscription, event, body):
    calls.append((subscription, event, body))
    if body.get('type') == 'verification':
        return 200, json.dumps({'challenge': body['challenge']})
    return 202, ''
events = Events(s, sender, clock=lambda: now[0])
params = {'name': 'vk.sidechat.owner_message.created',
          'arguments': {'project_id': 'project'},
          'delivery': {'mode': 'webhook', 'url': 'https://fixture.invalid',
                       'secret': 'fixture-only'}}
def message():
    return s.append(owner, t, 'workspace', str(uuid.uuid4()), 'Fixture message')
'''


class DeliveryExpiryProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        public = Path(__file__).resolve().parent
        source = Path(os.environ['DOT_EXPIRY_CANDIDATE_BASELINE']) if 'DOT_EXPIRY_CANDIDATE_BASELINE' in os.environ else Path(cls.temp.name)/'baseline'
        if 'DOT_EXPIRY_CANDIDATE_BASELINE' not in os.environ:
            source.mkdir()
            for f in public.iterdir():
                if f.is_file() and f.suffix in ('.py','.json'): shutil.copyfile(f,source/f.name)
            shutil.copyfile(public/'fixtures/legacy_delivery_binding.py',source/'scope_migration.py')
        cls.baseline = source
        expected = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                    for name in PATCHES}
        cls.candidate = Path(cls.temp.name) / 'source'
        cls.receipt = prepare(source, expected, cls.candidate)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, code):
        result = subprocess.run([sys.executable, '-I', '-B', '-c', BOOT + code,
                                 str(self.candidate)], capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_permanent_delivery_survives_time_and_delivers_once(self):
        self.run_case('''
sub = events.subscribe(owner, params)
assert sub['refreshBefore'] is None
assert s.db.execute('SELECT expires FROM sidechat_subscriptions').fetchone()[0] == 0
m = message()
now[0] += 40 * 365 * 86400
job = events.deliver_one('owner')
assert job and job['http_status'] == 202
assert events.deliver_one('owner') is None
assert s.db.execute('SELECT expires FROM bindings WHERE thread=?', (t,)).fetchone()[0] == 0
assert len([c for c in calls if 'data' in c[2]]) == 1
''')

    def test_explicit_unsubscribe_still_revokes_permanent_delivery(self):
        self.run_case('''
events.subscribe(owner, params)
message()
events.sync('owner')
events.subscribe(owner, params, unsubscribe=True)
assert events.deliver_one('owner') is None
assert s.db.execute('SELECT active FROM bindings').fetchone()[0] == 0
assert s.db.execute('SELECT active FROM sidechat_subscriptions').fetchone()[0] == 0
''')

    def test_scope_revocation_still_blocks_permanent_delivery(self):
        self.run_case('''
events.subscribe(owner, params)
message()
events.sync('owner')
s.db.execute('DELETE FROM scopes')
assert events.deliver_one('owner') is None
assert s.db.execute('SELECT active FROM bindings').fetchone()[0] == 0
''')

    def test_missing_scope_and_failed_callback_never_get_persistent_access(self):
        self.run_case('''
try:
    events.subscribe(Principal('other', 'owner'), params)
except Rejected:
    pass
else:
    raise AssertionError('foreign owner accepted')
bad = Events(s, lambda *a: (200, '{"challenge":"wrong"}'), clock=lambda: now[0])
try:
    bad.subscribe(owner, params)
except Rejected:
    pass
else:
    raise AssertionError('unverified callback accepted')
assert s.db.execute('SELECT count(*) FROM sidechat_subscriptions').fetchone()[0] == 0
''')

    def test_routine_finite_renewal_cannot_expire_permanent_subscription(self):
        self.run_case('''
sub = events.subscribe(owner, params)
renewed = events.subscribe(owner, dict(params, ttlMs=60000))
assert sub['id'] == renewed['id']
assert renewed['refreshBefore'] is None
assert s.db.execute('SELECT expires FROM sidechat_subscriptions').fetchone()[0] == 0
''')

    def test_legacy_finite_request_cannot_restore_expiry(self):
        self.run_case('''
sub = events.subscribe(owner, dict(params, ttlMs=60000))
assert sub['refreshBefore'] is None
message()
now[0] += 40 * 365 * 86400
assert events.deliver_one('owner')['http_status'] == 202
''')

    def test_permanent_scope_binding_keeps_filter_and_overlap_checks(self):
        self.run_case('''
events.subscribe(owner, params)
result = delivery_binding(s, Principal('owner', 'dot'), t)
assert result['subscription_id']
filters = s.db.execute('SELECT filters FROM sidechat_subscriptions').fetchone()[0]
events.subscribe(owner, dict(params, arguments={'thread_id': t}))
message()
assert events.deliver_one('owner') is None
assert s.db.execute('SELECT filters FROM sidechat_subscriptions ORDER BY rowid').fetchone()[0] == filters
''')


    def test_health_readonly_until_revoked(self):
        self.run_case("events.subscribe(owner, params)\nnow[0] += 40 * 365 * 86400\ns.db.execute('PRAGMA query_only=ON')\nbefore=s.db.total_changes\nh=registration_health(s,Principal('owner','dot'),{'thread_id':t},now[0])\nassert h['status']=='registered' and h['lifetime']=='until_revoked'\nassert h['expires_at'] is None and h['renewal_due'] is False\nassert h['delivery']=='not_confirmed' and h['agent_prompt_dependency'] is False\nassert before==s.db.total_changes\nassert 'https://' not in json.dumps(h) and 'fixture-only' not in json.dumps(h)\n")

    def test_durable_reopen_no_replay(self):
        self.run_case("events.subscribe(owner,params)\nmessage()\nassert events.deliver_one('owner')['http_status']==202\ns.db.close()\ns=Store(Path(workspace.name)/'chat.sqlite',clock=lambda:now[0])\nevents=Events(s,sender,clock=lambda:now[0])\nnow[0]+=40*365*86400\nassert events.deliver_one('owner') is None\nmessage()\nassert events.deliver_one('owner')['http_status']==202\nassert len([c for c in calls if 'data' in c[2]])==2\n")

    def test_callback_gone_revokes(self):
        self.run_case("events.subscribe(owner,params)\nmessage()\nevents.sender=lambda *a:(410,'')\nassert events.deliver_one('owner')['http_status']==410\nassert s.db.execute('SELECT active FROM sidechat_subscriptions').fetchone()[0]==0\nnow[0]+=40*365*86400\nassert events.deliver_one('owner') is None\n")

    def test_finite_old_rows_not_silently_promoted(self):
        self.run_case("sub=events.subscribe(owner,params)\ns.db.execute('UPDATE sidechat_subscriptions SET expires=?',(now[0]+60,))\nmessage()\nnow[0]+=61\nassert events.deliver_one('owner') is None\nassert registration_health(s,Principal('owner','dot'),{'thread_id':t},now[0])['status']=='expired'\nassert events.subscribe(owner,params)['id']==sub['id']\nassert events.deliver_one('owner')['http_status']==202\n")

    def test_disjoint_all_projects_cover_future(self):
        self.run_case("events.subscribe(owner,params)\ns.db.execute('INSERT INTO owner_project_policies VALUES (?,1)',('owner',))\ns.db.execute('INSERT OR IGNORE INTO project_grants VALUES (?,?)',('owner','project'))\ns.db.execute('INSERT OR IGNORE INTO project_grants VALUES (?,?)',('owner','future'))\nevents.subscribe(owner,dict(params,arguments={'all_projects':True,'exclude_project_ids':['project']}))\ns.register_scope('owner','future','future-issue','future-workspace')\nf=s.resolve(owner,'future','future-issue','future-workspace')['id']\nmessage()\ns.append(owner,f,'future-workspace',str(uuid.uuid4()),'Fixture future message')\nnow[0]+=40*365*86400\nassert events.deliver_one('owner')['http_status']==202\nassert events.deliver_one('owner')['http_status']==202\nassert events.deliver_one('owner') is None\nassert len({c[0] for c in calls if 'data' in c[2]})==2\n")

    def test_signing_key_rotation_grace_unchanged(self):
        self.run_case("events.subscribe(owner,params)\nevents.subscribe(owner,dict(params,delivery=dict(params['delivery'],secret='new-fixture-key')))\nassert s.db.execute('SELECT rotation_until FROM sidechat_subscriptions').fetchone()[0]==now[0]+300\nkeys=[]\nevents.sender=lambda url,key,*a:(keys.append(key) or 202,'')\nmessage()\nassert events.deliver_one('owner')['http_status']==202\nassert keys[0]==['new-fixture-key','fixture-only']\nnow[0]+=301\nmessage()\nassert events.deliver_one('owner')['http_status']==202\nassert keys[1]=='new-fixture-key'\n")

    def test_preparation_pins_preserves_sources_and_requires_confirmation(self):
        self.assertFalse(self.receipt['installed'])
        self.assertEqual(0,self.receipt['subscriptions_modified'])
        self.assertTrue(self.receipt['requires_action_time_confirmation'])
        for f in self.baseline.iterdir():
            if f.is_file() and f.suffix in ('.py','.json') and f.name not in PATCHES:
                self.assertEqual(f.read_bytes(),(self.candidate/f.name).read_bytes())
        expected={n:hashlib.sha256((self.baseline/n).read_bytes()).hexdigest() for n in PATCHES}
        expected['events.py']='0'*64
        output=Path(self.temp.name)/'bad'
        with self.assertRaises(ValueError):prepare(self.baseline,expected,output)
        self.assertFalse(output.exists())

    def test_only_delivery_methods_change(self):
        def kept(path,cls,names):
            tree=ast.parse(path.read_text())
            parent=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
            parent.body=[n for n in parent.body if not isinstance(n,ast.FunctionDef) or n.name not in names]
            return ast.dump(tree)
        for file,cls,names in [('sidechat.py','Store',{'bind','claim'}),('events.py','Events',{'subscribe','sync','deliver_one'})]:
            self.assertEqual(kept(self.baseline/file,cls,names),kept(self.candidate/file,cls,names))


if __name__ == '__main__':
    unittest.main()
