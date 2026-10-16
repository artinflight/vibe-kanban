// Test route discovery against a packaged frontend and the existing live API.
// Never pair a browser or submit a conversation, task, or configuration write.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from '/usr/lib/node_modules/playwright/index.mjs';

const base = process.env.VK_TEST_BASE ?? 'http://127.0.0.1:18126';
const api = process.env.VK_TEST_BACKEND ?? 'https://vibe.local';
const output = process.env.VK_TEST_OUTPUT;
if (!output)
  throw new Error('Set VK_TEST_OUTPUT to a directory on mounted SSD');
const workspaceId = '2e35466b-127e-41ba-ab56-1dd47bdb8b85';
const projectId = '1cf19067-4055-4432-bbc1-581919f9185d';
const issueId = 'c961527e-f090-4eac-9483-2480d016a552';
const browser = await chromium.launch({
  headless: true,
  chromiumSandbox: true,
});
const report = {
  checks: [],
  errors: [],
  blockedWrites: [],
  sessionStatuses: [],
};
let page;
try {
  const context = await browser.newContext({
    viewport: { width: 393, height: 852 },
    isMobile: true,
    hasTouch: true,
    ignoreHTTPSErrors: true,
  });
  page = await context.newPage();
  page.on('pageerror', (error) => report.errors.push(error.message));
  await page.route(/\/(api|v1)\//, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (
      !['GET', 'HEAD'].includes(request.method()) &&
      !(
        request.method() === 'POST' &&
        url.pathname === '/api/workspaces/summaries'
      )
    ) {
      report.blockedWrites.push({
        path: url.pathname,
        method: request.method(),
      });
      return route.fulfill({ json: { success: true, data: null } });
    }
    const headers = { ...request.headers(), origin: api };
    delete headers.host;
    if (url.pathname.startsWith('/api/dot-sidechat/')) {
      try {
        const response = await route.fetch({
          url: api + url.pathname + url.search,
          headers,
        });
        if (url.pathname.endsWith('/session')) {
          report.sessionStatuses.push(response.status());
        }
        return await route.fulfill({ response });
      } catch (error) {
        if (!/already handled|closed|disposed|aborted/i.test(error.message)) {
          report.errors.push(error.message);
        }
        return;
      }
    }
    return route.continue({ headers });
  });
  const nav = page.getByRole('navigation', { name: 'Primary navigation' });
  const pair = page.getByRole('region', { name: 'Pair private Dot chat' });
  await page.goto(`${base}/workspaces/${workspaceId}#dot`);
  await pair.waitFor({ state: 'visible', timeout: 60000 });
  assert.ok(report.sessionStatuses.includes(401), 'Real unpaired Dot gate');
  assert.equal(
    await nav
      .getByRole('button', { name: 'Dot', exact: true })
      .getAttribute('aria-current'),
    'page'
  );
  assert.ok(
    !report.blockedWrites.some((item) => item.path.endsWith('/seen')),
    'Direct Dot link must not mark the hidden agent chat seen'
  );
  report.checks.push(
    'Direct #dot link opens the real unpaired gate without opening agent chat'
  );
  await nav.getByRole('button', { name: 'Chat', exact: true }).click();
  await pair.waitFor({ state: 'hidden' });
  assert.equal(new URL(page.url()).hash, '');
  await nav.getByRole('button', { name: 'Dot', exact: true }).click();
  await pair.waitFor({ state: 'visible' });
  assert.equal(new URL(page.url()).hash, '#dot');
  report.checks.push('Chat/Dot switching updates the hash and selected panel');
  await page.goto(
    `${base}/projects/${projectId}/issues/${issueId}/workspaces/${workspaceId}`
  );
  await nav
    .getByRole('button', { name: 'Dot', exact: true })
    .waitFor({ state: 'visible' });
  await nav.getByRole('button', { name: 'Dot', exact: true }).click();
  await pair.waitFor({ state: 'visible' });
  assert.equal(new URL(page.url()).pathname, `/workspaces/${workspaceId}`);
  assert.equal(new URL(page.url()).hash, '#dot');
  report.checks.push(
    'Issue workspace exposes Dot and opens its standalone conversation'
  );
  assert.equal(await page.locator('#dot-pair').count(), 1);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth + 1
  );
  assert.equal(overflow, false);
  assert.deepEqual(report.errors, []);
  await page.goto(`${base}/projects/${projectId}`);
  await nav
    .getByRole('button', { name: 'Projects', exact: true })
    .waitFor({ state: 'visible' });
  assert.equal(
    await nav.getByRole('button', { name: 'Dot', exact: true }).count(),
    0
  );
  report.checks.push(
    'A board without workspace context does not offer a broken conversation'
  );
} finally {
  await page?.unrouteAll({ behavior: 'wait' });
  await browser.close();
  await fs.mkdir(output, { recursive: true });
  await fs.writeFile(
    `${output}/navigation-results.json`,
    JSON.stringify(report, null, 2)
  );
}
console.log(JSON.stringify(report));
