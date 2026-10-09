// Fully synthetic HTTP/WebSocket fixtures; no production requests or inference.
// VK_EXPECT_BUG=1 replays the immutable pre-fix assets with a simulated keyboard.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const output = process.env.VK_TEST_OUTPUT;
const base = process.env.VK_TEST_BASE;
const dist = process.env.VK_TEST_DIST;
if (
  !output ||
  (!base && !dist) ||
  !process.env.PLAYWRIGHT_MODULE ||
  !process.env.CHROMIUM_PATH
)
  throw new Error(
    'Set VK_TEST_OUTPUT on mounted SSD, PLAYWRIGHT_MODULE, CHROMIUM_PATH, and VK_TEST_BASE (preview) or VK_TEST_DIST (immutable build)'
  );
const origin = base ?? 'http://fixture.invalid';
const wid = '00000000-0000-4000-8000-000000000010',
  sid = '00000000-0000-4000-8000-000000000020';
const ws = {
  id: wid,
  name: 'Isolated Send test',
  branch: 'fixture',
  task_id: null,
  container_ref: null,
  setup_completed_at: null,
  created_at: '2026-10-09T00:00:00Z',
  updated_at: '2026-10-09T00:00:00Z',
  archived: false,
  pinned: false,
  worktree_deleted: false,
  is_running: false,
};
const session = {
  id: sid,
  workspace_id: wid,
  name: 'Fixture session',
  executor: 'CODEX',
  agent_working_dir: null,
  created_at: ws.created_at,
  updated_at: ws.updated_at,
};
const info = {
  version: '0.1.42',
  machine_id: 'isolated',
  login_status: { status: 'logged_out' },
  remote_auth_degraded: null,
  environment: {
    os_type: 'linux',
    os_version: 'test',
    os_architecture: 'x86_64',
    bitness: '64',
  },
  capabilities: { CODEX: [] },
  shared_api_base: null,
  preview_proxy_port: null,
  executors: { CODEX: { DEFAULT: { CODEX: {} } } },
  config: {
    config_version: 'v8',
    theme: 'LIGHT',
    executor_profile: { executor: 'CODEX', variant: 'DEFAULT' },
    disclaimer_acknowledged: true,
    onboarding_acknowledged: true,
    remote_onboarding_acknowledged: true,
    notifications: {
      sound_enabled: false,
      push_enabled: false,
      sound_file: 'ABSTRACT_SOUND1',
    },
    editor: { editor_type: 'VS_CODE' },
    github: {},
    analytics_enabled: false,
    workspace_dir: null,
    last_app_version: '0.1.42',
    show_release_notes: false,
    language: 'EN',
    git_branch_prefix: 'vk',
    showcases: { seen_features: ['workspaces-guide'] },
    send_message_shortcut: 'ModifierEnter',
    relay_enabled: false,
  },
};
const { chromium: testChromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await testChromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
});
const results = [];
try {
  for (const width of JSON.parse(
    process.env.VK_TEST_WIDTHS ??
      (process.env.VK_EXPECT_BUG === '1' ? '[390,412]' : '[390,412,1440]')
  )) {
    for (const mode of JSON.parse(
      process.env.VK_TEST_MODES ?? '["existing","new","running"]'
    )) {
      console.log('START', width, mode);
      const mobile = width < 768;
      const context = await browser.newContext({
        viewport: { width, height: 844 },
        isMobile: mobile,
        hasTouch: mobile,
        ...(mobile && {
          userAgent:
            'Mozilla/5.0 (Linux; Android 15; SM-S936W) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        }),
      });
      const writes = [],
        unknown = new Set();
      let failNext = false;
      let created = false;
      const proc = {
        id: '00000000-0000-4000-8000-000000000030',
        session_id: sid,
        run_reason: 'codingagent',
        status: 'running',
        dropped: false,
        created_at: ws.created_at,
        updated_at: ws.updated_at,
        started_at: ws.created_at,
        completed_at: null,
        exit_code: null,
        executor_action: {
          typ: {
            type: 'CodingAgentInitialRequest',
            prompt: 'Fixture agent message',
            executor_config: { executor: 'CODEX', variant: null },
          },
          next_action: null,
        },
      };
      const submissions = () =>
        writes.filter(
          (w) =>
            w.path.endsWith('/follow-up') ||
            (w.path.endsWith('/queue') && w.method === 'POST')
        );
      const waitSubmissions = async (count) => {
        for (let i = 0; i < 200 && submissions().length < count; i++)
          await new Promise((resolve) => setTimeout(resolve, 25));
        assert.equal(
          submissions().length,
          count,
          'Expected fixture submission count'
        );
      };
      await context.route('**/*', async (route) => {
        const r = route.request(),
          u = new URL(r.url()),
          p = u.pathname;
        if (p.startsWith('/api/') || p.startsWith('/v1/')) {
          let data = [];
          if (!['GET', 'HEAD'].includes(r.method()))
            writes.push({
              path: p,
              method: r.method(),
              payload: r.postDataJSON(),
            });
          if (
            p.endsWith('/follow-up') ||
            (p.endsWith('/queue') && r.method() === 'POST')
          ) {
            await new Promise((resolve) => setTimeout(resolve, 300));
            if (failNext) {
              failNext = false;
              return route.fulfill({
                status: 500,
                json: {
                  success: false,
                  message: 'Fixture failure',
                  data: null,
                },
              });
            }
          }
          if (p.includes('/scratch/') && r.method() === 'DELETE')
            await new Promise((resolve) => setTimeout(resolve, 200));
          if (p === '/api/info') data = info;
          else if (p === '/api/config') data = info.config;
          else if (p === '/api/projects') data = [];
          else if (p === '/api/workspaces/summaries')
            data = {
              summaries: [
                {
                  workspace_id: wid,
                  latest_session_id: sid,
                  latest_process_status:
                    mode === 'running' ? 'running' : 'completed',
                  has_unseen_turns: false,
                },
              ],
            };
          else if (p === '/api/workspaces') data = [ws];
          else if (p === `/api/workspaces/${wid}`) data = ws;
          else if (p === '/api/sessions') {
            if (r.method() === 'POST') {
              created = true;
              data = session;
            } else data = mode === 'new' && !created ? [] : [session];
          } else if (p === `/api/sessions/${sid}`) data = session;
          else if (p.endsWith('/queue')) data = { status: 'empty' };
          else if (p.includes('/scratch/')) data = null;
          else if (p === `/api/execution-processes/${proc.id}`) data = proc;
          else if (p.includes('subagent')) data = [];
          else if (p.includes('preset-options'))
            data = {
              models: [],
              agents: [],
              reasoning_options: [],
              permission_policies: [],
            };
          else unknown.add(p);
          return route.fulfill({
            json: { success: true, data, error_data: null, message: null },
          });
        }
        if (base && u.origin === new URL(base).origin) return route.continue();
        if (p.startsWith('/assets/') || p.endsWith('.webmanifest')) {
          const contentType = p.endsWith('.js')
            ? 'text/javascript'
            : p.endsWith('.css')
              ? 'text/css'
              : 'application/json';
          try {
            return route.fulfill({
              body: await fs.readFile(dist + p),
              contentType,
            });
          } catch {
            return route.fulfill({ status: 404 });
          }
        }
        if (r.resourceType() === 'document')
          return route.fulfill({
            body: await fs.readFile(dist + '/index.html'),
            contentType: 'text/html',
          });
        return route.fulfill({ status: 404 });
      });
      await context.routeWebSocket('**/*', (route) => {
        const u = new URL(route.url());
        if (process.env.VK_DEBUG) console.log('WS', u.pathname);
        let data = {};
        if (u.pathname.includes('workspaces/streams'))
          data = {
            workspaces:
              u.searchParams.get('archived') === 'true' ? {} : { [wid]: ws },
          };
        else if (u.pathname.includes('execution-processes/stream/session'))
          data = {
            execution_processes: mode === 'running' ? { [proc.id]: proc } : {},
          };
        else if (u.pathname.includes('approvals')) data = { approvals: {} };
        route.send(
          JSON.stringify({
            JsonPatch: Object.entries(data).map(([key, value]) => ({
              op: 'replace',
              path: `/${key}`,
              value,
            })),
          })
        );
        route.send(JSON.stringify({ Ready: true }));
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      const goto = (path) =>
        page.goto(origin + path, {
          waitUntil: 'domcontentloaded',
          timeout: 90000,
        });
      await goto('/');

      await page.waitForURL('**/workspaces', { timeout: 90000 });
      assert.equal(
        await page.locator('[contenteditable="true"]').count(),
        0,
        'Work View remains the landing screen'
      );
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForURL('**/workspaces');
      await goto(`/workspaces/${wid}`);
      const editor = page.getByRole('textbox', { name: 'Markdown editor' });
      await editor.waitFor({ timeout: 90000 });
      if (mode === 'running')
        await page
          .getByText('Fixture agent message', { exact: true })
          .waitFor();
      await editor.fill('One tap fixture');

      if (process.env.VK_DEBUG)
        console.log(await page.locator('body').innerText(), errors, [
          ...unknown,
        ]);
      const simulateKeyboard = async () => {
        if (!mobile) return;
        await page.evaluate(() => {
          Object.defineProperty(window.visualViewport, 'height', {
            configurable: true,
            value: 500,
          });
          window.visualViewport.dispatchEvent(new Event('resize'));
        });
      };
      await simulateKeyboard();
      const send = () =>
        page.getByRole('button', {
          name: mode === 'running' ? 'Send correction' : 'Send',
          exact: true,
        });
      await send().waitFor();
      const before = await send().boundingBox();
      await page.evaluate(() => {
        window.sendEvents = [];
        for (const name of [
          'pointerdown',
          'pointerup',
          'mousedown',
          'mouseup',
          'focusout',
          'click',
        ])
          document.addEventListener(
            name,
            (e) =>
              window.sendEvents.push({
                name,
                target: e.target.tagName,
                text: e.target.textContent?.slice(0, 30),
                keyboard:
                  document.querySelector('.mobile-app-shell')?.dataset
                    .keyboardOpen,
              }),
            true
          );
      });
      const tap = async () => {
        const b = await send().boundingBox();
        return mobile
          ? page.touchscreen.tap(b.x + b.width / 2, b.y + b.height / 2)
          : send().click();
      };
      await fs.mkdir(output, { recursive: true });
      await page.screenshot({ path: `${output}/${width}-${mode}-focused.png` });
      await tap();

      await page.waitForTimeout(80);
      if (process.env.VK_EXPECT_BUG === '1' && mobile) {
        assert.equal(
          submissions().length,
          0,
          'Original first tap must miss Send'
        );
        const after = await send().boundingBox();
        assert.ok(after.y < before.y - 40, 'Original navigation shifts Send');
        await tap();
        await waitSubmissions(1);
        assert.equal(submissions().length, 1, 'Original second tap submits');
        results.push({
          width,
          mode,
          reproduced: true,
          shift: before.y - after.y,
          events: await page.evaluate(() => window.sendEvents),
        });
        await context.close();
        continue;
      }
      await waitSubmissions(1);
      assert.equal(submissions().length, 1, 'First activation submits once');
      assert.equal(
        submissions()[0].payload.prompt ?? submissions()[0].payload.message,
        'One tap fixture'
      );
      const pending = page.getByRole('button', {
        name: mode === 'running' ? 'Loading' : 'Sending',
        exact: true,
      });
      await pending.waitFor();
      assert.equal(
        await pending.isDisabled(),
        true,
        'Pending Send cannot become Stop'
      );
      // A second tap at the original coordinate during the delayed request must do nothing.
      if (mobile)
        await page.touchscreen.tap(
          before.x + before.width / 2,
          before.y + before.height / 2
        );
      else await pending.evaluate((el) => el.click());
      await page.waitForTimeout(650);
      assert.equal(
        submissions().length,
        1,
        'Repeated activation does not duplicate or stop'
      );
      assert.equal(writes.filter((w) => w.path.endsWith('/stop')).length, 0);
      assert.equal(
        writes.filter((w) => w.path === '/api/sessions' && w.method === 'POST')
          .length,
        mode === 'new' ? 1 : 0,
        'New session is created once'
      );
      await page.screenshot({
        path: `${output}/${width}-${mode}-response.png`,
      });

      await editor.waitFor();
      assert.equal(
        await editor.innerText(),
        '',
        'Successful submission clears fixture draft'
      );
      // Failed request retains the draft and releases the admission guard for retry.
      failNext = true;
      await editor.fill('Retry fixture');
      await simulateKeyboard();
      await tap();
      await page.getByText(/Fixture failure/).waitFor();

      assert.equal(await editor.innerText(), 'Retry fixture');
      await editor.focus();
      await simulateKeyboard();
      await tap();
      await page.waitForTimeout(650);
      assert.equal(
        submissions().length,
        3,
        'One failed send and one explicit retry'
      );
      // Dragging away cancels activation; retaining focus must never submit on down.
      await editor.fill('Cancelled fixture');
      await simulateKeyboard();
      const b = await send().boundingBox();
      await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
      await page.mouse.down();
      await page.mouse.move(5, 100);
      await page.mouse.up();
      assert.equal(
        submissions().length,
        3,
        'Cancelled pointer gesture does not send'
      );
      // Keyboard activation follows the same guarded handler.
      await send().focus();
      await page.keyboard.press('Enter');
      await waitSubmissions(4);
      assert.equal(
        submissions().length,
        4,
        'Enter on focused Send submits once'
      );
      await page.waitForTimeout(650);
      if (mobile) {
        assert.equal(
          await page
            .locator('.mobile-app-shell')
            .getAttribute('data-keyboard-open'),
          'true'
        );
        await page.evaluate(() => {
          Object.defineProperty(window.visualViewport, 'height', {
            configurable: true,
            value: window.innerHeight,
          });
          window.visualViewport.dispatchEvent(new Event('resize'));
        });
        await page
          .getByRole('navigation', { name: 'Primary navigation' })
          .waitFor();
        assert.equal(
          await page
            .locator('.mobile-app-shell')
            .getAttribute('data-keyboard-open'),
          'false'
        );
      }
      assert.deepEqual(errors, [], 'No uncaught browser errors');
      await page.screenshot({ path: `${output}/${width}-${mode}-after.png` });
      results.push({
        width,
        mode,
        oneTap: true,
        repeatedTap: true,
        retry: true,
        cancel: true,
        keyboard: true,
        landing: true,
        events: await page.evaluate(() => window.sendEvents),
      });
      console.log(
        `PASS ${width}px ${mode}: first tap, pending/duplicate, retry, cancellation, keyboard, Work View`
      );
      await fs.writeFile(
        `${output}/results.json`,
        JSON.stringify(results, null, 2)
      );
      await context.close();
    }
  }
  await fs.writeFile(
    `${output}/results.json`,
    JSON.stringify(results, null, 2)
  );
} finally {
  await browser.close();
}
