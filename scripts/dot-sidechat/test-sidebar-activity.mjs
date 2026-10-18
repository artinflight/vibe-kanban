import assert from 'node:assert/strict';
import { sidebarActivityBundle } from './sidebar-activity-test-support.mjs';
import { JSDOM } from 'jsdom';
import { wait } from './notification-test-support.mjs';
const bundle = await sidebarActivityBundle();
const running = [
  'Running unread',
  'Running attention',
  'Running approval',
  'Active subagent',
  'Unresolved subagent',
  'Subagent approval',
  'Subagent attention',
];
const attention = [
  'Running attention',
  'Running approval',
  'Subagent approval',
  'Subagent attention',
  'Idle unseen',
  'Idle Dot unread',
  'Idle approval',
  'Idle attention',
  'Dispatch target',
];
const idle = ['Idle clean', 'Dispatch sibling'];
for (const width of [390, 1440]) {
  const dom = new JSDOM('<div id="root"></div>', {
    url: 'https://isolated.invalid',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    beforeParse(w) {
      w.matchMedia = () => ({
        matches: width < 768,
        addEventListener() {},
        removeEventListener() {},
      });
      w.fetch = () => {
        throw Error('No API calls permitted');
      };
    },
  });
  dom.window.eval(bundle.outputFiles[0].text);
  const document = dom.window.document;
  const button = (label) =>
    [...document.querySelectorAll('button')].find(
      (n) =>
        n.textContent === label ||
        n.textContent ===
          label +
            {
              Running: running.length,
              Attention: attention.length,
              Ready: idle.length,
            }[label]
    );
  await wait(() => document.querySelector('.mobile-workspace-card'));
  function section(label) {
    if (width < 768) {
      const b = [
        ...document.querySelectorAll('.phone-workspace-tabs button'),
      ].find((n) => n.textContent.startsWith(label));
      assert.ok(b);
      b.click();
      return document;
    }
    const b = button(label);
    assert.ok(b, label);
    return b.parentElement.parentElement;
  }
  const names = (root) =>
    [...root.querySelectorAll('.mobile-workspace-card')].map(
      (n) =>
        (
          n.querySelector('.phone-workspace-name') ??
          n.querySelector('button > div')
        ).textContent
    );
  for (const [category, expected] of [
    [width < 768 ? 'Running' : 'Running', running],
    [width < 768 ? 'Attention' : 'Needs Attention', attention],
    [width < 768 ? 'Ready' : 'Idle', idle],
  ]) {
    const root = section(category);
    await wait(() => JSON.stringify(names(root)) === JSON.stringify(expected));
    if (category === 'Running') {
      assert.ok(root.querySelector('[aria-label="Dot unread replies: 1"]'));
      assert.ok(root.querySelector('[aria-label="Dot Needs Attention: 1"]'));
      assert.ok(
        width < 768
          ? (root.body?.textContent ?? root.textContent).includes(
              'Approval needed'
            )
          : root.querySelector('[aria-label="Pending approval"]'),
        'Real approval remains visible on running rows'
      );
    }
  }
  // Management is independent of read/attention/activity, including summary rows.
  for (const changes of [
    { dotUnreadCount: 0, dotNeedsAttentionCount: 0, hasUnseenActivity: false },
    { dotUnreadCount: 1, dotNeedsAttentionCount: 1 },
    { dotUnreadCount: 0, dotNeedsAttentionCount: 0 },
  ]) {
    dom.window.fixtureUpdate('running-unread', changes);
    const root = section('Running');
    await wait(() => names(root).includes('Running unread'));
    const row = [...root.querySelectorAll('.mobile-workspace-card')].find((n) =>
      n.textContent.includes('Running unread')
    );
    assert.ok(row.querySelector('[data-dot-managed]'));
  }
  const neutralRoot = section(width < 768 ? 'Attention' : 'Needs Attention');
  await wait(() => names(neutralRoot).includes('Dispatch target'));
  assert.equal(
    [...neutralRoot.querySelectorAll('.mobile-workspace-card')]
      .find((n) => n.textContent.includes('Dispatch target'))
      .querySelector('[data-dot-managed]'),
    null,
    'Generic dispatch must not label a subordinate as managed'
  );
  dom.window.fixtureUpdate('running-unread', {
    isRunning: false,
    dotUnreadCount: 1,
    hasUnseenActivity: true,
  });
  const needs = section(width < 768 ? 'Attention' : 'Needs Attention');
  await wait(() => names(needs).includes('Running unread'));
  dom.window.fixtureUpdate('running-unread', {
    isRunning: true,
    dotNeedsAttentionCount: 1,
  });
  const active = section('Running');
  await wait(() => names(active).includes('Running unread'));
  const action = section(width < 768 ? 'Attention' : 'Needs Attention');
  await wait(() => names(action).includes('Running unread'));
  assert.equal(names(action).includes('Dispatch sibling'), false);
  dom.window.close();
  console.log(
    `PASS ${width}: running/unread, explicit attention, approvals, idle/unseen, subagents, independent activity/action transitions and target-only dispatch badge.`
  );
}
