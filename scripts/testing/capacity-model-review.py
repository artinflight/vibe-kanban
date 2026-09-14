"""Offline PR112 regression; only the existing disposable HTTP fixture is accepted."""
import json, os, sqlite3, subprocess, sys, time, uuid
from pathlib import Path
from urllib.request import Request, urlopen

root = Path('/mnt/vk-storage/codexusage-capacity/vk-continuation-http-9uy_k779')
repo = Path(__file__).resolve().parents[2]
output = Path('/mnt/vk-storage/codexusage-capacity/pr112-repair')
binary = Path(sys.argv[1]).resolve()
assert str(binary).startswith('/mnt/vk-storage/')
f = json.loads((root / 'fixture.json').read_text())
db = sqlite3.connect(root / 'release-xdg/vibe-kanban/db.v2.sqlite')
assert db.execute('select count(*) from sessions').fetchone()[0] == 1
sid = uuid.UUID(f['sessionId']).bytes
assert db.execute("select count(*) from execution_processes where status='running'").fetchone()[0] == 0
home = root / 'home'
profiles = root / 'release-xdg/vibe-kanban/profiles.json'
original_profile = profiles.read_text()
profile = json.loads(original_profile)
preset = profile['executors']['CODEX']['DEFAULT']['CODEX']
preset['env']['VK_GOAL_TEST_CAPTURE'] = '1'
token = (root / 'token').read_text().strip()
origin = 'http://127.0.0.1:49173'
results = []
process = None

def api(path, body=None, private=False):
    headers = {'Content-Type': 'application/json'}
    if private: headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request(origin + '/api/' + path, data=None if body is None else json.dumps(body).encode(), headers=headers), timeout=20) as response:
        return json.load(response)

def capacity(path='', body=None): return api('capacity' + path, body, True)
def state(): return capacity()['state']
def mutation(path, body):
    s = state()
    return capacity(path, dict(body, epoch=s['epoch'], revision=s['revision']))
def wait(check, seconds=35):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check(): return
        time.sleep(.1)
    raise AssertionError('Timed out')
def native():
    with sqlite3.connect(home / 'goals_1.sqlite') as con:
        return con.execute('select goal_id, thread_id, objective, created_at_ms from thread_goals where thread_id=?', (f['threadId'],)).fetchone()
before = native()
progress = json.loads((home / 'vk-goal-progress' / (f['threadId'] + '.json')).read_text())['completed']

def boot(default):
    global process
    preset['model'] = default
    preset['model_reasoning_effort'] = 'low'
    profiles.write_text(json.dumps(profile))
    env = dict(os.environ, CODEX_HOME=str(home), TMPDIR=str(root/'tmp'), XDG_DATA_HOME=str(root/'release-xdg'),
        VK_CAPACITY_STATE_DIR=str(root/'controller'), VK_CAPACITY_GUARD=str(output/'vk-capacity-guard'),
        VK_CAPACITY_TOKEN_FILE=str(root/'token'), VK_USE_SYSTEMD_RUN='1',
        VK_CODEX_BASE_COMMAND=f'python3 {repo}/scripts/testing/codex_goal_provider.py', VK_CAPACITY_MODEL_PROVIDER='fixture',
        VK_FRONTEND_DIST_DIR=str(output/'frontend'), HOST='127.0.0.1', BACKEND_PORT='49173')
    env.pop('OPENAI_API_KEY', None)
    log = (output/'native-backend.log').open('a')
    process = subprocess.Popen([str(binary)], cwd=repo, env=env, stdout=log, stderr=log)
    def ready():
        assert process.poll() is None
        try: state(); return True
        except OSError: return False
    wait(ready)
    info = api('info')['data']
    assert info['config']['workspace_dir'] == str(root/'workspaces')
    assert info['config']['analytics_enabled'] is False

def halt():
    global process
    if process:
        process.terminate()
        process.wait(timeout=15)
        process = None

def run(expected, ordinary=False):
    for name in ['capacity-request-active','capacity-resume-requests.jsonl','capacity-model-requests.jsonl']:
        (home/name).unlink(missing_ok=True)
    if ordinary:
        mutation('/eligibility', {'sessionId':f['sessionId'], 'eligible':False})
        response = api('sessions/'+f['sessionId']+'/follow-up', {'prompt':'/goal resume', 'executor_config':expected})
        assert response['success'], response
        execution = response['data']['id']
    else:
        if not state()['goals'].get(f['sessionId'], {}).get('eligible'):
            mutation('/eligibility', {'sessionId':f['sessionId'], 'eligible':True})
        now = int(time.time()*1000)
        response = mutation('/start', {'sessionId':f['sessionId'], 'grantId':str(uuid.uuid4()), 'allocationId':'pr112-offline', 'expiresAtMs':now+20000, 'stopAtMs':now+60000})
        execution = response['executionId']
    wait(lambda: (home/'capacity-request-active').exists())
    action = json.loads(db.execute('select executor_action from execution_processes where id=?',(uuid.UUID(execution).bytes,)).fetchone()[0])
    assert action['typ']['executor_config'] == expected, action
    resumes = [json.loads(x)['params'] for x in (home/'capacity-resume-requests.jsonl').read_text().splitlines()]
    resume = resumes[-1]
    assert resume['threadId'] == f['threadId']
    assert resume['model'] == expected['model_id'], resume
    assert resume['config']['model_reasoning_effort'] == expected['reasoning_id'], resume
    requests = [json.loads(x) for x in (home/'capacity-model-requests.jsonl').read_text().splitlines()]
    assert all(x['model'] == expected['model_id'] and x['reasoning']['effort'] == expected['reasoning_id'] for x in requests), requests
    if ordinary:
        assert 'default_permissions' not in (resume.get('config') or {})
        assert resume['sandbox'] == 'danger-full-access', resume
        api('execution-processes/'+execution+'/stop', {})
    else:
        # Native permissions must still be restrictive despite saved full-access choice.
        assert resume['config']['permissions.' + resume['config']['default_permissions'] + '.network.enabled'] is False, resume['config']
        mutation('/stop', {'reason':'Offline model regression cleanup'})
    wait(lambda: not capacity()['runningExecutionIds'])
    assert native() == before
    current = json.loads((home/'vk-goal-progress'/(f['threadId']+'.json')).read_text())['completed']
    assert all(current.get(k)==v for k,v in progress.items())
    results.append({'ordinary':ordinary, 'expected':expected, 'stored':action['typ']['executor_config'], 'resume':resume, 'modelRequests':requests, 'sameGoalAndProgress':True})

try:
    choice = {'executor':'CODEX','variant':'DEFAULT','model_id':'gpt-6','reasoning_id':'high','permission_policy':'AUTO'}
    row = db.execute("select id,executor_action from execution_processes where session_id=? and run_reason='codingagent' and dropped=0 order by created_at desc limit 1",(sid,)).fetchone()
    action = json.loads(row[1]); action['typ']['executor_config'] = choice
    db.execute('update execution_processes set executor_action=? where id=?',(json.dumps(action),row[0]))
    db.execute("delete from scratch where id=? and scratch_type='DRAFT_FOLLOW_UP'",(sid,)); db.commit()
    boot('gpt-5.5'); run(choice); halt()
    boot('gpt-5.6-sol'); run(choice)
    newer = dict(choice, model_id='gpt-5.5', reasoning_id='medium')
    api('scratch/DRAFT_FOLLOW_UP/'+f['sessionId'], {'payload':{'type':'DRAFT_FOLLOW_UP','data':{'message':'Unsubmitted user draft', 'executor_config':newer}}})
    run(newer)
    saved = api('scratch/DRAFT_FOLLOW_UP/'+f['sessionId'])['data']['payload']['data']
    assert saved == {'message':'Unsubmitted user draft', 'executor_config':newer}, saved
    run(newer, ordinary=True)
    subprocess.run(['node', str(repo/'scripts/testing/capacity-checkpoint-browser.mjs')], check=True, cwd=repo)
finally:
    if process:
        try: mutation('/stop', {'reason':'Offline regression final cleanup'})
        except Exception: pass
        for (execution,) in db.execute("select id from execution_processes where status='running'").fetchall():
            api('execution-processes/'+str(uuid.UUID(bytes=execution))+'/stop', {})
    halt(); profiles.write_text(original_profile); db.close()
    (output/'model-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'passed':len(results),'output':str(output)},indent=2))
