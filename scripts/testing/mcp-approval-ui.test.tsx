import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { act } from 'react';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionChatBox } from '../../packages/ui/src/components/SessionChatBox';
import { McpConsentCards } from '../../packages/web-core/src/features/workspace-chat/ui/McpConsentCards';
import { useApprovals } from '../../packages/web-core/src/shared/hooks/useApprovals';
import { calls } from './mcp-approval-ui-api';
import { publish, sockets } from './mcp-approval-stream';

for (const phoneLayout of [false, true]) {
  test(`mounted composer consent lifecycle races (${phoneLayout ? 'phone' : 'desktop'})`, async () => {
    calls.length = 0;
    sockets.length = 0;
    await i18next
      .use(initReactI18next)
      .init({ lng: 'en', resources: { en: { translation: {} } } });
    const dom = new JSDOM('<div id="root"></div>', {
      url: 'http://fixture.invalid',
    });
    dom.window.matchMedia = (query) =>
      Object.assign(new dom.window.EventTarget(), {
        media: query,
        matches: phoneLayout && query === '(max-width: 767px)',
        onchange: null,
        addListener() {},
        removeListener() {},
      }) as unknown as MediaQueryList;
    Object.assign(globalThis, {
      window: dom.window,
      document: dom.window.document,
      HTMLElement: dom.window.HTMLElement,
      IS_REACT_ACT_ENVIRONMENT: true,
    });
    const execution = '00000000-0000-4000-8000-000000000001';
    const info = (
      id: string,
      context:
        | string
        | null = `Tool: run_session_prompt\nConnector: Synthetic VK\nTarget: synthetic-${id}\nApprove this call only.`
    ) => ({
      approval_id: id,
      execution_process_id: execution,
      tool_name: 'codex.mcp_approval',
      is_question: false,
      mcp_consent: context,
      created_at: '2026-10-08T00:00:00Z',
      timeout_at: '2099-10-08T00:00:00Z',
    });
    const noop = () => {};
    let implicit: unknown;
    function Composer() {
      const approvals = useApprovals();
      implicit = approvals.getPendingForProcess(execution);
      return (
        <SessionChatBox
          status="running"
          editor={{ value: '', onChange: noop }}
          renderEditor={({ onCmdEnter }) => (
            <textarea
              aria-label="composer"
              onKeyDown={(e) => {
                if (e.key === 'Enter') onCmdEnter();
              }}
            />
          )}
          actions={{
            onSend: noop,
            onSendFollowUp: noop,
            onStop: noop,
            onCancelQueue: noop,
            onPasteFiles: noop,
          }}
          session={{ sessions: [], onSelectSession: noop }}
          consentCards={
            <McpConsentCards
              approvals={approvals.pendingApprovals}
              executionProcessIds={[execution]}
              isConnected={approvals.isConnected}
            />
          }
        />
      );
    }
    const queryClient = new QueryClient({
      defaultOptions: { queries: { gcTime: 0 }, mutations: { gcTime: 0 } },
    });
    const host = document.getElementById('root')!;
    const root = createRoot(host);
    async function snapshot(
      items: ReturnType<typeof info>[],
      connected = true
    ) {
      await act(async () =>
        publish(
          Object.fromEntries(items.map((item) => [item.approval_id, item])),
          connected
        )
      );
    }
    const card = (id: string) =>
      host.querySelector(`[data-approval-id="${id}"]`)!;
    const button = (id: string, approve = true) =>
      Array.from(card(id).querySelectorAll('button')).find(
        (b) =>
          b.textContent ===
          (approve ? 'Approve this call only' : 'Decline this call')
      )!;
    async function click(id: string, approve = true) {
      await act(async () => button(id, approve).click());
    }
    await act(async () =>
      root.render(
        <QueryClientProvider client={queryClient}>
          <Composer />
        </QueryClientProvider>
      )
    );
    assert.equal(
      Boolean(host.querySelector('.phone-prompt-actions')),
      phoneLayout,
      'the real presentation hook selects the requested layout'
    );
    await act(async () => sockets.at(-1)!.open());
    await snapshot([info('A'), info('B')]);
    assert.equal(
      implicit,
      null,
      'MCP requests cannot enter the generic composer selection'
    );
    assert.match(card('A').textContent!, /synthetic-A/);
    assert.match(card('B').textContent!, /synthetic-B/);
    assert.equal(calls.length, 0, 'mounting never implies approval');
    await snapshot([info('B'), info('A')]);
    await click('B');
    await click('B');
    assert.equal(calls.length, 1, 'one explicit action per card');
    assert.equal(calls[0].id, 'B');
    await click('A', false);
    assert.equal(calls[1].id, 'A');
    assert.deepEqual(
      calls.map((c) => c.response),
      [
        { execution_process_id: execution, status: { status: 'approved' } },
        {
          execution_process_id: execution,
          status: { status: 'denied', reason: 'User denied this request.' },
        },
      ]
    );
    writeFileSync(
      resolve(process.env.VK_TEST_OUTPUT!, 'mcp-ui-responses.json'),
      JSON.stringify(calls.map((c) => c.response))
    );
    await snapshot([info('C')]);
    const disconnectedButton = button('C');
    dom.window.setTimeout = ((fn: () => void) =>
      setTimeout(fn, 1)) as typeof dom.window.setTimeout;
    await act(async () => sockets.at(-1)!.close());
    await act(async () => disconnectedButton.click());
    assert.equal(calls.length, 2, 'disconnect disables cached pending consent');
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    await act(async () => sockets.at(-1)!.open());
    assert.equal(
      host.querySelector('[data-approval-id="C"]'),
      null,
      'old context cleared before reconnect Ready'
    );
    await snapshot([info('D')], false);
    await click('D');
    assert.equal(calls.length, 2, 'connected without Ready cannot consent');
    await snapshot([info('D')]);
    assert.equal(
      host.querySelector('[data-approval-id="C"]'),
      null,
      'reconnect replaces stale request'
    );
    await click('D');
    assert.equal(calls.at(-1)!.id, 'D');
    await snapshot([info('E', null)]);
    await click('E');
    assert.equal(calls.length, 3, 'delayed/missing context cannot be approved');
    await snapshot([
      info(
        'E',
        'Tool: run_session_prompt\nTarget: synthetic-E <script>window.bad=true</script>'
      ),
    ]);
    assert.equal(
      card('E').querySelector('script'),
      null,
      'consent is literal text'
    );
    await click('E');
    assert.equal(calls.at(-1)!.id, 'E');
    await snapshot([info('F')]);
    const staleButton = button('F');
    await snapshot([]);
    await act(async () => staleButton.click());
    assert.equal(calls.length, 4, 'cancelled cards cannot submit');
    const completeLongPrompt =
      'Full Visily-only task\n' +
      '🧭'.repeat(59_900) +
      '\n<script>unsafe()</script>\nNo Figma until per-view signoff.\nEND-OF-PROMPT';
    await snapshot([info('LONG', completeLongPrompt)]);
    const region = card('LONG').querySelector('[role="region"]')!;
    assert.equal(
      region.getAttribute('aria-label'),
      'Complete tool action and parameters'
    );
    assert.equal(region.getAttribute('tabindex'), '0');
    assert.match(region.className, /overflow-auto/);
    assert.equal(region.querySelector('pre')!.textContent, completeLongPrompt);
    assert.equal(region.querySelector('script'), null);
    assert.equal(region.querySelector('a'), null);
    assert.equal(calls.length, 4, 'full long rendering never grants consent');
    await click('LONG');
    assert.equal(
      calls.at(-1)!.id,
      'LONG',
      'long content keeps exact request binding'
    );
    await snapshot([{ ...info('G'), timeout_at: '2000-01-01T00:00:00Z' }]);
    await click('G');
    assert.equal(calls.length, 5, 'expired consent cannot submit');
    await snapshot([
      { ...info('H'), execution_process_id: 'different-execution' },
    ]);
    assert.equal(host.querySelector('[data-approval-id="H"]'), null);
    await act(async () => root.unmount());
    queryClient.clear();
    dom.window.close();
  });
}
