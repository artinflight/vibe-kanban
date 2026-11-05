import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
const root = process.env.VK_TEST_OUTPUT,
  base = 'https://vibe.local';
const { chromium, request } = await import(process.env.PLAYWRIGHT_MODULE);
await fs.mkdir(root, { recursive: true, mode: 0o700 });
async function control(action, fixture = {}) {
  const p = spawn('python3', ['-B', process.env.VK_DOT_QA_CONTROL, action], {
    env: process.env,
    stdio: ['pipe', 'pipe', 'pipe', 'pipe'],
  });
  let privateResult = '',
    errors = '';
  p.stdio[3].on('data', (x) => (privateResult += x));
  p.stderr.on('data', (x) => (errors += x));
  p.stdin.end(JSON.stringify(fixture));
  await new Promise((resolve, reject) => {
    p.on('error', reject);
    p.on('exit', (code) =>
      code === 0 ? resolve() : reject(Error('QA control failed: ' + errors))
    );
  });
  return JSON.parse(privateResult);
}
const reports = [];
const browser = await chromium.launch({
  headless: true,
  chromiumSandbox: true,
  executablePath: process.env.CHROMIUM_PATH,
});
try {
  for (const width of [393, 1440]) {
    let fixture;
    let context;
    const api = await request.newContext({ ignoreHTTPSErrors: true });
    try {
      fixture = await control('setup');
      context = await browser.newContext({
        viewport: { width, height: 950 },
        isMobile: width < 768,
        hasTouch: width < 768,
        ignoreHTTPSErrors: true,
      });
      const page = await context.newPage(),
        calls = [],
        blocked = [],
        errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      // Only this owned page uses a ten-minute synthetic QA identity. Preserve all
      // real paired sessions, browser credentials and automation subscriptions.
      await page.route(/\/(api|v1)\//, async (route) => {
        const r = route.request(),
          url = new URL(r.url()),
          method = r.method();
        if (url.pathname.startsWith('/api/dot-sidechat/')) {
          const headers = {
            'X-Dot-Request': (await r.headerValue('x-dot-request')) ?? '',
            Cookie: '__Secure-vibe-dot=' + fixture.token,
          };
          for (const h of [
            'origin',
            'content-type',
            'x-dot-csrf',
            'sec-fetch-site',
          ]) {
            const value = await r.headerValue(h);
            if (value) headers[h] = value;
          }
          const response = await api.fetch(r.url(), {
            method,
            headers,
            ...(r.postDataBuffer() ? { data: r.postDataBuffer() } : {}),
            maxRedirects: 0,
          });
          const safeHeaders = { ...response.headers() };
          delete safeHeaders['set-cookie'];
          calls.push({ path: url.pathname, method, status: response.status() });
          return route.fulfill({
            status: response.status(),
            headers: safeHeaders,
            body: await response.body(),
          });
        }
        if (
          ['GET', 'HEAD'].includes(method) ||
          (method === 'POST' && url.pathname === '/api/workspaces/summaries')
        )
          return route.continue();
        blocked.push({ path: url.pathname, method });
        return route.fulfill({ json: { success: true, data: null } });
      });
      // Start in the list: the retained reply has not been made visible.
      await page.goto(base + '/workspaces', {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      await page
        .getByLabel('Dot unread replies: 1', { exact: true })
        .first()
        .waitFor({ timeout: 60000 });
      await page
        .getByLabel('Dot Needs Attention: 1', { exact: true })
        .first()
        .waitFor({ state: 'visible' });
      assert.deepEqual(await control('inspect', fixture), {
        unread: 1,
        attention: 1,
        coding_unchanged: true,
        outbound_attempts: 0,
      });
      await page.goto(base + '/workspaces/' + fixture.workspace, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      if (width < 768)
        await page
          .getByRole('navigation', { name: 'Primary navigation' })
          .getByRole('button', { name: 'Dot', exact: true })
          .click();
      const panel = page.getByRole('region', {
        name: 'Private Dot conversation',
      });
      await panel.waitFor({ state: 'visible', timeout: 60000 });
      await page.waitForFunction(() =>
        document.querySelector('.dot-reply-actions button')
      );
      await panel.locator('.dot-history').evaluate((n) => {
        n.scrollTop = n.scrollHeight;
        n.dispatchEvent(new Event('scroll'));
      });
      await page.waitForTimeout(300);
      let state = await control('inspect', fixture);
      assert.equal(state.unread, 0);
      assert.equal(state.attention, 1);
      assert.ok(state.coding_unchanged);
      await page.waitForFunction(
        () => !document.querySelector('[aria-label="Dot unread replies: 1"]')
      );
      if (width < 768)
        await page
          .getByRole('navigation', { name: 'Primary navigation' })
          .getByRole('button', { name: /Wksps|Workspaces/ })
          .click();
      await page
        .getByLabel('Dot Needs Attention: 1', { exact: true })
        .first()
        .waitFor({ state: 'visible' });
      const afterReadBlocked = blocked.length;
      await page.reload({ waitUntil: 'domcontentloaded' });
      if (width < 768)
        await page
          .getByRole('navigation', { name: 'Primary navigation' })
          .getByRole('button', { name: 'Dot', exact: true })
          .click();
      await panel.waitFor({ state: 'visible' });
      await panel
        .getByRole('button', { name: 'Resolve Dot question', exact: true })
        .waitFor();
      state = await control('inspect', fixture);
      assert.equal(state.unread, 0);
      assert.equal(state.attention, 1);
      assert.ok(state.coding_unchanged);
      await panel.screenshot({
        path: root + '/' + width + '-read-attention.png',
      });
      await panel
        .getByRole('button', { name: 'Resolve Dot question', exact: true })
        .click();
      await panel
        .getByRole('button', { name: 'Reopen Dot question', exact: true })
        .waitFor();
      state = await control('inspect', fixture);
      assert.equal(state.unread, 0);
      assert.equal(state.attention, 0);
      assert.ok(state.coding_unchanged);
      await page.waitForFunction(
        () => !document.querySelector('[aria-label="Dot Needs Attention: 1"]')
      );
      await panel
        .getByRole('button', { name: 'Reopen Dot question', exact: true })
        .click();
      await panel
        .getByRole('button', { name: 'Resolve Dot question', exact: true })
        .waitFor();
      assert.equal((await control('inspect', fixture)).attention, 1);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1
        ),
        true
      );
      assert.deepEqual(errors, []);
      assert.ok(
        calls.some((c) => c.path.endsWith('/seen') && c.status === 200)
      );
      assert.ok(
        calls.some((c) => c.path.endsWith('/attention') && c.status === 200)
      );
      reports.push({
        width,
        actualServedFrontend: true,
        actualLiveSidechat: true,
        unreadClearedOnlyByVisibleReply: true,
        attentionSurvivedReadAndReload: true,
        explicitResolveAndReopen: true,
        codingAgentFlagsUnchanged: state.coding_unchanged,
        outboundAttempts: state.outbound_attempts,
        errors,
        calls,
        otherWritesBlocked: blocked.length,
      });
      console.log(
        'PASS live ' +
          width +
          ': unread, persistent attention, resolve/reopen, coding-agent isolation; bounded synthetic data, zero wake attempts.'
      );
    } finally {
      if (context) await context.close();
      await api.dispose();
      if (fixture) await control('cleanup', fixture);
    }
  }
} finally {
  await browser.close();
  await fs.writeFile(root + '/results.json', JSON.stringify(reports, null, 2));
}
