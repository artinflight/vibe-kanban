"""Staging-only orchestration inside the unchanged reviewed CU boundary."""
import argparse, hashlib, json, os, selectors, sqlite3, subprocess, sys, time, uuid, threading
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
VK=Path('/mnt/vk-storage/vk-combined-release-20261007/source')
CU=Path('/mnt/vk-storage/worktrees/d750-cu-credit-aware/codexusage')
BUNDLE=Path('/mnt/vk-storage/vk-scheduled-first-run-20261006/bundle-5ec5722455d9b12ae8a9b00b371351ad12a685ef')
sys.path.insert(0,str(CU/'ops'))
from fixture_isolation import provision,prove,command,environment,wrapper,require
from fixture_manager import FixtureManager
from fixture_publication import Publication
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,x):p.write_text(json.dumps(x,indent=2)+'\n')

def outer():
    manifest=json.loads((BUNDLE/'manifest.json').read_text())
    require(manifest['sourceCommit']=='5ec5722455d9b12ae8a9b00b371351ad12a685ef','Wrong source')
    require(subprocess.check_output(['git','-C',str(CU),'rev-parse','HEAD'],text=True).strip()=='95e7aea47e137015daa8efcbb210184ee7ce723c','Wrong CU')
    for name,entry in manifest['artifacts'].items():require(sha(BUNDLE/name)==entry['sha256'],name)
    for name,value in manifest['trackedHashes'].items():require(sha(VK/name)==value,name)
    boundary={n:sha(CU/'ops'/n) for n in ['fixture_isolation.py','fixture_manager.py','fixture_manager_worker.py','fixture_manager_client.py','fixture_publication.py']}
    base=Path('/mnt/vk-storage/vk-sfr-http-20261006');base.mkdir(exist_ok=True)
    root,evidence=provision(base,'vk-continuation-http-')
    (root/'controller').mkdir();(root/'home').mkdir()
    manager=FixtureManager(root,BUNDLE/'vk-capacity-guard')
    publication=Publication(root)
    done=threading.Event()
    def observe():
        with publication.open_text('host-observer.jsonl') as log:
            while not done.is_set():
                with manager.lock:units=list(manager.units)
                for unit in units:
                    if not unit.endswith('.service'):continue
                    actual=manager.prefix+unit
                    try:
                        output=subprocess.check_output(['systemctl','--user','show',actual,'-p','MainPID','-p','ActiveState','-p','SubState','-p','Result','-p','ExecMainStatus','-p','ControlGroup'],text=True,timeout=2)
                        properties=dict(line.split('=',1) for line in output.splitlines() if '=' in line)
                        group=properties.get('ControlGroup','');procs=Path('/sys/fs/cgroup'+group+'/cgroup.procs')
                        members=procs.read_text().splitlines() if group and procs.exists() else []
                        log.write(json.dumps({'atMs':time.time()*1000,'unit':actual,'properties':properties,'cgroupPids':members})+'\n');log.flush()
                    except Exception as error:log.write(json.dumps({'atMs':time.time()*1000,'unit':actual,'error':str(error)})+'\n');log.flush()
                for path in (root/'controller').glob('*.json'):
                    if path.name=='state.json':continue
                    try:
                        value=json.loads(path.read_text())
                        if 'revoked' in value:log.write(json.dumps({'atMs':time.time()*1000,'leaseFile':path.name,'lease':value})+'\n');log.flush()
                    except (OSError,ValueError):pass
                done.wait(.1)
    observer=threading.Thread(target=observe)
    if os.environ.get('VK_STAGING_ACCEPTANCE_PHASE') in ('stalled','lock-only'):observer.start()
    try:
        proof=prove(root,evidence)
        wrapper(root,BUNDLE/'vk-capacity-guard','isolated-capacity-guard')
        publication.write_text('provenance.json',json.dumps(dict(vk=manifest['sourceCommit'],cu='95e7aea47e137015daa8efcbb210184ee7ce723c',artifacts=manifest['artifacts'],boundary=boundary,sourceFiles=len(manifest['trackedHashes']),proof=str(evidence/'proof.json')),indent=2))
        print('COMBINED ROOT '+str(root),flush=True)
        with publication.open_text('driver.log') as log:
            p=subprocess.run(command(root,[sys.executable,'-B',__file__,'--inner',str(root),os.environ.get('VK_STAGING_ACCEPTANCE_PHASE','candidate')],controller=True,cwd=root),env=environment(root),stdout=log,stderr=log,timeout=600)
        publication.write_text('driver-result.json',json.dumps(dict(exitCode=p.returncode,productionChanged=False,paidProvider=False)))
        require(boundary=={n:sha(CU/'ops'/n) for n in boundary},'Boundary changed')
    finally:
        done.set()
        if observer.is_alive():observer.join(timeout=5)
        require(not observer.is_alive(),'Observer still running')
        manager.close();publication.close()
    print((root/'driver.log').read_text()[-12000:],flush=True)
    return p.returncode

def inner(root,phase):
    require(os.statvfs(VK).f_flag&os.ST_RDONLY,'Host source must be read-only')
    require(json.loads((root/'isolation-proof.json').read_text())['passed'],'No boundary proof')
    home=root/'home';xdg=root/'xdg';(xdg/'vibe-kanban').mkdir(parents=True)
    (root/'cache').mkdir();(root/'workspaces').mkdir()
    token=uuid.uuid4().hex+uuid.uuid4().hex;(root/'token').write_text(token);(root/'token').chmod(0o600)
    provider=VK/'scripts/testing/codex_goal_provider.py'
    native='/mnt/vk-storage/vk-model-autoswitch-v1/codex-current/node_modules/.bin/codex'
    env={**environment(root),'HOME':str(home),'CODEX_HOME':str(home),'XDG_DATA_HOME':str(xdg),'XDG_CACHE_HOME':str(root/'cache'),
         'CU_FIXTURE_SUPERVISOR':str(root/'supervisor.sock'),'DISABLE_WORKTREE_CLEANUP':'1','DISABLE_STATUS_WORKTREE_CLEANUP':'1',
         'VK_CAPACITY_STATE_DIR':str(root/'controller'),'VK_CAPACITY_TOKEN_FILE':str(root/'token'),'VK_CAPACITY_GUARD':str(root/'isolated-capacity-guard'),
         'VK_CAPACITY_MODEL_PROVIDER':'fixture','VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION':'1','VK_USE_SYSTEMD_RUN':'1',
         'VK_CODEX_BASE_COMMAND':'python3 '+str(provider),'VK_GOAL_TEST_CODEX':native,'HOST':'127.0.0.1','BACKEND_PORT':'49174',
         'GIT_CONFIG_NOSYSTEM':'1','RUST_LOG':'info','VK_GOAL_TEST_CAPTURE':'1'}
    if phase=='frontend':env['VK_FRONTEND_DIST_DIR']='/mnt/vk-storage/vk-first-run-gates-20261006/frontend-86f62b2/source/packages/local-web/dist'
    profiles={'executors':{'CODEX':{}}}
    variants=['success','input','failure','empty','plan','pending','race','concurrent1','concurrent2','concurrent3','race-goal','race-thread','race-objective','race-created','race-anchor','revoke','cutoff','interrupted','withdrawn']
    if phase in ('stalled','lock-only'):
        variants+=['stalled-one','stalled-two-a','stalled-two-b','stalled-unconfirmed','stalled-lock']
        if phase=='lock-only':variants=['pending','stalled-lock']
        faults=root/'fault-bin';faults.mkdir()
        for name in ('systemctl','systemd-run'):(faults/name).symlink_to(OUT/'fault-manager.py')
        env['PATH']=str(faults)+':'+env['PATH']
        env['VK_SYNTHETIC_ROOT']=str(root)
        env['VK_CODEX_BASE_COMMAND']='python3 '+str(OUT/'stall-provider.py')
    for variant in variants:
        scenario='capacity-first-run-'+variant if variant in ('input','failure','empty') else 'capacity-first-run'
        profiles['executors']['CODEX'][variant.upper()]={'CODEX':{'model':'gpt-6','model_provider':'fixture','sandbox':'danger-full-access','ask_for_approval':'never',
            'plan':variant=='plan','base_command_override':'python3 '+str(provider),
            'env':{'VK_GOAL_TEST_SCENARIO':scenario,'VK_GOAL_TEST_CODEX':native,'VK_GOAL_TEST_CAPTURE':'1'}}}
        if variant.startswith('stalled-'):
            profiles['executors']['CODEX'][variant.upper()]['CODEX'].update(base_command_override='python3 '+str(OUT/'stall-provider.py'))
            profiles['executors']['CODEX'][variant.upper()]['CODEX']['env'].update(VK_GOAL_TEST_SCENARIO='capacity-first-run-stalled',VK_STALLED_TIMELINE=variant+'-timeline.jsonl')
    profiles['executors']['CODEX']['DEFAULT']=profiles['executors']['CODEX'].get('SUCCESS',profiles['executors']['CODEX']['PENDING'])
    profiles['executors']['CODEX']['DELAYED']={'CODEX':{**profiles['executors']['CODEX']['DEFAULT']['CODEX'],'base_command_override':'python3 '+str(OUT/'delay-provider.py')}}
    if phase in ('fencing','launcher'):env['VK_CODEX_BASE_COMMAND']='python3 '+str(OUT/'delay-provider.py')
    put(xdg/'vibe-kanban/profiles.json',profiles)
    origin='http://127.0.0.1:49174'
    def api(path='',body=None):
        r=Request(origin+'/api/capacity'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(r,timeout=15) as reply:return json.load(reply)
    process=None;iteration=0
    def start(kind='candidate',gate='1'):
        nonlocal process,iteration
        iteration+=1
        current={**env}
        if gate is None:current.pop('VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION',None)
        else:current['VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION']=gate
        log=(root/f'backend-{iteration}-{kind}.log').open('w')
        process=subprocess.Popen([str(BUNDLE/kind/'server')],env=current,cwd=root,stdout=log,stderr=log);log.close()
        for _ in range(200):
            require(process.poll() is None,'Backend exited')
            try:return api()
            except OSError:time.sleep(.1)
        raise RuntimeError('Backend failed to start')
    def stop():
        nonlocal process
        if process and process.poll() is None:
            process.terminate();process.wait(timeout=20)
        process=None
    try:
        initial=start();require(initial['state']['version']==1,'Wire compatibility')
        if phase=='frontend':
            result=subprocess.run(['node','/mnt/vk-storage/vk-first-run-gates-20261006/frontend-browser.mjs',str(root),origin,env['VK_FRONTEND_DIST_DIR']],env=env,timeout=120)
            require(result.returncode==0,'Frontend browser failed')
            put(root/'combined-result.json',{'passed':True,'phase':phase,'productionChanged':False,'paidProvider':False})
            return
        stop()
        dbpath=xdg/'vibe-kanban/db.v2.sqlite'
        with sqlite3.connect(dbpath) as db:
            put(root/'schema.json',{t:list(db.execute('pragma table_info('+t+')')) for t in ['workspaces','sessions','repos','workspace_repos','execution_processes','coding_agent_turns']})
        # A real native app-server creates paused goals and completes ordinary seed
        # turns. These are not first-run checklists and incur no external inference.
        seedlog=(root/'seed-stderr.log').open('w')
        child=subprocess.Popen(['python3',str(provider)],env={**env,'VK_GOAL_TEST_SCENARIO':'scheduled-seed'},stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=seedlog,bufsize=0)
        seq=0;transcript=[];buffer=b''
        def read():
            nonlocal buffer
            while b'\n' not in buffer:
                ready=selectors.DefaultSelector();ready.register(child.stdout,selectors.EVENT_READ)
                require(bool(ready.select(25)),'Native seed timed out');ready.close()
                chunk=os.read(child.stdout.fileno(),65536);require(bool(chunk),'Native seed exited');buffer+=chunk
            line,buffer=buffer.split(b'\n',1)
            value=json.loads(line);transcript.append(value)
            return value
        def rpc(method,params):
            nonlocal seq
            seq+=1;ident=seq
            child.stdin.write((json.dumps({'id':ident,'method':method,'params':params})+'\n').encode());child.stdin.flush()
            while True:
                value=read()
                if value.get('id')==ident:
                    require('error' not in value,str(value));return value['result']
        fixtures=[]
        try:
            rpc('initialize',{'clientInfo':{'name':'vk-staging-synthetic','version':'1'},'capabilities':{'experimentalApi':True}})
            child.stdin.write(b'{"method":"initialized"}\n');child.stdin.flush()
            for variant in variants:
                workspace=root/'workspaces'/variant;workspace.mkdir()
                repo=root/'repos'/variant/'fixture-repo';repo.mkdir(parents=True)
                subprocess.run(['git','init','-b','main',str(repo)],env=env,check=True,capture_output=True)
                subprocess.run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=fixture@invalid','commit','--allow-empty','-m','Synthetic seed'],env=env,check=True,capture_output=True)
                subprocess.run(['git','-C',str(repo),'worktree','add','-b',variant,str(workspace/'fixture-repo')],env=env,check=True,capture_output=True)
                thread=rpc('thread/start',{'model':'fixture','modelProvider':'fixture','cwd':str(workspace),'approvalPolicy':'never','sandbox':'danger-full-access'})['thread']['id']
                goal=rpc('thread/goal/set',{'threadId':thread,'objective':'Synthetic overnight '+variant+' acceptance','status':'paused'})
                turn=rpc('turn/start',{'threadId':thread,'input':[{'type':'text','text':'Record an ordinary synthetic seed anchor.','text_elements':[]}]})['turn']['id']
                while True:
                    value=read()
                    if value.get('method')=='turn/completed' and value['params']['turn']['id']==turn:
                        require(value['params']['turn']['status']=='completed',str(value));break
                fixtures.append({'variant':variant,'threadId':thread,'turnId':turn,'workspace':str(workspace),'repo':str(repo),'sessionId':str(uuid.uuid4()),'workspaceId':str(uuid.uuid4()),'executionId':str(uuid.uuid4())})
        finally:
            child.stdin.close();child.wait(timeout=15);seedlog.close();put(root/'seed-protocol.json',transcript)
        with sqlite3.connect(dbpath) as db:
            for f in fixtures:
                sid=uuid.UUID(f['sessionId']).bytes;wid=uuid.UUID(f['workspaceId']).bytes;eid=uuid.UUID(f['executionId']).bytes
                db.execute('INSERT INTO workspaces(id,container_ref,branch,name) VALUES(?,?,?,?)',(wid,f['workspace'],f['variant'],'Synthetic '+f['variant']))
                rid=uuid.uuid4().bytes
                db.execute('INSERT INTO repos(id,path,name,display_name) VALUES(?,?,?,?)',(rid,f['repo'],'fixture-repo','Synthetic repo'))
                db.execute('INSERT INTO workspace_repos(id,workspace_id,repo_id,target_branch) VALUES(?,?,?,?)',(uuid.uuid4().bytes,wid,rid,'main'))
                db.execute('INSERT INTO sessions(id,workspace_id,executor,name) VALUES(?,?,?,?)',(sid,wid,'CODEX','Synthetic '+f['variant']))
                profile=f['variant'].upper() if f['variant'] in ('input','failure','empty','plan') else 'SUCCESS'
                if f['variant'].startswith('stalled-'):profile=f['variant'].upper().replace('-','_')
                if f['variant'] in ('cutoff','interrupted','withdrawn'):profile='DELAYED'
                if phase=='launcher':profile='DELAYED'
                action={'typ':{'type':'CodingAgentFollowUpRequest','prompt':'Record an ordinary synthetic seed anchor.','session_id':f['threadId'],'executor_config':{'executor':'CODEX','variant':profile},'working_dir':None},'next_action':None}
                db.execute("INSERT INTO execution_processes(id,session_id,run_reason,executor_action,status,exit_code,completed_at) VALUES(?,?,'codingagent',?,'completed',0,datetime('now','subsec'))",(eid,sid,json.dumps(action)))
                db.execute('INSERT INTO coding_agent_turns(id,execution_process_id,agent_session_id,agent_message_id,summary) VALUES(?,?,?,?,?)',(uuid.uuid4().bytes,eid,f['threadId'],f['turnId'],'Existing synthetic paused goal seed anchor.'))
        put(root/'fixtures.json',fixtures)
        require(not (home/'auth.json').exists(),'Unexpected credential')
        require(not (home/'vk-goal-progress').exists(),'Seed invented a checklist')
        status=start();put(root/'initial-http.json',status);put(root/'initial-candidates.json',api('/candidates'))
        # Node drives real CU control/scheduler against actual authenticated HTTP.
        result=subprocess.run(['node','--experimental-sqlite',str(OUT/'combined.mjs'),str(root),origin,str(CU),phase],env=env,timeout=300)
        require(result.returncode==0,'Combined CU driver failed')
        if phase=='fencing':
            stop()
            start('candidate','0')
            result=subprocess.run(['node','--experimental-sqlite',str(OUT/'combined.mjs'),str(root),origin,str(CU),'restart'],env=env,timeout=120)
            require(result.returncode==0,'Restart reconciliation driver failed')
        state=api()['state'];require(not api()['runningExecutionIds'],'Fixture workers still active')
        api('/ownership/release',{'epoch':state['epoch'],'revision':state['revision']});stop()
        for gate in (None,'1'):
            latest=json.loads((root/'controller/state.json').read_text())
            put(root/'latest-before-rollback.json',latest)
            put(root/f'latest-before-rollback-gate-{gate}.json',latest)
            status=start('rollback',gate);require(status['capabilities']['scheduledGoalInitialization']==0,'Rollback enabled first run')
            result=subprocess.run(['node','--experimental-sqlite',str(OUT/'combined.mjs'),str(root),origin,str(CU),'rollback'],env=env,timeout=120)
            require(result.returncode==0,'Rollback CU driver failed')
            state=api()['state'];api('/ownership/release',{'epoch':state['epoch'],'revision':state['revision']});stop()
        findings=[x for p in root.glob('*-findings-*.json') for x in json.loads(p.read_text())]
        put(root/'combined-result.json',{'assertionsPassed':True,'passed':not findings,'phase':phase,'findings':findings,'productionChanged':False,'paidProvider':False,'rollbackGateAbsentAndForcedPassed':True})
    finally:
        if process and process.poll() is None:
            try:
                state=api()['state'];api('/stop',{'epoch':state['epoch'],'revision':state['revision'],'reason':'Synthetic acceptance teardown'})
            finally:stop()

if __name__=='__main__':
    if len(sys.argv)>1:inner(Path(sys.argv[2]),sys.argv[3])
    else:sys.exit(outer())
