import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import {
  projectRoutingBundle,
  routingState,
  routingTransport,
  ids,
} from './project-routing-test-support.mjs';
import { wait } from './notification-test-support.mjs';
console.log('Bundling project notice fixture');
const bundle = await projectRoutingBundle(
  'scripts/dot-sidechat/project-notice-fixture.tsx'
);
console.log('Fixture bundled');
const future = '66666666-6666-4666-8666-666666666666';
for (const width of [390, 1440]) {
  const s = routingState();
  s.projectNotices = [
    { project_id: ids.project, unread_count: 3, needs_attention_count: 1 },
    { project_id: '55555555-5555-4555-8555-555555555555', unread_count: 0 },
    { project_id: future, unread_count: 2 },
    { project_id: ids.project, unread_count: 3 },
  ];
  const before = JSON.stringify(s.messages);
  const dom = new JSDOM('<div id="root"></div>', {
    url: 'https://fixture.invalid/projects/' + ids.project,
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    beforeParse(w) {
      w.matchMedia = () => ({
        matches: width < 768,
        addEventListener() {},
        removeEventListener() {},
      });
      w.fetch = routingTransport(s);
      w.document.hasFocus = () => false;
      w.CSS = { escape: (x) => x };
      w.ResizeObserver = class {
        constructor(fn) {
          this.fn = fn;
        }
        observe() {
          this.fn();
        }
        disconnect() {}
      };
      w.HTMLElement.prototype.getBoundingClientRect = () => ({
        top: 0,
        left: 0,
        right: width,
        bottom: 900,
        width,
        height: 900,
      });
      w.HTMLElement.prototype.scrollIntoView = function () {};
    },
  });
  try {
    console.log('Evaluating', width);
    dom.window.eval(bundle.js);
    const doc = dom.window.document;
    const pane = () => doc.querySelector('[data-workspace-pane]');
    const notices = () => pane().querySelectorAll('[data-project-dot-notice]');
    const notice = () =>
      pane().querySelector(`[data-project-dot-notice="${ids.project}"]`);
    const button = (label) =>
      [...doc.querySelectorAll('button')].find(
        (b) =>
          b.getAttribute('aria-label') === label ||
          b.textContent.trim() === label
      );
    const input = () => doc.getElementById('dot-draft');
    const type = (value) => {
      Object.getOwnPropertyDescriptor(
        dom.window.HTMLTextAreaElement.prototype,
        'value'
      ).set.call(input(), value);
      input().dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    };
    async function attention() {
      await wait(() => pane());
      if (width < 768) {
        [...pane().querySelectorAll('.phone-workspace-tabs button')]
          .find((b) => b.textContent.startsWith('Attention'))
          .click();
      }
      await wait(() => notices().length === 2);
    }
    await attention();
    console.log('Notices loaded', width);
    assert.equal(
      notice().textContent.includes('Synthetic project Alpha'),
      true
    );
    assert.equal(notices().length, 2);
    assert.ok(pane().textContent.includes('Project ' + future));
    const target = () =>
      [...pane().querySelectorAll('.mobile-workspace-card')].find((n) =>
        n.textContent.includes('Workspace target')
      );
    assert.equal(
      target().querySelector('[aria-label="Dot unread replies: 1"]') !== null,
      true
    );
    assert.equal(
      target().querySelector('[aria-label="Dot unread replies: 3"]'),
      null
    );
    if (width < 768) {
      [...pane().querySelectorAll('.phone-workspace-tabs button')]
        .find((b) => b.textContent.startsWith('Running'))
        .click();
      await wait(() => notices().length === 0);
      await attention();
    }
    console.log('Initial rows checked', width);
    for (const mode of ['flat', 'accordion']) {
      dom.window.fixtureSetMode(mode);
      await attention();
      assert.equal(notices().length, 2);
    }
    console.log('Modes checked', width);
    s.projectNotices[0].unread_count = 7;
    s.projectNotices[3].unread_count = 7;
    dom.window.dispatchEvent(
      new dom.window.CustomEvent('dot-sidechat-changed')
    );
    await wait(() => notice().textContent.includes('7 unread'));
    assert.ok(target().querySelector('[aria-label="Dot unread replies: 1"]'));
    console.log('Updated', width);
    dom.window.fixtureSetEmpty(true);
    await wait(
      () => pane().querySelectorAll('.mobile-workspace-card').length === 0
    );
    assert.equal(notices().length, 2);
    assert.equal(pane().textContent.includes('You’re all caught up'), false);
    dom.window.fixtureSetEmpty(false);
    // Establish a project draft/reply/cursor, then request the same chat from its plan tab.
    console.log('Opening project', width);
    notice().click();
    await wait(
      () =>
        input() &&
        doc.querySelector('.dot-scope')?.textContent.includes('Project-wide')
    );
    type('Retained project draft');
    doc.querySelector('[aria-label="Reply to message 1"]').click();
    button('Jump to Needs Attention').click();
    await wait(
      () =>
        doc.querySelector('.dot-reply-target') &&
        doc.querySelector('[data-dot-attention-current]')
    );
    const oldInput = input();
    doc.getElementById('project-plan-tab').click();
    await wait(() => doc.getElementById('project-chat-panel').hidden);
    notice().click();
    await wait(() => !doc.getElementById('project-chat-panel').hidden);
    assert.ok(
      input() === oldInput,
      'Project notice must retain the mounted composer'
    );
    assert.ok(doc.querySelector('[data-dot-attention-current]'));
    assert.equal(input().value, 'Retained project draft');
    // The generic workspace selection remains A: the notice must explicitly drop it.
    doc.getElementById('route-workspace').click();
    await wait(
      () =>
        doc.getElementById('displayed-workspace')?.textContent === 'Workspace a'
    );
    if (width < 768) button('Open project sidebar').click();
    await wait(() =>
      doc.querySelector('.dot-scope')?.textContent.includes('Workspace a')
    );
    type('Retained workspace draft');
    doc.querySelector('[aria-label="Reply to message 1"]').click();
    dom.window.fixtureShowWorkspaces();
    notice().click();
    await wait(
      () =>
        input() &&
        doc.querySelector('.dot-scope')?.textContent.includes('Project-wide')
    );
    assert.equal(dom.window.history.state.destination, 'project');
    assert.equal(input().value, 'Retained project draft');
    assert.match(
      doc.querySelector('.dot-reply-target').textContent,
      /Conversation project/
    );
    assert.equal(dom.window.fixtureWorkspaceSelections.length, 0);
    const requests = s.requests.filter((r) =>
      r.url.startsWith('/api/dot-sidechat/thread?')
    );
    assert.ok(requests.at(-1).url.includes('project=' + ids.project));
    assert.ok(!requests.at(-1).url.includes('workspace='));
    const historyLength = dom.window.history.length;
    s.projectNotices = [
      { project_id: ids.project, unread_count: 0, needs_attention_count: 5 },
    ];
    dom.window.dispatchEvent(
      new dom.window.CustomEvent('dot-sidechat-changed')
    );
    await wait(() => notices().length === 0);
    assert.equal(dom.window.history.length, historyLength);
    assert.equal(JSON.stringify(s.messages), before);
    assert.ok(s.requests.every((r) => r.method === 'GET'));
    assert.equal(s.sends.length, 0);
    console.log(
      `PASS project notices ${width}: distinct project rows, positive/update/zero counts, flat/grouped, zero workspaces, no fanout, exact project intent, drafts/replies/cursor/flags preserved; GET only.`
    );
  } finally {
    dom.window.close();
  }
}
