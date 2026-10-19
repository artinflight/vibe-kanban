// Isolated full Dot container, native incumbent theme + candidate Dot CSS.
// No real backend/account/clipboard writes. One browser, serial desktop/mobile.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import {
  bundleNotifications,
  state,
  transport,
} from './notification-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output || !process.env.VK_INCUMBENT_THEME_CSS)
  throw Error('Set admitted output and incumbent theme CSS paths');
const bundle = await bundleNotifications();
const css =
  (await readFile(process.env.VK_INCUMBENT_THEME_CSS, 'utf8')) +
  '\n' +
  (await readFile(
    'packages/web-core/src/pages/workspaces/dot-sidechat.css',
    'utf8'
  ));
const server = createServer((req, res) => {
  if (req.url === '/app.js') {
    res.setHeader('Content-Type', 'text/javascript');
    return res.end(bundle.js);
  }
  if (req.url === '/style.css') {
    res.setHeader('Content-Type', 'text/css');
    return res.end(css);
  }
  res.setHeader('Content-Type', 'text/html');
  res.end(
    '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/style.css"></head><body><div id="root"></div><script src="/app.js"></script></body></html>'
  );
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = 'http://127.0.0.1:' + server.address().port;
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
  args: [
    '--no-sandbox',
    '--disk-cache-size=1',
    '--media-cache-size=1',
    '--disable-gpu-shader-disk-cache',
  ],
});
const results = [];
try {
  for (const theme of ['light', 'dark'])
    for (const width of [390, 1440])
      for (const project of [false, true]) {
        const context = await browser.newContext({
          viewport: { width, height: 1000 },
          isMobile: width < 768,
          hasTouch: width < 768,
        });
        const code =
          '  const escaped = "<img src=x onerror=alert(1)>";\r\n\t// whitespace  \r\n' +
          '// ' +
          'long '.repeat(240) +
          '\r\n';
        const text =
          'Ordinary <script>alert(1)</script> text.\n```javascript\r\n' +
          code +
          '```\r\nAfter\n~~~unknown-lang\n<svg onload=alert(1)>\n~~~';
        const note = {
          id: 'dot-reply',
          seq: 2,
          role: 'dot',
          body: text,
          workspace: '11111111-1111-4111-8111-111111111111',
          created: 1792321200,
          seen: false,
          manual_unread: true,
          attention: { kind: 'question', resolved: false },
        };
        const s = {
          ...state(),
          manualUnread: true,
          supportsReplies: true,
          messages: [note],
        };
        const original = JSON.stringify(s.messages),
          api = transport(s);
        await context.addInitScript(() => {
          document.hasFocus = () => false;
          window.testCopies = [];
          window.testDenyCopy = false;
          Object.defineProperty(navigator, 'clipboard', {
            value: {
              writeText: async (text) => {
                if (window.testDenyCopy) throw Error('Isolated denial');
                window.testCopies.push(text);
              },
            },
          });
        });
        await context.route('**/*', async (route) => {
          const req = route.request(),
            u = new URL(req.url());
          if (u.origin !== base) return route.abort();
          if (u.pathname.startsWith('/api/')) {
            const response = await api(u.pathname + u.search, {
              method: req.method(),
              headers: { 'X-Dot-CSRF': req.headers()['x-dot-csrf'] },
              body: req.postData(),
            });
            return route.fulfill({
              status: response.status,
              json: await response.json(),
            });
          }
          return route.continue();
        });
        const page = await context.newPage();
        page.setDefaultTimeout(10000);
        const errors = [];
        page.on('pageerror', (e) => errors.push(e.message));
        try {
          const open = async () => {
            await page
              .locator('#message-dot-reply')
              .waitFor({ state: 'attached' });
            await page.locator('#toggle-dot').click();
            await page.locator('.dot-panel:visible').waitFor();
          };
          await page.goto(base + (project ? '/?project' : '/'));
          await page.evaluate(
            (theme) =>
              document.documentElement.classList.toggle(
                'dark',
                theme === 'dark'
              ),
            theme
          );
          await open();
          const blocks = page.locator('.dot-code-block');
          assert.equal(await blocks.count(), 2);
          assert.equal(
            await blocks.first().locator('code').textContent(),
            code
          );
          assert.ok(await blocks.first().locator('code span').count());
          assert.equal(await blocks.nth(1).locator('code span').count(), 0);
          const metrics = await page.evaluate(() => {
            const block = document.querySelector('.dot-code-block'),
              pre = block.querySelector('pre'),
              button = block.querySelector('button'),
              token = block.querySelector('code span'),
              p = document.querySelector('.dot-message > p');
            return {
              body: getComputedStyle(p).fontSize,
              composer: getComputedStyle(document.querySelector('#dot-draft'))
                .fontSize,
              code: getComputedStyle(pre.querySelector('code')).fontSize,
              tokenColor: getComputedStyle(token).color,
              plainColor: getComputedStyle(pre).color,
              buttonHeight: button.getBoundingClientRect().height,
              internalScroll: pre.scrollWidth > pre.clientWidth,
              overflow: document.documentElement.scrollWidth > innerWidth,
              bodyText: p.textContent,
            };
          });
          assert.equal(metrics.body, '16px');
          assert.equal(metrics.composer, '16px');
          assert.equal(metrics.code, '16px');
          assert.notEqual(metrics.tokenColor, metrics.plainColor);
          assert.equal(metrics.overflow, false);
          assert.equal(metrics.internalScroll, true);
          if (width < 768) assert.ok(metrics.buttonHeight >= 44);
          assert.ok(metrics.bodyText.includes('<script>'));
          assert.equal(
            await page
              .locator('.dot-message script,.dot-message img,.dot-message svg')
              .count(),
            0
          );
          const copy = blocks
            .first()
            .getByRole('button', { name: 'Copy code block', exact: true });
          await copy.focus();
          await page.keyboard.press('Enter');
          await blocks
            .first()
            .getByText('Code copied', { exact: true })
            .waitFor({ state: 'attached' });
          assert.equal(
            await page.evaluate(() => window.testCopies.at(-1)),
            code
          );
          await blocks
            .nth(1)
            .getByRole('button', { name: 'Copy code block', exact: true })
            .click();
          assert.equal(
            await page.evaluate(() => window.testCopies.at(-1)),
            '<svg onload=alert(1)>\n'
          );
          await page.evaluate(() => (window.testDenyCopy = true));
          await copy.click();
          await blocks
            .first()
            .getByText(/Could not copy/)
            .waitFor();
          await page.evaluate(() => (window.testDenyCopy = false));
          await copy.click();
          await blocks
            .first()
            .getByText('Code copied', { exact: true })
            .waitFor({ state: 'attached' });
          await page.locator('#dot-draft').fill('Retained code test draft');
          await page
            .getByRole('button', { name: 'Reply to message 2', exact: true })
            .click();
          await page
            .getByRole('button', {
              name: 'Jump to Needs Attention',
              exact: true,
            })
            .click();
          assert.equal(
            await page.locator('[data-dot-attention-current]').count(),
            1
          );
          await page
            .getByRole('button', {
              name: 'Mark Dot reply as read',
              exact: true,
            })
            .click();
          await page
            .getByRole('button', {
              name: 'Mark Dot reply as unread',
              exact: true,
            })
            .click();
          assert.equal(s.manualUnread, true);
          assert.equal(s.resolved, false);
          await page.reload();
          await open();
          assert.equal(
            await blocks.first().locator('code').textContent(),
            code
          );
          assert.equal(
            await page.locator('#dot-draft').inputValue(),
            'Retained code test draft'
          );
          assert.equal(await page.locator('.dot-reply-target').count(), 1);
          assert.equal(JSON.stringify(s.messages), original);
          assert.equal(s.reads.length, 0);
          assert.equal(s.resolved, false);
          assert.equal(errors.length, 0, errors.join('\n'));
          results.push({
            width,
            theme,
            scope: project ? 'project' : 'workspace',
            metrics,
            exact_copy: true,
            clipboard_failure_retry: true,
            reload_draft_reply_and_flags: true,
            real_writes: 0,
          });
          console.log(
            'PASS browser fenced code',
            width,
            project ? 'project' : 'workspace'
          );
        } finally {
          await context.close();
        }
      }
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
}
await writeFile(
  output + '/code-browser-results.private.json',
  JSON.stringify({ measured_at: new Date().toISOString(), results }, null, 2) +
    '\n'
);
