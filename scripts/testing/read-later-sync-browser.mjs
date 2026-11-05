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

const records = new Map(),
  receipts = new Set();
const errors = [],
  writes = [],
  preferenceWrites = [];
let target, serverUser;
let dotPolls = 0;
const json = (data) => ({ json: { success: true, data } });
async function context(width, seed) {
  const c = await browser.newContext({
    viewport: { width, height: 1000 },
    isMobile: width < 768,
    hasTouch: width < 768,
  });
  if (seed)
    await c.addInitScript(
      (value) =>
        localStorage.setItem('vk-read-later-v1', JSON.stringify(value)),
      seed
    );
  await c.route('**/*', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      p = url.pathname;
    if (/^\/api\/read-later\//.test(p)) {
      const user = decodeURIComponent(p.split('/')[3]);
      serverUser ??= user;
      assert.equal(user, serverUser, 'same user on both devices');
      if (request.method() === 'GET')
        return route.fulfill(json([...records.values()]));
      const input = request.postDataJSON();
      preferenceWrites.push({ method: request.method(), path: p });
      if (p.endsWith('/import')) {
        for (const item of input.items) {
          const key = JSON.stringify([item.kind, item.id]);
          if (!records.has(key))
            records.set(key, { item, saved: true, revision: 1 });
        }
      } else {
        assert.equal(request.method(), 'PUT');
        if (!receipts.has(input.change_id)) {
          receipts.add(input.change_id);
          const key = JSON.stringify([input.item.kind, input.item.id]);
          records.set(key, {
            item: input.item,
            saved: input.saved,
            revision: (records.get(key)?.revision ?? 0) + 1,
          });
        }
      }
      return route.fulfill(json(null));
    }
    if (p === '/api/dot-sidechat/notifications') dotPolls++;
    if (request.method() === 'POST' && p === '/api/workspaces/summaries') {
      const response = await route.fetch({
        url: new URL(p + url.search, process.env.VK_TEST_BACKEND).href,
      });
      const body = await response.json();
      const rows = body.data?.summaries ?? [];
      target ??= rows.find(
        (r) => r.latest_process_status !== 'running'
      )?.workspace_id;
      for (const row of rows) {
        row.has_unseen_turns = row.workspace_id === target;
        row.has_pending_approval = false;
      }
      return route.fulfill({ response, json: body });
    }
    if (/^\/(api|v1)\//.test(p)) {
      if (['GET', 'HEAD'].includes(request.method())) return route.continue();
      writes.push({ path: p, method: request.method() });
      return route.fulfill(json(null));
    }
    const relative = decodeURIComponent(p).slice(1);
    assert(!relative.split('/').includes('..'));
    let file = join(process.env.VK_TEST_DIST, relative || 'index.html');
    try {
      if (!(await stat(file)).isFile())
        file = join(process.env.VK_TEST_DIST, 'index.html');
    } catch {
      file = join(process.env.VK_TEST_DIST, 'index.html');
    }
    return route.fulfill({ path: file });
  });
  const page = await c.newPage();
  page.on('pageerror', (e) => errors.push(e.message));
  page.setDefaultTimeout(30000);
  await page.goto(base + '/workspaces', { waitUntil: 'domcontentloaded' });
  return { c, page };
}
const header = (page, count) =>
  page
    .locator('button[aria-expanded]')
    .filter({ hasText: new RegExp('^Read Later\\s*' + count) });
async function openLater(page) {
  const h = page
    .locator('button[aria-expanded]')
    .filter({ hasText: /^Read Later/ });
  if ((await h.getAttribute('aria-expanded')) === 'false') await h.click();
}
try {
  const desktop = await context(1440);
  await desktop.page
    .locator('[data-workspace-section="attention"]')
    .getByRole('button', { name: 'Read Later', exact: true })
    .first()
    .waitFor();
  const scope = await desktop.page.evaluate(
    () =>
      Object.keys(
        JSON.parse(localStorage.getItem('vk-read-later-v1')).state
          .migratedScopes
      )[0]
  );
  assert(scope);
  const item = {
    kind: 'workspace',
    id: target,
    name: 'Premiere Pro to mobile',
  };
  const cacheKey = JSON.stringify([scope, item.kind, item.id]);
  const legacy = { state: { items: { [cacheKey]: item } }, version: 0 };
  await desktop.page.evaluate(
    (value) => localStorage.setItem('vk-read-later-v1', JSON.stringify(value)),
    legacy
  );
  await desktop.page.reload({ waitUntil: 'domcontentloaded' });
  await header(desktop.page, 1).waitFor();
  await desktop.page.waitForFunction(() =>
    Object.values(
      JSON.parse(localStorage.getItem('vk-read-later-v1')).state.migratedScopes
    ).includes(true)
  );
  const mobile = await context(393);
  await header(mobile.page, 1).waitFor();
  await openLater(mobile.page);
  const remove = mobile.page
    .locator('[data-workspace-section="later"]')
    .getByRole('button', { name: 'Remove from Read Later', exact: true });
  await remove.waitFor();
  await mobile.page.screenshot({ path: resolve(output, 'mobile-synced.png') });
  await remove.click();
  await header(mobile.page, 0).waitFor();
  await desktop.page.bringToFront();
  await desktop.page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await header(desktop.page, 0).waitFor();
  const stale = await context(393, legacy);
  await header(stale.page, 0).waitFor();
  await stale.page.waitForFunction(() =>
    Object.values(
      JSON.parse(localStorage.getItem('vk-read-later-v1')).state
        .migratedScopes ?? {}
    ).includes(true)
  );
  assert.equal([...records.values()].filter((r) => r.saved).length, 0);
  // A fresh desktop action must appear in the already-open phone session.
  await desktop.page
    .locator('[data-workspace-section="attention"]')
    .getByRole('button', { name: 'Read Later', exact: true })
    .first()
    .click();
  await header(desktop.page, 1).waitFor();
  await mobile.page.bringToFront();
  await mobile.page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await header(mobile.page, 1).waitFor();
  await mobile.page.reload({ waitUntil: 'domcontentloaded' });
  await header(mobile.page, 1).waitFor();
  for (const page of [desktop.page, mobile.page, stale.page])
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth
      ),
      false
    );
  assert.deepEqual(writes, []);
  assert.equal(dotPolls, 0);
  assert.deepEqual(errors, []);
  const result = {
    passed: true,
    independentContexts: 3,
    legacyImport: true,
    desktopSaveVisibleOnMobile: true,
    mobileRemovalVisibleOnDesktop: true,
    staleImportRespectsRemoval: true,
    survivesReload: true,
    sharedPreferenceWrites: preferenceWrites.length,
    applicationWrites: writes.length,
    dotPolls,
    pageErrors: errors,
    backend: 'disposable API fixture; not production persistence',
  };
  await writeFile(
    resolve(output, 'results.json'),
    JSON.stringify(result, null, 2)
  );
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
}
