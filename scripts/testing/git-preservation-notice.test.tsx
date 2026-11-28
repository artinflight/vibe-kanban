import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { after, afterEach, beforeEach, test } from 'node:test';
import type { NormalizedEntry } from '../../shared/types';
import { isCapturedGitNotice } from '../../packages/web-core/src/features/workspace-chat/model/gitPreservationNotice';
import { useQuietGitPreservationNotice } from '../../packages/web-core/src/features/workspace-chat/model/hooks/useQuietGitPreservationNotice';
import { state } from './git-preservation-notice.fixture';
const workspace = '0a34b260-c02a-4516-9362-37303df568ab';
const execution = '3c8eaec3-6295-4bfa-a551-5ba191710588';
const blocked = 'completed-turn observation is unproven; original obligation retained; scoped reconciliation required';
function entry(reason = blocked, type = 'error_message', status = 'blocked') {
  return { entry_type: {type}, content: `Git preservation ${status}. Workspace: ${workspace}. Turn: ${execution}. ${reason}. Excluded files are not Git-protected.` } as NormalizedEntry;
}
const dom = new JSDOM('<!doctype html><html><body></body></html>');
Object.assign(globalThis, {window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT:true});
let root: Root;let client: QueryClient;let element: HTMLDivElement;
function Notice({value}:{value:NormalizedEntry}) {
  const quiet = useQuietGitPreservationNotice(value,workspace,execution);
  return quiet ? null : <div>{value.content}</div>;
}
async function render(value = entry()) {
  await act(async () => root.render(<QueryClientProvider client={client}><Notice value={value}/></QueryClientProvider>));
  await act(async () => {await new Promise(resolve=>setTimeout(resolve,25));});
}
beforeEach(()=>{state.checkpoints=[];state.calls=[];state.fail=false;client=new QueryClient();element=document.createElement('div');document.body.append(element);root=createRoot(element);});
afterEach(async()=>{await act(async()=>root.unmount());client.clear();element.remove();});
after(()=>dom.window.close());
test('captured inherited warning disappears using exact durable owner status',async()=>{
 state.checkpoints=[{execution_process_id:execution,observation_state:'observed'}];await render();
 assert.equal(element.textContent,'');assert.deepEqual(state.calls,[`/api/workspaces/${workspace}/github-sync`]);
});
test('successful pending acknowledgement disappears after durable capture',async()=>{
 state.checkpoints=[{execution_process_id:execution,observation_state:'observed'}];
 await render(entry('completed original heads durably observed; publication admission remains blocked','system_message','pending'));assert.equal(element.textContent,'');
});
test('policy-wait acknowledgement stays out of captured replies',async()=>{
 state.checkpoints=[{execution_process_id:execution,observation_state:'observed'}];
 await render(entry('original heads retained; publication awaits a reviewed repository policy','system_message','pending'));assert.equal(element.textContent,'');
});
test('repaired original-obligation warning disappears after native reconciliation',async()=>{
 state.checkpoints=[{execution_process_id:execution,observation_state:'observed'}];await render(entry('completion observation has no matching original obligation'));assert.equal(element.textContent,'');
});
test('failed current observation remains visible',async()=>{
 state.checkpoints=[{execution_process_id:execution,observation_state:'failed'}];await render();assert.match(element.textContent!,/Git preservation blocked/);
});
test('unknown owner remains visible even when another owner is observed',async()=>{
 state.checkpoints=[{execution_process_id:'other',observation_state:'observed'}];await render();assert.match(element.textContent!,/Git preservation blocked/);
});
test('status API failure retains the warning',async()=>{
 state.fail=true;await render();assert.match(element.textContent!,/Git preservation blocked/);
});
test('publication failures remain visible without capture lookup',async()=>{
 state.checkpoints=[{execution_process_id:execution,observation_state:'observed'}];await render(entry('remote publication failed'));assert.match(element.textContent!,/remote publication failed/);assert.deepEqual(state.calls,[]);
});
test('user and assistant quotations stay untouched',async()=>{
 for(const type of ['user_message','assistant_message'])assert.equal(isCapturedGitNotice(entry(blocked,type),workspace,execution),false);
 await render(entry(blocked,'assistant_message'));assert.match(element.textContent!,/Git preservation blocked/);assert.deepEqual(state.calls,[]);
});
test('another workspace or turn cannot suppress a notice',()=>{
 assert.equal(isCapturedGitNotice(entry(),'other',execution),false);assert.equal(isCapturedGitNotice(entry(),workspace,'other'),false);
});
