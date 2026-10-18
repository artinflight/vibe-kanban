// Real SQLite + BrowserAPI in a disposable fixture, actual React container/panel.
// No production API, credentials, dispatch, build or release action.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { bundleNotifications } from './notification-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output) throw Error('Set VK_TEST_OUTPUT to a mounted SSD directory');
await mkdir(output, { recursive: true });
const bundle = await bundleNotifications();
const css = await readFile(
  'packages/web-core/src/pages/workspaces/dot-sidechat.css',
  'utf8'
);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
  args: ['--no-sandbox'],
});
const results = [];
try {
  for (const project of [false, true])
    for (const width of [390, 1440]) {
      const child = spawn(
        'python3',
        ['-B', 'scripts/dot-sidechat/reply-browser-fixture.py', output],
        { stdio: ['pipe', 'pipe', 'inherit'] }
      );
      const lines = createInterface({ input: child.stdout });
      const pending = [];
      lines.on('line', (line) => {
        const result = JSON.parse(line);
        const job = pending.shift();
        result.ok
          ? job.resolve(result.result)
          : job.reject(Error(result.error));
      });
      const rpc = (operation, args = {}) =>
        new Promise((resolve, reject) => {
          pending.push({ resolve, reject });
          child.stdin.write(JSON.stringify({ operation, ...args }) + '\n');
        });
      let loseResponse = false;
      const sends = [];
      const mutations = [];
      const server = createServer(async (req, res) => {
        try {
          const url = new URL(req.url, 'http://fixture');
          const json = (body) => {
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify(body));
          };
          if (url.pathname.startsWith('/api/dot-sidechat/')) {
            const route = url.pathname.split('/').at(-1);
            let raw = '';
            for await (const chunk of req) raw += chunk;
            if (req.method !== 'GET') mutations.push(route);
            if (route === 'session')
              return json({
                csrf: 'fixture',
                session_id: 'fixture',
                expires: null,
              });
            if (route === 'notifications')
              return json((await rpc('inspect')).notifications);
            if (route === 'thread')
              return json(
                await rpc('page', {
                  query: Object.fromEntries(url.searchParams),
                })
              );
            if (route === 'send') {
              assert.equal(req.headers['x-dot-csrf'], 'fixture');
              const body = JSON.parse(raw);
              sends.push(body);
              const result = await rpc('send', { body });
              if (loseResponse) {
                loseResponse = false;
                res.statusCode = 503;
                return json({ error: 'Response lost after commit' });
              }
              return json(result);
            }
            throw Error('Unexpected mutation/route: ' + route);
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
                '\nbody{margin:0}#workspace-list{display:none}#dot-slot{height:900px!important;width:100%;max-width:520px}'
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
      const context = await browser.newContext({
        viewport: { width, height: 1200 },
        isMobile: width < 768,
        hasTouch: width < 768,
        timezoneId: 'Asia/Tokyo',
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      try {
        await page.goto(
          `http://127.0.0.1:${server.address().port}/${project ? '?project' : ''}`
        );
        await page.click('#toggle-dot');
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .waitFor();
        const targetId = await page
          .locator('.dot-message-dot')
          .getAttribute('id');
        const target = targetId.slice('message-'.length);
        const before = await rpc('inspect');
        await page
          .getByRole('button', { name: 'Reply to message 1', exact: true })
          .click();
        await page
          .getByRole('textbox', { name: 'Message Dot' })
          .fill('Keep this draft');
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .click();
        const banner = page.getByRole('group', {
          name: 'Reply target',
          exact: true,
        });
        assert.match(await banner.textContent(), /Replying to Dot · #2/);
        assert.match(await banner.textContent(), /Exact Dot context/);
        assert.match(await banner.locator('time').textContent(), /EDT$/);
        assert.ok(
          await page
            .getByRole('textbox', { name: 'Message Dot' })
            .evaluate((n) => document.activeElement === n)
        );
        const height = await page
          .getByRole('button', { name: 'Cancel reply', exact: true })
          .evaluate((n) => n.getBoundingClientRect().height);
        assert.ok(height >= (width < 768 ? 44 : 36));
        await page
          .getByRole('button', { name: 'Cancel reply', exact: true })
          .click();
        assert.equal(await banner.count(), 0);
        assert.equal(
          await page.getByRole('textbox', { name: 'Message Dot' }).inputValue(),
          'Keep this draft'
        );
        assert.equal(sends.length, 0);
        assert.deepEqual(await rpc('inspect'), before);
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .click();
        await page
          .getByRole('button', { name: 'Send to Dot ↑', exact: true })
          .evaluate((n) => {
            n.click();
            n.click();
          });
        await page.locator('.dot-message-owner .dot-reply-reference').waitFor();
        assert.equal(sends.length, 1);
        assert.equal(sends[0].in_reply_to, target);
        assert.equal(await banner.count(), 0);
        assert.equal(
          await page.getByRole('textbox', { name: 'Message Dot' }).inputValue(),
          ''
        );
        const quote = page.locator('.dot-message-owner .dot-reply-reference');
        assert.match(
          await quote.textContent(),
          /Reply to Dot · #2.*Exact Dot context/s
        );
        await quote.locator('a').click();
        await page.waitForURL((url) => url.hash.endsWith('&message=' + target));
        let inspection = await rpc('inspect');
        const event = inspection.pending.items.find(
          (p) => p.event.data.sequence === 3
        ).event;
        assert.equal(event.data.in_reply_to, target);
        assert.equal(
          await quote.locator('a').getAttribute('href'),
          '#thread=' + event.data.thread_id + '&message=' + target
        );
        assert.equal(inspection.links, 1);
        assert.deepEqual(inspection.notifications, before.notifications);
        // A lost response must retain the exact target, key and body through reload.
        await page
          .getByRole('button', { name: 'Reply to message 1', exact: true })
          .click();
        await page
          .getByRole('textbox', { name: 'Message Dot' })
          .fill('Retry exact target');
        loseResponse = true;
        await page
          .getByRole('button', { name: 'Send to Dot ↑', exact: true })
          .click();
        await page.getByRole('alert').waitFor();
        const original = structuredClone(sends.at(-1));
        assert.ok(
          await page
            .getByRole('button', { name: 'Cancel reply', exact: true })
            .isDisabled()
        );
        assert.ok(
          await page
            .getByRole('button', { name: 'Reply to message 2', exact: true })
            .isDisabled()
        );
        await rpc('reopen');
        await page.reload();
        await page.click('#toggle-dot');
        await banner.waitFor();
        assert.match(await banner.textContent(), /Replying to you · #1/);
        assert.equal(
          await page.getByRole('textbox', { name: 'Message Dot' }).inputValue(),
          'Retry exact target'
        );
        // Older services cannot silently drop a restored target and send ordinary chat.
        await rpc('legacy', { value: false });
        await page
          .getByRole('button', { name: 'Refresh conversation', exact: true })
          .click();
        await page.waitForFunction(
          () => !document.querySelector('[aria-label="Reply to message 1"]')
        );
        const count = sends.length;
        await page
          .getByRole('button', { name: 'Retry same message ↑', exact: true })
          .click();
        await page
          .getByRole('alert')
          .filter({ hasText: 'Reply targeting is unavailable' })
          .waitFor();
        assert.equal(sends.length, count);
        await rpc('legacy', { value: true });
        await page
          .getByRole('button', { name: 'Refresh conversation', exact: true })
          .click();
        await page
          .getByRole('button', { name: 'Reply to message 1', exact: true })
          .waitFor();
        await page
          .getByRole('button', { name: 'Retry same message ↑', exact: true })
          .click();
        await page.waitForFunction(
          () => document.querySelector('#dot-draft').value === ''
        );
        assert.deepEqual(sends.at(-1), original);
        inspection = await rpc('inspect');
        assert.equal(inspection.links, 2);
        // Normal messages after cancellation remain unlinked.
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .click();
        await page
          .getByRole('button', { name: 'Cancel reply', exact: true })
          .click();
        await page
          .getByRole('textbox', { name: 'Message Dot' })
          .fill('Ordinary chat');
        await page
          .getByRole('button', { name: 'Send to Dot ↑', exact: true })
          .click();
        await page.waitForFunction(
          () => document.querySelector('#dot-draft').value === ''
        );
        assert.equal(sends.at(-1).in_reply_to, undefined);
        await rpc('reopen');
        await page.reload();
        await page.click('#toggle-dot');
        await page
          .locator('.dot-message-owner .dot-reply-reference')
          .first()
          .waitFor();
        assert.equal(
          await page.locator('.dot-message-owner .dot-reply-reference').count(),
          2
        );
        assert.equal(await banner.count(), 0);
        // A selected but unsent reply can still be canceled after a capability downgrade.
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .click();
        await rpc('legacy', { value: false });
        await page
          .getByRole('button', { name: 'Refresh conversation', exact: true })
          .click();
        await page.waitForFunction(
          () => !document.querySelector('[aria-label="Reply to message 2"]')
        );
        await page
          .getByRole('button', { name: 'Cancel reply', exact: true })
          .click();
        assert.equal(await banner.count(), 0);
        await rpc('legacy', { value: true });
        await page
          .getByRole('button', { name: 'Refresh conversation', exact: true })
          .click();
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .waitFor();
        // A different workspace has a separate selection; remounting the same project
        // restores its own retained draft/target. Durable shared history remains.
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .click();
        await page.click('#sibling');
        await page
          .getByRole('button', { name: 'Reply to message 2', exact: true })
          .waitFor();
        assert.equal(await banner.count(), project ? 1 : 0);
        assert.equal(
          await page.locator('.dot-message-owner .dot-reply-reference').count(),
          2
        );
        assert.ok(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          )
        );
        assert.equal(await page.locator('.dot-panel script').count(), 0);
        assert.deepEqual(
          (await rpc('inspect')).notifications,
          before.notifications
        );
        assert.ok(mutations.every((m) => m === 'send'));
        assert.deepEqual(errors, []);
        await page.screenshot({
          path: `${output}/reply-${project ? 'project' : 'issue'}-${width}.png`,
          fullPage: true,
        });
        results.push({
          width,
          project,
          passed: true,
          realSQLite: true,
          newReloadHistory: true,
          exactEventTarget: true,
          selectReplaceCancel: true,
          lostResponseReopenRetry: true,
          legacyCapabilityGuard: true,
          normalChatUnchanged: true,
          unreadAttentionUnchanged: true,
        });
        console.log('PASS owner reply target', results.at(-1));
      } finally {
        await context.close();
        await new Promise((r) => server.close(r));
        child.stdin.end();
        await new Promise((resolve, reject) =>
          child.on('exit', (code) =>
            code ? reject(Error('Fixture exit ' + code)) : resolve()
          )
        );
        lines.close();
      }
    }
  await writeFile(output + '/results.json', JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
