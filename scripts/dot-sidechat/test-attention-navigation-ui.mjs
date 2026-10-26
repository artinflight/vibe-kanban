// Real container + full snapshot pagination; controlled geometry, no live API.
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { bundleNotifications, wait } from './notification-test-support.mjs';
import {
  attentionState,
  attentionTransport,
} from './attention-navigation-test-support.mjs';
const bundle = await bundleNotifications();
for (const project of [false, true])
  for (const width of [390, 1440]) {
    const s = attentionState();
    let release;
    s.hold = new Promise((resolve) => {
      release = resolve;
    });
    const dom = new JSDOM('<div id="root"></div>', {
      url: 'https://fixture.invalid/' + (project ? '?project' : ''),
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(w) {
        w.matchMedia = () => ({
          matches: width < 768,
          addEventListener() {},
          removeEventListener() {},
        });
        w.fetch = attentionTransport(s);
        w.CSS = { escape: (x) => x };
        w.document.hasFocus = () => false;
        w.HTMLElement.prototype.getBoundingClientRect = function () {
          return {
            top: 0,
            bottom: 200,
            left: 0,
            right: width,
            width,
            height: 200,
          };
        };
        w.HTMLElement.prototype.scrollIntoView = function () {
          w.fixtureRevealed = this.id;
        };
      },
    });
    try {
      dom.window.eval(bundle.js);
      const doc = dom.window.document;
      const button = (label) =>
        [...doc.querySelectorAll('button')].find(
          (b) =>
            b.getAttribute('aria-label') === label || b.textContent === label
        );
      await wait(() => s.requests.some((r) => r.url.includes('after=50')));
      assert.ok(button('Jump to Needs Attention').disabled);
      assert.match(
        doc.querySelector('.dot-attention-nav').textContent,
        /Loading conversation/
      );
      release();
      s.hold = null;
      await wait(() => !button('Jump to Needs Attention').disabled);
      assert.ok(s.requests.some((r) => r.url.includes('after=100')));
      assert.ok(
        s.requests
          .filter((r) => r.url.includes('after='))
          .every((r) => r.url.includes('through=125'))
      );
      doc.getElementById('toggle-dot').click();
      const selected = () =>
        doc.querySelector('[data-dot-attention-current]')?.id;
      const click = (label) => button(label).click();
      click('Jump to Needs Attention');
      await wait(() => selected() === 'message-attention-3');
      assert.equal(doc.activeElement.id, selected());
      click('Next flagged message');
      await wait(() => selected() === 'message-attention-61');
      click('Next flagged message');
      await wait(() => selected() === 'message-attention-112');
      click('Next flagged message');
      await wait(() => selected() === 'message-attention-3');
      click('Previous flagged message');
      await wait(() => selected() === 'message-attention-112');
      // Refresh changes flags without resolving anything as a consequence of navigation.
      s.messages[111].attention.resolved = true;
      s.messages[119].attention = { kind: 'action', resolved: false };
      click('Refresh conversation');
      await wait(() =>
        doc
          .querySelector('.dot-attention-nav')
          .textContent.includes('Flag changed')
      );
      click('Next flagged message');
      await wait(() => selected() === 'message-attention-120');
      click('Previous flagged message');
      await wait(() => selected() === 'message-attention-61');
      click('Jump to Needs Attention');
      await wait(() => selected() === 'message-attention-3');
      // An older quote URL must not steal the navigation position when polling refreshes.
      dom.window.location.hash =
        'thread=' +
        (project ? 'project' : 'issue') +
        '-attention-thread&message=attention-1';
      await wait(() => dom.window.fixtureRevealed === 'message-attention-1');
      click('Jump to Needs Attention');
      await wait(() => selected() === 'message-attention-3');
      dom.window.fixtureRevealed = 'none';
      click('Refresh conversation');
      await new Promise((r) => setTimeout(r, 80));
      assert.equal(dom.window.fixtureRevealed, 'none');
      assert.equal(selected(), 'message-attention-3');
      s.messages.forEach((m) => {
        if (m.attention) m.attention.resolved = true;
      });
      click('Refresh conversation');
      await wait(() =>
        doc
          .querySelector('.dot-attention-nav')
          .textContent.includes('No unresolved flagged messages')
      );
      assert.ok(button('Jump to Needs Attention').disabled);
      assert.ok(button('Next flagged message').disabled);
      s.messages[7].attention = { kind: 'question', resolved: false };
      click('Refresh conversation');
      await wait(() => !button('Jump to Needs Attention').disabled);
      click('Next flagged message');
      await wait(() => selected() === 'message-attention-8');
      assert.match(
        doc.querySelector('.dot-attention-nav').textContent,
        /1 of 1/
      );
      s.fail = true;
      click('Refresh conversation');
      await wait(() =>
        doc
          .querySelector('.dot-attention-nav')
          .textContent.includes('Could not check flags')
      );
      assert.ok(button('Jump to Needs Attention').disabled);
      assert.ok(s.requests.every((r) => r.method === 'GET'));
      assert.ok(s.messages.every((m) => m.manual_unread && !m.seen));
      console.log(
        `PASS attention DOM ${project ? 'project' : 'issue'} ${width}: all pages, stable cursors, wrap, changing/empty flags, error and no mutations.`
      );
    } finally {
      dom.window.close();
    }
  }
