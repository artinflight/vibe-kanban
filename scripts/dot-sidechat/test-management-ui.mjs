// Actual paired-owner metadata hook + desktop/mobile row/card; synthetic GETs only.
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import {
  bundleNotifications,
  state,
  transport,
  wait,
} from './notification-test-support.mjs';
const bundle = await bundleNotifications();
const association = {
  workspace_id: '11111111-1111-4111-8111-111111111111',
  issue_id: 'issue-fixture',
  project_id: 'project-fixture',
  manager: 'dot',
  state: 'managed',
};
for (const width of [390, 1440]) {
  const s = { ...state(), managed: [association] };
  for (const reload of [false, true]) {
    const dom = new JSDOM('<div id="root"></div>', {
      url: 'https://fixture.invalid/',
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(w) {
        w.matchMedia = () => ({
          matches: width < 768,
          addEventListener() {},
          removeEventListener() {},
        });
        w.fetch = transport(s);
        w.document.hasFocus = () => false;
      },
    });
    try {
      dom.window.eval(bundle.js);
      const doc = dom.window.document;
      const indicators = () => doc.querySelectorAll('[data-dot-managed]');
      await wait(() => indicators().length === 2);
      const refresh = () =>
        dom.window.dispatchEvent(
          new dom.window.CustomEvent('dot-sidechat-changed')
        );
      s.seen = true;
      s.resolved = true;
      refresh();
      await wait(
        () => !doc.querySelector('[aria-label^="Dot unread replies:"]')
      );
      assert.equal(
        doc.querySelector('[aria-label^="Dot Needs Attention:"]'),
        null
      );
      assert.equal(indicators().length, 2);
      assert.equal(
        [...doc.querySelectorAll('.mobile-workspace-card')]
          .find((n) => n.textContent.includes('Workspace B'))
          .querySelector('[data-dot-managed]'),
        null
      );
      s.managed = [];
      refresh();
      await wait(() => indicators().length === 0);
      // A legacy service with notifications, but no explicit association, stays neutral.
      s.managed = undefined;
      s.seen = false;
      refresh();
      await wait(() =>
        doc.querySelector('[aria-label^="Dot unread replies:"]')
      );
      assert.equal(indicators().length, 0);
      s.managed = [association];
      s.seen = true;
      refresh();
      await wait(() => indicators().length === 2);
      assert.ok(s.requests.every((r) => r.method === 'GET'));
      console.log(
        `PASS management metadata ${width} reload=${reload}: read/clear independent; exact row/card only; legacy neutral; GET only.`
      );
    } finally {
      dom.window.close();
    }
  }
}
