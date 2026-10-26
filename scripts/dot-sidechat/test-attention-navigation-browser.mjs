// Fresh unpaired browsers + read-only fixture transport. No live APIs or state.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { bundleNotifications, wait } from './notification-test-support.mjs';
import {
  attentionState,
  attentionTransport,
} from './attention-navigation-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output) throw Error('Set VK_TEST_OUTPUT to a mounted SSD directory');
await mkdir(output, { recursive: true });
const bundle = await bundleNotifications();
let css = '';
if (process.env.DOT_BASELINE_RELEASE) {
  const root = process.env.DOT_BASELINE_RELEASE,
    html = await readFile(root + '/index.html', 'utf8');
  css = await readFile(
    root + html.match(/href="(\/assets\/[^\"]+\.css)"/)[1],
    'utf8'
  );
}
let s;
const server = createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/dot-sidechat/')) {
      let body = '';
      for await (const chunk of req) body += chunk;
      const result = await attentionTransport(s)(req.url, {
        method: req.method,
        body,
        headers: { 'X-Dot-CSRF': req.headers['x-dot-csrf'] },
      });
      res.statusCode = result.status;
      res.setHeader('Content-Type', 'application/json');
      return res.end(JSON.stringify(await result.json()));
    }
    if (req.url === '/fixture.js') {
      res.setHeader('Content-Type', 'text/javascript');
      return res.end(bundle.js);
    }
    if (req.url === '/fixture.css') {
      res.setHeader('Content-Type', 'text/css');
      return res.end(
        css +
          bundle.css +
          '\nbody{margin:0}.new-design{height:100vh;display:flex;flex-direction:column;overflow:hidden}#workspace-list{display:none}#toggle-dot,#sibling{flex-shrink:0}#dot-slot{flex:1;min-height:0;height:auto!important;width:100%;max-width:520px}'
      );
    }
    res.end(
      '<html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/fixture.css"><div id="root"></div><script src="/fixture.js"></script></html>'
    );
  } catch (e) {
    res.statusCode = 500;
    res.end(JSON.stringify({ error: String(e) }));
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
      s = attentionState();
      let release;
      s.hold = new Promise((r) => (release = r));
      const context = await browser.newContext({
        viewport: { width, height: 1000 },
        isMobile: width < 768,
        hasTouch: width < 768,
      });
      const page = await context.newPage(),
        errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      try {
        await page.goto(
          `http://127.0.0.1:${server.address().port}/${project ? '?project' : ''}`
        );
        await page.waitForFunction(() =>
          document.querySelector('.dot-attention-nav')
        );
        await wait(() => s.requests.some((r) => r.url.includes('after=50')));
        const jump = page.getByRole('button', {
          name: 'Jump to Needs Attention',
          exact: true,
        });
        await page.click('#toggle-dot');
        assert.ok(await jump.isDisabled());
        assert.match(
          await page.locator('.dot-attention-nav').textContent(),
          /Loading conversation/
        );
        release();
        s.hold = null;
        await jump.waitFor();
        await page.waitForFunction(
          () => !document.querySelector('.dot-attention-nav button').disabled
        );
        assert.ok(s.requests.some((r) => r.url.includes('after=100')));
        assert.ok(
          s.requests
            .filter((r) => r.url.includes('after='))
            .every((r) => r.url.includes('through=125'))
        );
        const status = page.locator('.dot-attention-nav [role=status]');
        const next = page.getByRole('button', {
          name: 'Next flagged message',
          exact: true,
        });
        const previous = page.getByRole('button', {
          name: 'Previous flagged message',
          exact: true,
        });
        const refresh = () =>
          page
            .getByRole('button', { name: 'Refresh conversation', exact: true })
            .click();
        async function selected(seq) {
          await page.waitForFunction(
            (seq) =>
              document.querySelector('[data-dot-attention-current]')?.id ===
              'message-attention-' + seq,
            seq
          );
          await page.waitForFunction((seq) => {
            const n = document.getElementById('message-attention-' + seq),
              r = n.closest('.dot-history').getBoundingClientRect(),
              b = n.getBoundingClientRect();
            const history = n.closest('.dot-history');
            const atEnd =
              history.scrollTop >=
              history.scrollHeight - history.clientHeight - 1;
            return (
              b.top >= r.top - 1 &&
              b.top < r.bottom &&
              (Math.abs(b.top - r.top - 12) < 1.5 || atEnd)
            );
          }, seq);
          assert.equal(
            await page.evaluate(() => document.activeElement.id),
            'message-attention-' + seq
          );
        }
        const windowScroll = await page.evaluate(() => scrollY);
        await jump.click();
        await selected(3);
        assert.equal(await status.textContent(), '1 of 3');
        await next.click();
        await selected(61);
        assert.equal(await status.textContent(), '2 of 3');
        await next.click();
        await selected(112);
        await next.click();
        await selected(3);
        await previous.click();
        await selected(112);
        await jump.click();
        await selected(3);
        await jump.evaluate((n) => {
          n.click();
          n.click();
        });
        await selected(3);
        assert.equal(
          await page.evaluate(() => scrollY),
          windowScroll,
          'Only history scrolls'
        );
        const touch = await next.evaluate(
          (n) => n.getBoundingClientRect().height
        );
        assert.ok(touch >= (width < 768 ? 44 : 36));
        // Resolve/reflag remotely between navigations. The cursor uses stable sequence.
        s.messages[2].attention.resolved = true;
        await refresh();
        await page.waitForFunction(() =>
          document
            .querySelector('.dot-attention-nav')
            .textContent.includes('Flag changed')
        );
        await next.click();
        await selected(61);
        s.messages[1].attention = { kind: 'action', resolved: false };
        await refresh();
        await page.waitForFunction(
          () =>
            document.querySelector('.dot-attention-nav [role=status]')
              .textContent === '2 of 3'
        );
        await previous.click();
        await selected(2);
        await next.click();
        await selected(61);
        await next.click();
        await selected(112);
        const oldTop = await page
          .locator('.dot-history')
          .evaluate((n) => n.scrollTop);
        s.messages.push({
          ...s.messages.at(-1),
          id: 'attention-126',
          seq: 126,
          body: 'New flagged message',
          attention: { kind: 'question', resolved: false },
        });
        await refresh();
        await page.waitForFunction(
          () =>
            document.querySelector('.dot-attention-nav [role=status]')
              .textContent === '3 of 4'
        );
        assert.equal(
          await page.locator('[data-dot-attention-current]').getAttribute('id'),
          'message-attention-112'
        );
        assert.ok(
          Math.abs(
            (await page.locator('.dot-history').evaluate((n) => n.scrollTop)) -
              oldTop
          ) < 2,
          'New messages must not pull flag navigation to latest: ' +
            JSON.stringify({
              oldTop,
              actual: await page
                .locator('.dot-history')
                .evaluate((n) => n.scrollTop),
            })
        );
        await next.click();
        await selected(126);
        await next.click();
        await selected(2);
        // Quote deep links still work; later refresh cannot steal the attention cursor.
        await page
          .locator('#message-attention-1 .dot-byline a')
          .evaluate((n) => n.click());
        await page.waitForURL((url) =>
          url.hash.endsWith('message=attention-1')
        );
        await jump.click();
        await selected(2);
        await refresh();
        await page.waitForTimeout(150);
        assert.equal(
          await page.locator('[data-dot-attention-current]').getAttribute('id'),
          'message-attention-2'
        );
        // Empty, single and re-opened flags all remain explicit, without mutations.
        s.messages.forEach((m) => {
          if (m.attention) m.attention.resolved = true;
        });
        await refresh();
        await page.waitForFunction(() =>
          document
            .querySelector('.dot-attention-nav')
            .textContent.includes('No unresolved flagged messages')
        );
        assert.ok(await jump.isDisabled());
        assert.ok(await next.isDisabled());
        assert.ok(await previous.isDisabled());
        s.messages[7].attention = { kind: 'action', resolved: false };
        await refresh();
        await page.waitForFunction(
          () => !document.querySelector('.dot-attention-nav button').disabled
        );
        await next.click();
        await selected(8);
        await previous.click();
        await selected(8);
        assert.equal(await status.textContent(), '1 of 1');
        // Reload still fetches complete retained history and can find an old flag.
        await page.reload();
        await page.click('#toggle-dot');
        await page.waitForFunction(
          () => !document.querySelector('.dot-attention-nav button').disabled
        );
        await jump.click();
        await selected(8);
        await page
          .getByRole('button', { name: 'Jump to latest ↓', exact: true })
          .click();
        assert.equal(
          await page.locator('[data-dot-attention-current]').count(),
          0
        );
        assert.ok(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          )
        );
        assert.ok(
          s.requests.every((r) => r.method === 'GET'),
          'Navigation must never post seen/read-state/attention'
        );
        assert.ok(s.messages.every((m) => m.manual_unread && !m.seen));
        assert.equal(s.messages[7].attention.resolved, false);
        assert.deepEqual(errors, []);
        await jump.click();
        await selected(8);
        await page.screenshot({
          path: `${output}/attention-${project ? 'project' : 'issue'}-${width}.png`,
          fullPage: true,
        });
        results.push({
          width,
          project,
          passed: true,
          pages: 3,
          olderAndLongMessages: true,
          forwardBackwardWrap: true,
          changingEmptySingleFlags: true,
          reload: true,
          quoteNavigationPreserved: true,
          outerScrollUnchanged: true,
          mutations: 0,
        });
        console.log('PASS attention browser', results.at(-1));
      } finally {
        release();
        s.hold = null;
        await context.close();
      }
    }
  await writeFile(output + '/results.json', JSON.stringify(results, null, 2));
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
}
