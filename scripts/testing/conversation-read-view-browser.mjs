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
const negative = process.env.VK_TEST_EXPECT_NO_VIEW_READ === '1';
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
      let failRead = false;
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
      async function waitReads(count) {
        for (let n = 0; n < 600 && reads.length < count; n++) await page.waitForTimeout(100);
        assert.equal(reads.length, count, `Expected ${count} read acknowledgements on ${surface} ${width}`);
      }
      try {
        await page.goto(base + route, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await page.locator('[data-row-index]').first().waitFor({ timeout: 60000 });
        if (negative) {
          await page.waitForTimeout(1500);
          assert.equal(reads.length, 0, 'Manual-only frontend reproduces failure to clear on opening');
          results.push({surface, width, reproducedMissingReadOnOpen: true, loadedRows: await page.locator('[data-row-index]').count(), liveApplicationWrites: 0});
          continue;
        }
        // Workspaces can restore a position above the latest reply. Deliberately
        // use the actual jump-to-latest button before expecting a read.
        const jump = page.getByRole('button', {name:'Scroll to bottom', exact:true});
        if (surface === 'workspaces') {
          await page.waitForTimeout(1000);
          if (await jump.isVisible()) await jump.click();
        }
        await waitReads(1);
        assert.equal(unread(), 0, 'Opening the loaded, displayed conversation clears unread');
        database.exec('UPDATE replies SET seen=0');
        await returnToTab();
        await page.waitForTimeout(4500);
        assert.equal(unread(), 2, 'A new unread update survives tab return and polling');
        assert.equal(reads.length, 1);
        failRead = true;
        if (width === 1440 && surface === 'project') {
          await page.locator('div[role="button"].bg-panel').filter({has: page.getByText("VK::Can't clear un-read notifications", {exact:true})}).last().click();
        } else if (width === 1440) {
          await page.getByRole('button').filter({hasText:"VK::Can't clear un-read notifications"}).first().click();
        } else {
          await page.reload({waitUntil:'domcontentloaded'});
        }
        await waitReads(2);
        assert.equal(reads[1].status, 503);
        assert.equal(unread(), 2, 'Failed read leaves unread intact');
        await returnToTab();
        await page.waitForTimeout(600);
        assert.equal(reads.length, 2, 'Tab return must not retry a failed automatic acknowledgement');
        failRead = false;
        await button().click();
        await waitReads(3);
        assert.equal(unread(), 0, 'The explicit bulk control remains a working fallback');
        database.exec('UPDATE replies SET seen=0');
        await returnToTab();
        await page.waitForTimeout(600);
        assert.equal(unread(), 2);
        assert.equal(reads.length, 3);
        await page.reload({waitUntil:'domcontentloaded'});
        await waitReads(4);
        assert.equal(unread(), 0, 'Deliberately reopening restores normal clearing');
        await page.screenshot({path:path.join(output, `${surface}-${width}-view.png`)});
        assert.deepEqual(errors, []);
        results.push({surface,width,passed:true,clearOnLoadedView:true,
          passiveReturnAndPollingPreserved:true,deliberateReselectOrReopen:true,
          explicitReadStatuses:reads.map(r=>r.status),failedReadPreserved:true,
          bulkFallbackWorks:true,pageErrors:errors,liveApplicationWrites:0});
      } catch (error) {
        await page.screenshot({path: path.join(output, `failure-${surface}-${width}.png`)});
        throw error;
      } finally { closing = true; await context.close(); database.close(); }
    }
  }
} finally { await browser.close(); }
await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ passed: true, results }, null, 2) + '\n');
console.log(JSON.stringify(results));
