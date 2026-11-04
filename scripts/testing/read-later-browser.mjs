// Branch frontend + existing backend. All writes are intercepted; unread data is disposable.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { stat, readFile } from 'node:fs/promises';
import { X509Certificate, createHash } from 'node:crypto';

const base = process.env.VK_TEST_BASE;
const output = process.env.VK_TEST_OUTPUT;
assert(base && output, 'Set VK_TEST_BASE and VK_TEST_OUTPUT on mounted SSD');
await mkdir(resolve(output, 'browser-tmp'), { recursive: true });
process.env.TMPDIR = resolve(output, 'browser-tmp');
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || '/usr/lib/node_modules/playwright/index.mjs'
);
const certificate = process.env.VK_TEST_CA;
const pin = certificate
  ? createHash('sha256')
      .update(
        new X509Certificate(await readFile(certificate)).publicKey.export({
          type: 'spki',
          format: 'der',
        })
      )
      .digest('base64')
  : null;
const browser = await chromium.launch({
  executablePath:
    process.env.CHROMIUM_PATH ||
    '/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',
  headless: true,
  args: [
    '--no-sandbox',
    ...(pin ? ['--ignore-certificate-errors-spki-list=' + pin] : []),
  ],
});
const results = [];
try {
  for (const [width, unread] of [
    [1440, true],
    [1440, false],
    [393, true],
    [393, false],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const errors = [],
      writes = [],
      seen = [],
      dotRequests = [];
    let target;
    let closing = false;
    // Pending polling requests can finish while a verified context is closing.
    const guard = (handler) => async (route) => {
      try {
        await handler(route);
      } catch (error) {
        if (!closing || !/closed|disposed/i.test(String(error))) throw error;
      }
    };
    if (process.env.VK_TEST_DIST)
      await context.route(
        '**/*',
        guard(async (route) => {
          const url = new URL(route.request().url());
          if (
            url.origin !== new URL(base).origin ||
            /^\/(api|v1)\//.test(url.pathname) ||
            route.request().method() !== 'GET'
          )
            return route.fallback();
          const relative = decodeURIComponent(url.pathname).slice(1);
          assert(!relative.split('/').includes('..'));
          let file = join(process.env.VK_TEST_DIST, relative || 'index.html');
          try {
            if (!(await stat(file)).isFile())
              file = join(process.env.VK_TEST_DIST, 'index.html');
          } catch {
            file = join(process.env.VK_TEST_DIST, 'index.html');
          }
          return route.fulfill({ path: file });
        })
      );
    await context.route(
      /\/(api|v1)\//,
      guard(async (route) => {
        const request = route.request();
        const path = new URL(request.url()).pathname;
        if (path === '/api/dot-sidechat/notifications') dotRequests.push(path);
        if (
          request.method() === 'POST' &&
          path === '/api/workspaces/summaries'
        ) {
          const response = await route.fetch(
            process.env.VK_TEST_BACKEND
              ? {
                  url: new URL(
                    new URL(request.url()).pathname +
                      new URL(request.url()).search,
                    process.env.VK_TEST_BACKEND
                  ).href,
                }
              : {}
          );
          const body = await response.json();
          const rows = body.data?.summaries ?? [];
          target ??= rows.find(
            (row) => row.latest_process_status !== 'running'
          )?.workspace_id;
          for (const row of rows) {
            if (row.workspace_id === target) {
              row.has_unseen_turns = unread;
              row.has_pending_approval = false;
            }
          }
          return route.fulfill({ response, json: body });
        }
        if (['GET', 'HEAD'].includes(request.method())) return route.continue();
        writes.push({ path, method: request.method() });
        if (path.endsWith('/seen')) seen.push(path);
        return route.fulfill({ json: { success: true, data: null } });
      })
    );
    const page = await context.newPage();
    page.on('pageerror', (error) => errors.push(error.message));
    page.setDefaultTimeout(30000);
    await page.goto(`${base}/workspaces`, { waitUntil: 'domcontentloaded' });
    const sourceSection = unread ? 'attention' : 'ready';
    const attention = page.locator(
      `[data-workspace-section="${sourceSection}"]`
    );
    const laterHeader = page
      .locator('button[aria-expanded]')
      .filter({ hasText: /^Read Later/ });
    await attention
      .locator('.mobile-workspace-card')
      .getByRole('button', { name: 'Read Later', exact: true })
      .first()
      .waitFor();
    const action = attention
      .locator('.mobile-workspace-card')
      .getByRole('button', { name: 'Read Later', exact: true })
      .first();
    assert.equal(
      (await action.innerText()).trim(),
      '',
      'Read Later is icon-only'
    );
    const geometry = await action.evaluate((button) => {
      const row = button.closest('.mobile-workspace-card');
      const main = row.querySelector('button');
      const a = button.getBoundingClientRect(),
        b = main.getBoundingClientRect();
      return {
        top: a.top,
        bottom: a.bottom,
        mainTop: b.top,
        mainBottom: b.bottom,
      };
    });
    assert(
      geometry.top < geometry.mainBottom && geometry.bottom > geometry.mainTop,
      'Read Later must share the notification row'
    );
    const sectionBounds = await page
      .locator('[data-workspace-section]')
      .evaluateAll((sections) =>
        sections.map((section) => ({
          contentBottom: section.getBoundingClientRect().bottom,
          containerBottom: section.parentElement.getBoundingClientRect().bottom,
        }))
      );
    assert(
      sectionBounds.every(
        (box) => box.contentBottom <= box.containerBottom + 1
      ),
      'Workspace section content must not overlap the following header'
    );
    const beforeSeen = seen.length;
    await attention
      .locator('.mobile-workspace-card')
      .getByRole('button', { name: 'Read Later', exact: true })
      .first()
      .click();
    await laterHeader.filter({ hasText: '1' }).waitFor();
    assert.equal(seen.length, beforeSeen);
    await laterHeader.click();
    const later = page.locator('[data-workspace-section="later"]');
    await later
      .getByRole('button', { name: 'Remove from Read Later', exact: true })
      .waitFor();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await later
      .getByRole('button', { name: 'Remove from Read Later', exact: true })
      .waitFor();
    await later
      .getByRole('button', { name: 'Remove from Read Later', exact: true })
      .click();
    await laterHeader.filter({ hasText: '0' }).waitFor();
    assert.equal(seen.length, beforeSeen);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth
      ),
      false
    );
    assert.deepEqual(errors, []);
    if (process.env.VK_EXPECT_DOT_DISABLED === '1')
      assert.deepEqual(
        dotRequests,
        [],
        'Preserve the previous disabled Dot notification setting'
      );
    results.push({
      width,
      initiallyUnread: unread,
      iconOnly: true,
      inline: true,
      dotNotificationRequests: dotRequests.length,
      persisted: true,
      restored: true,
      readCallsFromActions: seen.length - beforeSeen,
      blockedWrites: writes.length,
      pageErrors: errors,
    });
    await page.screenshot({
      path: resolve(
        output,
        `read-later-${width}-${unread ? 'unread' : 'read'}.png`
      ),
    });
    console.log(
      `Read Later browser passed: ${width}px, ${unread ? 'unread' : 'read'}`
    );
    closing = true;
    await context.close();
  }
} finally {
  await browser.close();
}
await writeFile(
  resolve(output, 'browser-results.json'),
  JSON.stringify(results, null, 2)
);
console.log(JSON.stringify(results, null, 2));
