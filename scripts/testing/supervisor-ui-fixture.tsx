// Real supervisor components with an isolated in-memory transport. No VK runtime,
// coding agent, model or external provider is contacted by this fixture.
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import common from '../../packages/web-core/src/i18n/locales/en/common.json';
import { SupervisorProvider } from '../../packages/web-core/src/features/conversation/SupervisorProvider';
import { SupervisorLauncher } from '../../packages/web-core/src/shared/components/ui-new/containers/SupervisorLauncher';
import { setLocalApiTransport } from '../../packages/web-core/src/shared/lib/localApiTransport';

let seq = 1;
let revision = 1;
let loseAcknowledgement = true;
const postIds: string[] = [];
const sockets = new Set<any>();
const raw = 'Validation:: 42 tests passed\nCommit:: abc123\n```rust\nfn original() {}\n```';
let messages: any[] = [{id:'opening',conversation_id:'conversation',created_seq:1,role:'assistant',origin:'derived',body:'The Android agent matched onboarding to web.',revision:1,status:'final',reply_to_id:null,client_message_id:null,created_at:'2026-09-26T00:00:00Z'}];
const capabilities = {enabled:true,accepting_messages:true,agent_actions:false,voice:false,authority:'local_operator'};
const snapshot = () => ({conversation:{id:'conversation',authority_id:'local',principal_id:'owner',next_seq:seq+1,revision,created_at:'2026-09-26T00:00:00Z',archived_at:null},last_seq:seq,capabilities});
const event = (type: string, payload: unknown) => {
  seq += 1; revision += 1;
  const record = {conversation_id:'conversation',seq,event_id:`event-${seq}`,type,schema_version:1,entity_id:'record',revision,occurred_at:'2026-09-26T00:00:00Z',payload};
  for (const socket of sockets) socket.onmessage?.({data:JSON.stringify(record)});
};
setLocalApiTransport({
  request: async (path, init) => {
    if (init?.hostScope !== 'none') throw new Error('Supervisor followed workspace host');
    const url = new URL(path,'https://fixture.invalid');
    const success = (data:unknown) => new Response(JSON.stringify({success:true,data,error_data:null,message:null}),{headers:{'Content-Type':'application/json'}});
    if (url.pathname.endsWith('/capabilities')) return success(capabilities);
    if (url.pathname.endsWith('/resolve') || url.pathname === '/api/conversations/conversation') return success(snapshot());
    if (url.pathname.endsWith('/messages') && init?.method === 'POST') {
      const input = JSON.parse(String(init.body)); postIds.push(input.client_message_id);
      let message = messages.find((row) => row.client_message_id === input.client_message_id);
      if (!message) { message = {...messages[0],id:input.client_message_id,role:'user',origin:'typed',body:input.body,client_message_id:input.client_message_id,created_seq:seq+1}; messages.push(message); event('message.created',message); }
      if (loseAcknowledgement) { loseAcknowledgement = false; throw new Error('Simulated acknowledgement loss'); }
      return success({message,run_id:'run'});
    }
    if (url.pathname.endsWith('/messages')) return success(messages.filter((row) => row.created_seq < Number(url.searchParams.get('before_seq') ?? Infinity)).slice(-50));
    if (url.pathname.endsWith('/actions') || url.pathname.endsWith('/memories')) return success([]);
    if (url.pathname.endsWith('/messages/opening/evidence')) return success([{evidence_id:'source',relationship:'summarised',source:{kind:'agent_report',session_id:'agent-session',process_id:'process'},availability:'retained'}]);
    if (url.pathname.endsWith('/evidence/source')) return success({id:'source',conversation_id:'conversation',source:{kind:'agent_report',session_id:'agent-session',process_id:'process'},source_revision:'final',content_hash:'fixture',availability:'retained',raw_report:raw,captured_at:'2026-09-26T00:00:00Z'});
    if (url.pathname.endsWith('/history') && init?.method === 'DELETE') { messages=[]; event('history.cleared',{}); return success(snapshot()); }
    if (url.pathname.endsWith('/export')) return success({messages});
    throw new Error(`Unexpected fixture request: ${url.pathname}`);
  },
  openWebSocket: (_path, options) => {
    if (options?.hostScope !== 'none') throw new Error('Supervisor socket followed workspace host');
    const socket = {readyState:1,onopen:null,onmessage:null,onclose:null,onerror:null,close() { sockets.delete(this); (this.onclose as any)?.(); }};
    sockets.add(socket); return socket as unknown as WebSocket;
  },
});
(window as any).__supervisorFixture = {postIds, raw, get messageCount(){return messages.length;}};
function Workspace() {
  const [topic,setTopic] = useState('Android');
  return <><SupervisorLauncher /><button onClick={() => setTopic('Mission Perform')}>Navigate project</button><main key={topic}><h1>{topic}</h1><pre>{raw}</pre></main></>;
}
void i18next.use(initReactI18next).init({lng:'en',resources:{en:{common}},defaultNS:'common',interpolation:{escapeValue:false}}).then(() => {
  createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><SupervisorProvider><Workspace /></SupervisorProvider></QueryClientProvider>);
});
