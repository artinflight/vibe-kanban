// Real branch UI + real disposable Python sidechat; Vibe writes are blocked.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
const { chromium, request } = await import(
  process.env.PLAYWRIGHT_MODULE || '/usr/lib/node_modules/playwright/index.mjs'
);
const output = process.env.VK_TEST_OUTPUT;
const base = process.env.VK_TEST_BASE;
if (!output || !base)
  throw Error('Set VK_TEST_OUTPUT on SSD and VK_TEST_BASE to branch frontend');
await fs.mkdir(output, { recursive: true });
const project =
  process.env.VK_TEST_PROJECT_ID ?? '1cf19067-4055-4432-bbc1-581919f9185d';
const otherProject =
  process.env.VK_TEST_OTHER_PROJECT_ID ??
  '3e9a9fda-2bd6-414f-ba93-a4a7913fede0';
const lookup = await request.newContext();
const response = await lookup.get(
  base + '/v1/fallback/issues?project_id=' + project
);
const payload = await response.json();
const available = Array.isArray(payload)
  ? payload
  : (payload.issues ?? payload.data);
const selectedIssue =
  available.find((item) => item.id === process.env.VK_TEST_ISSUE_ID) ??
  available.find((item) => item.title.includes('Project Dot Chat')) ??
  available[0];
if (!selectedIssue)
  throw Error(
    'Browser acceptance requires one existing issue in the selected project'
  );
const issue = selectedIssue.id;
await lookup.dispose();
const browser = await chromium.launch({
  executablePath:
    process.env.CHROMIUM_PATH ||
    '/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',
  headless: true,
  args: ['--no-sandbox'],
});
const report = [];
try {
  for (const width of [393, 1440]) {
    const fixture = spawn(
      'python3',
      [
        '-B',
        'scripts/dot-sidechat/project_browser_fixture.py',
        '--output',
        output,
        '--project',
        project,
        '--project',
        otherProject,
        '--issue',
        issue,
      ],
      { stdio: ['ignore', 'ignore', 'pipe', 'pipe'] }
    );
    let privateReady = '',
      fixtureError = '';
    fixture.stdio[3].on('data', (x) => (privateReady += x));
    fixture.stderr.on('data', (x) => (fixtureError += x));
    await new Promise((resolve, reject) => {
      fixture.stdio[3].on('end', resolve);
      fixture.on('exit', (code) => {
        if (code) reject(Error('Fixture failed: ' + fixtureError));
      });
    });
    const ready = JSON.parse(privateReady);
    const fixtureOrigin = 'http://127.0.0.1:' + ready.port;
    const http = await request.newContext();
    const context = await browser.newContext({
      viewport: { width, height: 950 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const page = await context.newPage();
    const writes = [],
      sidechat = [],
      errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    try {
      await page.route(/\/(api|v1)\//, async (route) => {
        const req = route.request(),
          url = new URL(req.url()),
          method = req.method();
        if (url.pathname.startsWith('/api/dot-sidechat/')) {
          const headers = {
            Host: 'fixture.invalid',
            Origin: 'https://fixture.invalid',
            'X-Dot-Request': '1',
            Cookie: '__Secure-vibe-dot=' + ready.token,
          };
          const csrf = await req.headerValue('x-dot-csrf');
          if (csrf) headers['X-Dot-CSRF'] = csrf;
          if (req.postDataBuffer())
            headers['Content-Type'] = 'application/json';
          const response = await http.fetch(
            fixtureOrigin + url.pathname + url.search,
            {
              method,
              headers,
              ...(req.postDataBuffer() ? { data: req.postDataBuffer() } : {}),
              maxRedirects: 0,
            }
          );
          const body = await response.body();
          sidechat.push({
            path: url.pathname,
            method,
            status: response.status(),
          });
          return route.fulfill({
            status: response.status(),
            contentType: 'application/json',
            body,
          });
        }
        if (
          ['GET', 'HEAD'].includes(method) ||
          (method === 'POST' && url.pathname === '/api/workspaces/summaries')
        )
          return route.continue();
        writes.push({ path: url.pathname, method });
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: null, txid: 1 }),
        });
      });
      await page.goto(base + '/projects/' + project, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      await page
        .getByRole('button', { name: 'Open project sidebar', exact: true })
        .waitFor({ timeout: 60000 });
      if (width < 768)
        await page
          .getByRole('button', { name: 'Open project sidebar', exact: true })
          .click();
      const sidebar = page.getByRole('complementary', {
        name: 'Project collaboration',
        exact: true,
      });
      await sidebar
        .getByRole('textbox', { name: 'Message Dot', exact: true })
        .fill('Think across the project');
      await sidebar
        .getByRole('button', { name: /^Send to Dot/, exact: true })
        .click();
      await sidebar
        .getByText('Saved · awaiting delivery', { exact: true })
        .waitFor();
      await http.post(fixtureOrigin + '/__qa/reply', { data: { project } });
      await sidebar
        .getByRole('button', { name: 'Refresh conversation', exact: true })
        .click();
      await sidebar
        .getByText('Project reply needs your decision', { exact: true })
        .waitFor();
      await sidebar
        .getByRole('button', { name: 'Resolve Dot question', exact: true })
        .click();
      await sidebar
        .getByRole('button', { name: 'Reopen Dot question', exact: true })
        .waitFor();
      await sidebar
        .getByRole('tab', { name: 'Shared plan', exact: true })
        .click();
      const plan = sidebar.getByRole('region', {
        name: 'Shared project plan',
        exact: true,
      });
      await plan.getByRole('button', { name: 'Add item', exact: true }).click();
      await plan.getByLabel('Title', { exact: true }).fill('Linked acceptance');
      await plan
        .getByLabel('Link Vibe tasks', { exact: true })
        .selectOption(issue);
      assert(await plan.getByRole('checkbox').isDisabled());
      await plan
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await plan
        .getByRole('button', { name: 'Edit Linked acceptance', exact: true })
        .waitFor();
      await plan
        .getByText('In progress · From linked tasks', { exact: true })
        .waitFor();
      await plan
        .getByRole('button', { name: 'Add milestone', exact: true })
        .click();
      await plan.getByLabel('Title', { exact: true }).fill('Project launch');
      await plan.getByLabel('Target date', { exact: true }).fill('2026-11-01');
      await plan
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await plan
        .getByRole('button', { name: 'Edit Project launch', exact: true })
        .waitFor();
      await plan
        .getByRole('button', { name: 'Add decision', exact: true })
        .click();
      await plan
        .getByLabel('Title', { exact: true })
        .fill('Use canonical tasks');
      await plan.getByLabel('Decision recorded', { exact: true }).check();
      await plan
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await plan.getByText('Recorded', { exact: true }).waitFor();
      await plan
        .getByRole('button', { name: 'Add question', exact: true })
        .click();
      await plan
        .getByLabel('Title', { exact: true })
        .fill('Which release window?');
      await plan
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await plan
        .getByRole('button', {
          name: 'Edit Which release window?',
          exact: true,
        })
        .waitFor();
      await page.screenshot({
        path: output + `/project-plan-${width}.png`,
        fullPage: true,
      });
      // Mobile Back closes only the panel, leaving the project board in place.
      if (width < 768) {
        await page.goBack();
        await sidebar.waitFor({ state: 'hidden' });
        assert(new URL(page.url()).pathname === '/projects/' + project);
        await page
          .getByRole('button', { name: 'Open project sidebar', exact: true })
          .click();
        await sidebar
          .getByRole('tab', { name: 'Shared plan', exact: true })
          .click();
      }
      // A stale concurrent edit must fail rather than overwrite dot's changes.
      await plan
        .getByRole('button', {
          name: 'Edit Which release window?',
          exact: true,
        })
        .click();
      const entriesResponse = await http.get(
        fixtureOrigin + '/api/dot-sidechat/project-plan?project=' + project,
        {
          headers: {
            Host: 'fixture.invalid',
            'X-Dot-Request': '1',
            Cookie: '__Secure-vibe-dot=' + ready.token,
          },
        }
      );
      const entry = (await entriesResponse.json()).entries.find(
        (e) => e.title === 'Which release window?'
      );
      await http.post(fixtureOrigin + '/__qa/conflict', {
        data: { project, entry: entry.id },
      });
      await plan.getByLabel('Notes', { exact: true }).fill('Stale local edit');
      await plan
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await plan
        .getByRole('alert')
        .filter({ hasText: 'changed elsewhere' })
        .waitFor();
      await page.reload({ waitUntil: 'domcontentloaded' });
      await sidebar.waitFor({ state: 'visible' });
      await sidebar
        .getByRole('tab', { name: 'Shared plan', exact: true })
        .click();
      await plan
        .getByRole('button', { name: 'Retry same save', exact: true })
        .waitFor();
      assert.equal(
        await plan.getByLabel('Notes', { exact: true }).inputValue(),
        'Stale local edit'
      );
      await plan.getByRole('button', { name: 'Cancel', exact: true }).click();
      await plan
        .getByText('Edited concurrently by dot', { exact: true })
        .waitFor();
      assert.deepEqual(
        writes,
        [],
        'Project sidebar performs no Vibe mutations'
      );
      // Opening a canonical task closes the mobile history step and uses Vibe navigation.
      await plan
        .getByRole('button', {
          name: selectedIssue.simple_id + ' · ' + selectedIssue.title,
          exact: true,
        })
        .click();
      await page.waitForURL('**/issues/' + issue);
      await page.goto(base + '/projects/' + otherProject, {
        waitUntil: 'domcontentloaded',
      });
      if (width < 768)
        await page
          .getByRole('button', { name: 'Open project sidebar', exact: true })
          .click();
      await sidebar
        .getByRole('tab', { name: 'Shared plan', exact: true })
        .click();
      await plan.getByText('No checklist yet.', { exact: true }).waitFor();
      assert.equal(
        await plan.getByText('Linked acceptance', { exact: true }).count(),
        0
      );
      await sidebar.getByRole('tab', { name: /Dot Chat/ }).click();
      await sidebar
        .getByRole('textbox', { name: 'Message Dot', exact: true })
        .waitFor();
      assert.equal(
        await sidebar
          .getByText('Think across the project', { exact: true })
          .count(),
        0
      );
      await page.screenshot({
        path: output + `/project-chat-${width}.png`,
        fullPage: true,
      });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 1
      );
      assert.equal(overflow, false, 'No document horizontal overflow');
      assert(
        writes.every(
          (item) =>
            item.method === 'PATCH' && item.path === '/v1/issues/' + issue
        ),
        'Only the existing issue panel may attempt its normal autosave; every mutation is blocked'
      );
      assert.deepEqual(errors, [], 'No browser errors');
      report.push({
        width,
        passed: true,
        sidechatRequests: sidechat.length,
        blockedVibeWrites: writes.length,
      });
    } catch (error) {
      await page.screenshot({
        path: output + '/failure-' + width + '.png',
        fullPage: true,
      });
      await fs.writeFile(
        output + '/failure-' + width + '.txt',
        await page.locator('body').innerText()
      );
      await fs.writeFile(
        output + `/transport-${width}.json`,
        JSON.stringify(sidechat, null, 2)
      );
      throw error;
    } finally {
      await context.close();
      await http.dispose();
      fixture.kill('SIGTERM');
      await new Promise((resolve) => fixture.once('exit', resolve));
    }
  }
  await fs.writeFile(
    output + '/browser-results.json',
    JSON.stringify(report, null, 2)
  );
  console.log(
    'PASS real project sidebar desktop/mobile, real isolated sidechat sends/replies/plans, links, conflict/reload, Back, project isolation; zero Vibe writes',
    report
  );
} finally {
  await browser.close();
}
