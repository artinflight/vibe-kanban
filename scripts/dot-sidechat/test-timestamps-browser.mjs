// Synthetic transport only: exercises the actual container, panel and stylesheet.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import {
  bundleNotifications,
  state,
  transport,
} from './notification-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output) throw Error('Set VK_TEST_OUTPUT to a mounted SSD directory');
await mkdir(output, { recursive: true });
const bundle = await bundleNotifications();
const cases = [
  ['2026-01-01T00:30:00Z', 'Dec 31, 2025, 7:30 PM EST'],
  ['2026-03-08T06:59:00Z', 'Mar 8, 2026, 1:59 AM EST'],
  ['2026-03-08T07:00:00Z', 'Mar 8, 2026, 3:00 AM EDT'],
  ['2026-11-01T05:30:00Z', 'Nov 1, 2026, 1:30 AM EDT'],
  ['2026-11-01T06:30:00Z', 'Nov 1, 2026, 1:30 AM EST'],
];
let s;
const css = await readFile(
  'packages/web-core/src/pages/workspaces/dot-sidechat.css',
  'utf8'
);
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
          '\nbody{margin:0} #workspace-list{display:none} #dot-slot{width:100%;max-width:520px}'
      );
    } else {
      res.end(
        '<html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/fixture.css"><div id="root"></div><script src="/fixture.js"></script></html>'
      );
    }
  } catch (e) {
    res.statusCode = 500;
    res.end(String(e));
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
  args: ['--no-sandbox'],
});
const results = [];
try {
  for (const project of [false, true])
    for (const width of [390, 1440]) {
      s = state();
      s.messages = cases.map(([iso], i) => ({
        id: 'history-' + i,
        seq: i + 1,
        role: i % 2 ? 'owner' : 'dot',
        body: 'Retained message',
        workspace: '11111111-1111-4111-8111-111111111111',
        created: Date.parse(iso) / 1000,
        seen: false,
        manual_unread: true,
        attention: i === 0 ? { kind: 'action', resolved: false } : null,
        ...(i === 0
          ? {
              dispatch_note: {
                workspace_id: '11111111-1111-4111-8111-111111111111',
                execution_id: 'fixture',
              },
            }
          : {}),
      }));
      const context = await browser.newContext({
        viewport: { width, height: 950 },
        timezoneId: 'Asia/Tokyo',
        isMobile: width < 768,
        hasTouch: width < 768,
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      await page.goto(
        `http://127.0.0.1:${server.address().port}/${project ? '?project' : ''}`
      );
      await page.click('#toggle-dot');
      await page.locator('.dot-message time').last().waitFor();
      assert.deepEqual(
        await page.locator('.dot-message time').allTextContents(),
        cases.map((c) => c[1])
      );
      assert.deepEqual(
        await page
          .locator('.dot-message time')
          .evaluateAll((ns) => ns.map((n) => n.dateTime)),
        cases.map((c) => new Date(c[0]).toISOString())
      );
      assert.equal(
        await page.locator('.dot-message time').first().getAttribute('title'),
        'Eastern time · America/Toronto'
      );
      // A poll replaces the existing timestamp/body; never substitute render time.
      s.messages[0] = {
        ...s.messages[0],
        created: Date.parse('2026-07-01T04:01:00Z') / 1000,
        body: 'Updated retained message',
      };
      s.messages.push({
        ...s.messages[1],
        id: 'new-message',
        seq: 6,
        created: Date.parse('2026-07-02T03:59:00Z') / 1000,
        body: 'New message',
      });
      await page
        .getByRole('button', { name: 'Refresh conversation', exact: true })
        .click();
      await page.locator('#message-new-message time').waitFor();
      assert.equal(
        await page.locator('#message-history-0 time').textContent(),
        'Jul 1, 2026, 12:01 AM EDT'
      );
      assert.equal(
        await page.locator('#message-new-message time').textContent(),
        'Jul 1, 2026, 11:59 PM EDT'
      );
      const timestamps = await page
        .locator('.dot-message time')
        .allTextContents();
      await page.reload();
      await page.click('#toggle-dot');
      await page.locator('#message-new-message time').waitFor();
      assert.deepEqual(
        await page.locator('.dot-message time').allTextContents(),
        timestamps
      );
      await page.locator('.dot-history').evaluate((n) => {
        n.scrollTop = 0;
      });
      const layout = await page.locator('.dot-message').evaluateAll((ns) =>
        ns.map((n) => {
          const time = n.querySelector('time'),
            box = n.getBoundingClientRect(),
            t = time.getBoundingClientRect();
          return {
            inside: t.left >= box.left && t.right <= box.right,
            size: parseFloat(getComputedStyle(time).fontSize),
            opacity: getComputedStyle(time).opacity,
          };
        })
      );
      assert.ok(
        layout.every((t) => t.inside && t.size >= 11 && t.opacity === '1'),
        'Timestamps readable inside every message, including dispatch byline'
      );
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth
        ),
        'No horizontal overflow'
      );
      assert.equal(s.reads.length, 0);
      assert.equal(s.readStates.length, 0);
      assert.ok(
        s.messages.filter((m) => m.role === 'dot').every((m) => m.manual_unread)
      );
      assert.equal(s.messages[0].attention.resolved, false);
      assert.deepEqual(errors, []);
      await page.screenshot({
        path: `${output}/timestamps-${project ? 'project' : 'issue'}-${width}.png`,
        fullPage: true,
      });
      results.push({
        width,
        project,
        browserZone: 'Asia/Tokyo',
        passed: true,
        checked: [
          'history',
          'spring DST',
          'fall repeated hour',
          'Eastern previous date/year',
          'new/updated',
          'reload',
          'layout',
          'manual unread/attention preserved',
        ],
      });
      console.log('PASS timestamps', results.at(-1));
      await context.close();
    }
  await writeFile(output + '/results.json', JSON.stringify(results, null, 2));
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
}
