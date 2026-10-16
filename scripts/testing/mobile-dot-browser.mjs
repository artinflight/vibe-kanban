// Render the real branch UI with local-only Dot responses; never send a prompt.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const base = process.env.VK_TEST_BASE ?? 'http://127.0.0.1:3002';
const output = process.env.VK_TEST_OUTPUT;
if (!output)
  throw new Error('Set VK_TEST_OUTPUT to a directory on mounted SSD');
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE ?? '/usr/lib/node_modules/playwright/index.mjs'
);
const physical = Boolean(process.env.VK_TEST_CDP);
const browser = physical
  ? await chromium.connectOverCDP(process.env.VK_TEST_CDP, { timeout: 15000 })
  : await chromium.launch({ headless: true, chromiumSandbox: true });
const reports = [];
const ownedPages = [];
await fs.mkdir(output, { recursive: true });
try {
  const widths = physical ? [null] : [360, 393, 412, 844, 1440];
  for (const width of widths) {
    const context = physical
      ? browser.contexts()[0]
      : await browser.newContext({
          viewport: { width, height: width === 844 ? 393 : 852 },
          isMobile: width < 768,
          hasTouch: width < 768,
        });
    const page = await context.newPage();
    ownedPages.push(page);
    if (physical) await page.bringToFront();
    // Guard this test's page only, including on shared Android Chrome.
    let paired = false;
    let failSend = true;
    const sends = [];
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route(/\/(api|v1)\//, async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.startsWith('/api/dot-sidechat/')) {
        const action = path.split('/').at(-1);
        if (action === 'pair') {
          paired = true;
          return route.fulfill({
            json: {
              csrf: 'fixture-only',
              session_id: 'fixture',
              expires: null,
            },
          });
        }
        if (!paired) return route.fulfill({ status: 401, json: {} });
        if (action === 'session')
          return route.fulfill({
            json: {
              csrf: 'fixture-only',
              session_id: 'fixture',
              expires: null,
            },
          });
        if (action === 'send') {
          sends.push(request.postDataJSON());
          if (failSend) return route.fulfill({ status: 503, json: {} });
          return route.fulfill({ json: { accepted: true } });
        }
        if (action === 'thread')
          return route.fulfill({
            json: {
              thread: { id: 'fixture-thread' },
              scope: {
                issue_label: 'VK mobile Dot test ' + 'long-label-'.repeat(12),
                workspace_label: 'Mobile workspace ' + 'context-'.repeat(12),
              },
              messages: Array.from({ length: 25 }, (_, i) => ({
                id: 'fixture-' + i,
                seq: i + 1,
                role: i % 2 ? 'dot' : 'owner',
                body:
                  'Synthetic mobile history ' +
                  i +
                  '\n' +
                  'Long text '.repeat(12),
                workspace: 'fixture',
                created: 0,
              })),
              receipts: {},
              through: 25,
              next_after: null,
            },
          });
        return route.fulfill({ json: {} });
      }
      if (
        ['GET', 'HEAD'].includes(request.method()) ||
        path === '/api/workspaces/summaries'
      )
        return route.continue();
      return route.fulfill({ json: { success: true, data: null } });
    });
    const response = await page.request.get(
      (process.env.VK_TEST_BACKEND ?? base) + '/api/workspaces'
    );
    const data = (await response.json()).data;
    const workspaces = Array.isArray(data) ? data : data.workspaces;
    const own = workspaces.find(
      (item) => item.branch === 'vk/2e35-vk-mobile-dot-in'
    );
    assert.ok(own, 'Task workspace exists');
    await page.goto(base + '/workspaces/' + own.id, {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    const mobile = physical || width < 768;
    if (mobile)
      await page
        .getByRole('navigation', { name: 'Primary navigation' })
        .getByRole('button', { name: 'Dot', exact: true })
        .click();
    const pairing = page.getByRole('region', { name: 'Pair private Dot chat' });
    await pairing.waitFor({ state: 'visible', timeout: 60000 });
    const code = pairing.getByLabel('Pairing code');
    await code.fill('synthetic-pairing-fixture');
    await pairing.getByRole('button', { name: 'Pair browser' }).click();
    const panel = page.getByRole('region', {
      name: 'Private Dot conversation',
    });
    await panel.waitFor({ state: 'visible' });
    const draft = panel.getByRole('textbox');
    await draft.fill('Synthetic draft; no external delivery');
    if (mobile) {
      const nav = page.getByRole('navigation', { name: 'Primary navigation' });
      await nav.getByRole('button', { name: 'Chat', exact: true }).click();
      await nav.getByRole('button', { name: 'Dot', exact: true }).click();
      assert.equal(
        await draft.inputValue(),
        'Synthetic draft; no external delivery'
      );
      assert.equal(await page.locator('.dot-panel').count(), 1);
      assert.equal(
        await nav
          .getByRole('button', { name: 'Dot', exact: true })
          .getAttribute('aria-current'),
        'page'
      );
    }
    await panel
      .getByRole('button', { name: 'Send to Dot ↑', exact: true })
      .click();
    await panel.getByRole('alert').waitFor();
    assert.equal(
      await draft.inputValue(),
      'Synthetic draft; no external delivery'
    );
    failSend = false;
    await panel
      .getByRole('button', { name: 'Retry same message ↑', exact: true })
      .click();
    await page.waitForFunction(
      () => document.querySelector('.dot-composer textarea')?.value === ''
    );
    assert.equal(sends.length, 2);
    assert.deepEqual(sends[0], sends[1], 'Retries reuse the same request/body');
    let keyboard = null;
    if (physical) {
      const initialHeight = await page.evaluate(() => visualViewport.height);
      await draft.tap();
      await page.waitForFunction(
        (before) => visualViewport.height < before - 100,
        initialHeight,
        { timeout: 15000 }
      );
      await panel
        .getByRole('button', { name: 'Send to Dot ↑', exact: true })
        .scrollIntoViewIfNeeded();
      keyboard = await page.evaluate(() => ({
        height: visualViewport.height,
        offset: visualViewport.offsetTop,
        composer: document
          .querySelector('.dot-composer')
          .getBoundingClientRect()
          .toJSON(),
      }));
      assert.ok(
        keyboard.height < initialHeight - 100,
        'Real software keyboard reduces the viewport'
      );
    }
    await page.screenshot({
      path: output + '/' + (physical ? 's25-full' : width + '-full') + '.png',
    });
    const geometry = await panel.evaluate((element) => {
      const send = element
        .querySelector('.dot-composer-actions button')
        .getBoundingClientRect();
      const input = element.querySelector('textarea');
      return {
        width: innerWidth,
        height: innerHeight,
        inputFont: getComputedStyle(input).fontSize,
        sendHeight: send.height,
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
      };
    });
    assert.equal(geometry.overflow, false);
    if (mobile) {
      assert.equal(geometry.inputFont, '16px');
      assert.ok(geometry.sendHeight >= 44);
      if (!physical) {
        await page.setViewportSize({ width, height: 430 });
        await draft.focus();
        await panel
          .getByRole('button', { name: 'Send to Dot ↑', exact: true })
          .scrollIntoViewIfNeeded();
        assert.ok(await draft.isVisible());
      }
    }
    await page.screenshot({
      path: output + '/' + (physical ? 's25' : width) + '.png',
    });
    reports.push({
      viewport: physical ? 'S25+' : width,
      geometry,
      mockSends: sends.length,
      keyboard,
      errors,
    });
    assert.deepEqual(errors, []);
    await page.close();
    if (!physical) await context.close();
  }
} finally {
  for (const page of ownedPages) if (!page.isClosed()) await page.close();
  await fs.writeFile(
    output + '/results.json',
    JSON.stringify(reports, null, 2)
  );
  // Disconnect from shared Chrome; do not close the operator's browser.
  if (!physical) await browser.close();
}
console.log(JSON.stringify(reports));
if (physical) process.exit(0);
