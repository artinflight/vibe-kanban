// Packaged UI with disposable unread persistence. All application writes are
// intercepted; read-only API/history requests use the existing green backend.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || '/usr/lib/node_modules/playwright/index.mjs'
);
const base = process.env.VK_TEST_BASE;
const output = process.env.VK_TEST_OUTPUT;
const workspace = process.env.VK_TEST_WORKSPACE;
const project = process.env.VK_TEST_PROJECT;
const issue = process.env.VK_TEST_ISSUE;
const dist = process.env.VK_TEST_DIST;
const negative = process.env.VK_TEST_EXPECT_AUTOMATIC_READ === '1';
assert(base && output && workspace && project && issue);
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ||
    '/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',
  headless: true,
  args: ['--no-sandbox'],
});
const results = [];
try {
  for (const width of negative ? [393] : [1440, 393]) {
    for (const surface of negative ? ['project'] : ['project', 'workspaces']) {
      const database = new DatabaseSync(':memory:');
      database.exec('CREATE TABLE replies(session TEXT, seen INTEGER); INSERT INTO replies VALUES (\'displayed\',0),(\'sibling\',0)');
      const unread = () => database.prepare('SELECT COUNT(*) AS n FROM replies WHERE seen=0').get().n;
      const reads = [], errors = [], blockedWrites = [];
      let failRead = true;
      let closing = false;
      const context = await browser.newContext({
        viewport: { width, height: 1000 }, isMobile: width < 768, hasTouch: width < 768,
      });
      await context.route('**/*', async route => {
        try {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin !== new URL(base).origin) return route.continue();
        const api = /^\/(api|v1)\//.test(url.pathname);
        if (!api && dist && request.method() === 'GET') {
          const relative = decodeURIComponent(url.pathname).slice(1);
          assert(!relative.split('/').includes('..'));
          let file = path.join(dist, relative || 'index.html');
          try {
            if (!(await fs.stat(file)).isFile()) file = path.join(dist, 'index.html');
          } catch { file = path.join(dist, 'index.html'); }
          return route.fulfill({ path: file });
        }
        if (request.method() === 'POST' && url.pathname === '/api/workspaces/summaries') {
          const response = await route.fetch();
          const data = await response.json();
          for (const row of data.data.summaries) if (row.workspace_id === workspace) row.has_unseen_turns = unread() > 0;
          return route.fulfill({ response, json: data });
        }
        if (request.method() === 'PUT' && url.pathname === `/api/workspaces/${workspace}/seen`) {
          reads.push({ workspace, method: request.method(), body: request.postData(), status: failRead ? 503 : 200 });
          if (failRead) return route.fulfill({ status: 503, json: { success: false, message: 'Disposable offline fixture' } });
          database.exec('UPDATE replies SET seen=1');
          return route.fulfill({ json: { success: true, data: null } });
        }
        if (['GET', 'HEAD'].includes(request.method())) return route.continue();
        blockedWrites.push({ path: url.pathname, method: request.method() });
        return route.fulfill({ json: { success: true, data: null } });
        } catch (error) {
          if (!closing) throw error;
        }
      });
      const page = await context.newPage();
      page.on('pageerror', e => errors.push(e.message));
      const route = surface === 'project'
        ? `/projects/${project}/issues/${issue}/workspaces/${workspace}`
        : `/workspaces/${workspace}`;
      const button = () => page.getByRole('button', { name: 'Mark all replies read', exact: true });
      const returnToTab = () => page.evaluate(() => {
        Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        delete document.visibilityState;
        document.dispatchEvent(new Event('visibilitychange'));
        window.dispatchEvent(new Event('focus'));
      });
      try {
        await page.goto(base + route, { waitUntil: 'domcontentloaded', timeout: 60000 });
        if (negative) {
          await page.waitForTimeout(9000);
          assert(reads.length > 0, 'Previous frontend must reproduce an automatic seen request');
          assert.equal(unread(), 2, 'Diagnostic writes remain blocked');
          results.push({ surface, width, reproducedAutomaticRead: true, automaticReadRequests: reads.length, liveApplicationWrites: 0 });
          continue;
        }
        await button().waitFor({ timeout: 60000 });
        await page.waitForTimeout(1500);
        assert.equal(reads.length, 0, 'Opening must not acknowledge replies');
        assert.equal(unread(), 2, 'Both sessions stay unread');
        await returnToTab();
        await page.waitForTimeout(4500);
        assert.equal(reads.length, 0, 'Tab return and polling must not acknowledge replies');
        await page.reload({ waitUntil: 'domcontentloaded' });
        await button().waitFor();
        assert.equal(reads.length, 0, 'Reload must not acknowledge replies');
        await button().click();
        await page.getByRole('alert').filter({ hasText: 'Could not mark replies read' }).waitFor();
        assert.equal(unread(), 2);
        assert.equal(reads.length, 1);
        await returnToTab();
        await page.waitForTimeout(300);
        assert.equal(reads.length, 1, 'Failed request must not automatically retry');
        failRead = false;
        const beforeReadUrl = page.url();
        await button().click();
        await page.waitForFunction(() => !document.querySelector('button[title^="Mark all agent replies"]')?.disabled);
        assert.equal(unread(), 0, 'Explicit workspace read acknowledges all sessions');
        assert.equal(reads.length, 2);
        assert.equal(page.url(), beforeReadUrl);
        assert.equal(await page.getByRole('alert').filter({ hasText: 'Could not mark replies read' }).count(), 0);
        await page.reload({ waitUntil: 'domcontentloaded' });
        await button().waitFor();
        assert.equal(unread(), 0, 'Fixture persistence survives reload');
        // Simulate a later completion/manual unread reminder. No UI event reads it.
        database.exec('UPDATE replies SET seen=0');
        await returnToTab();
        await page.reload({ waitUntil: 'domcontentloaded' });
        await button().waitFor();
        assert.equal(unread(), 2);
        assert.equal(reads.length, 2);
        // Session hydration can replace the initial Workspaces chat subtree.
        // Inspect the currently attached control atomically rather than keeping
        // an element across that legitimate remount.
        await page.waitForFunction(() => {
          const button = document.querySelector('button[title^="Mark all agent replies"]');
          if (!button) return false;
          const bounds = button.getBoundingClientRect();
          return bounds.width > 0 && bounds.height > 0 && bounds.x >= 0 && bounds.right <= window.innerWidth;
        });
        await page.screenshot({ path: path.join(output, `${surface}-${width}-viewport.png`) });
        assert.deepEqual(errors, []);
        results.push({ surface, width, passed: true, noAutomaticReads: true, siblingUnreadPreserved: true,
          explicitReadStatuses: reads.map(r => r.status), failedRequestPreserved: true,
          reloadPersistence: true, laterUnreadPreserved: true, pageErrors: errors,
          blockedWriteCount: blockedWrites.length, liveApplicationWrites: 0 });
      } catch (error) {
        await page.screenshot({path: path.join(output, `failure-${surface}-${width}.png`)});
        throw error;
      } finally { closing = true; await context.close(); database.close(); }
    }
  }
} finally { await browser.close(); }
await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ passed: true, results }, null, 2) + '\n');
console.log(JSON.stringify(results));
