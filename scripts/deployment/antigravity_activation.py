"""Fresh operator-authorized activation, with current-data cutback and owned recovery.
No history restoration, queue acknowledgement/replay or publication grant.
"""
import ast,fcntl,hashlib,importlib.util,json,os,sqlite3,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
if len(sys.argv)!=3: raise SystemExit('usage: antigravity_activation.py RELEASE_DIR init|worker|recover|supervise')
D=Path(sys.argv[1]).resolve(strict=True)
assert D.is_dir() and str(D).startswith('/mnt/vk-storage/')
BINDING=json.loads((D/'BINDING.private.json').read_text())
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R))
primitive=Path(BINDING['retained_primitives']['path']);assert hashlib.sha256(primitive.read_bytes()).hexdigest()==BINDING['retained_primitives']['sha256']
spec=importlib.util.spec_from_file_location('primitives',primitive);P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
P.ROOT=D
base=P.base;digest=P.digest;unit=P.unit_state;members=P.members;save=P.save;progress=P.progress
from vk_restart_ingress_hold import install,verify
from vk_restart_no_progress import supervise
UNITS=[base.UNIT,'vibe-dot-connector.service','vibe-dot-sidechat-publisher.service','fitrdy-manager.service','codexusage-preview.service']
ADAPTER=Path('/home/mcp/code/vibe-dot-connector/adapter.py')
def setup():
 assert os.path.ismount('/mnt/vk-storage')
 raw=P.OLD/'MANIFEST.private.json';assert digest(raw)=='703488c3caa16d48336049e9be23e60967cccb95c4a48b10466b896200d0c961'
 cfg=json.loads(raw.read_text());P.verify_references(cfg['references'])
 cfg.update(runtime_state=str(D/'RUNTIME_STATE.private.json'),evidence_output=str(D/'evidence'),browser_output_candidate=str(D/'BROWSER_CANDIDATE.private.json'),browser_output_fallback=str(D/'BROWSER_FALLBACK.private.json'))
 fresh=json.loads((D/'BINDING.private.json').read_text())
 assert digest(__file__)==fresh['controller_sha256']
 assert digest(R/'antigravity_native_backup.py')==fresh['native_controller_sha256']
 for v in ['candidate','fallback']:
  cfg['pair'][v]=fresh[v];cfg['staged_dropins'][v]=str(D/(v+'-execstart.conf'))
  assert digest(cfg['staged_dropins'][v])==fresh['dropin_sha256'][v]
 cfg['pair']['frontend_forward']=fresh['frontend_forward'];cfg['pair']['frontend_cutback']=fresh['frontend_cutback']
 incumbent_adapter=str(D/'incumbent-adapter.py');expected=fresh['incumbent_adapter_sha256']
 assert digest(incumbent_adapter)==expected
 cfg['companion_forward'][str(ADAPTER)]=incumbent_adapter;cfg['companion_forward_sha256'][str(ADAPTER)]=expected
 cfg['companion_previous'][str(ADAPTER)]=dict(backup=dict(path=incumbent_adapter,sha256=expected),sha256=expected,mode=0o600)
 for v in ['candidate','fallback']:assert digest(cfg['pair'][v]['path'])==cfg['pair'][v]['sha256']
 cfg['recent_histories']=json.loads((P.OLD/'QUIET_RECENT_HISTORY_BINDING.private.json').read_text())['recent_histories']+fresh['additional_histories']
 ops=P.build_ops(cfg,base,P.transaction)
 initial=json.loads((D/'INITIAL.private.json').read_text())
 assert digest(D/'BINDING.private.json')==initial['binding_sha256']
 cfg['owned_writers']={n:dict(pid=int(initial['units'][n]['MainPID']),invocation=initial['units'][n]['InvocationID'])for n in UNITS[1:3]}
 ops.h=base.load(Path(cfg['release_primitives']),'ag_activation_release');ops.boundary=base.load(Path(cfg['queue_boundary']),'ag_activation_boundary')
 ops.queue_namespace=dict(DB=base.DB,PORT=5621,ROUTE=base.ROUTE,OLD=base.UNIT,h=ops.h,vibe_cgroup_quiet=lambda:members(unit(base.UNIT)['ControlGroup'])=={int(unit(base.UNIT)['MainPID'])})
 base.load(Path(cfg['queue_hooks']),'ag_activation_queues').install(ops.queue_namespace)
 ops.total_end=ops.data_end=None;ops.maintenance_started=time.monotonic();ops.installed_dropin_sha=initial['dropin_sha256'];ops.variant='fallback'
 if (D/'RUNTIME_STATE.private.json').exists():
  st=json.loads((D/'RUNTIME_STATE.private.json').read_text())
  for k in ['owned_stops','owned_start_holds','owned_poller_freeze','released_response','installed_dropin_sha','variant']:setattr(ops,k,st[k])
 if (D/'RELEASED.private.json').exists():ops.released_response=json.loads((D/'RELEASED.private.json').read_text())
 ops.output.mkdir(mode=0o700,exist_ok=True);ops.sequence=max([int(p.name[:4])for p in ops.output.glob('[0-9][0-9][0-9][0-9]-*')]or[0])
 record=ops.record
 def observed(phase,value):record(phase,value);progress(phase)
 ops.record=observed
 nodes=[n for n in ast.parse(base.ORIGINAL.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in ('routed_get','live_acceptance')]
 ops.smoke=dict(json=json,ssl=P.ssl,CA=base.CA,re=P.re,time=time,urllib=__import__('urllib'),META=base.META,digest=digest,hashlib=hashlib)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(base.ORIGINAL),'exec'),ops.smoke)
 return cfg,ops,initial

def exact_owner(n,expected):
 s=unit(n);assert all(s[k]==expected[k]for k in ['MainPID','InvocationID']), 'Unit owner changed: '+n
 assert s['ActiveState']=='active'and s['FreezerState']=='running'
 if n in ('vibe-dot-connector.service','codexusage-preview.service'):
  assert members(s['ControlGroup'])==set(expected['members']),'Connector membership changed'
 else:assert members(s['ControlGroup'])=={int(s['MainPID'])},'Unit not naturally idle: '+n

def adapter(cfg,variant):
 target=cfg['companion_previous'][str(ADAPTER)]['backup']['path']if variant=='fallback'else cfg['companion_forward'][str(ADAPTER)]
 expected=cfg['companion_previous'][str(ADAPTER)]['sha256']if variant=='fallback'else cfg['companion_forward_sha256'][str(ADAPTER)]
 assert digest(target)==expected
 allowed={cfg['companion_previous'][str(ADAPTER)]['sha256'],cfg['companion_forward_sha256'][str(ADAPTER)]}
 assert digest(ADAPTER)in allowed,'Unrelated connector source changed'
 for n in UNITS[1:3]:assert unit(n)['MainPID']=='0'and unit(n)['ActiveState']=='inactive'
 assert digest(ADAPTER)==expected,'Connector must remain the unchanged working adapter'
 progress(variant+'-matching-connector-selected')

def accept(cfg,ops,variant,before):
 ops.verify_executable(variant)
 old=before['info'];new=ops.info()
 assert old['config']==new['config'],'User config changed'
 missing=set(old['executors'])-set(new['executors'])
 if missing:
  assert missing=={'ANTIGRAVITY'}and hashlib.sha256(json.dumps(old['executors']['ANTIGRAVITY'],sort_keys=True).encode()).hexdigest()=='e08a58a5ceeb1f0901db08800a9315a67fd20867c1ccad6574d6f4f4c39ea50b','Unexpected removed executor'
  old=dict(old,executors={k:v for k,v in old['executors'].items()if k!='ANTIGRAVITY'})
 P.transaction.preserve_settings(old,new,candidate=variant=='candidate')
 ops.verify_semantics(before['semantic']);ops.recovery_acceptance(variant);ops.reader_check()
 assert P.quiet(ops)['fingerprint']==before['boundary']['fingerprint'],'Queue/history changed during switch'
 if variant=='candidate':
  available=ops.h.read_api(5621,'agents/check-availability?executor=ANTIGRAVITY')
  presets=ops.h.read_api(5621,'agents/preset-options?executor=ANTIGRAVITY')
  assert available['success'] and available['data']['type']=='INSTALLATION_FOUND'
  assert presets['success'] and presets['data']['permission_policy']=='SUPERVISED'
  assert presets['data']['model_id']=='gemini-3.8-flash-low'
  save('ANTIGRAVITY_LIVE.safe.json',dict(available=available['data'],presets=presets['data'],prompt_calls=0))
 progress(variant+'-fresh-data-history-settings-verified')

def cu_idle():
 with P.urllib.request.urlopen('http://127.0.0.1:4177/api/mobile/control',timeout=5) as response:value=json.load(response)
 auto=value['automation'];capacity=value['capacity'];background=capacity['background']
 assert not auto['enabled'] and not auto['pending'] and not capacity['enabled']
 assert background['runningCount']==0 and not background['stopping'] and background['reconciled']
 assert not background['trial'] and not background['weeklyRun']
 return dict(automation_enabled=False,pending_reset=False,capacity_enabled=False,runningCount=0)

def freeze_cu(ops,initial):
 name='codexusage-preview.service';exact_owner(name,initial['units'][name]);idle=cu_idle()
 save('CU_FENCE.private.json',dict(unit=name,expected=initial['units'][name],idle=idle,purpose='stable native recovery capture; preserve original process'))
 ops.h.ctl('freeze',name)
 assert unit(name)['FreezerState']=='frozen'
 progress('owned-usage-monitor-frozen-for-native-backup')

def resume_cu(ops):
 if not (D/'CU_FENCE.private.json').exists():return
 pin=json.loads((D/'CU_FENCE.private.json').read_text());state=unit(pin['unit'])
 assert all(state[k]==pin['expected'][k] for k in ['MainPID','InvocationID']),'Usage monitor owner changed; preserve external process'
 if state['FreezerState']=='frozen':ops.h.ctl('thaw',pin['unit'])
 assert unit(pin['unit'])['FreezerState']=='running'
 progress('original-usage-monitor-resumed')

def verify_native_recovery():
 spec=importlib.util.spec_from_file_location('native_recovery',R/'antigravity_native_backup.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
 receipt=json.loads((D/'native-recovery-fenced/RECEIPT.private.json').read_text())
 assert receipt['complete'] and all(r['independent_native_readback_verified'] for r in receipt['files'])
 assert {p:native.sig(Path(p)) for p in receipt['source_signatures']}==receipt['source_signatures'],'Native history changed since fresh B backup'
 assert [str(p) for p in native.sessions()]==receipt['selected_sessions'],'Native history selection changed'

def worker():
 assert not (D/'CONTROL_INTENT.private.json').exists(),'Consumed operation; inspect recovery receipt'
 cfg,ops,initial=setup();assert P.current_variant(cfg)=='fallback'
 rehearsal=json.loads(Path(BINDING['rehearsal_path']).read_text());assert rehearsal.get('passed') and rehearsal.get('same_current_database_roundtrip')
 assert digest(Path(BINDING['rehearsal_path']))==BINDING['rehearsal_sha256']
 for n in UNITS:exact_owner(n,initial['units'][n])
 assert digest(base.DROPIN)==initial['dropin_sha256']and str(base.POINTER.resolve())==initial['frontend']
 assert base.ROUTE.read_text()==initial['route']
 assert digest(ADAPTER)==initial['adapter_sha256']
 for target,source in cfg['companion_forward'].items():
  if target!=str(ADAPTER):assert digest(target)==cfg['companion_forward_sha256'][target], 'Companion support changed'
 ops.reader_check();ops.resources();P.quiet(ops)
 lease=os.open(cfg['cutover_lease'],os.O_RDONLY|os.O_NOFOLLOW);fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  save('CONTROL_INTENT.private.json',dict(original=initial,controller_sha256=digest(__file__),purpose='activate verified Antigravity; retain current data and the working incumbent fallback'))
  ops.route_maintenance();ops.record('maintenance-route-established',{})
  holds=[]
  for n in UNITS[1:3]:
   body='# Owned antigravity-activation-20261030\n[Unit]\nRefuseManualStart=yes\n';holds.append(dict(unit=n,path='/run/user/1000/systemd/user/'+n+'.d/90-vk-antigravity-activation-20261030.conf',body=body,sha256=hashlib.sha256(body.encode()).hexdigest()))
  ops.owned_start_holds=holds;ops.record('fresh-ingress-holds-intent',{})
  install(holds,record=ops.record)
  for n in UNITS[1:3]:
   exact_owner(n,initial['units'][n]);ops.owned_stops.append(n);ops.record('fresh-ingress-stop-intent',dict(unit=n));ops.h.ctl('stop',n)
   assert unit(n)['MainPID']=='0'and unit(n)['ActiveState']=='inactive'
  exact_owner('fitrdy-manager.service',initial['units']['fitrdy-manager.service']);ops.owned_poller_freeze=True;ops.record('fresh-poller-freeze-intent',{});ops.h.ctl('freeze','fitrdy-manager.service')
  freeze_cu(ops,initial)
  boundary=P.quiet(ops);before=dict(info=ops.info(),semantic=ops.semantic_snapshot(),boundary=boundary)
  save('BEFORE.private.json',before)
  released=ops.release_ownership();save('RELEASED.private.json',ops.released_response);ops.record('fresh-capacity-released',{})
  ops.h.ctl('freeze',base.UNIT)
  assert unit(base.UNIT)['FreezerState']=='frozen'and unit('fitrdy-manager.service')['FreezerState']=='frozen';verify(holds)
  assert ops.boundary.inventory(base.DB)['fingerprint']==boundary['fingerprint']
  cap=Path('/mnt/vk-storage/codexusage-capacity/runtime/controller/controller.lock')
  # Use the configured existing lock path, never invent a second authority.
  plan=json.loads(Path(cfg['plan']['path']).read_text());cap=Path(plan['writer_fence']['capacity_lock'])
  capfd=os.open(cap,os.O_RDONLY|os.O_NOFOLLOW);fcntl.flock(capfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   durable=json.loads(Path(plan['writer_fence']['capacity_state']).read_text());assert dict(durable,version=1)==released
   native=base.load(R/'antigravity_native_backup.py','fresh_fenced_native_backup');native.progress=progress;native.main()
   verify_native_recovery();P.backup(cfg,ops)
   assert ops.boundary.inventory(base.DB)['fingerprint']==boundary['fingerprint'];ops.verify_semantics(before['semantic']);ops.reader_check()
  finally:os.close(capfd)
  save('SWITCH_INTENT.private.json',dict(from_PID=initial['units'][base.UNIT]['MainPID'],target_sha256=cfg['pair']['candidate']['sha256'],retained_latest_database=True))
  ops.thaw_if_frozen();ops.stop_variant_if_running();ops.install_variant('candidate');ops.record('candidate-dropin-installed',{})
  adapter(cfg,'candidate');ops.start_variant('candidate');ops.wait_health('candidate');ops.record('candidate-started',{})
  accept(cfg,ops,'candidate',before);P.publish(cfg,ops,'candidate',before['info'])
  save('ACCEPTED.private.json',dict(variant='candidate',PID=unit(base.UNIT)['MainPID'],sha256=cfg['pair']['candidate']['sha256'],UTC=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
  ops.resume_owned_consumers(False);resume_cu(ops)
  save('RESULT.private.json',dict(status='verified-antigravity-build-serving',PID=unit(base.UNIT)['MainPID'],current_data_retained=True,received_inputs_preserved_not_replayed=boundary['unresolved_incoming_preserved_not_resumed'],protected_histories=18,recent_histories=len(cfg['recent_histories']),consumers_resumed=True,UTC=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
  progress('antigravity-activation-complete')
 finally:os.close(lease)

def recover():
 if (D/'RESULT.private.json').exists():return
 cfg,ops,initial=setup()
 lease=os.open(cfg['cutover_lease'],os.O_RDONLY|os.O_NOFOLLOW);fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  variant=P.current_variant(cfg)
  if (D/'ACCEPTED.private.json').exists():
   assert variant=='candidate';ops.verify_public_review();ops.resume_owned_consumers(False);resume_cu(ops);save('RESULT.private.json',dict(status='verified-antigravity-build-serving',recovered_cleanup=True,PID=unit(base.UNIT)['MainPID']));return
  ops.thaw_if_frozen()
  if variant!='fallback':
   # Never interrupt work received after routing. A new writer is preserved.
   if variant: P.quiet(ops)
   ops.route_maintenance()
   if variant:
    owned=ops.h.ownership(5621)
    if owned['owned']:ops.released_response=ops.h.ownership(5621,'release',owned['state']);save('RELEASED.private.json',ops.released_response)
    ops.stop_variant_if_running()
   ops.install_variant('fallback');ops.record('recovery-fallback-installed',{});ops.start_variant('fallback');ops.wait_health('fallback')
  if ops.owned_stops:adapter(cfg,'fallback')
  if (D/'BEFORE.private.json').exists():
   before=json.loads((D/'BEFORE.private.json').read_text());review=base.load(Path(cfg['review_projection']),'fresh_recovery_review');snap=D/'current-before-switch.sqlite';baseline=review.capture(snap if snap.exists()else base.DB,'Recovery baseline')
   ops.review_before=hashlib.sha256(json.dumps(baseline['tables'],sort_keys=True).encode()).hexdigest();accept(cfg,ops,'fallback',before)
  ops.select_frontend('fallback');owned=ops.h.ownership(5621)
  if not owned['owned']:
   assert ops.released_response;P.transaction.same_ownership(ops.released_response['state'],ops.acquire_ownership(ops.released_response['state']))
  ops.route_serving();ops.resume_owned_consumers(False);save('RECOVERED.private.json',dict(status='stable-earlier-build-restored',PID=unit(base.UNIT)['MainPID'],data_restored=False));progress('original-service-recovered')
 finally:
  try:resume_cu(ops)
  finally:os.close(lease)

def init():
 assert not (D/'INITIAL.private.json').exists()
 states={n:unit(n)for n in UNITS}
 for n in UNITS:states[n]['members']=sorted(members(states[n]['ControlGroup']))
 for n in UNITS:exact_owner(n,states[n])
 assert states[base.UNIT]['MainPID']==BINDING['expected_incumbent_PID']
 assert states[base.UNIT]['InvocationID']==BINDING['expected_incumbent_invocation']
 save('INITIAL.private.json',dict(binding_sha256=digest(D/'BINDING.private.json'),units=states,dropin_sha256=digest(base.DROPIN),frontend=str(base.POINTER.resolve()),route=base.ROUTE.read_text(),adapter_sha256=digest(ADAPTER)))
 cfg,ops,_=setup();cu_idle();P.quiet(ops);ops.reader_check();ops.resources();assert P.current_variant(cfg)=='fallback';print('Fresh current-owner preflight passed; no service actions',flush=True)

if __name__=='__main__':
 mode=sys.argv[2]
 if mode=='init':init()
 elif mode=='worker':
  try:worker()
  except BaseException as e:save('FAILURE.private.json',dict(type=type(e).__name__,reason=str(e)));raise
 elif mode=='recover':recover()
 elif mode=='supervise':
  try:supervise([sys.executable,'-B',str(Path(__file__).resolve()),str(D),'worker'],D/'progress.json',idle_seconds=600)
  except BaseException as e:
   save('SUPERVISOR_FAILURE.private.json',dict(type=type(e).__name__,reason=str(e)));subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),str(D),'recover'],check=True,timeout=300);raise
 else:raise ValueError('Explicit init/worker/recover/supervise mode required')
