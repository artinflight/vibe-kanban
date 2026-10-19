// No real transport, prompts, assignment writes or browser. Bundle only in RAM.
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const fixture = resolve('scripts/testing/workspace-destination.fixture.tsx');
const realHooks =
  /useWorkspace(Sessions|Record)$|workspaceSessionKeys$|workspaceSummaryKeys$|useUiPreferencesStore$|shared\/types\/attempt$/;
const result = await build({
  entryPoints: ['scripts/testing/workspace-destination-harness.tsx'],
  bundle: true,
  write: false,
  format: 'iife',
  platform: 'browser',
  jsx: 'automatic',
  tsconfig: 'packages/web-core/tsconfig.json',
  define: { 'import.meta.hot': 'undefined', 'process.env.NODE_ENV': '"test"' },
  alias: {
    '@': resolve('packages/web-core/src'),
    '@tanstack/react-query': resolve(
      'packages/web-core/node_modules/@tanstack/react-query'
    ),
    react: resolve('packages/ui/node_modules/react'),
    'react-dom': resolve('packages/ui/node_modules/react-dom'),
  },
  plugins: [
    {
      name: 'synthetic-destination-boundaries',
      setup(b) {
        b.onResolve({ filter: /^@\/shared\// }, ({ path }) =>
          realHooks.test(path) ? undefined : { path: fixture }
        );
        b.onResolve(
          {
            filter:
              /^(react-i18next|@tanstack\/react-router|@vibe\/ui\/components\/|@\/features\/|\.\/KanbanIssuePanelContainer$|\.\/useSessionQueueInteraction$)/,
          },
          ({ path }) =>
            path.endsWith('/useSessionSend') ||
            path.endsWith('/useCreateSession')
              ? undefined
              : { path: fixture }
        );
        b.onResolve({ filter: /^@phosphor-icons\/react$/ }, () => ({
          path: 'icons',
          namespace: 'fixture',
        }));
        b.onLoad({ filter: /.*/, namespace: 'fixture' }, () => ({
          contents:
            'export const ArrowDownIcon=()=>null,ArrowsOutIcon=()=>null,XIcon=()=>null,LinkIcon=()=>null,PlusIcon=()=>null;',
          loader: 'js',
        }));
      },
    },
  ],
});
const wait = async (check) => {
  for (let i = 0; i < 200; i++) {
    if (check()) return;
    await new Promise((r) => setTimeout(r, 5));
  }
  assert.ok(check(), 'Fixture condition did not settle');
};
const tick = () => new Promise((r) => setTimeout(r, 20));
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
};
const session = (workspace, suffix = '1') => ({
  id: workspace + '-session-' + suffix,
  workspace_id: workspace,
});
const record = (id) => ({
  id,
  name: 'Human name ' + id,
  branch: 'vk/opaque-' + id,
});
const issue = (id, extra = {}) => ({
  id,
  title: 'Matching ' + id,
  simple_id: 'T-' + id,
  issue_number: 1,
  priority: 'high',
  status_id: 'todo',
  parent_issue_id: null,
  ...extra,
});
const remote = (id, local, name = 'Human name ' + local) => ({
  id,
  local_workspace_id: local,
  name,
  project_id: 'project',
  issue_id: 'issue',
});
async function boot(extra = {}) {
  const calls = [];
  const f = {
    workspaceId: 'B',
    navigations: [],
    renders: [],
    remote: [remote('remote-A', 'A')],
    local: { activeWorkspaces: [], archivedWorkspaces: [] },
    getWorkspace: async (id) => record(id),
    getSessions: async (id) => [session(id)],
    createSession: async ({ workspace_id }) => session(workspace_id, 'new'),
    followUp: async (id, body) => {
      calls.push({ id, body });
    },
    calls,
    filterParams: {
      issues: [],
      issueAssignees: [],
      issueTags: [],
      issueRelationships: [],
      issuesById: new Map(),
      doneStatusIds: new Set(),
      showSubIssues: true,
      hideBlocked: false,
    },
    ...extra,
  };
  const errors = [];
  const dom = new JSDOM('<div id="root"></div>', {
    url: 'https://fixture.invalid',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    beforeParse(w) {
      w.fixture = f;
      w.fetch = () => {
        throw Error('No real network permitted');
      };
      w.HTMLElement.prototype.scrollIntoView = () => {};
      w.console.error = (...args) => errors.push(args.join(' '));
    },
  });
  dom.window.eval(result.outputFiles[0].text);
  await wait(() => f.composer && f.cards && f.selection);
  return {
    f,
    dom,
    d: dom.window.document,
    close: () => {
      f.close();
      dom.window.close();
      assert.deepEqual(
        errors.filter(
          (e) => !e.includes('function components cannot be given refs')
        ),
        []
      );
    },
  };
}
// Loading/stale sidebar must never substitute a sibling or guess by human name.
{
  const delayed = deferred();
  const t = await boot({
    getWorkspace: () => delayed.promise,
    local: { activeWorkspaces: [record('A')], archivedWorkspaces: [] },
  });
  try {
    assert.deepEqual(t.f.navigations, []);
    assert.equal(t.f.composer.mode, 'placeholder');
    delayed.resolve(record('B'));
    await wait(() => t.f.composer.session?.id === 'B-session-1');
    assert.equal(
      t.d.querySelector('[aria-label="Open workspace"]').textContent,
      'Human name B'
    );
    assert.equal(
      t.d.querySelector('[data-history-workspace]').dataset.historyWorkspace,
      'B'
    );
    assert.equal(await t.f.composer.sender.send('Synthetic B prompt'), true);
    assert.deepEqual(
      t.f.calls.map((c) => c.id),
      ['B-session-1']
    );
    t.f.local = {
      activeWorkspaces: [{ id: 'foreign', name: 'collision' }],
      archivedWorkspaces: [],
    };
    t.f.remote = [
      remote('unlinked', null, 'collision'),
      remote('linked', 'B', 'same name'),
    ];
    t.f.render();
    await wait(() => t.f.cards.workspaces[0].name === 'collision');
    assert.equal(t.f.cards.workspaces[0].localWorkspaceId, null);
    t.f.cards.onWorkspaceClick(t.f.cards.workspaces[0].localWorkspaceId);
    assert.deepEqual(t.f.navigations, []);
    t.f.cards.onWorkspaceClick(t.f.cards.workspaces[1].localWorkspaceId);
    assert.deepEqual(JSON.parse(JSON.stringify(t.f.navigations)), [
      ['goToProjectIssueWorkspace', 'project', 'issue', 'B'],
    ]);
    t.f.remote = [t.f.remote[1], t.f.remote[0]];
    t.f.render();
    await tick();
    t.f.cards.onWorkspaceClick(t.f.cards.workspaces[0].localWorkspaceId);
    assert.equal(t.f.navigations.at(-1).at(-1), 'B');
  } finally {
    t.close();
  }
}
// Slow A cannot replace B/C's displayed record, selected session or send target.
{
  const slow = deferred();
  const t = await boot({
    workspaceId: 'A',
    getWorkspace: (id) =>
      id === 'A' ? slow.promise : Promise.resolve(record(id)),
  });
  try {
    t.f.workspaceId = 'B';
    t.f.render();
    await wait(() => t.f.composer.session?.workspace_id === 'B');
    const oldSelect = t.f.selection.selectSession;
    t.f.selection.selectSession('B-session-1');
    t.f.workspaceId = 'C';
    t.f.render();
    await wait(() => t.f.composer.session?.workspace_id === 'C');
    slow.resolve(record('A'));
    oldSelect('B-session-late');
    await tick();
    assert.equal(
      t.d.querySelector('[aria-label="Open workspace"]').textContent,
      'Human name C'
    );
    assert.equal(t.f.selection.selectedSessionId, 'C-session-1');
    assert.ok(
      t.f.renders.every(
        (r) => !r.session || r.session.startsWith(r.workspace + '-session-')
      )
    );
    assert.equal(await t.f.composer.sender.send('Synthetic C prompt'), true);
    assert.deepEqual(
      t.f.calls.map((c) => c.id),
      ['C-session-1']
    );
    t.f.workspaceId = 'B';
    t.f.render();
    await wait(() => t.f.selection.selectedSessionId === 'B-session-1');
    oldSelect('B-session-late');
    await tick(); // A -> B -> A must also reject old callback.
    assert.equal(t.f.selection.selectedSessionId, 'B-session-1');
    t.f.setSessions('B', [session('B', '2'), session('B')]);
    await tick();
    assert.equal(
      t.f.selection.selectedSessionId,
      'B-session-1',
      'reorder preserves recipient'
    );
    t.f.selection.selectSession('B-session-2');
    await tick();
    assert.equal(t.f.selection.selectedSessionId, 'B-session-2');
  } finally {
    t.close();
  }
}
// Creation stays pinned to click-time destination; a late result cannot select B in C.
{
  const create = deferred();
  const t = await boot({
    getSessions: async () => [],
    createSession: () => create.promise,
  });
  try {
    await wait(() => t.f.composer.mode === 'new-session');
    const pending = t.f.composer.sender.send('Synthetic creation B');
    await tick();
    t.f.workspaceId = 'C';
    t.f.render();
    await wait(() => t.f.composer.workspaceId === 'C');
    create.resolve(session('B', 'new'));
    assert.equal(await pending, true);
    await tick();
    assert.deepEqual(
      t.f.calls.map((c) => c.id),
      ['B-session-new']
    );
    assert.equal(t.f.selection.selectedSessionId, undefined);
    assert.equal(t.f.composer.workspaceId, 'C');
  } finally {
    t.close();
  }
}
// Wrong API identity fails closed before history/composer/send is made available.
for (const mismatch of ['record', 'list', 'create']) {
  const t = await boot({
    getWorkspace: async (id) => record(mismatch === 'record' ? 'wrong' : id),
    getSessions: async (id) =>
      mismatch === 'list'
        ? [session('wrong')]
        : mismatch === 'create'
          ? []
          : [session(id)],
    createSession: async () => session('wrong'),
  });
  try {
    await tick();
    if (mismatch === 'create') {
      await wait(() => t.f.composer.mode === 'new-session');
      assert.equal(
        await t.f.composer.sender.send('Synthetic rejected prompt'),
        false
      );
    } else {
      assert.equal(t.f.composer.mode, 'placeholder');
      assert.equal(t.f.selection.isNewSessionMode, false);
    }
    assert.deepEqual(t.f.calls, []);
  } finally {
    t.close();
  }
}
// Personal means self OR unassigned. Other filters remain ANDed, with no writes.
{
  const issues = [
    issue('self'),
    issue('none'),
    issue('other'),
    issue('child', { parent_issue_id: 'self' }),
    issue('blocked'),
    issue('low', { priority: 'low' }),
  ];
  const params = {
    issues,
    issueAssignees: [
      { issue_id: 'self', user_id: 'self' },
      { issue_id: 'other', user_id: 'other' },
    ],
    issueTags: issues.map((i) => ({ issue_id: i.id, tag_id: 'tag' })),
    issueRelationships: [
      {
        issue_id: 'other',
        related_issue_id: 'blocked',
        relationship_type: 'blocking',
      },
    ],
    issuesById: new Map(issues.map((i) => [i.id, i])),
    doneStatusIds: new Set(['done']),
    showSubIssues: false,
    hideBlocked: true,
  };
  const t = await boot({ filterParams: params });
  try {
    assert.deepEqual(
      [...t.f.visibleIssues.map((i) => i.id)],
      ['self', 'none', 'low']
    );
    const defaults = t.f.filtersApplied;
    t.f.filters = {
      ...defaults,
      assigneeIds: [defaults.assigneeIds[0]],
      searchQuery: 'Matching',
      priorities: ['high'],
      tagIds: ['tag'],
    };
    t.f.render();
    await tick();
    assert.deepEqual([...t.f.visibleIssues.map((i) => i.id)], ['self', 'none']);
    assert.equal(t.f.filtersApplied.searchQuery, 'Matching');
    t.f.filters = { ...t.f.filters, tagIds: ['absent-tag'] };
    t.f.render();
    await tick();
    assert.deepEqual([...t.f.visibleIssues], []);
    t.f.filters = { ...t.f.filters, tagIds: ['tag'], searchQuery: 'none' };
    t.f.render();
    await tick();
    assert.deepEqual([...t.f.visibleIssues.map((i) => i.id)], ['none']);
    t.f.filters = { ...t.f.filters, searchQuery: 'Matching' };
    assert.deepEqual([...t.f.filtersApplied.tagIds], ['tag']);
    t.f.view = 'team';
    t.f.filters = undefined;
    t.f.render();
    await tick();
    assert.deepEqual(
      [...t.f.visibleIssues.map((i) => i.id)],
      ['self', 'none', 'other', 'low']
    );
    t.f.view = 'personal';
    t.f.filters = { ...defaults, assigneeIds: ['other'] };
    t.f.render();
    await tick();
    assert.deepEqual([...t.f.visibleIssues.map((i) => i.id)], ['other']);
    assert.deepEqual(t.f.calls, []);
  } finally {
    t.close();
  }
}
console.log(
  'PASS destination: loading/stale siblings, explicit links, reorder, rapid/ABA navigation, late creation, API identity guards and Personal self-or-unassigned with other filters'
);
