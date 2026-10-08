// Read-only acceptance against a branch frontend and an existing backend.
// All application writes are fulfilled locally; no prompts are executed.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { resolve } from 'node:path';

const output = process.env.VK_TEST_OUTPUT;
const base = process.env.VK_TEST_BASE;
const backend = process.env.VK_TEST_BACKEND;
if (!output || !base || !backend || !process.env.PLAYWRIGHT_MODULE) {
  throw new Error(
    'Set VK_TEST_OUTPUT on mounted SSD, VK_TEST_BASE, VK_TEST_BACKEND and PLAYWRIGHT_MODULE'
  );
}
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
if (!process.env.PLAYWRIGHT_WS_BUNDLE)
  throw new Error(
    'Set PLAYWRIGHT_WS_BUNDLE to the installed Playwright core utilsBundle.js'
  );
const { default: bundle } = await import(process.env.PLAYWRIGHT_WS_BUNDLE);
const WebSocketBridge = bundle.ws;
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
});
const results = [];
await fs.mkdir(output, { recursive: true });

try {
  const cases = JSON.parse(
    process.env.VK_TEST_VIEWPORTS ??
      '[{"width":360},{"width":390},{"width":412},{"width":1440},{"width":390,"colorScheme":"dark"}]'
  );
  for (const { width, colorScheme = 'light' } of cases) {
    const mobile = width < 768;
    const context = await browser.newContext({
      viewport: { width, height: mobile ? 844 : 1000 },
      colorScheme,
      isMobile: mobile,
      hasTouch: mobile,
      ...(mobile && {
        userAgent:
          'Mozilla/5.0 (Linux; Android 15; SM-S936W) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
      }),
    });
    const writes = [];
    const scratch = new Map();
    // Both local API routes and project fallback routes must remain read-only.
    await context.route(/\/(?:api|v1)\//, async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (
        path === '/api/attachments/00000000-0000-4000-8000-000000000001/file'
      ) {
        return route.fulfill({
          body: 'Mobile test file',
          contentType: 'text/plain',
        });
      }
      if (request.method() === 'POST' && path.endsWith('/attachments/upload')) {
        writes.push({ path, method: 'POST' });
        return route.fulfill({
          json: {
            success: true,
            data: {
              id: '00000000-0000-4000-8000-000000000001',
              file_path: '.vibe-attachments/phone-test.txt',
              original_name: 'phone-test.txt',
              mime_type: 'text/plain',
              size_bytes: 16,
              hash: 'mobile-layout-fixture',
              created_at: '2026-10-08T00:00:00Z',
              updated_at: '2026-10-08T00:00:00Z',
            },
          },
        });
      }
      if (
        ['GET', 'HEAD'].includes(request.method()) ||
        (request.method() === 'POST' && path === '/api/workspaces/summaries')
      ) {
        return route.continue({
          headers: { ...request.headers(), origin: new URL(backend).origin },
        });
      }
      const payload = request.postDataJSON();
      writes.push({ path, method: request.method(), payload });
      if (path.startsWith('/api/scratch/')) scratch.set(path, payload);
      return route.fulfill({ json: { success: true, data: payload ?? null } });
    });
    // The production allowlist does not include temporary Vite origins. Bridge
    // subscription sockets through Node's WebSocket with the nominated backend
    // Origin. Client frames are intentionally never forwarded to the backend.
    const sockets = new Set();
    await context.routeWebSocket('**/api/**', (route) => {
      const source = new URL(route.url());
      const url = new URL(`${source.pathname}${source.search}`, backend);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocketBridge(url, {
        origin: new URL(backend).origin,
      });
      sockets.add(socket);
      socket.on('message', (data) => route.send(data.toString()));
      socket.on('error', () => route.close());
      socket.on('close', () => {
        sockets.delete(socket);
        route.close();
      });
      route.onClose(() => socket.close());
    });

    const projects = (
      await (await context.request.get(`${backend}/api/projects`)).json()
    ).data;
    const workspaces = (
      await (await context.request.get(`${backend}/api/workspaces`)).json()
    ).data;
    const project =
      projects.find((p) => p.name === 'VK Dev') ??
      projects.find((p) => !p.archived);
    const workspace =
      workspaces.find((w) => w.name?.includes('TF::Build')) ??
      workspaces.find((w) => !w.archived);
    assert(
      project && workspace,
      'Need an active project and populated workspace'
    );
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => {
      if (message.text().includes('Maximum update depth'))
        errors.push(message.text());
    });
    const goto = (path) =>
      page.goto(base + path, { waitUntil: 'domcontentloaded', timeout: 60000 });
    const screenshot = (name) =>
      page.screenshot({
        path: resolve(
          output,
          `${name}-${width}${colorScheme === 'dark' ? '-dark' : ''}.png`
        ),
      });
    const noHorizontalOverflow = async () => {
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1
        ),
        'Page must fit phone width'
      );
    };
    const touchTarget = async (locator) => {
      const box = await locator.boundingBox();
      assert(
        box && box.height >= 48 && box.width >= 48,
        `Touch target ${JSON.stringify(box)}`
      );
    };

    console.log(`START ${width}px board`);
    await goto(`/projects/${project.id}`);
    await (
      mobile
        ? page.locator('.phone-task-row').first()
        : page.getByText('To do', { exact: true }).first()
    ).waitFor({ timeout: 60000 });
    await noHorizontalOverflow();
    await screenshot('after-board');
    let searchHeight;
    if (mobile) {
      const taskSearch = page.getByRole('textbox', {
        name: 'Search tasks',
        exact: true,
      });
      await touchTarget(taskSearch);
      searchHeight = await taskSearch
        .locator('..')
        .evaluate((el) => el.getBoundingClientRect().height);
      assert(
        searchHeight <= 50,
        `Phone search must stay compact: ${searchHeight}`
      );
      const query = (
        await page.locator('.phone-task-title').first().innerText()
      ).slice(0, 12);
      await taskSearch.fill(query);
      const clearSearch = page.getByRole('button', {
        name: 'Clear search',
        exact: true,
      });
      await touchTarget(clearSearch);
      const inputBox = await taskSearch.boundingBox();
      const clearBox = await clearSearch.boundingBox();
      assert(
        inputBox.x + inputBox.width <= clearBox.x,
        'Search clear control has a separate target'
      );
      await clearSearch.click();
      assert.equal(
        await taskSearch.inputValue(),
        '',
        'Task search clears without leaving the screen'
      );
      assert.equal(
        await page.locator('.phone-task-feed').count(),
        1,
        'Phone has a dedicated task feed'
      );
      assert.equal(
        await page.locator('.phone-task-feed [draggable="true"]').count(),
        0,
        'Tasks need no drag gesture'
      );
      const rows = page.locator('.phone-task-row');
      assert((await rows.count()) > 2, 'Useful task feed populated');
      await page.getByRole('button', { name: /filters/i, exact: true }).click();
      await page.getByText('Task visibility', { exact: true }).waitFor();
      await page.keyboard.press('Escape');
    }
    if (mobile) {
      const nav = page.getByRole('navigation', { name: 'Primary navigation' });
      await touchTarget(
        nav.getByRole('button', { name: 'Projects', exact: true })
      );
      await nav.getByRole('button', { name: 'Projects', exact: true }).click();
      const sheet = page.getByRole('dialog', { name: 'Projects', exact: true });
      await sheet.waitFor();
      // A project can append an accessible needs-review indicator to its name.
      // Match its exact visible title while preserving that announced state.
      await touchTarget(
        sheet
          .getByRole('button')
          .filter({ has: page.getByText(project.name, { exact: true }) })
      );
      assert(
        await sheet.evaluate((el) => el.contains(document.activeElement)),
        'Sheet takes focus'
      );
      await page.keyboard.press('Tab');
      assert(
        await sheet.evaluate((el) => el.contains(document.activeElement)),
        'Sheet traps focus'
      );
      await screenshot('after-projects');
      await page.goBack();
      await sheet.waitFor({ state: 'hidden' });
      await page.waitForFunction(() =>
        document.activeElement?.closest('.mobile-bottom-navigation')
      );
      assert.equal(
        await nav
          .getByRole('button', { name: 'Projects', exact: true })
          .evaluate((el) => el === document.activeElement),
        true,
        'Closing sheet restores the invoking button'
      );
      assert(
        new URL(page.url()).pathname === `/projects/${project.id}`,
        'Back dismisses sheet before leaving board'
      );
      await nav.getByRole('button', { name: 'Projects', exact: true }).click();
      const another = projects.find((p) => !p.archived && p.id !== project.id);
      await sheet
        .getByRole('button')
        .filter({ has: page.getByText(another.name, { exact: true }) })
        .click();
      await page.waitForURL(`**/projects/${another.id}`);
      await page.goBack();
      await page.waitForURL(`**/projects/${project.id}`);
      await sheet.waitFor({ state: 'hidden' });

      const statusChip = page
        .locator('.phone-status-tabs button')
        .filter({ hasText: 'To do' });
      await touchTarget(statusChip);
      await statusChip.click();
      assert.equal(
        await statusChip.getAttribute('aria-pressed'),
        'true',
        'Selected status is explicit'
      );
      const task = page.locator('.mobile-task-card').nth(1);
      await task.waitFor();
      // Identify the board's scroll container rather than window.scrollY.
      const boardScroll = await task.evaluate((el) => {
        let parent = el.parentElement;
        while (parent && parent.scrollHeight <= parent.clientHeight + 1)
          parent = parent.parentElement;
        if (!parent) throw new Error('Board scroll container missing');
        parent.dataset.mobileTestScroller = 'true';
        parent.scrollTop = 70;
        return parent.scrollTop;
      });
      await task.locator('.mobile-task-metadata').click();
      await page.getByLabel('Task status', { exact: true }).waitFor();
      await page
        .getByRole('button', { name: 'Tags & pull requests', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Tags & pull requests', exact: true })
        .click();
      await touchTarget(page.getByLabel('Task status', { exact: true }));
      await noHorizontalOverflow();
      await screenshot('after-task');
      await page.goBack();
      await page
        .getByLabel('Task status', { exact: true })
        .waitFor({ state: 'hidden' });
      assert.equal(
        await page
          .locator('[data-mobile-test-scroller]')
          .evaluate((el) => el.scrollTop),
        boardScroll,
        'Task Back restores board scroll'
      );
      assert.equal(
        await statusChip.getAttribute('aria-pressed'),
        'true',
        'Task Back preserves the selected feed status'
      );
      // Creation remains a reachable screen; submitting it is never exercised.
      await page
        .getByRole('button', { name: 'New Issue', exact: true })
        .click();
      await page.getByLabel('Issue title', { exact: true }).waitFor();
      await page.goBack();
    }

    if (!mobile) {
      await page.getByText('T48', { exact: true }).first().click();
      await page.getByLabel('Task status', { exact: true }).waitFor();
      await screenshot('after-task');
      await page.goBack();
      await page
        .getByLabel('Task status', { exact: true })
        .waitFor({ state: 'hidden' });
      const another = projects.find((p) => !p.archived && p.id !== project.id);
      await page
        .getByRole('button', {
          name: new RegExp(
            `^${another.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`
          ),
        })
        .first()
        .click();
      await page.waitForURL(`**/projects/${another.id}`);
      await page.goBack();
      await page.waitForURL(`**/projects/${project.id}`);
    }
    console.log(`START ${width}px chat`);
    await goto(`/workspaces/${workspace.id}`);
    const editor = page.getByRole('textbox', {
      name: 'Markdown editor',
      exact: true,
    });
    await editor.waitFor({ timeout: 60000 });
    await page.waitForFunction(
      () =>
        !document
          .querySelector('.mobile-composer')
          ?.textContent.includes('Loading...'),
      null,
      { timeout: 60000 }
    );
    await page
      .locator('[aria-label="Markdown content"]')
      .first()
      .waitFor({ timeout: 60000 });
    await screenshot('after-chat');
    await noHorizontalOverflow();
    if (mobile) {
      const copy = page
        .getByRole('button', { name: 'Copy as Markdown', exact: true })
        .first();
      await touchTarget(copy);
      assert.equal(
        await copy.evaluate((el) => getComputedStyle(el.parentElement).opacity),
        '1',
        'Message actions visible without hover'
      );
    }
    if (mobile) {
      const composerBox = await page.locator('.mobile-composer').boundingBox();
      assert(
        composerBox.height < 180,
        `Collapsed composer must leave room for conversation: ${composerBox.height}`
      );
      await page.getByRole('button', { name: 'Options', exact: true }).click();
      await page.getByText('Model & permissions', { exact: true }).waitFor();
      await screenshot('after-prompt-options');
    }
    const modelBefore = await page
      .locator('.mobile-model-selector')
      .innerText();
    if (mobile)
      await page.getByRole('button', { name: 'Options', exact: true }).click();
    // Work in an isolated, intercepted scratch buffer, never a real prompt.
    await editor.fill('Mobile UX validation draft\nSecond line — do not send.');
    await page.waitForTimeout(700);
    if (mobile) {
      const nav = page.getByRole('navigation', { name: 'Primary navigation' });
      for (const name of ['Workspaces', 'Chat', 'Changes', 'More'])
        await touchTarget(nav.getByRole('button', { name, exact: true }));
      await nav.getByRole('button', { name: 'Changes', exact: true }).click();
      await nav.getByRole('button', { name: 'Chat', exact: true }).click();
      assert.match(await editor.innerText(), /Mobile UX validation draft/);
      await page.getByRole('button', { name: 'Options', exact: true }).click();
      assert.equal(
        await page.locator('.mobile-model-selector').innerText(),
        modelBefore,
        'Model/effort unchanged'
      );
      await page.getByRole('button', { name: 'Options', exact: true }).click();
      await nav.getByRole('button', { name: 'More', exact: true }).click();
      const tools = page.getByRole('dialog', {
        name: 'Workspace tools',
        exact: true,
      });
      await tools.getByRole('button', { name: 'Logs', exact: true }).click();
      await tools.waitFor({ state: 'hidden' });
      await nav.getByRole('button', { name: 'More', exact: true }).click();
      await tools.getByRole('button', { name: 'Preview', exact: true }).click();
      await nav.getByRole('button', { name: 'More', exact: true }).click();
      await tools.getByRole('button', { name: 'Git', exact: true }).click();
      await nav.getByRole('button', { name: 'Chat', exact: true }).click();
      await editor.focus();
      // Desktop automation cannot open a real software keyboard. Exercise the
      // VisualViewport events/geometry explicitly and retain that limitation.
      await page.evaluate(() => {
        Object.defineProperty(window.visualViewport, 'height', {
          configurable: true,
          value: 480,
        });
        Object.defineProperty(window.visualViewport, 'offsetTop', {
          configurable: true,
          value: 24,
        });
        window.visualViewport.dispatchEvent(new Event('resize'));
      });
      await page.waitForFunction(
        () =>
          document.querySelector('.mobile-app-shell')?.dataset.keyboardOpen ===
          'true'
      );
      assert.equal(
        await nav.isVisible(),
        false,
        'Keyboard hides bottom navigation'
      );
      const send = page.getByRole('button', { name: 'Send', exact: true });
      await touchTarget(send);
      const sendBox = await send.boundingBox();
      assert(
        sendBox.y + sendBox.height <= 504,
        'Send remains above simulated keyboard'
      );
      assert.match(await editor.innerText(), /Second line/);
      await screenshot('after-keyboard');
      await page.evaluate(() => {
        Object.defineProperty(window.visualViewport, 'scale', {
          configurable: true,
          value: 2,
        });
        Object.defineProperty(window.visualViewport, 'height', {
          configurable: true,
          value: 300,
        });
        window.visualViewport.dispatchEvent(new Event('resize'));
      });
      assert.equal(
        await page
          .locator('.mobile-app-shell')
          .evaluate((el) => el.style.height),
        '480px',
        'Pinch zoom stays browser-owned'
      );
      await page.evaluate(() => {
        delete window.visualViewport.scale;
        delete window.visualViewport.height;
        delete window.visualViewport.offsetTop;
        window.visualViewport.dispatchEvent(new Event('resize'));
      });
      await nav.waitFor();
      // Exercise the actual file chip using a locally fulfilled upload response.
      // The browser sends no attachment bytes to the backend.
      const attach = page.getByRole('button', {
        name: 'Attach file',
        exact: true,
      });
      await touchTarget(attach);
      const chooserReady = page.waitForEvent('filechooser');
      await attach.click();
      const chooser = await chooserReady;
      await chooser.setFiles({
        name: 'phone-test.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Mobile test file'),
      });
      const chip = editor
        .locator('span.group[role="button"]')
        .filter({ hasText: 'phone-test.txt' });
      await chip.waitFor();
      const remove = chip.getByRole('button', { name: /Remove/ });
      const download = chip.getByRole('button', { name: /Download/ });
      await touchTarget(remove);
      await touchTarget(download);
      const removeBox = await remove.boundingBox();
      const downloadBox = await download.boundingBox();
      assert(
        removeBox.x + removeBox.width <= downloadBox.x ||
          removeBox.y + removeBox.height <= downloadBox.y,
        'Attachment touch targets do not overlap'
      );
      assert.equal(
        await remove.evaluate((el) => getComputedStyle(el).opacity),
        '1'
      );
      await noHorizontalOverflow();
      await screenshot('after-attachment');
      await remove.click();
      await chip.waitFor({ state: 'hidden' });
      assert.match(await editor.innerText(), /Mobile UX validation draft/);
      await nav
        .getByRole('button', { name: 'Workspaces', exact: true })
        .click();
      const search = page.getByPlaceholder('Search...', { exact: true });
      await search.waitFor();
      await search.fill(workspace.name);
      await page
        .locator('.mobile-workspace-card > button:first-of-type')
        .filter({ hasText: workspace.name })
        .first()
        .waitFor();
      await screenshot('after-workspaces-filtered');
      await page
        .locator('.mobile-workspace-card > button:first-of-type')
        .filter({ hasText: workspace.name })
        .first()
        .click();
      assert.match(await editor.innerText(), /Mobile UX validation draft/);
      await nav
        .getByRole('button', { name: 'Workspaces', exact: true })
        .click();
      assert.equal(
        await search.inputValue(),
        workspace.name,
        'Workspace filter preserved'
      );
      await touchTarget(search);
      const workspaceSearchHeight = await search
        .locator('..')
        .evaluate((el) => el.getBoundingClientRect().height);
      assert(
        workspaceSearchHeight <= 50,
        `Workspace search must stay compact: ${workspaceSearchHeight}`
      );
      const clearWorkspaceSearch = page.getByRole('button', {
        name: 'Clear search',
        exact: true,
      });
      await touchTarget(clearWorkspaceSearch);
      await clearWorkspaceSearch.click();
      assert.equal(await search.inputValue(), '');
      const activityTabs = page.locator('.phone-workspace-tabs');
      const runningChip = activityTabs.getByRole('button', {
        name: /^Running/,
      });
      await runningChip.click();
      assert.equal(await runningChip.getAttribute('aria-pressed'), 'true');
      for (const caption of await page
        .locator('.phone-workspace-caption')
        .allTextContents())
        assert.match(caption, /Running/, 'Activity filter shows matching rows');
      await activityTabs.getByRole('button', { name: /^All/ }).click();
      await screenshot('after-workspaces');
      await page
        .getByRole('button', { name: 'List options', exact: true })
        .click();
      assert(
        await page.locator('.phone-list-options').isVisible(),
        'Workspace sort/filter controls reachable'
      );
      await page
        .getByRole('button', { name: 'List options', exact: true })
        .click();
      const secondWorkspace = page
        .locator('.mobile-workspace-card > button:first-of-type')
        .filter({ hasNotText: workspace.name })
        .first();
      await secondWorkspace.click();
      await page.waitForURL(
        (url) =>
          url.pathname.startsWith('/workspaces/') &&
          !url.pathname.includes(workspace.id)
      );
      await editor.waitFor();
      await page.goBack();
      await page.waitForURL(`**/workspaces/${workspace.id}`);
    } else {
      assert.equal(
        await page.locator('.mobile-bottom-navigation').count(),
        0,
        'Desktop retains panel navigation'
      );
      assert.equal(await page.locator('.mobile-app-shell').count(), 0);
      const sendBox = await page
        .getByRole('button', { name: 'Send', exact: true })
        .boundingBox();
      assert(sendBox.height < 48, 'Desktop retains compact controls');
      const nextWorkspace = page
        .locator('.mobile-workspace-card > button:first-of-type')
        .filter({ hasNotText: workspace.name })
        .first();
      await nextWorkspace.click();
      await page.waitForURL(
        (url) =>
          url.pathname.startsWith('/workspaces/') &&
          !url.pathname.includes(workspace.id)
      );
      await page.goBack();
      await page.waitForURL(`**/workspaces/${workspace.id}`);
    }
    if (mobile) {
      await goto('/workspaces/create');
      await page
        .locator('.mobile-create-workspace h2')
        .waitFor({ timeout: 60000 });
      await noHorizontalOverflow();
      await screenshot('after-create-workspace');
      const focused = await page.evaluate(() =>
        document.activeElement?.getAttribute('contenteditable')
      );
      assert.notEqual(
        focused,
        'true',
        'Creation does not open keyboard before an intentional tap'
      );
    }
    assert.deepEqual(errors, [], 'No application exceptions');
    results.push({
      width,
      colorScheme,
      passed: true,
      modelPreserved: true,
      ...(mobile && { searchHeight }),
      writesIntercepted: writes.length,
      promptSubmitted: false,
    });
    for (const socket of sockets) socket.close();
    await context.close();
    console.log(`PASS ${width}px ${colorScheme}`);
  }
  await fs.writeFile(
    resolve(output, 'results.json'),
    JSON.stringify(results, null, 2)
  );
} finally {
  await browser.close();
}
