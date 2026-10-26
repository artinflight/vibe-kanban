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
