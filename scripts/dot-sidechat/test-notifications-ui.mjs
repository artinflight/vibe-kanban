import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import {
  bundleNotifications,
  state,
  transport,
  wait,
} from './notification-test-support.mjs';
const bundle = await bundleNotifications();
for (const width of [390, 1440]) {
  const s = state();
  let focused = false,
    atEnd = false;
  function load() {
    return new JSDOM('<div id="root"></div>', {
      url: 'https://fixture.invalid',
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(w) {
        Object.defineProperty(w, 'innerWidth', { value: width });
        w.matchMedia = () => ({
          matches: width < 768,
          addEventListener() {},
          removeEventListener() {},
        });
        w.fetch = transport(s);
        w.document.hasFocus = () => focused;
        w.CSS = { escape: (x) => x };
        w.HTMLElement.prototype.scrollIntoView = function () {};
        w.HTMLElement.prototype.getClientRects = function () {
          return [this.getBoundingClientRect()];
        };
        w.HTMLElement.prototype.getBoundingClientRect = function () {
          return this.hasAttribute('data-dot-read')
            ? {
                top: atEnd ? 100 : 1200,
                bottom: atEnd ? 101 : 1201,
                left: 20,
                right: 21,
                width: 1,
                height: 1,
              }
            : {
                top: 0,
                bottom: 500,
                left: 0,
                right: width,
                width,
                height: 500,
              };
        };
      },
    });
  }
  let dom = load();
  dom.window.eval(bundle.js);
  await wait(
    () =>
      dom.window.document.querySelectorAll(
        '[aria-label="Dot unread replies: 1"]'
      ).length === 3
  );
  assert.equal(
    s.reads.length,
    0,
    'Hidden/inactive panel must not mark fetched replies seen'
  );
  dom.window.document.getElementById('toggle-dot').click();
  dom.window.dispatchEvent(new dom.window.Event('focus'));
  await new Promise((r) => setTimeout(r, 60));
  assert.equal(s.reads.length, 0, 'Unfocused tab must not read');
  focused = true;
  dom.window.dispatchEvent(new dom.window.Event('focus'));
  await new Promise((r) => setTimeout(r, 60));
  assert.equal(s.reads.length, 0, 'Offscreen reply end must not read');
  atEnd = true;
  dom.window.dispatchEvent(new dom.window.Event('focus'));
  await wait(
    () =>
      s.seen &&
      !dom.window.document.querySelector('[aria-label="Dot unread replies: 1"]')
  );
  assert.equal(
    dom.window.document.querySelectorAll(
      '[aria-label="Dot Needs Attention: 1"]'
    ).length,
    3
  );
  assert.match(
    dom.window.document.body.textContent,
    /Coding-agent unread remains/
  );
  dom.window.document.getElementById('sibling').click();
  await wait(() =>
    s.requests.some((r) =>
      r.url.includes('workspace=22222222-2222-4222-8222-222222222222')
    )
  );
  await wait(() =>
    dom.window.document.querySelector('[aria-label="Resolve Dot question"]')
  );
  assert.equal(
    s.reads.length,
    1,
    'Sibling issue view shares durable seen state'
  );
  dom.window.close();
  dom = load();
  dom.window.eval(bundle.js);
  await wait(
    () =>
      dom.window.document.querySelectorAll(
        '[aria-label="Dot Needs Attention: 1"]'
      ).length === 3
  );
  assert.equal(
    dom.window.document.querySelector('[aria-label="Dot unread replies: 1"]'),
    null
  );
  dom.window.document.getElementById('toggle-dot').click();
  await wait(() =>
    dom.window.document.querySelector('[aria-label="Resolve Dot question"]')
  );
  dom.window.document
    .querySelector('[aria-label="Resolve Dot question"]')
    .click();
  await wait(
    () =>
      s.resolved &&
      !dom.window.document.querySelector(
        '[aria-label="Dot Needs Attention: 1"]'
      )
  );
  assert.equal(
    s.requests.some((r) => !r.url.startsWith('/api/dot-sidechat/')),
    false
  );
  assert.match(
    dom.window.document.body.textContent,
    /Coding-agent unread remains/
  );
  dom.window.close();
}
// Exercise the real container/panel for both context targets. Transport is isolated.
for (const project of [false, true])
  for (const width of [390, 1440]) {
    const s = state();
    s.attention = false;
    function load() {
      return new JSDOM('<div id="root"></div>', {
        url: 'https://fixture.invalid/' + (project ? '?project' : ''),
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        beforeParse(w) {
          Object.defineProperty(w, 'innerWidth', { value: width });
          w.matchMedia = () => ({
            matches: width < 768,
            addEventListener() {},
            removeEventListener() {},
          });
          w.fetch = transport(s);
          w.document.hasFocus = () => true;
          w.CSS = { escape: (x) => x };
          w.HTMLElement.prototype.scrollIntoView = function () {};
          w.HTMLElement.prototype.getBoundingClientRect = function () {
            return {
              top: 0,
              bottom: 200,
              left: 0,
              right: 300,
              width: 300,
              height: 200,
            };
          };
          w.HTMLElement.prototype.getClientRects = function () {
            return [this.getBoundingClientRect()];
          };
        },
      });
    }
    let dom;
    const button = (label) =>
      dom.window.document.querySelector(`[aria-label="${label}"]`);
    const settle = () => new Promise((r) => setTimeout(r, 80));
    async function mount() {
      dom = load();
      dom.window.eval(bundle.js);
      await wait(
        () =>
          button('Mark Dot reply as unread') || button('Mark Dot reply as read')
      );
      dom.window.document.getElementById('toggle-dot').click();
      await settle();
      dom.window.dispatchEvent(new dom.window.Event('focus'));
    }
    await mount();
    await wait(() => s.reads.length === 1);
    await settle();
    s.holdThread = true;
    dom.window.document
      .querySelector('[aria-label="Refresh conversation"]')
      .click();
    await wait(() => s.releaseThread);
    button('Mark Dot reply as unread').click();
    button('Mark Dot reply as unread').click();
    await wait(
      () =>
        button('Mark Dot reply as read') &&
        !button('Mark Dot reply as read').disabled
    );
    assert.equal(
      s.readStates.length,
      1,
      'Repeated in-flight clicks issue one explicit operation'
    );
    s.holdThread = false;
    s.releaseThread();
    await settle();
    assert.ok(
      button('Mark Dot reply as read'),
      'Stale refresh cannot replace manual unread'
    );
    assert.equal(s.seen, false);
    assert.equal(s.attention, false);
    assert.equal(
      s.readStates[0][project ? 'project' : 'workspace'],
      '11111111-1111-4111-8111-111111111111'
    );
    dom.window.dispatchEvent(new dom.window.Event('focus'));
    dom.window.document
      .querySelector('[aria-label="Refresh conversation"]')
      .click();
    await settle();
    assert.equal(s.reads.length, 1, 'Open chat cannot undo manual unread');
    button('Mark Dot reply as needing attention').click();
    await wait(
      () => button('Resolve Dot action') || button('Resolve Dot question')
    );
    assert.equal(s.seen, false, 'Adding attention must preserve unread');
    button('Resolve Dot question').click();
    await wait(() => s.resolved);
    await wait(() => button('Reopen Dot question'));
    assert.equal(s.seen, false, 'Resolving attention must preserve unread');
    button('Reopen Dot question').click();
    await wait(() => !s.resolved);
    dom.window.document.getElementById('sibling').click();
    await wait(() => button('Mark Dot reply as read'));
    await settle();
    assert.equal(
      s.reads.length,
      1,
      'Navigation cannot auto-clear manual unread'
    );
    dom.window.close();
    await mount();
    await settle();
    assert.equal(s.seen, false);
    assert.equal(s.manualUnread, true);
    assert.equal(s.reads.length, 1, 'Reload cannot auto-clear manual unread');
    s.failReadState = true;
    button('Mark Dot reply as read').click();
    await wait(() => dom.window.document.querySelector('[role="alert"]'));
    await wait(() => !button('Mark Dot reply as read').disabled);
    assert.equal(
      s.manualUnread,
      true,
      'Failed explicit read retains manual unread'
    );
    s.failReadState = false;
    button('Mark Dot reply as read').click();
    await wait(() => button('Mark Dot reply as unread'));
    assert.equal(s.seen, true);
    assert.equal(s.resolved, false, 'Reading cannot resolve attention');
    dom.window.close();
    await mount();
    await settle();
    assert.equal(s.seen, true);
    assert.equal(s.manualUnread, false);
    assert.ok(button('Resolve Dot question'), 'Attention survives read/reload');
    // A response to an earlier automatic read must not overwrite a later manual unread.
    s.seen = false;
    s.holdRead = true;
    dom.window.close();
    await mount();
    await wait(() => s.releaseRead);
    button('Mark Dot reply as unread').click();
    await wait(() => button('Mark Dot reply as read'));
    s.releaseRead();
    await settle();
    assert.equal(s.manualUnread, true);
    assert.ok(button('Mark Dot reply as read'));
    assert.ok(s.requests.every((r) => r.url.startsWith('/api/dot-sidechat/')));
    dom.window.close();
    // A new frontend remains usable with the incumbent API until service adoption.
    s.supportsManualUnread = false;
    dom = load();
    dom.window.eval(bundle.js);
    await wait(() => button('Resolve Dot question'));
    assert.equal(button('Mark Dot reply as unread'), null);
    assert.equal(button('Mark Dot reply as read'), null);
    dom.window.close();
  }
console.log(
  'PASS: manual unread/read, repeated clicks, failed operation retry, open-chat/focus protection, sibling/navigation/reload persistence, attention transitions and late automatic-read race for issue/project at desktop/mobile sizes.'
);
console.log(
  'PASS: desktop/mobile independent indicators, visible focused reply reads, sibling/reload persistence, explicit resolve and no coding-agent API calls. DOM geometry controlled.'
);
