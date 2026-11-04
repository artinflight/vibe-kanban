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
  for (const width of [1440, 393]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const errors = [],
      writes = [],
      seen = [];
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
              row.has_unseen_turns = true;
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
    const attention = page.locator('[data-workspace-section="attention"]');
    const laterHeader = page
      .locator('button[aria-expanded]')
      .filter({ hasText: /^Read Later/ });
    await attention
      .locator('.mobile-workspace-card')
      .getByRole('button', { name: 'Read Later', exact: true })
      .first()
      .waitFor();
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
      .getByRole('button', { name: 'Return to Attention', exact: true })
      .waitFor();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await later
      .getByRole('button', { name: 'Return to Attention', exact: true })
      .waitFor();
    await later
      .getByRole('button', { name: 'Return to Attention', exact: true })
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
    results.push({
      width,
      persisted: true,
      restored: true,
      readCallsFromActions: seen.length - beforeSeen,
      blockedWrites: writes.length,
      pageErrors: errors,
    });
    await page.screenshot({ path: resolve(output, `read-later-${width}.png`) });
    console.log(`Read Later browser passed: ${width}px`);
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
