// Isolated synthetic browser acceptance. Never connects to Vibe or a paired browser.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import {
  bundleNotifications,
  state,
  transport,
} from './notification-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output) throw Error('Set VK_TEST_OUTPUT to a mounted SSD task directory');
await mkdir(output, { recursive: true });
const bundle = await bundleNotifications();
const release = process.env.DOT_BASELINE_RELEASE;
let css = '';
if (release) {
  const html = await readFile(release + '/index.html', 'utf8');
  const asset = html.match(/href="(\/assets\/[^\"]+\.css)"/)[1];
  css = await readFile(release + asset, 'utf8');
}
let s;
const server = createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/dot-sidechat/')) {
      let body = '';
      for await (const chunk of req) body += chunk;
      const response = await transport(s)(req.url, {
        method: req.method,
        body: body || undefined,
        headers: { 'X-Dot-CSRF': req.headers['x-dot-csrf'] },
      });
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(await response.json()));
    } else if (req.url === '/fixture.js') {
      res.setHeader('Content-Type', 'text/javascript');
      res.end(bundle.js);
    } else if (req.url === '/fixture.css') {
      res.setHeader('Content-Type', 'text/css');
      res.end(
        css +
          bundle.css +
          '\nbody{margin:0} #workspace-list{max-width:100%} .new-design{padding:8px;min-height:100vh} #dot-slot{width:100%;max-width:520px}'
      );
    } else if (req.url === '/') {
      res.end(
        '<html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/fixture.css"><body><div id="root"></div><script src="/fixture.js"></script></body></html>'
      );
    } else {
      res.statusCode = 404;
      res.end();
    }
  } catch (error) {
    res.statusCode = 500;
    res.end(String(error));
  }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
  args: ['--no-sandbox'],
});
try {
  for (const width of [390, 1440]) {
    s = state(true);
    const context = await browser.newContext({
      viewport: { width, height: 950 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const page = await context.newPage();
    await page.goto(origin);
    await page
      .locator('[aria-label="Dot unread replies: 1"]')
      .first()
      .waitFor();
    await page.waitForTimeout(150);
    assert.equal(s.reads.length, 0, 'Mounted hidden panel must not read');
    const colors = await page
      .locator('[data-dot-indicators] span[aria-label]')
      .first()
      .evaluate((n) => getComputedStyle(n).color);
    assert.match(colors, /rgb\(\d+, \d+, \d+\)/);
    const readable = await page
      .locator('#workspace-list [data-dot-indicators] > [aria-label]')
      .evaluateAll((nodes) =>
        nodes.every((n) => {
          const r = n.getBoundingClientRect();
          for (let p = n; p; p = p.parentElement) {
            const style = getComputedStyle(p);
            if (Number(style.opacity) < 1) return false;
            if (/hidden|clip/.test(style.overflowX + style.overflowY)) {
              const bounds = p.getBoundingClientRect();
              if (
                r.left < bounds.left - 1 ||
                r.right > bounds.right + 1 ||
                r.bottom > bounds.bottom + 1
              )
                return false;
            }
          }
          return true;
        })
      );
    assert.ok(
      readable,
      'Dot indicators must remain readable and unclipped in a narrow sidebar with coding status and file stats'
    );
    await page.screenshot({
      path: `${output}/dot-notifications-${width}-unread.png`,
      fullPage: true,
    });
    await page.click('#toggle-dot');
    // Showing a previously hidden long conversation leaves its reply end below the viewport.
    await page.locator('.dot-history').evaluate((n) => {
      n.scrollTop = 0;
      n.dispatchEvent(new Event('scroll'));
    });
    await page.waitForTimeout(200);
    assert.equal(
      s.reads.length,
      0,
      'Long reply above its end must stay unread'
    );
    await page.locator('.dot-history').evaluate((n) => {
      n.scrollTop = n.scrollHeight;
      n.dispatchEvent(new Event('scroll'));
    });
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Dot unread replies: 1"]')
    );
    assert.equal(s.reads.length, 1);
    assert.equal(
      await page.locator('[aria-label="Dot Needs Attention: 1"]').count(),
      3
    );
    assert.equal(
      await page.locator('#coding-unread').textContent(),
      'Coding-agent unread remains'
    );
    const buttonHeight = await page
      .locator('[aria-label="Resolve Dot question"]')
      .evaluate((n) => n.getBoundingClientRect().height);
    assert.ok(buttonHeight >= (width < 768 ? 44 : 36));
    await page.screenshot({
      path: `${output}/dot-notifications-${width}-read.png`,
      fullPage: true,
    });
    await Promise.all([
      page.waitForResponse((r) => r.url().includes('workspace=22222222')),
      page.click('#sibling'),
    ]);
    assert.equal(s.reads.length, 1);
    await page.reload();
    await page
      .locator('[aria-label="Dot Needs Attention: 1"]')
      .first()
      .waitFor();
    assert.equal(
      await page.locator('[aria-label="Dot unread replies: 1"]').count(),
      0
    );
    await page.click('#toggle-dot');
    await page.locator('[aria-label="Resolve Dot question"]').click();
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Dot Needs Attention: 1"]')
    );
    assert.ok(s.resolved);
    assert.ok(s.requests.every((r) => r.url.startsWith('/api/dot-sidechat/')));
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth
      ),
      true,
      'No horizontal phone overflow'
    );
    console.log(
      `PASS Chromium ${width}: separate badges (${colors}), hidden/long reply visibility, sibling/reload persistence, explicit resolution, independent agent state.`
    );
    await context.close();
  }
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
