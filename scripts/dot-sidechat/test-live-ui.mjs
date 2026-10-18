// DOM-only live transport contract tests. No real browser or external event.
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const result = await build({
  stdin: { contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import {DotSidechatLive} from './packages/web-core/src/pages/workspaces/DotSidechatLive'; createRoot(document.getElementById('root')).render(<DotSidechatLive workspaceId="11111111-1111-4111-8111-111111111111"/>);`, resolveDir: process.cwd(), loader:'tsx' },
  bundle:true, write:false, outdir:'unused', jsx:'automatic',
  alias:{'@vibe/ui':'./packages/ui/src',react:'./packages/ui/node_modules/react','react-dom':'./packages/ui/node_modules/react-dom'}
});
const js=result.outputFiles.find(x=>x.path.endsWith('.js')).text;
const wait=async(fn)=>{for(let n=0;n<150;n++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw Error('DOM condition timed out');};
let paired=false, loseResponse=true, messages=[], sends=[], requests=[];
const session={csrf:'csrf-test',session_id:'session-one',expires:9999999999};
function load(saved={}) {
  return new JSDOM('<div id="root"></div>',{
    url:'https://vibe.local/workspaces/11111111-1111-4111-8111-111111111111',runScripts:'dangerously',pretendToBeVisual:true,
    beforeParse(w){
      for(const [key,val] of Object.entries(saved))w.sessionStorage.setItem(key,val);
      w.HTMLElement.prototype.scrollIntoView=function(){};
      w.fetch=async(url,opts)=>{
        requests.push({url,opts});
        assert.equal(opts.credentials,'same-origin');
        assert.equal(opts.headers['X-Dot-Request'],'1');
        const route=url.split('/api/dot-sidechat/')[1];
        const reply=(status,body)=>({status,ok:status===200,json:async()=>body});
        if(route==='session')return reply(paired?200:401,session);
        if(route==='pair'){paired=true;return reply(200,session);}
        if(!paired)return reply(401,{});
        if(route==='logout'){paired=false;return reply(200,{});}
        if(route.startsWith('thread?'))return reply(200,{
          thread:{id:'thread-one'},scope:{issue_label:'Real scoped issue',workspace_label:'Chosen workspace'},
          messages,receipts:Object.fromEntries(messages.map(m=>[m.id,{state:'pending',reply_persisted:false}])),through:messages.length,next_after:null
        });
        if(route==='send'){
          assert.equal(opts.headers['X-Dot-CSRF'],'csrf-test');
          const body=JSON.parse(opts.body);sends.push(body);
          assert.deepEqual(Object.keys(body).sort(),['body','request','workspace']);
          if(!messages.length)messages=[{id:'message-one',seq:1,role:'owner',body:body.body,workspace:body.workspace,created:1}];
          if(loseResponse){loseResponse=false;throw Error('Response lost');}
          return reply(200,messages[0]);
        }
        throw Error('Unexpected route '+route);
      };
    }
  });
}
function input(dom,selector,value){
  const node=dom.window.document.querySelector(selector);
  const proto=node.tagName==='TEXTAREA'?dom.window.HTMLTextAreaElement.prototype:dom.window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto,'value').set.call(node,value);
  node.dispatchEvent(new dom.window.Event('input',{bubbles:true}));
}
let dom=load();dom.window.eval(js);
await wait(()=>dom.window.document.querySelector('#dot-pair'));
assert.equal(requests.some(r=>r.url.includes('thread?')),false);
input(dom,'#dot-pair','one-use-test-code');
dom.window.document.querySelector('button[type=submit]').click();
await wait(()=>dom.window.document.body.textContent.includes('Real scoped issue'));
assert.doesNotMatch(dom.window.document.body.textContent,/fixture replies|Dot · fixture/);
input(dom,'#dot-draft','Keep this exact message on retry.');
await wait(()=>!dom.window.document.querySelector('button[type=submit]').disabled);
dom.window.document.querySelector('button[type=submit]').click();
await wait(()=>dom.window.document.body.textContent.includes('Response lost'));
const saved=Object.fromEntries(Object.keys(dom.window.sessionStorage).map(k=>[k,dom.window.sessionStorage.getItem(k)]));
assert.equal(Object.keys(saved).length,1);
dom.window.close();
dom=load(saved);dom.window.eval(js);
await wait(()=>dom.window.document.body.textContent.includes('Retry same message'));
assert.equal(dom.window.document.querySelector('#dot-draft').readOnly,true);
await wait(()=>!dom.window.document.querySelector('button[type=submit]').disabled);
dom.window.document.querySelector('button[type=submit]').click();
await wait(()=>sends.length===2 && dom.window.sessionStorage.length===0);
assert.deepEqual(sends[0],sends[1]);
assert.match(dom.window.document.body.textContent,/Saved · awaiting delivery/);
[...dom.window.document.querySelectorAll('button')].find(x=>x.textContent==='Disconnect').click();
await wait(()=>dom.window.document.querySelector('#dot-pair'));
assert.equal(dom.window.document.querySelector('.dot-history'),null);
dom.window.close();
console.log('PASS: pairing gate, real workspace transport, no fixture identity, lost-response/reload idempotency, receipt distinction, logout clears private UI. DOM only.');
