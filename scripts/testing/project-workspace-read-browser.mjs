// Real persistence check bounded to this task's own workspace. No provider turn.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium, request } from '/usr/lib/node_modules/playwright/index.mjs';

const base = process.env.VK_TEST_BASE;
const output = process.env.VK_TEST_OUTPUT;
assert(base && output, 'Set VK_TEST_BASE and VK_TEST_OUTPUT (on mounted SSD)');
const project = '1cf19067-4055-4432-bbc1-581919f9185d';
const issue = '7fee0e75-39d2-4f2e-9698-e4212c55f263';
const workspace = 'c097e5f5-e814-456f-98ee-f37f73efe46f';
const title = "VK::Can't clear un-read notifications";
const api = await request.newContext();
async function unread() {
  const response = await api.post(base + '/api/workspaces/summaries', {
    data: { archived: false },
  });
  assert(response.ok());
  return (await response.json()).data.summaries.find(
    (x) => x.workspace_id === workspace
  ).has_unseen_turns;
}
async function seedUnread() {
  const response = await api.put(
    base + '/api/workspaces/' + workspace + '/unread',
    { headers: { Origin: base } }
  );
  assert(response.ok());
  assert.equal(await unread(), true);
}
const issueResponse = await api.get(
  base + '/v1/fallback/issues?project_id=' + project
);
assert(issueResponse.ok());
const ownIssue = (await issueResponse.json()).issues.find(
  (x) => x.id === issue
);
assert(ownIssue);
const browser = await chromium.launch({
  executablePath:
    '/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',
  headless: true,
  args: ['--no-sandbox'],
});
const results = [];
try {
  for (const width of [1440, 393]) {
    const mobile = width === 393;
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      isMobile: mobile,
      hasTouch: mobile,
    });
    const page = await context.newPage();
    const reads = [],
      errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (
        response.request().method() === 'PUT' &&
        new URL(response.url()).pathname ===
          '/api/workspaces/' + workspace + '/seen'
      )
        reads.push(response.status());
    });
    await page.route(/\/(api|v1)\//, async (route) => {
      const req = route.request(),
        path = new URL(req.url()).pathname;
      if (
        ['GET', 'HEAD'].includes(req.method()) ||
        (req.method() === 'POST' && path === '/api/workspaces/summaries') ||
        (req.method() === 'PUT' &&
          path === '/api/workspaces/' + workspace + '/seen')
      )
        return route.continue();
      return route.fulfill({ json: { success: true, data: null } });
    });
    async function openWorkspace() {
      if (mobile) {
        await page
          .locator('.phone-status-tabs')
          .getByRole('button', { name: 'All', exact: true })
          .click({ timeout: 60000 });
        const row = page
          .locator('.phone-task-row')
          .filter({
            has: page.getByRole('button', {
              name: 'Actions for ' + ownIssue.simple_id,
              exact: true,
            }),
          });
        await row
          .getByRole('button', { name: /Open conversation/ })
          .click({ timeout: 60000 });
      } else {
        // The nested workspace card, not its parent issue card. Clicking the
        // parent changes routes and previously hid the actual reselect failure.
        await page
          .locator('div[role="button"].bg-panel')
          .filter({ has: page.getByText(title, { exact: true }) })
          .last()
          .click({ timeout: 60000 });
      }
      await page
        .getByRole('button', { name: 'Close conversation view', exact: true })
        .waitFor({ timeout: 60000 });
    }
    async function expectRead() {
      for (let n = 0; n < 100 && (await unread()); n++)
        await page.waitForTimeout(100);
      assert.equal(
        await unread(),
        false,
        'Conversation opening must persist native seen state'
      );
    }
    try {
      await seedUnread();
      await page.goto(base + '/projects/' + project, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      await openWorkspace();
      await expectRead();
      const result = { width, initialOpenPersisted: true };
      await seedUnread();
      const count = reads.length;
      await page.waitForTimeout(4500);
      assert.equal(
        await unread(),
        true,
        'Polling must preserve a newly unread completion while chat stays open'
      );
      assert.equal(reads.length, count);
      result.newCompletionPreserved = true;
      const selectedUrl = page.url();
      if (mobile)
        await page
          .getByRole('button', { name: 'Close conversation view', exact: true })
          .click();
      await openWorkspace();
      await expectRead();
      assert.equal(page.url(), selectedUrl);
      result.reselectPersisted = true;
      result.sameRouteClick = !mobile;
      result.newReadStatuses = reads.slice(count);
      assert(result.newReadStatuses.includes(200));
      // Reload from the server, not just local query cache.
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
      await page
        .getByRole('button', { name: 'Close conversation view', exact: true })
        .waitFor({ timeout: 60000 });
      assert.equal(await unread(), false);
      result.reloadVerified = true;
      result.pageErrors = errors;
      assert.deepEqual(errors, []);
      result.passed = true;
      results.push(result);
    } finally {
      // Restore only the owned unread flag through the standard API if needed.
      if (await unread()) {
        const response = await api.put(
          base + '/api/workspaces/' + workspace + '/seen',
          { headers: { Origin: base } }
        );
        assert(response.ok());
      }
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await context.close();
    }
  }
} finally {
  await browser.close();
  await api.dispose();
  await fs.writeFile(
    output,
    JSON.stringify(
      {
        workspace,
        results,
        passed: results.length === 2 && results.every((x) => x.passed),
      },
      null,
      2
    ) + '\n'
  );
}
console.log(JSON.stringify({ results }));
