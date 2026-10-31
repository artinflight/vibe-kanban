// Real project UI with persistent, disposable issue metadata; no live task writes.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
const { chromium, request } = await import(
  process.env.PLAYWRIGHT_MODULE || '/usr/lib/node_modules/playwright/index.mjs'
);
const base = process.env.VK_TEST_BASE;
const output = process.env.VK_TEST_OUTPUT;
assert(base && output, 'Set VK_TEST_BASE and mounted-SSD VK_TEST_OUTPUT');
await fs.mkdir(output, { recursive: true });
const project = '1cf19067-4055-4432-bbc1-581919f9185d';
const issueId = '7fee0e75-39d2-4f2e-9698-e4212c55f263';
const workspaceId = 'c097e5f5-e814-456f-98ee-f37f73efe46f';
const lookup = await request.newContext();
const response = await lookup.get(
  base + '/v1/fallback/issues?project_id=' + project
);
assert(response.ok());
const issue = (await response.json()).issues.find((x) => x.id === issueId);
assert(issue);
await lookup.dispose();
const browser = await chromium.launch({
  executablePath:
    process.env.CHROMIUM_PATH ||
    '/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',
  headless: true,
  args: ['--no-sandbox'],
});
const results = [];
try {
  for (const width of process.env.EXPECT_BROKEN ? [393] : [393, 1440]) {
    const file = output + '/flags-' + width + '.sqlite';
    const database = new DatabaseSync(file);
    database.exec(
      'CREATE TABLE IF NOT EXISTS fixture (id TEXT PRIMARY KEY, metadata TEXT NOT NULL)'
    );
    database.prepare('INSERT OR REPLACE INTO fixture VALUES (?, ?)').run(
      issueId,
      JSON.stringify({
        vk_flags: { needs_review: true, keep_me: true },
        unrelated: 'keep',
      })
    );
    const metadata = () =>
      JSON.parse(
        database.prepare('SELECT metadata FROM fixture WHERE id=?').get(issueId)
          .metadata
      );
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const page = await context.newPage();
    const errors = [],
      writes = [],
      seen = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route(/\/(api|v1)\//, async (route) => {
      const req = route.request(),
        path = new URL(req.url()).pathname,
        method = req.method();
      if (method === 'GET' && path === '/v1/fallback/issues') {
        const r = await route.fetch();
        const data = await r.json();
        for (const row of data.issues)
          if (row.id === issueId) row.extension_metadata = metadata();
        return route.fulfill({ response: r, json: data });
      }
      if (method === 'POST' && path === '/api/workspaces/summaries') {
        const r = await route.fetch();
        const data = await r.json();
        for (const row of data.data.summaries)
          if (row.workspace_id === workspaceId) {
            row.has_unseen_turns = false;
            row.latest_process_status = 'completed';
          }
        return route.fulfill({ response: r, json: data });
      }
      if (['GET', 'HEAD'].includes(method)) return route.continue();
      if (method === 'PATCH' && path === '/v1/issues/' + issueId) {
        const update = req.postDataJSON();
        // The board may also persist initial sort order. Keep that unrelated
        // write local; only the explicit flag update belongs to this fixture.
        if (!update.extension_metadata) {
          return route.fulfill({ json: { txid: Date.now() } });
        }
        database
          .prepare('UPDATE fixture SET metadata=? WHERE id=?')
          .run(JSON.stringify(update.extension_metadata), issueId);
        writes.push({ path, method });
        return route.fulfill({ json: { txid: Date.now() } });
      }
      if (path.endsWith('/seen')) seen.push(path);
      return route.fulfill({ json: { success: true, data: null } });
    });
    async function board() {
      await page.goto(base + '/projects/' + project, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      if (width < 768) {
        await page
          .locator('.phone-status-tabs')
          .getByRole('button', { name: 'All', exact: true })
          .click({ timeout: 60000 });
        return page.locator('.phone-task-row').filter({
          has: page.getByRole('button', {
            name: 'Actions for ' + issue.simple_id,
            exact: true,
          }),
        });
      }
      return page.locator('[data-rfd-draggable-id="' + issueId + '"]');
    }
    try {
      let card = await board();
      await card.waitFor({ timeout: 60000 });
      if (process.env.EXPECT_BROKEN) {
        assert.equal(
          await card.locator('.phone-task-review').textContent(),
          'Needs review'
        );
        assert.equal(
          await card
            .getByRole('button', { name: /^Clear review flag/ })
            .count(),
          0
        );
        results.push({
          width,
          reproduced: true,
          unreadWorkspace: false,
          misleadingNeedsReview: true,
          clearControlMissing: true,
        });
        continue;
      }
      assert.equal(
        await card.locator('.phone-task-review').count(),
        0,
        'A manual flag must not masquerade as unread'
      );
      const clear = card.getByRole('button', { name: /^Clear review flag/ });
      await clear.waitFor();
      const url = page.url();
      await clear.click();
      for (let n = 0; n < 100 && metadata().vk_flags?.needs_review; n++)
        await page.waitForTimeout(100);
      assert.equal(metadata().vk_flags?.needs_review, undefined);
      assert.equal(metadata().vk_flags?.keep_me, true);
      assert.equal(metadata().unrelated, 'keep');
      assert.equal(page.url(), url, 'Clearing a flag must not navigate');
      assert.equal(writes.length, 1, 'One click must persist exactly once');
      assert.deepEqual(
        seen,
        [],
        'Clearing a flag must not mark workspace replies read'
      );
      card = await board();
      await card.waitFor({ timeout: 60000 });
      assert.equal(
        await card.getByRole('button', { name: /^Clear review flag/ }).count(),
        0,
        'Cleared flag stays cleared after reload'
      );
      assert.equal(await card.locator('.phone-task-review').count(), 0);
      assert.deepEqual(errors, []);
      results.push({
        width,
        passed: true,
        metadataPersisted: true,
        reloadVerified: true,
        unrelatedFlagsPreserved: true,
        navigationUnchanged: true,
      });
    } finally {
      await context.close();
      database.close();
    }
  }
} finally {
  await browser.close();
  await fs.writeFile(
    output + '/results.json',
    JSON.stringify({ results, liveTaskWrites: false }, null, 2) + '\n'
  );
}
console.log(JSON.stringify({ passed: true, results }));
