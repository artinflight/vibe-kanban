#!/usr/bin/env python3
"""Four bounded VK executions against an explicitly nominated private candidate.
Requires --run; never retries a POST or interrupts an unrelated execution.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--origin', required=True)
p.add_argument('--root', required=True)
p.add_argument('--run', action='store_true')
p.add_argument('--resume-after-interruption', action='store_true', help='Resume exactly two recorded executions after verifying the second failed')
a = p.parse_args()
if not a.run or not a.origin.startswith('http://127.0.0.1:'):
    p.error('Explicit --run and a loopback candidate origin required')
root = Path(a.root).resolve()
if not str(root).startswith('/mnt/vk-storage/'):
    p.error('Use mounted SSD storage')
root.mkdir(exist_ok=True, parents=True)
receipt = root / 'acceptance.json'
if receipt.exists() and not a.resume_after_interruption:
    p.error('Existing receipt: reconcile previous executions; never replay blindly')
state = json.loads(receipt.read_text()) if a.resume_after_interruption else {'origin': a.origin, 'executions': [], 'status': 'running'}

def save():
    receipt.write_text(json.dumps(state, indent=2) + '\n')
    handoff = Path('/mnt/vk-storage/vk-model-autoswitch-20260930/CU_ACCEPTANCE_HANDOFF.json')
    shared = json.loads(handoff.read_text()) if handoff.exists() else {}
    shared.pop('reason', None)
    shared.update({'status':state['status'], 'acceptanceReceipt':str(receipt),
        'executions':state['executions'], 'executionIds':[e['executionId'] for e in state['executions']],
        'feedPath':str(root/'router-events.jsonl'),
        'nativeLogRoot':'/home/mcp/.local/share/vibe-kanban-green-codex-home/sessions'})
    temporary = handoff.with_suffix('.tmp'); temporary.write_text(json.dumps(shared,indent=2)+'\n'); temporary.replace(handoff)

def api(path, data=None):
    request = urllib.request.Request(a.origin + '/api' + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        body = json.load(response)
    if not body.get('success'): raise RuntimeError(str(body))
    return body.get('data')

def wait_execution(execution, timeout=150):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = api('/execution-processes/' + execution)
        if row['status'] != 'running': return row
        time.sleep(1)
    raise TimeoutError('Execution still active; reconcile before another turn: ' + execution)

def record(row, role):
    state['executions'].append({'role': role, 'executionId': row['id'], 'sessionId': row['session_id']})
    save()
    return row['id']

policy = {'mode': 'auto', 'floor': 'workhorse', 'denied_models': [], 'allow_escalation': True}
config = {'executor':'CODEX','variant':'DEFAULT','permission_policy':'AUTO','routing':policy}
try:
    info = api('/info')
    assert info['config']['workspace_dir'] == str(root/'workspaces'), 'Not the nominated isolated candidate'
    if a.resume_after_interruption:
        assert state['origin']==a.origin and [e['role'] for e in state['executions']]==['normal_auto','controlled_failure']
        assert wait_execution(state['executions'][0]['executionId'])['status']=='completed'
        failed_id=state['executions'][1]['executionId']
        assert wait_execution(failed_id)['status']=='failed'
        session=state['executions'][1]['sessionId']; work=Path(state['worktree'])
        assert work.is_relative_to(root/'workspaces') and (work/'checkpoint.txt').exists()
        state['interruptionReconciled']='Original signal stopped main process; persisted failed outcome verified before continuation.'
        state.pop('error',None); state['status']='running'; save()
    else:
        repo = root / 'fixture'
        repo.mkdir()
        subprocess.run(['git', 'init', '-b', 'main', str(repo)], check=True, capture_output=True)
        (repo/'dirty.txt').write_text('baseline\n')
        (repo/'README.md').write_text('Isolated AutoSwitch acceptance fixture. Do not commit changes.\n')
        subprocess.run(['git','-C',str(repo),'add','.'], check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=VK acceptance','-c','user.email=fixture@localhost','commit','-m','fixture'],check=True,capture_output=True)
        registered = api('/repos', {'path':str(repo),'display_name':'AutoSwitch acceptance'})
        result = api('/workspaces/start', {'name':'AutoSwitch telemetry acceptance', 'repos':[{'repo_id':registered['id'],'target_branch':'main'}], 'executor_config':config,
            'prompt':'Use no tools. Remember the phrase glacier spoon for this isolated acceptance. Reply exactly ROUTING_OK glacier spoon.'})
        initial = result['execution_process']
        execution = record(initial, 'normal_auto')
        done = wait_execution(execution)
        assert done['status'] == 'completed', done['status']
        assert done['executor_action']['typ']['executor_config']['model_id'] == 'gpt-6.1-sol'
        workspace = api('/workspaces/' + result['workspace']['id'])
        work = Path(workspace['container_ref']) / repo.name
        (work/'dirty.txt').write_text('operator uncommitted sentinel\n')
        state['workspaceId'] = workspace['id']; state['worktree'] = str(work); save()
        session = initial['session_id']
        failed = api('/sessions/' + session + '/follow-up', {'executor_config':config,
            'prompt':'Controlled interruption fixture. Use the shell once: write the exact text checkpoint glacier spoon into checkpoint.txt in the fixture repo, then run sleep 45. Do not touch dirty.txt, commit, or call other tools. After sleep reply ROUTING_OK.'})
        failed_id = record(failed, 'controlled_failure')
        deadline = time.monotonic() + 90
        while not (work/'checkpoint.txt').exists() and time.monotonic() < deadline: time.sleep(.5)
        assert (work/'checkpoint.txt').exists(), 'No checkpoint; do not interrupt an unknown process'
        # Match our exact execution ID in the unit environment, never a timestamp/name guess.
        units = subprocess.check_output(['systemctl','--user','list-units','vk-exec-codex-*.service','--state=running','--no-legend','--plain'],text=True)
        matching=[]
        for line in units.splitlines():
            unit=line.split()[0]
            env=subprocess.check_output(['systemctl','--user','show',unit,'-p','Environment','--value'],text=True)
            if 'VK_EXECUTION_PROCESS_ID='+failed_id in env: matching.append(unit)
        assert len(matching)==1, 'Cannot identify exact fixture unit; no signal sent'
        subprocess.run(['systemctl','--user','kill','--kill-whom=main','--signal=SIGKILL',matching[0]],check=True)
        assert wait_execution(failed_id)['status']=='failed', 'Controlled interruption did not produce failed status'
    escalated=api('/sessions/'+session+'/follow-up', {'executor_config':config,
        'prompt':'Resume this fixture. Read checkpoint.txt and dirty.txt. If checkpoint contains glacier spoon and dirty.txt is exactly operator uncommitted sentinel followed by newline, write resume.txt containing ROUTING_OK glacier spoon. Leave both originals untouched. Do not commit.'})
    escalated_id=record(escalated,'escalation')
    done=wait_execution(escalated_id)
    assert done['status']=='completed'
    assert done['executor_action']['routing_decision']['previous_execution_id']==failed_id
    assert done['executor_action']['typ']['executor_config']['model_id']=='gpt-6-astra'
    assert (work/'dirty.txt').read_text()=='operator uncommitted sentinel\n'
    assert 'glacier spoon' in (work/'checkpoint.txt').read_text()
    assert 'ROUTING_OK' in (work/'resume.txt').read_text()
    manual={**config, 'model_id':'gpt-6-sol','reasoning_id':'medium','routing':{**policy,'mode':'manual'}}
    explicit=api('/sessions/'+session+'/follow-up', {'executor_config':manual,'prompt':'Use no tools and change no files. Reply exactly MANUAL_OK.'})
    explicit_id=record(explicit,'manual_override')
    done=wait_execution(explicit_id)
    assert done['status']=='completed'
    assert done['executor_action']['typ']['executor_config']['model_id']=='gpt-6-sol'
    assert done['executor_action']['typ']['executor_config']['reasoning_id']=='medium'
    assert (work/'dirty.txt').read_text()=='operator uncommitted sentinel\n'
    state['status']='passed'; save()
except Exception as error:
    state['status']='blocked'; state['error']=str(error); save(); raise
print(json.dumps(state,indent=2))
