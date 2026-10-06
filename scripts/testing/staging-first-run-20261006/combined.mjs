import assert from 'node:assert/strict';
import {readFile,writeFile,stat,mkdir} from 'node:fs/promises';
import {DatabaseSync} from 'node:sqlite';
import {createServer} from 'node:http';
import {randomUUID} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';
const [root,origin,repo,mode]=process.argv.slice(2);
assert.match(root,/\/vk-continuation-http-[a-z0-9_]+$/);
const {VkCapacity}=await import(`${repo}/src/vk-capacity.js`);
const {UsageMonitor}=await import(`${repo}/src/usage-monitor.js`);
const {CapacityScheduler}=await import(`${repo}/src/capacity-scheduler.js`);
const {CapacityAudit}=await import(`${repo}/src/capacity-audit.js`);
const {capacityControl,capacityOwner}=await import(`${repo}/src/capacity-control.js`);
const {allocationPeriod,initialCapacityState}=await import(`${repo}/src/daily-allocation.js`);
const fixtures=JSON.parse(await readFile(`${root}/fixtures.json`,'utf8'));
const receipts=[],http=[],findings=[];
const vk=new VkCapacity({origin,tokenFile:`${root}/token`,fetchImpl:async(url,options)=>{
  const response=await fetch(url,options);const body=await response.clone().json();
  http.push({at:Date.now(),url,method:options.method,request:options.body?JSON.parse(options.body):null,status:response.status,body});
  return response;
}});
const goals=new DatabaseSync(`${root}/home/goals_1.sqlite`,{readOnly:true});
const native=f=>goals.prepare('SELECT * FROM thread_goals WHERE thread_id=?').get(f.threadId);
const ledger=async()=>JSON.parse(await readFile(`${root}/controller/state.json`,'utf8'));
const identity=g=>Object.fromEntries(['goalId','threadId','objective','createdAt'].map(k=>[k,g[k]]));
let offset=new Date().getUTCHours()-1;if(offset>12)offset-=24;
const settings={timezone:`Etc/GMT${offset<0?offset:`+${offset}`}`};
let now=allocationPeriod(Date.now(),settings).startAt,consume=0;
let shortReset=(Date.now()+3600000)/1000;
const weekReset=(Date.now()+5*86400000)/1000;
const account={
  read:async()=>({accountId:'offline-synthetic',rateLimitsByLimitId:{codex:{
    primary:{usedPercent:10,windowDurationMins:300,resetsAt:shortReset},
    secondary:{usedPercent:20,windowDurationMins:10080,resetsAt:weekReset}
  }}}),
  consume:async()=>{consume++;throw Error('No redemption permitted');}
};
let monitor=new UsageMonitor({account,file:`${root}/cu-${mode||'candidate'}.json`,clock:()=>now});
monitor.state.capacity=initialCapacityState(settings);
await monitor.tick();await monitor.configureCapacity({enabled:true});now=Date.now()-(mode==='policy'?6*3600000:0);await monitor.tick();
const audit=new CapacityAudit(`${root}/cu-${mode||'candidate'}-audit-${Date.now()}.sqlite`);
let scheduler=new CapacityScheduler({monitor,vk,audit,clock:()=>now});
const server=createServer(async(req,res)=>{
  res.setHeader('Content-Type','application/json');
  if(!capacityOwner(req,{login:'synthetic@invalid',origin:'http://synthetic.invalid'})){res.statusCode=403;res.end('{}');return;}
  try{
    let input;if(req.method==='POST'){let text='';for await(const b of req)text+=b;input=JSON.parse(text);}
    res.end(JSON.stringify(await capacityControl({monitor,scheduler},input)));
  }catch(e){res.statusCode=409;res.end(JSON.stringify({error:e.message}));}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const cu=`http://127.0.0.1:${server.address().port}/api/capacity/control`;
async function control(input,expected=200){
  const r=await fetch(cu,{method:input?'POST':'GET',headers:{'tailscale-user-login':'synthetic@invalid','x-cu-mobile':'1','content-type':'application/json'},body:input?JSON.stringify(input):undefined});
  const body=await r.json();http.push({url:cu,request:input,status:r.status,body});assert.equal(r.status,expected,JSON.stringify(body));return body;
}
async function until(fn,ms=35000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await delay(100);}throw Error('Timed out: '+fn.toString());}
const record=(name,extra={})=>{receipts.push({name,passed:true,...extra});console.log('PASS '+name);};
async function fresh(){await delay(15);now=Date.now();await monitor.tick();}
async function select(f){const c=(await vk.candidates()).candidates.find(c=>c.sessionId===f.sessionId);assert.ok(c,JSON.stringify(await vk.candidates()));await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:identity(c.goal)});return c.goal;}
async function remove(f){await control({action:'eligibility',sessionId:f.sessionId,eligible:false});}
async function stop(f){
  const state=(await vk.status()).state;
  try{await vk.stop(state,'Synthetic bounded teardown',f?.sessionId);}
  catch(error){
    if(!error.message.includes('connection unavailable'))throw error;
    findings.push({name:'stop-transport-timeout',sessionId:f?.sessionId,at:Date.now(),error:error.message,retried:false});
  }
  await until(async()=>!(await vk.status()).runningExecutionIds.length,45000);
  await scheduler.tick();
}
async function resumedCount(f){return (await readFile(`${root}/home/capacity-resume-requests.jsonl`,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse).filter(x=>x.params.threadId===f.threadId).length;}
async function modelCount(){return (await readFile(`${root}/home/capacity-model-requests.jsonl`,'utf8')).trim().split('\n').length;}
async function launch(f){await fresh();await scheduler.tick();const status=await vk.status();const grant=status.state.goals[f.sessionId]?.grant;assert.ok(grant?.executionId,JSON.stringify({scheduler:scheduler.view(),goal:status.state.goals[f.sessionId],q:scheduler.quota()}));return grant;}
try{
  assert.equal((await fetch(cu)).status,403);
  assert.equal((await fetch(`${origin}/api/capacity`)).status,401);
  assert.equal((await vk.status()).state.version,1);assert.equal(monitor.state.capacity.enabled,true);assert.notEqual(monitor.state.creditBudget?.settings?.enabled,true);
  record('authenticated-http-and-preserved-synthetic-mode-choices');
  await scheduler.tick();
  if(mode==='rollback'){
    assert.equal((await vk.status()).capabilities.scheduledGoalInitialization,0);
    const before=JSON.parse(await readFile(`${root}/latest-before-rollback.json`,'utf8'));
    const after=await ledger();assert.equal(after.version,2);
    assert.deepEqual(after.goals,before.goals);assert.deepEqual(after.issuedIds,before.issuedIds);
    const f=fixtures.find(f=>f.variant==='pending'),g=after.goals[f.sessionId];assert.equal(g.initializationState,'pending');
    for(const firstRun of [undefined,identity(g)]){
      const s=(await vk.status()).state;
      await assert.rejects(vk.start(s,{sessionId:f.sessionId,grantId:randomUUID(),allocationId:'synthetic-denied',expiresAtMs:Date.now()+15000,stopAtMs:Date.now()+30000,...(firstRun?{firstRun}:{})}));
    }
    await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:identity(g)},409);
    await fresh();await scheduler.tick();assert.equal((await vk.status()).runningExecutionIds.length,0);
    assert.deepEqual((await ledger()).issuedIds,before.issuedIds);
    record('latest-v2-rollback-preserves-holds-identities-receipts-issued-ids-and-denies-initialization');
    for(const held of Object.values(before.goals).filter(g=>g.initializationState==='held')){
      await control({action:'eligibility',sessionId:held.sessionId,eligible:false});
      const current=(await ledger()).goals[held.sessionId];
      for(const key of ['goalId','threadId','objective','createdAt','binding','initializationState','initializationReceipt'])assert.deepEqual(current[key],held[key]);
    }
    record('rollback-removal-preserves-held-identities-bindings-and-receipts');
    const gone=Object.values(before.goals).find(g=>g.initializationState==='held');
    if(gone){
      const privateDb=new DatabaseSync(`${root}/xdg/vibe-kanban/db.v2.sqlite`);
      privateDb.prepare('DELETE FROM sessions WHERE id=?').run(Buffer.from(gone.sessionId.replaceAll('-',''),'hex'));privateDb.close();
      await control({action:'eligibility',sessionId:gone.sessionId,eligible:false});
      const current=(await ledger()).goals[gone.sessionId];
      for(const key of ['goalId','threadId','objective','createdAt','binding','initializationState','initializationReceipt'])assert.deepEqual(current[key],gone[key]);
      assert.ok(goals.prepare('SELECT 1 FROM thread_goals WHERE thread_id=?').get(gone.threadId));
      record('rollback-removal-with-gone-synthetic-session-preserves-native-goal-and-hold');
    }
    const ready=Object.values(before.goals).find(g=>g.initializationState==='checkpointed');
    if(ready){
      const f=fixtures.find(f=>f.sessionId===ready.sessionId),oldNative=native(f);
      const progress=await readFile(`${root}/home/vk-goal-progress/${f.threadId}.json`,'utf8');
      await control({action:'eligibility',sessionId:f.sessionId,eligible:true});
      const oldResumes=await resumedCount(f),oldModels=await modelCount();const resumed=await launch(f);
      await until(async()=>await resumedCount(f)>oldResumes&&await modelCount()>oldModels);
      await stop(f);await remove(f);
      for(const key of ['goal_id','thread_id','objective','created_at_ms'])assert.equal(native(f)[key],oldNative[key]);
      assert.deepEqual(JSON.parse(await readFile(`${root}/home/vk-goal-progress/${f.threadId}.json`,'utf8')).requirements,JSON.parse(progress).requirements);
      record('rollback-allows-later-normal-same-thread-resume-retains-authentic-checklist',{executionId:resumed.executionId});
    }
  }else if(mode==='launcher'){
    const nativeWrite=new DatabaseSync(`${root}/home/goals_1.sqlite`),vkdb=new DatabaseSync(`${root}/xdg/vibe-kanban/db.v2.sqlite`);
    try{
      for(const [variant,key] of [['race-goal','goal_id'],['race-thread','thread_id'],['race-objective','objective'],['race-created','created_at_ms'],['race-anchor','anchor']]){
        const f=fixtures.find(f=>f.variant===variant),g=await select(f),old=native(f),before=await modelCount();
        const state=(await vk.status()).state,deadline=Date.now()+15000;
        await vk.start(state,{sessionId:f.sessionId,grantId:randomUUID(),allocationId:'launcher-race',expiresAtMs:deadline,stopAtMs:deadline,firstRun:identity(g)});
        if(key==='anchor')vkdb.prepare('UPDATE coding_agent_turns SET agent_message_id=? WHERE execution_process_id=?').run(randomUUID(),Buffer.from(f.executionId.replaceAll('-',''),'hex'));
        else nativeWrite.prepare(`UPDATE thread_goals SET ${key}=? WHERE thread_id=?`).run(key==='created_at_ms'?old[key]+1000:key==='objective'?'Changed after issue':randomUUID(),f.threadId);
        await until(async()=>(await vk.status()).state.goals[f.sessionId].initializationState==='held',25000);
        await stop(f);assert.equal(await modelCount(),before);await remove(f);
        record('actual-worker-rejects-post-issue-'+key+'-race-before-provider');
      }
    }finally{nativeWrite.close();vkdb.close();}
    await select(fixtures.find(f=>f.variant==='pending'));
  }else if(mode==='sameworkspace'){
    const peers=['concurrent1','concurrent2'].map(v=>fixtures.find(f=>f.variant===v));
    const privateDb=new DatabaseSync(`${root}/xdg/vibe-kanban/db.v2.sqlite`);
    privateDb.prepare('UPDATE sessions SET workspace_id=? WHERE id=?').run(Buffer.from(peers[0].workspaceId.replaceAll('-',''),'hex'),Buffer.from(peers[1].sessionId.replaceAll('-',''),'hex'));privateDb.close();
    for(const f of peers)await select(f);
    await fresh();await scheduler.tick();let state=(await vk.status()).state;
    const first=peers.find(f=>state.goals[f.sessionId].grant),other=peers.find(f=>f!==first);assert.ok(first);
    await until(async()=>(await vk.status()).state.goals[first.sessionId].initializationState==='checkpointed');
    await fresh();await scheduler.tick();state=(await vk.status()).state;
    assert.equal(Object.values(state.goals).filter(g=>g.grant).length,1);
    const current=state.goals[first.sessionId].grant;
    await assert.rejects(vk.start(state,{sessionId:other.sessionId,grantId:randomUUID(),allocationId:current.allocationId,expiresAtMs:Date.now()+10000,stopAtMs:current.stopAtMs,firstRun:identity(state.goals[other.sessionId])}),/workspace|Interactive/i);
    record('same-workspace-cross-session-cannot-launch-second-native-worker');
    for(const f of peers)await remove(f);await stop();await select(fixtures.find(f=>f.variant==='pending'));
  }else if(mode==='policy'){
    const pending=fixtures.find(f=>f.variant==='pending');await select(pending);
    now+=20;await monitor.tick();await scheduler.tick();
    assert.equal(scheduler.quota().canRun,false);assert.equal((await ledger()).issuedIds.length,0);
    assert.match(scheduler.quota().reason,/window|overnight|scheduled/i);
    assert.equal(await modelCount(),fixtures.length);record('outside-saved-window-does-not-initialize',{reason:scheduler.quota().reason});
    const original=(await vk.candidates()).candidates;
    await mkdir(`${root}/home/vk-goal-progress`,{recursive:true});
    for(const [variant,kind] of [['success','corrupt'],['input','empty'],['failure','mismatch'],['empty','input-hold'],['plan','checkpointed']]){
      const f=fixtures.find(f=>f.variant===variant),g=original.find(c=>c.sessionId===f.sessionId).goal;
      const progress={objective:kind==='mismatch'?'Not this goal':g.objective,created_at:g.createdAt,requirements:kind==='empty'?{}:{check:'Synthetic negative fixture'},completed:{},turns:0,stagnant_turns:0,last_completed_count:0,last_turn:null,pause_reason:kind==='input-hold'?'Human input required':null,recovery_plans:[]};
      await writeFile(`${root}/home/vk-goal-progress/${f.threadId}.json`,kind==='corrupt'?'not json':JSON.stringify(progress));
      const candidate=(await vk.candidates()).candidates.find(c=>c.sessionId===f.sessionId);
      assert.notEqual(candidate?.goal.initializationState,'pending');
      await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:identity(g)},409);
      record('preexisting-'+kind+'-cannot-become-missing-checkpoint-first-run');
    }
    const nativeWrite=new DatabaseSync(`${root}/home/goals_1.sqlite`),vkdb=new DatabaseSync(`${root}/xdg/vibe-kanban/db.v2.sqlite`);
    try{
      for(const [variant,status] of [['race-goal','complete'],['race-thread','budget_limited']]){
        const f=fixtures.find(f=>f.variant===variant),g=original.find(c=>c.sessionId===f.sessionId).goal;
        nativeWrite.prepare('UPDATE thread_goals SET status=? WHERE thread_id=?').run(status,f.threadId);
        assert.equal((await vk.candidates()).candidates.some(c=>c.sessionId===f.sessionId),false);
        await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:identity(g)},409);
        record('native-'+status+'-cannot-initialize');
      }
      const f=fixtures.find(f=>f.variant==='race-anchor'),id=Buffer.from(f.executionId.replaceAll('-',''),'hex');
      vkdb.prepare("UPDATE execution_processes SET status='running',completed_at=NULL WHERE id=?").run(id);
      await fresh();await scheduler.tick();assert.equal((await vk.status()).foregroundActive,true);
      assert.match(scheduler.reason,/Other Codex work/);assert.equal((await ledger()).issuedIds.length,0);
      vkdb.prepare("UPDATE execution_processes SET status='completed',completed_at=datetime('now','subsec') WHERE id=?").run(id);
      record('foreground-execution-record-blocks-scheduled-first-run');
      const archived=fixtures.find(f=>f.variant==='race-objective');vkdb.prepare('UPDATE workspaces SET archived=1 WHERE id=?').run(Buffer.from(archived.workspaceId.replaceAll('-',''),'hex'));
      assert.equal((await vk.candidates()).candidates.some(c=>c.sessionId===archived.sessionId),false);
      record('archived-workspace-excluded');
    }finally{nativeWrite.close();vkdb.close();}
  }else if(mode==='restart'){
    assert.equal((await vk.status()).capabilities.scheduledGoalInitialization,0);
    const before=JSON.parse(await readFile(`${root}/ambiguous-issued.json`,'utf8'));
    const state=(await vk.status()).state,g=state.goals[before.sessionId];
    assert.equal(g.initializationState,'held');assert.equal(g.eligible,false);
    assert.ok(state.issuedIds.includes(before.grant.id));assert.equal(await modelCount(),before.modelCount);
    await control({action:'eligibility',sessionId:g.sessionId,eligible:true,firstRun:identity(g)},409);
    await fresh();await scheduler.tick();assert.equal((await vk.status()).runningExecutionIds.length,0);
    record('actual-backend-restart-and-capability-withdrawal-retain-spent-hold-without-provider-replay');
  }else if(mode==='fencing'){
    const pending=fixtures.find(f=>f.variant==='pending');await select(pending);
    await remove(pending);
    for(const variant of ['interrupted','cutoff']){
      const f=fixtures.find(f=>f.variant===variant),g=await select(f),before=await modelCount();
      const state=(await vk.status()).state,deadline=Date.now()+(variant==='cutoff'?4000:15000);
      const grant={sessionId:f.sessionId,grantId:randomUUID(),allocationId:'bounded-interruption',expiresAtMs:deadline,stopAtMs:deadline,firstRun:identity(g)};
      await vk.start(state,grant);
      if(variant==='interrupted')await stop(f);
      else await until(async()=>(await vk.status()).state.goals[f.sessionId].initializationState==='held',15000);
      await stop(f);const held=(await vk.status()).state.goals[f.sessionId];
      assert.equal(held.initializationState,'held');assert.equal(await modelCount(),before);
      await remove(f);await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:identity(held)},409);
      record('pre-native-'+variant+'-holds-no-provider-work-or-reselection');
    }
    await select(pending);
    const f=fixtures.find(f=>f.variant==='withdrawn'),g=await select(f),before=await modelCount();
    const state=(await vk.status()).state,deadline=Date.now()+15000;
    await vk.start(state,{sessionId:f.sessionId,grantId:randomUUID(),allocationId:'ambiguous-restart',expiresAtMs:deadline,stopAtMs:deadline,firstRun:identity(g)});
    const current=(await vk.status()).state.goals[f.sessionId];assert.equal(current.initializationState,'pending');
    await writeFile(`${root}/ambiguous-issued.json`,JSON.stringify({...current,modelCount:before}));
    record('owned-pending-receipt-issued-before-controlled-fixture-backend-restart');
  }else if(mode==='extended'){
    const nativeWrite=new DatabaseSync(`${root}/home/goals_1.sqlite`);
    const vkdb=new DatabaseSync(`${root}/xdg/vibe-kanban/db.v2.sqlite`);
    const request=(f,g)=>({sessionId:f.sessionId,grantId:randomUUID(),allocationId:'synthetic-race',expiresAtMs:Date.now()+15000,stopAtMs:Date.now()+30000,firstRun:identity(g)});
    try{
      for(const [variant,key,value] of [['race-goal','goal_id',randomUUID()],['race-thread','thread_id',randomUUID()],['race-objective','objective','Changed synthetic objective'],['race-created','created_at_ms',1000]]){
        const f=fixtures.find(x=>x.variant===variant);const g=await select(f);const old=native(f);
        nativeWrite.prepare(`UPDATE thread_goals SET ${key}=? WHERE thread_id=?`).run(key==='created_at_ms'?old[key]+value:value,f.threadId);
        const before=await modelCount(),state=(await vk.status()).state,issued=state.issuedIds.length;
        await assert.rejects(vk.start(state,request(f,g)));
        assert.equal((await vk.status()).runningExecutionIds.length,0);assert.equal(await modelCount(),before);
        assert.equal((await vk.status()).state.issuedIds.length,issued);
        await remove(f);record('dispatch-rejects-native-'+key+'-race-without-inference');
      }
      const f=fixtures.find(x=>x.variant==='race-anchor'),g=await select(f);
      vkdb.prepare('UPDATE coding_agent_turns SET agent_message_id=? WHERE execution_process_id=?').run(randomUUID(),Buffer.from(f.executionId.replaceAll('-',''),'hex'));
      await assert.rejects(vk.start((await vk.status()).state,request(f,g)));await remove(f);
      record('dispatch-rejects-changed-completed-turn-anchor');
      const revoked=fixtures.find(x=>x.variant==='revoke'),rg=await select(revoked);const stale=(await vk.status()).state;
      await remove(revoked);const before=await modelCount();
      await assert.rejects(vk.start(stale,request(revoked,rg)));
      await assert.rejects(vk.start((await vk.status()).state,request(revoked,rg)));
      assert.equal(await modelCount(),before);record('revocation-and-stale-revision-reject-without-launch');

      const peers=['concurrent1','concurrent2','concurrent3'].map(v=>fixtures.find(f=>f.variant===v));
      for(const peer of peers)await select(peer);
      await fresh();await Promise.all([scheduler.tick(),scheduler.tick(),scheduler.tick()]);
      let state=(await vk.status()).state;assert.equal(Object.values(state.goals).filter(g=>g.grant).length,1);
      await fresh();await scheduler.tick();state=(await vk.status()).state;
      assert.equal(Object.values(state.goals).filter(g=>g.grant).length,2);
      await fresh();await scheduler.tick();assert.equal(Object.values((await vk.status()).state.goals).filter(g=>g.grant).length,2);
      const running=peers.filter(f=>state.goals[f.sessionId].grant);
      await until(async()=>(await vk.status()).state.goals[running[0].sessionId].initializationState==='checkpointed'&&(await vk.status()).state.goals[running[1].sessionId].initializationState==='checkpointed');
      record('concurrent-scheduler-ticks-serialize-two-native-workers-third-waits',{executionIds:running.map(f=>state.goals[f.sessionId].grant.executionId)});
      for(const peer of peers)await remove(peer);
      await stop();await until(async()=>!(await vk.status()).runningExecutionIds.length);
      record('revocation-drains-both-workers-without-new-dispatch');
    }finally{nativeWrite.close();vkdb.close();}
    const pending=fixtures.find(f=>f.variant==='pending');await select(pending);
    const before=await ledger();scheduler.stop();
    const freshMonitor=new UsageMonitor({account,file:monitor.file,clock:()=>now});await freshMonitor.init();monitor=freshMonitor;
    scheduler=new CapacityScheduler({monitor,vk,audit});await scheduler.tick();
    assert.deepEqual((await ledger()).goals,before.goals);assert.equal((await vk.status()).runningExecutionIds.length,0);
    record('persisted-cu-reload-before-dispatch-preserves-inert-selection');
  }else{
    const f=fixtures.find(f=>f.variant==='success');
    const candidates=(await vk.candidates()).candidates;assert.equal(candidates.length,fixtures.length);
    const g=candidates.find(c=>c.sessionId===f.sessionId).goal;
    for(const key of ['goalId','threadId','objective','createdAt']){
      const bad={...identity(g),[key]:key==='createdAt'?g[key]+1:key==='objective'?'Changed stale card':randomUUID()};
      await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:bad},409);
    }
    const oldNative=native(f);await select(f);
    let state=(await vk.status()).state;assert.equal(state.goals[f.sessionId].initializationState,'pending');assert.equal(state.goals[f.sessionId].grant,null);
    assert.deepEqual(native(f),oldNative);assert.equal(oldNative.status,'paused');
    await assert.rejects(stat(`${root}/home/vk-goal-progress/${f.threadId}.json`),{code:'ENOENT'});
    const durable=await ledger();assert.equal(durable.version,2);assert.deepEqual(durable.goals[f.sessionId],state.goals[f.sessionId]);
    assert.equal(state.goals[f.sessionId].binding.accountHome,`${root}/home`);
    await assert.rejects(vk.start(state,{sessionId:f.sessionId,grantId:randomUUID(),allocationId:'legacy',expiresAtMs:Date.now()+15000,stopAtMs:Date.now()+30000}));
    await assert.rejects(scheduler.startTrial(f.sessionId));await assert.rejects(scheduler.weeklyOffer());
    record('inert-identity-bound-selection-stale-cards-legacy-manual-weekly-rejected');
    const grant=await launch(f);await until(async()=>(await vk.status()).state.goals[f.sessionId].initializationState==='checkpointed');
    const progress=JSON.parse(await readFile(`${root}/home/vk-goal-progress/${f.threadId}.json`,'utf8'));
    assert.ok(Object.keys(progress.requirements).length);state=(await vk.status()).state;
    assert.ok(state.goals[f.sessionId].initializationReceipt.checkpointTurnId);
    await stop(f);record('scheduled-authentic-native-first-turn',{executionId:grant.executionId,receipt:state.goals[f.sessionId].initializationReceipt});
    const oldResumes=await resumedCount(f),oldModels=await modelCount();
    const resumed=await launch(f);assert.notEqual(resumed.id,grant.id);
    await until(async()=>await resumedCount(f)>oldResumes&&await modelCount()>oldModels);
    await stop(f);await remove(f);record('later-ordinary-same-native-thread-resume',{executionId:resumed.executionId});
    for(const variant of ['input','failure','empty','plan']){
      const f=fixtures.find(f=>f.variant===variant);const old=native(f);await select(f);await launch(f);
      await until(async()=>(await vk.status()).state.goals[f.sessionId].initializationState==='held');
      await stop(f);let s=(await vk.status()).state;const held=s.goals[f.sessionId];assert.equal(held.eligible,false);
      for(const key of ['goal_id','thread_id','objective','created_at_ms'])assert.equal(native(f)[key],old[key]);
      await remove(f);await control({action:'eligibility',sessionId:f.sessionId,eligible:true,firstRun:identity(held)},409);
      const issued=s.issuedIds.length;await fresh();await scheduler.tick();assert.equal((await vk.status()).state.issuedIds.length,issued);
      if(variant==='failure')assert.equal((await readFile(`${root}/home/first-run-provider-count`,'utf8')).trim(),'1');
      record('durable-'+variant+'-hold-no-reselection-or-provider-retry',{receipt:held.initializationReceipt});
    }
    const pending=fixtures.find(f=>f.variant==='pending');await select(pending);
    const before=await ledger();scheduler.stop();scheduler=new CapacityScheduler({monitor,vk,audit});await scheduler.tick();
    assert.deepEqual((await ledger()).goals,before.goals);assert.equal((await vk.status()).runningExecutionIds.length,0);
    record('scheduler-restart-before-first-dispatch-is-inert');
  }
  assert.equal(consume,0);
}finally{
  scheduler.stop();
  await new Promise(resolve=>server.close(resolve));goals.close();audit.close();
  await writeFile(`${root}/${mode||'candidate'}-http-${Date.now()}.json`,JSON.stringify(http,null,2));
  await writeFile(`${root}/${mode||'candidate'}-receipts-${Date.now()}.json`,JSON.stringify(receipts,null,2));
  await writeFile(`${root}/${mode||'candidate'}-findings-${Date.now()}.json`,JSON.stringify(findings,null,2));
}
