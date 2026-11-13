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
console.log(
  'PASS: desktop/mobile independent indicators, visible focused reply reads, sibling/reload persistence, explicit resolve and no coding-agent API calls. DOM geometry controlled.'
);
