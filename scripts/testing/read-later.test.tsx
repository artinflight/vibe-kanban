import assert from 'node:assert/strict';
import { test, before } from 'node:test';
import { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import i18next from 'i18next';
import { I18nextProvider } from 'react-i18next';
import common from '../../packages/web-core/src/i18n/locales/en/common.json';
import {
  WorkspacesSidebar,
  type WorkspacesSidebarWorkspace,
} from '../../packages/ui/src/components/WorkspacesSidebar';
import { workspaceSidebarSections } from '../../packages/ui/src/lib/workspaceSidebarSections';
import { paginateWorkspaceSidebar } from '../../packages/web-core/src/pages/workspaces/workspaceSidebarPagination';
import {
  useReadLaterStore,
  readLaterKey,
} from '../../packages/web-core/src/shared/stores/useReadLaterStore';
import { useReadLater } from '../../packages/web-core/src/shared/hooks/useReadLater';
import { IssueReadLaterAction } from '../../packages/web-core/src/shared/components/IssueReadLaterAction';
import { NotificationsPage } from '../../packages/web-core/src/pages/workspaces/NotificationsPage';
import type { GroupedNotification } from '../../packages/web-core/src/shared/lib/notifications';
import { setNotifications, navigations, writes } from './read-later.fixture';

before(async () => {
  await i18next.init({ lng: 'en', resources: { en: { common } } });
});
const click = async (element: Element | null) => {
  assert.ok(element);
  await act(async () => {
    element.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  });
};
async function mount(element: React.ReactNode) {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  await act(async () =>
    root.render(<I18nextProvider i18n={i18next}>{element}</I18nextProvider>)
  );
  return {
    host,
    close: async () => {
      await act(async () => root.unmount());
      host.remove();
    },
  };
}
const reset = () => {
  localStorage.clear();
  useReadLaterStore.setState({
    items: {},
    pending: {},
    migratedScopes: {},
    syncErrors: {},
  });
};
const scope = JSON.stringify(['local', 'owner']);

test('preference persists, restores independently and isolates host/user/kind', async () => {
  reset();
  const { setReadLater } = useReadLaterStore.getState();
  setReadLater(scope, { kind: 'workspace', id: 'one' }, true);
  setReadLater('other-host', { kind: 'workspace', id: 'one' }, true);
  setReadLater(scope, { kind: 'project', id: 'one' }, true);
  const saved = localStorage.getItem('vk-read-later-v1');
  assert.ok(saved);
  useReadLaterStore.setState({
    items: {},
    pending: {},
    migratedScopes: {},
    syncErrors: {},
  });
  localStorage.setItem('vk-read-later-v1', saved);
  await useReadLaterStore.persist.rehydrate();
  assert.equal(Object.keys(useReadLaterStore.getState().items).length, 3);
  setReadLater(scope, { kind: 'workspace', id: 'one' }, false);
  assert.equal(
    useReadLaterStore.getState().items[readLaterKey(scope, 'workspace', 'one')],
    undefined
  );
  assert.ok(
    useReadLaterStore.getState().items[
      readLaterKey('other-host', 'workspace', 'one')
    ]
  );
  assert.ok(
    useReadLaterStore.getState().items[readLaterKey(scope, 'project', 'one')]
  );
});

test('grouping preserves unread and running activity beyond the first page', () => {
  const rows = Array.from(
    { length: 55 },
    (_, i) => ({ id: String(i) }) as WorkspacesSidebarWorkspace
  );
  rows.push({
    id: 'later',
    name: 'Deferred',
    readLater: true,
    hasUnseenActivity: true,
  });
  rows.push({ id: 'running', name: 'Running', isRunning: true });
  rows.push({
    id: 'approval',
    name: 'Approval',
    hasPendingApproval: true,
    isRunning: true,
  });
  rows.push({ id: 'subagent', name: 'Subagent', activeSubagentCount: 1 });
  rows.push({
    id: 'read',
    name: 'Read',
    readLater: true,
    hasUnseenActivity: false,
  });
  const before = JSON.stringify(rows);
  const groups = workspaceSidebarSections(
    paginateWorkspaceSidebar(rows, 50, false, true)
  );
  assert.deepEqual(
    groups.readLaterWorkspaces.map((row) => row.id),
    ['later', 'read']
  );
  assert.ok(groups.runningWorkspaces.some((row) => row.id === 'running'));
  assert.ok(groups.runningWorkspaces.some((row) => row.id === 'subagent'));
  assert.ok(groups.raisedHandWorkspaces.some((row) => row.id === 'approval'));
  assert.equal(JSON.stringify(rows), before);
  assert.ok(!groups.idleWorkspaces.some((row) => row.id === 'read'));
  assert.ok(
    paginateWorkspaceSidebar(rows, 50, false, false).some(
      (row) => row.id === 'read'
    )
  );
});

for (const phone of [false, true])
  for (const layoutMode of ['accordion', 'flat'] as const) {
    test(`sidebar defer/restore preserves unread without navigation (${phone ? 'phone' : 'desktop'}, ${layoutMode})`, async () => {
      reset();
      window.matchMedia = (() => ({
        matches: phone,
        addEventListener() {},
        removeEventListener() {},
      })) as typeof window.matchMedia;
      let selections = 0;
      let menus = 0;
      const source = [
        {
          id: 'done',
          name: 'Old completed work',
          latestProcessStatus: 'completed' as const,
        },
        {
          id: 'unread',
          name: 'Unread issue workspace',
          hasUnseenActivity: true,
          dotUnreadCount: 3,
        },
        { id: 'running', name: 'Active work', isRunning: true },
      ];
      function Sidebar() {
        const { isReadLater, setReadLater } = useReadLater();
        const rows = source.map((row) => ({
          ...row,
          readLater: isReadLater('workspace', row.id),
        }));
        return (
          <WorkspacesSidebar
            layoutMode={layoutMode}
            workspaces={rows}
            activityWorkspaces={rows}
            totalWorkspacesCount={rows.length}
            selectedWorkspaceId={null}
            onSelectWorkspace={() => selections++}
            onOpenWorkspaceActions={() => menus++}
            searchQuery=""
            onSearchChange={() => {}}
            onToggleWorkspaceReadLater={(id) =>
              setReadLater(
                { kind: 'workspace', id },
                !isReadLater('workspace', id)
              )
            }
            projectDotNotices={[
              {
                projectId: 'p',
                name: 'Project notice',
                unreadCount: 2,
                readLater: isReadLater('project', 'p'),
              },
            ]}
            onOpenProjectChat={() => selections++}
            onToggleProjectReadLater={(id) =>
              setReadLater({ kind: 'project', id }, !isReadLater('project', id))
            }
          />
        );
      }
      const { host, close } = await mount(<Sidebar />);
      try {
        assert.equal(host.querySelectorAll('button button').length, 0);
        await click(
          host.querySelector(
            '.mobile-workspace-card [data-workspace-status-row] button[aria-label="More actions"], .phone-row-more'
          )
        );
        assert.equal(menus, 1);
        assert.equal(selections, 0);
        assert.ok(host.querySelector('[data-workspace-section="running"]'));
        // Deferred work starts folded so it cannot push running work down.
        assert.equal(
          host.querySelector('[data-workspace-section="later"]'),
          null
        );
        await click(
          [...host.querySelectorAll('button[aria-expanded]')].find((button) =>
            button.textContent?.startsWith('Read Later')
          ) ?? null
        );
        assert.deepEqual(
          [...host.querySelectorAll('[data-workspace-section]')].map((node) =>
            node.getAttribute('data-workspace-section')
          ),
          ['attention', 'later', 'running', 'ready']
        );
        await click(
          host.querySelector(
            '[data-workspace-section="attention"] [aria-label="Read Later"]'
          )
        );
        assert.match(
          host.querySelector('[data-workspace-section="later"]')!.textContent!,
          /Project notice/
        );
        assert.match(
          host.querySelector('[data-workspace-section="later"]')!.textContent!,
          /2 unread/
        );
        await click(
          host.querySelector(
            '[data-workspace-section="attention"] [aria-label="Read Later"]'
          )
        );
        assert.match(
          host.querySelector('[data-workspace-section="later"]')!.textContent!,
          /Unread issue workspace/
        );
        assert.match(
          host.querySelector('[data-workspace-section="later"]')!.textContent!,
          /3/
        );
        assert.doesNotMatch(
          host.querySelector('[data-workspace-section="attention"]')!
            .textContent!,
          /Unread issue workspace/
        );
        assert.equal(selections, 0);
        assert.equal(source[1].hasUnseenActivity, true);
        assert.equal(source[1].dotUnreadCount, 3);
        await click(
          host.querySelector(
            '[data-workspace-section="later"] [aria-label="Remove from Read Later"]'
          )
        );
        assert.match(
          host.querySelector('[data-workspace-section="attention"]')!
            .textContent!,
          /Project notice/
        );
        assert.equal(selections, 0);
      } finally {
        await close();
      }
    });
  }

for (const phone of [false, true])
  for (const layoutMode of ['accordion', 'flat'] as const) {
    test(`read workspaces can be saved and stay saved after reading (${phone ? 'phone' : 'desktop'}, ${layoutMode})`, async () => {
      reset();
      window.matchMedia = (() => ({
        matches: phone,
        addEventListener() {},
        removeEventListener() {},
      })) as typeof window.matchMedia;
      let selections = 0;
      const read = {
        id: 'read',
        name: 'Already read workspace',
        hasUnseenActivity: false,
        dotUnreadCount: 0,
      };
      const unread = {
        id: 'unread',
        name: 'Unread workspace',
        hasUnseenActivity: true,
        dotUnreadCount: 2,
      };
      let markRead = () => {};
      function Sidebar() {
        const { isReadLater, setReadLater } = useReadLater();
        const [hasUnread, setUnread] = useState(true);
        markRead = () => setUnread(false);
        const rows = [
          read,
          {
            ...unread,
            hasUnseenActivity: hasUnread,
            dotUnreadCount: hasUnread ? 2 : 0,
          },
        ].map((row) => ({
          ...row,
          readLater: isReadLater('workspace', row.id),
        }));
        return (
          <WorkspacesSidebar
            layoutMode={layoutMode}
            workspaces={rows}
            activityWorkspaces={rows}
            totalWorkspacesCount={rows.length}
            selectedWorkspaceId={null}
            onSelectWorkspace={() => selections++}
            searchQuery=""
            onSearchChange={() => {}}
            onToggleWorkspaceReadLater={(id) =>
              setReadLater(
                { kind: 'workspace', id },
                !isReadLater('workspace', id)
              )
            }
          />
        );
      }
      const { host, close } = await mount(<Sidebar />);
      try {
        await click(
          host.querySelector(
            '[data-workspace-section="ready"] [aria-label="Read Later"]'
          )
        );
        await click(
          [...host.querySelectorAll('button[aria-expanded]')].find((button) =>
            button.textContent?.startsWith('Read Later')
          ) ?? null
        );
        const later = () =>
          host.querySelector('[data-workspace-section="later"]')!;
        assert.match(later().textContent!, /Already read workspace/);
        assert.equal(read.hasUnseenActivity, false);
        assert.equal(read.dotUnreadCount, 0);
        await click(
          host.querySelector(
            '[data-workspace-section="attention"] [aria-label="Read Later"]'
          )
        );
        await act(async () => markRead());
        assert.match(later().textContent!, /Unread workspace/);
        assert.equal(
          later().querySelectorAll('[aria-label="Remove from Read Later"]')
            .length,
          2
        );
        await act(async () => useReadLaterStore.persist.rehydrate());
        assert.match(later().textContent!, /Already read workspace/);
        assert.match(later().textContent!, /Unread workspace/);
        await click(
          later().querySelector('[aria-label="Remove from Read Later"]')
        );
        assert.match(
          host.querySelector('[data-workspace-section="ready"]')!.textContent!,
          /Already read workspace/
        );
        assert.equal(selections, 0);
      } finally {
        await close();
      }
    });
  }

test('issue action is reversible and does not open/read its parent', async () => {
  reset();
  let opened = 0;
  const { host, close } = await mount(
    <div role="button" onClick={() => opened++} onKeyDown={() => opened++}>
      <IssueReadLaterAction
        issueId="i"
        projectId="p"
        title="Unread issue"
        unread
      />
    </div>
  );
  try {
    const button = host.querySelector('button')!;
    await act(async () => {
      button.dispatchEvent(
        new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
      );
    });
    assert.equal(opened, 0);
    await click(button);
    assert.ok(
      useReadLaterStore.getState().items[readLaterKey(scope, 'issue', 'i')]
    );
    assert.equal(opened, 0);
    await click(host.querySelector('[aria-label="Remove from Read Later"]'));
    assert.equal(
      useReadLaterStore.getState().items[readLaterKey(scope, 'issue', 'i')],
      undefined
    );
  } finally {
    await close();
  }
});

const notification = (seen = false): GroupedNotification => ({
  id: 'group',
  kind: 'single',
  seen,
  deeplinkPath: '/projects/p/issues/i',
  notificationCount: 1,
  unseenNotificationIds: seen ? [] : ['n'],
  issueChangeCount: 0,
  latest: {
    id: 'n',
    seen,
    created_at: new Date().toISOString(),
    notification_type: 'issue_comment_added',
    payload: { issue_simple_id: 'T1' },
  } as GroupedNotification['latest'],
});

test('notification moves to later unread, restores, and completed read items sink to bottom', async () => {
  reset();
  const original = notification();
  setNotifications([original]);
  const { host, close } = await mount(<NotificationsPage />);
  try {
    await click(
      host.querySelector('[aria-label="Attention"] [aria-label="Read Later"]')
    );
    assert.ok(
      host.querySelector(
        '[aria-label="Read Later"] [aria-label="Remove from Read Later"]'
      )
    );
    assert.equal(writes.length, 0);
    assert.equal(navigations.length, 0);
    assert.equal(original.seen, false);
    await act(async () => {
      host
        .querySelector('[aria-label="Remove from Read Later"]')!
        .dispatchEvent(
          new window.KeyboardEvent('keydown', { key: ' ', bubbles: true })
        );
    });
    assert.equal(writes.length, 0);
    assert.equal(navigations.length, 0);
    await click(host.querySelector('[aria-label="Remove from Read Later"]'));
    assert.ok(
      host.querySelector('[aria-label="Attention"] [aria-label="Read Later"]')
    );
    await click(
      host.querySelector('[aria-label="Attention"] [aria-label="Read Later"]')
    );
    await act(async () => setNotifications([notification(true)]));
    assert.equal(
      host.querySelector('[aria-label="Read Later"] [role="button"]'),
      null
    );
    assert.ok(host.querySelector('[aria-label="Completed"] [role="button"]'));
  } finally {
    await close();
  }
});

test('new unread notifications in a regrouped thread return it to attention', async () => {
  reset();
  useReadLaterStore
    .getState()
    .setReadLater(scope, { kind: 'notification', id: 'n' }, true);
  setNotifications([
    { ...notification(), unseenNotificationIds: ['new', 'n'] },
  ]);
  const { host, close } = await mount(<NotificationsPage />);
  try {
    assert.ok(host.querySelector('[aria-label="Attention"] [role="button"]'));
  } finally {
    await close();
  }
});

test('scoped hook never exposes another host or user entry with the same ID', async () => {
  reset();
  const set = useReadLaterStore.getState().setReadLater;
  set(
    'other-host-and-user',
    { kind: 'issue', id: 'i', name: 'Other title' },
    true
  );
  set(scope, { kind: 'issue', id: 'i', name: 'Current title' }, true);
  function ScopeProbe() {
    const { items } = useReadLater();
    return (
      <output>
        {Object.values(items)
          .map((item) => item.name)
          .join(',')}
      </output>
    );
  }
  const { host, close } = await mount(<ScopeProbe />);
  try {
    assert.equal(host.textContent, 'Current title');
  } finally {
    await close();
  }
});

test('storage denial keeps the reversible preference usable in memory', () => {
  reset();
  const prototype = Object.getPrototypeOf(localStorage);
  const original = prototype.setItem;
  prototype.setItem = () => {
    throw new Error('Storage unavailable');
  };
  try {
    const set = useReadLaterStore.getState().setReadLater;
    assert.doesNotThrow(() => set(scope, { kind: 'workspace', id: 'w' }, true));
    assert.ok(
      useReadLaterStore.getState().items[readLaterKey(scope, 'workspace', 'w')]
    );
    assert.doesNotThrow(() =>
      set(scope, { kind: 'workspace', id: 'w' }, false)
    );
    assert.equal(
      useReadLaterStore.getState().items[readLaterKey(scope, 'workspace', 'w')],
      undefined
    );
  } finally {
    prototype.setItem = original;
  }
});
