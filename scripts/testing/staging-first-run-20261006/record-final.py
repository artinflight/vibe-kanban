"""Index exact final-source receipts, observe production read-only, retain evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen

sys.dont_write_bytecode=True
ROOT=Path('/mnt/vk-storage/vk-first-run-final-20261006')
SOURCE='9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4'
CU='95e7aea47e137015daa8efcbb210184ee7ce723c'
BASE=Path('/mnt/vk-storage/vk-sfr-http-20261006')
SUITES={'candidate':'717zekit','extended':'wg4jtjnq','fencing':'grs6htc3','policy':'ok_b7xal','launcher':'57s38f39','sameworkspace':'t2ubgywa','stalled':'2dmpcvzg','lock-only':'y9yxmbc9','frontend':'27blad5n'}
def read(path):return json.loads(path.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def put(name,data):(ROOT/name).write_text(json.dumps(data,indent=2)+'\n')
def get(url,headers={}):
    with urlopen(Request(url,headers=headers),timeout=10) as response:return json.load(response)

assert os.path.ismount('/mnt/vk-storage')
boundary=read(Path('/mnt/vk-storage/vk-scheduled-first-run-20261006/stop-response-boundary-verification.json'))['hashes']
groups={};names=set();timelines=[]
for phase,suffix in SUITES.items():
    root=BASE/('vk-continuation-http-'+suffix)
    result=read(root/'combined-result.json');assert result['passed'] and result['phase']==phase
    provenance=read(root/'provenance.json');assert provenance['vk']==SOURCE and provenance['cu']==CU
    assert provenance['boundary']==boundary
    proof=read(root/'isolation-proof.json');assert proof['passed'] and proof['realWorkspaceMutationAttempts']==0
    cleanup=read(root/'fixture-cleanup.json');assert not cleanup['sharedServicesModified'] and not cleanup['evidenceDeleted']
    assert all(u['workerState'] in ('inactive','failed') for u in cleanup['ownedUnits'])
    for unit in cleanup['ownedUnits']:
        if not unit['timerStopped']:
            loaded=subprocess.check_output(['systemctl','--user','show',unit['timer'],'-p','LoadState','--value'],text=True).strip()
            assert loaded=='not-found',unit
    receipts=[entry for path in root.glob('*-receipts-*.json') for entry in read(path)]
    assert all(r['passed'] for r in receipts);names.update(r['name'] for r in receipts)
    selected=[]
    for pattern in ('*-receipts-*.json','*-http-*.json','*-findings-*.json','combined-result.json','provenance.json','isolation-proof.json','fixture-cleanup.json','driver-result.json','host-observer.jsonl','fault-manager-events.jsonl','backend-*.log','frontend-browser.json','frontend-*.png','latest-before-rollback*.json','controller/state.json'):
        selected.extend(root.glob(pattern))
    groups[phase]={'root':str(root),'passed':True,'receiptCount':len(receipts),'files':{str(p.relative_to(root)):sha(p) for p in sorted(set(selected))}}
    if phase=='stalled':
        observed=[json.loads(line) for line in (root/'host-observer.jsonl').read_text().splitlines()]
        for r in receipts:
            if not r['name'].startswith('real-cu-http-stalled-'):continue
            for sid,goal in r['before']['goals'].items():
                grant=goal.get('grant')
                if not grant or sid not in r['stopped']['goals']:continue
                lease=[e for e in observed if e.get('leaseFile')==grant['id']+'.json']
                revoked=next(e for e in lease if e['lease']['revoked'])
                before=[e for e in lease if not e['lease']['revoked'] and e['atMs']<=revoked['atMs']]
                units=[e for e in observed if grant['executionId'].replace('-','') in e.get('unit','')]
                live=[e for e in units if e['cgroupPids']]
                assert live
                exited=next(e for e in units if e['atMs']>=live[0]['atMs'] and not e['cgroupPids'] and e['properties']['ActiveState'] in ('inactive','failed'))
                fixture=next(f for f in read(root/'fixtures.json') if f['sessionId']==sid)
                events=[json.loads(line) for line in (root/'home'/(fixture['variant']+'-timeline.jsonl')).read_text().splitlines()]
                request=[e for e in events if e['event']=='providerRequest'];assert len(request)==1
                term=next(e for e in events if e['event']=='providerTerminating')
                assert exited['atMs']<grant['expiresAtMs'] and exited['atMs']<grant['stopAtMs']
                assert term['wallMs']<grant['expiresAtMs']
                timelines.append({'case':fixture['variant'],'sessionId':sid,'executionId':grant['executionId'],'grantId':grant['id'],'httpStartedAtMs':r['startedAt'],'responseAtMs':r['endedAt'],'httpElapsedMs':r['httpElapsedMs'],'leaseExpiresAtMs':grant['expiresAtMs'],'hardStopAtMs':grant['stopAtMs'],'persistedRevokeObservedIntervalMs':[before[-1]['atMs'] if before else None,revoked['atMs']],'providerRequestAtMs':request[0]['wallMs'],'lastProviderActivityAtMs':max(e['wallMs'] for e in events if e['event']=='providerActive'),'providerTermAtMs':term['wallMs'],'independentEmptyCgroupObservedAtMs':exited['atMs'],'providerRequests':len(request),'nativeStoredStatus':'active','initializationState':'held','unverifiedExitFault':r['unverifiedExit']})
put('stop-timelines.json',{'source':SOURCE,'timelines':timelines,'originalIncidentExactRevokeAndProviderTimes':'Unavailable; new synthetic timestamps do not fill historical gaps','faultScope':'Final HTTP binary: dropped graceful pause/interrupt responses and held controller-side EOF; denied OS exit confirmation; private FIFO forces initial/final lock contention. Internal mutex/log/exit-signal stall coverage is complementary packaged developer helper evidence, not an HTTP hook.'})
browser=read(BASE/('vk-continuation-http-'+SUITES['frontend'])/'frontend-browser.json')
assert browser['passed'] and all(not r['errors'] and 'Create Workspace' in r['afterContinue'] for r in browser['results'])
control=get('http://127.0.0.1:4177/api/capacity/control',{'Tailscale-User-Login':'seamus@artinflight.ca'})
owner={'schedulingEnabled':control['capacity']['enabled'],'creditsEnabled':control['capacity']['creditBudget']['enabled'],'capacitySettings':control['capacity']['settings'],'grants':sum(bool(g.get('grant')) for g in control.get('goals',[]))}
assert owner['schedulingEnabled'] is True and owner['creditsEnabled'] is False
units={}
for unit,pid in [('vibe-kanban-green-production-20261005.service','3027197'),('codexusage-preview.service','414400')]:
    value=subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','-p','ActiveState','-p','SubState'],text=True)
    units[unit]=dict(line.split('=',1) for line in value.splitlines());assert units[unit]['MainPID']==pid and units[unit]['ActiveState']=='active'
assert sha(Path('/proc/3027197/exe'))=='5e7948921f962b9ea74597781ca2e1b0c7bd745edc0d1901a8274dab444097a2'
pr=json.loads(subprocess.check_output(['gh','pr','view','147','--repo','artinflight/vibe-kanban','--json','headRefOid,statusCheckRollup,isDraft,state,url'],text=True));assert pr['headRefOid']==SOURCE
cuhead=subprocess.check_output(['git','-C','/mnt/vk-storage/worktrees/d750-cu-credit-aware/codexusage','rev-parse','HEAD'],text=True).strip();assert cuhead==CU
space=os.statvfs(ROOT)
put('acceptance.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'vkSource':SOURCE,'cuSource':CU,'isolatedAcceptancePassed':True,'uniqueAssertionNames':sorted(names),'groups':groups,'stopTimelineSha256':sha(ROOT/'stop-timelines.json'),'frontendScope':'Real final backend/external assets/local shell at1440/390px, not physical phone or full UX; known pre-existing onboarding overflow and expected unconfigured remote400s retained','liveOwnerChoices':owner,'liveServices':units,'recommendRouting':'Preserved: no production config or routing mutation. Bind existing owner routing choices during approved rollout, never promote synthetic fixture profiles.','pr147':pr,'freeBytes':space.f_bavail*space.f_frsize,'productionChanged':False,'bytesDeleted':0,'paidProviderCalls':0,'cutoverAuthorized':False,'sealedHandoverReady':False,'remaining':['Explicit rollout approval and protected-branch promotion','SSD headroom for fresh production backup and complete-workload rehearsal','Bind latest data/config/module/runtime and v2-safe fallback with installed PR142; safe agent/queue/grant drain','Deploy compatible CU before exposing pending candidates'],'historicalRecoveryExceptions':'Unchanged; original revoke/provider timestamps unavailable; five-root later-unbacked edits and historical rollout gaps not erased'})
print(json.dumps({'groups':len(groups),'uniqueAssertions':len(names),'stopTimelines':timelines,'freeBytes':space.f_bavail*space.f_frsize}))
