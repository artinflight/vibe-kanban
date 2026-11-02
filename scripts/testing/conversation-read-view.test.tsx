import React, { act, useRef } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { test, beforeEach, afterEach, after } from 'node:test';
import { useReadOnConversationView } from '../../packages/web-core/src/features/workspace-chat/model/useReadOnConversationView';
import { requestWorkspaceRead } from '../../packages/web-core/src/shared/lib/workspaceReadIntent';
import { state } from './workspace-seen.fixture';
const dom = new JSDOM('<html><body></body></html>');
Object.assign(globalThis, { window: dom.window, document: dom.window.document, CustomEvent: dom.window.CustomEvent,
  getComputedStyle: dom.window.getComputedStyle.bind(dom.window),
  MutationObserver: dom.window.MutationObserver, IS_REACT_ACT_ENVIRONMENT: true });
let visibility='visible', focused=true, bottom=450;
Object.defineProperty(document,'visibilityState',{get:()=>visibility});
Object.defineProperty(document,'hasFocus',{value:()=>focused});
const box=(top:number,bottom:number)=>({x:0,y:top,top,bottom,left:0,right:400,width:400,height:bottom-top,toJSON(){return {};}});
dom.window.HTMLElement.prototype.getBoundingClientRect=function(){return this.hasAttribute('data-workspace-read-reply')?box(bottom-300,bottom):box(0,500);};
dom.window.HTMLElement.prototype.getClientRects=function(){return [this.getBoundingClientRect()] as unknown as DOMRectList;};
let root:Root, element:HTMLDivElement, client:QueryClient;
const reveal=()=>{bottom=450;};
function Chat({ready=true,revision='reply-1',id='a',session='s',hidden=false}:{ready?:boolean;revision?:string;id?:string;session?:string;hidden?:boolean}){
 const ref=useRef<HTMLDivElement>(null);
 useReadOnConversationView({workspaceId:id,sessionId:session,ready,replyKey:'reply',revision,scrollRef:ref,revealLatest:reveal});
 return <div style={{display:hidden?'none':undefined}}><div ref={ref} data-chat="true"><div data-workspace-read-reply="reply">{revision}</div></div></div>;
}
async function render(child:React.ReactNode=<Chat/>){await act(async()=>{root.render(<QueryClientProvider client={client}>{child}</QueryClientProvider>);});}
async function settle(){await act(async()=>{await new Promise(resolve=>setTimeout(resolve,400));});}
async function event(name:string,target:EventTarget=window){await act(async()=>{target.dispatchEvent(new dom.window.Event(name,{bubbles:true}));});}
beforeEach(()=>{state.calls=[];state.fail=false;state.pause=undefined;visibility='visible';focused=true;bottom=450;client=new QueryClient();client.invalidateQueries=async()=>{};element=document.createElement('div');document.body.append(element);root=createRoot(element);});
afterEach(async()=>{await act(async()=>root.unmount());element.remove();client.clear();});
after(()=>dom.window.close());
test('opening a loaded conversation acknowledges its displayed reply after dwell',async()=>{await render();assert.deepEqual(state.calls,[]);await settle();assert.deepEqual(state.calls,['a']);});
test('record/session loading waits for actual transcript content',async()=>{await render(<Chat ready={false}/>);await settle();assert.deepEqual(state.calls,[]);await render(<Chat ready/>);await settle();assert.deepEqual(state.calls,['a']);});
test('an out-of-viewport reply is not read until scrolling deliberately to its end',async()=>{bottom=900;await render();await settle();assert.deepEqual(state.calls,[]);const chat=element.querySelector('[data-chat]')!;await event('wheel',chat);bottom=450;await event('scroll',chat);await settle();assert.deepEqual(state.calls,['a']);});
test('background mount and later tab return cannot acknowledge unread',async()=>{visibility='hidden';await render();visibility='visible';await event('visibilitychange',document);await settle();assert.deepEqual(state.calls,[]);await event('pointerdown',element.querySelector('[data-chat]')!);await settle();assert.deepEqual(state.calls,['a']);});
test('unfocused window cannot mark read',async()=>{focused=false;await render();await settle();assert.deepEqual(state.calls,[]);});
test('blurring during dwell cancels the read and focus alone does not retry',async()=>{await render();await event('blur');await event('focus');await settle();assert.deepEqual(state.calls,[]);});
test('hiding during dwell cancels read; returning alone does not read',async()=>{await render();visibility='hidden';await event('visibilitychange',document);visibility='visible';await event('visibilitychange',document);await settle();assert.deepEqual(state.calls,[]);});
test('a new reply/poll after the initial read remains unread without a gesture',async()=>{await render();await settle();await render(<Chat revision="reply-2"/>);await event('scroll',element.querySelector('[data-chat]')!);await settle();assert.deepEqual(state.calls,['a']);});
test('a changed revision invalidates a pending read instead of swallowing new output',async()=>{await render();await render(<Chat revision="reply-2"/>);await settle();assert.deepEqual(state.calls,[]);});
test('same-workspace reselection reveals the latest reply and can read again',async()=>{await render();await settle();bottom=900;await act(async()=>requestWorkspaceRead('a'));await settle();assert.deepEqual(state.calls,['a','a']);});
test('a sibling workspace reselection cannot clear this chat',async()=>{bottom=900;await render();await act(async()=>requestWorkspaceRead('b'));await settle();assert.deepEqual(state.calls,[]);});
test('hidden phone/panel content is never read; opening the panel can read it',async()=>{await render(<Chat hidden/>);await settle();assert.deepEqual(state.calls,[]);await render(<Chat/>);await settle();assert.deepEqual(state.calls,['a']);});
test('failed automatic read is not retried on polling or tab return',async()=>{const warn=console.warn;console.warn=()=>{};try{state.fail=true;await render();await settle();state.fail=false;await render(<Chat revision="reply-2"/>);await event('focus');await settle();assert.deepEqual(state.calls,['a']);await act(async()=>requestWorkspaceRead('a'));await settle();assert.deepEqual(state.calls,['a','a']);}finally{console.warn=warn;}});
test('navigation/unmount during dwell cannot clear the abandoned chat',async()=>{await render();await render(<div/>);await settle();assert.deepEqual(state.calls,[]);});
