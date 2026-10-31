import assert from 'node:assert/strict';
import { test } from 'node:test';
import { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import i18next from 'i18next';
import { I18nextProvider } from 'react-i18next';
import common from '../../packages/web-core/src/i18n/locales/en/common.json';
import { KanbanCardContent } from '../../packages/ui/src/components/KanbanCardContent';
import {
  KanbanCard,
  KanbanCards,
  KanbanProvider,
} from '../../packages/ui/src/components/KanbanBoard';

await i18next.init({ lng: 'en', resources: { en: { common } } });

for (const isMobile of [false, true]) {
  test(`collapse, restore and navigation (${isMobile ? 'phone' : 'desktop'})`, async () => {
    let opens = 0;
    let drags = 0;
    function Board() {
      const [expanded, setExpanded] = useState<Record<string, boolean>>({});
      return (
        <I18nextProvider i18n={i18next}>
          <KanbanProvider onDragEnd={() => drags++}>
            <KanbanCards id="todo">
              {['one', 'two'].map((id, index) => (
                <KanbanCard
                  key={id}
                  id={id}
                  name={id}
                  index={index}
                  isMobile={isMobile}
                  onClick={() => opens++}
                >
                  <KanbanCardContent
                    displayId={id}
                    title={`Issue ${id}`}
                    primaryContent={<button>Workspace {id}</button>}
                    priority="high"
                    tags={[]}
                    assignees={[]}
                    pullRequests={[
                      {
                        id,
                        number: 42,
                        url: 'https://example.invalid/pr',
                        status: 'open',
                      },
                    ]}
                    relationships={[
                      {
                        relationshipId: id,
                        displayType: 'blocks',
                        relatedIssueDisplayId: 'T9',
                      },
                    ]}
                    isMobile={isMobile}
                    isExpanded={expanded[id] ?? true}
                    onToggleExpanded={() =>
                      setExpanded((values) => ({
                        ...values,
                        [id]: !(values[id] ?? true),
                      }))
                    }
                  />
                </KanbanCard>
              ))}
            </KanbanCards>
          </KanbanProvider>
        </I18nextProvider>
      );
    }
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const click = async (element: Element) => {
      await act(async () => {
        for (const type of ['mousedown', 'mouseup', 'click']) {
          element.dispatchEvent(
            new window.MouseEvent(type, { bubbles: true, button: 0 })
          );
        }
      });
    };
    try {
      await act(async () => root.render(<Board />));
      const card = host.querySelector<HTMLElement>(
        '[data-rfd-draggable-id="one"]'
      )!;
      const toggle = card.querySelector<HTMLButtonElement>(
        'button[aria-expanded]'
      )!;
      assert.equal(toggle.getAttribute('aria-expanded'), 'true');
      assert.ok(card.textContent?.includes('Workspace one'));
      assert.ok(!card.textContent?.includes('Issue one'));
      await click(toggle);
      assert.equal(toggle.getAttribute('aria-expanded'), 'false');
      assert.equal(toggle.getAttribute('aria-label'), 'Expand issue one');
      assert.ok(card.textContent?.includes('Issue one'));
      assert.ok(!card.textContent?.includes('Workspace one'));
      assert.ok(!card.textContent?.includes('#42'));
      assert.ok(!card.textContent?.includes('T9'));
      assert.ok(host.textContent?.includes('Workspace two'));
      assert.equal(opens, 0, 'toggle must not navigate');
      assert.equal(drags, 0, 'toggle must not drag');
      await click(toggle);
      assert.ok(card.textContent?.includes('Workspace one'));
      assert.ok(!card.textContent?.includes('Issue one'));
      assert.ok(card.textContent?.includes('#42'));
      assert.ok(card.textContent?.includes('T9'));
      await click(card);
      assert.equal(opens, 1, 'card surface still opens the issue');
    } finally {
      await act(async () => root.unmount());
      host.remove();
    }
  });
}

test('issues without workspaces retain the title in both states', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  try {
    for (const isExpanded of [true, false]) {
      await act(async () =>
        root.render(
          <I18nextProvider i18n={i18next}>
            <KanbanCardContent
              displayId="T1"
              title="No workspace yet"
              priority={null}
              tags={[]}
              assignees={[]}
              description="Details"
              isExpanded={isExpanded}
              onToggleExpanded={() => {}}
            />
          </I18nextProvider>
        )
      );
      assert.ok(host.textContent?.includes('No workspace yet'));
      assert.equal(host.querySelectorAll('button').length, isExpanded ? 2 : 1);
    }
  } finally {
    await act(async () => root.unmount());
  }
});

test('manual review flag is clearable without navigation or read side effects', async () => {
  const { IssueReviewFlagButton } = await import(
    '../../packages/ui/src/components/IssueReviewFlagButton'
  );
  let opens = 0;
  let drags = 0;
  let toggles = 0;
  function Host() {
    const [flagged, setFlagged] = useState(true);
    return (
      <div onClick={() => opens++} onMouseDown={() => drags++}>
        <IssueReviewFlagButton
          flagged={flagged}
          displayId="VK-1"
          showLabel
          onToggle={() => {
            toggles++;
            setFlagged((value) => !value);
          }}
        />
      </div>
    );
  }
  const host = document.createElement('div');
  const root = createRoot(host);
  try {
    await act(async () => root.render(<Host />));
    const button = host.querySelector('button')!;
    assert.equal(
      button.getAttribute('aria-label'),
      'Clear review flag for VK-1'
    );
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.match(button.textContent!, /Flagged for review/);
    assert.doesNotMatch(button.textContent!, /Needs review/);
    await act(async () => {
      button.dispatchEvent(
        new window.MouseEvent('mousedown', { bubbles: true })
      );
      button.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });
    assert.equal(toggles, 1);
    assert.equal(opens, 0, 'clearing a flag must not open the issue or chat');
    assert.equal(drags, 0, 'clearing a flag must not start a drag');
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.getAttribute('aria-label'), 'Add review flag for VK-1');
  } finally {
    await act(async () => root.unmount());
  }
});

test('issue unread labels track workspace replies independently from manual flags', async () => {
  const { getWorkspacesAttentionLabel } = await import(
    '../../packages/ui/src/lib/workspaceAttention'
  );
  const readWorkspace = {
    hasUnseenActivity: false,
    isRunning: false,
    latestProcessStatus: 'completed',
    needsReviewFlag: true,
  };
  assert.equal(getWorkspacesAttentionLabel([readWorkspace]), undefined);
  assert.equal(getWorkspacesAttentionLabel([]), undefined);
  assert.equal(getWorkspacesAttentionLabel([undefined]), undefined);
  const unread = { ...readWorkspace, hasUnseenActivity: true };
  assert.equal(getWorkspacesAttentionLabel([unread]), 'Needs review');
  assert.equal(
    getWorkspacesAttentionLabel([readWorkspace, unread]),
    'Needs review',
    'an unread sibling remains actionable'
  );
  assert.equal(
    getWorkspacesAttentionLabel([{ ...unread, isRunning: true }]),
    undefined
  );
  assert.equal(
    getWorkspacesAttentionLabel([{ ...unread, latestProcessStatus: 'failed' }]),
    undefined
  );
  assert.equal(
    getWorkspacesAttentionLabel([unread, { hasPendingApproval: true }]),
    'Needs approval'
  );
});

for (const isMobile of [false, true]) {
  test(`nested workspace click never opens the parent issue (${isMobile ? 'phone' : 'desktop'})`, async () => {
    const { IssueWorkspaceCard } = await import(
      '../../packages/ui/src/components/IssueWorkspaceCard'
    );
    let issueOpens = 0;
    let workspaceOpens = 0;
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const click = async (element: Element) => {
      await act(async () => {
        for (const type of ['mousedown', 'mouseup', 'click']) {
          element.dispatchEvent(
            new window.MouseEvent(type, { bubbles: true, button: 0 })
          );
        }
      });
    };
    try {
      await act(async () =>
        root.render(
          <I18nextProvider i18n={i18next}>
            <KanbanProvider onDragEnd={() => {}}>
              <KanbanCards id="todo">
                <KanbanCard
                  id="issue"
                  name="Issue"
                  index={0}
                  isMobile={isMobile}
                  onClick={() => issueOpens++}
                >
                  <IssueWorkspaceCard
                    workspace={{
                      id: 'workspace',
                      localWorkspaceId: 'workspace',
                      name: 'Workspace',
                      archived: false,
                      filesChanged: 0,
                      linesAdded: 0,
                      linesRemoved: 0,
                      prs: [],
                      owner: null,
                      updatedAt: new Date().toISOString(),
                    }}
                    onClick={() => workspaceOpens++}
                  />
                </KanbanCard>
              </KanbanCards>
            </KanbanProvider>
          </I18nextProvider>
        )
      );
      const parent = host.querySelector('[data-rfd-draggable-id="issue"]')!;
      const workspace = parent.querySelector('[role="button"]')!;
      await click(workspace.querySelector('span.text-high')!);
      assert.equal(workspaceOpens, 1);
      assert.equal(
        issueOpens,
        0,
        'mouse-up must not open the parent before the workspace click'
      );
      await click(parent);
      assert.equal(
        issueOpens,
        1,
        'the issue card background remains actionable'
      );
    } finally {
      await act(async () => root.unmount());
      host.remove();
    }
  });
}
