// Actual project layout/sidebar/chat in a fresh browser; synthetic transport only.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import {
  projectRoutingBundle,
  routingState,
  routingTransport,
  deferred,
  ids,
} from './project-routing-test-support.mjs';
import { wait } from './notification-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output) throw Error('Set mounted SSD output');
await mkdir(output, { recursive: true });
const bundle = await projectRoutingBundle();
let baseline = '';
if (process.env.DOT_BASELINE_RELEASE) {
  const root = process.env.DOT_BASELINE_RELEASE;
  const html = await readFile(root + '/index.html', 'utf8');
  baseline = await readFile(
    root + html.match(/href="(\/assets\/[^\"]+\.css)"/)[1],
    'utf8'
  );
}
let s;
const server = createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/')) {
      let body = '';
      for await (const chunk of req) body += chunk;
      const result = await routingTransport(s)(req.url, {
        method: req.method,
        body,
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
        baseline +
          bundle.css +
          '\n*{box-sizing:border-box}body{margin:0}.fixture-project{height:100dvh;display:flex;flex-direction:column;overflow:hidden}#fixture-controls{display:flex;flex-shrink:0;gap:4px}#fixture-controls button{min-height:44px;padding:4px}.fixture-project>.project-space-layout{height:auto;min-height:0}#displayed-workspace{height:100%}'
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
  for (const width of [390, 1440]) {
    s = routingState();
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    try {
      await page.goto(
        `http://127.0.0.1:${server.address().port}/projects/${ids.project}`
      );
      const input = () =>
        page.getByRole('textbox', { name: 'Message Dot', exact: true });
      const sidebar = page.locator('.project-collaboration');
      async function open() {
        const trigger = page.getByRole('button', {
          name: 'Open project sidebar',
          exact: true,
        });
        await trigger.waitFor();
        if ((await trigger.getAttribute('aria-expanded')) !== 'true')
          await trigger.click();
        await input().waitFor();
      }
      async function ready(d) {
        await open();
        await page.waitForFunction(
          (d) =>
            document
              .querySelector('.dot-scope')
              ?.textContent.includes(
                d === 'project' ? 'Project-wide' : 'Workspace ' + d
              ) && document.getElementById('message-note-' + d),
          d
        );
      }
      async function route(d) {
        await page.evaluate((d) => window.fixtureNavigate(d), d);
        await page.waitForFunction(
          (d) =>
            document.getElementById('displayed-workspace')?.textContent ===
            (d === 'project' ? 'Project board' : 'Displayed workspace ' + d),
          d
        );
      }
      async function noOverflow() {
        assert.ok(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          )
        );
        const box = await sidebar.boundingBox();
        assert.ok(box.x >= -1 && box.x + box.width <= width + 1);
        assert.ok(box.y + box.height <= 1001);
      }
      await ready('project');
      await input().fill('Project retained draft');
      await page
        .getByRole('button', { name: 'Reply to message 1', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Jump to Needs Attention', exact: true })
        .click();
      await noOverflow();
      const textarea = await input().elementHandle();
      if (width >= 768) {
        const handle = page.getByRole('separator', {
          name: 'Resize project sidebar',
        });
        await handle.focus();
        await page.keyboard.press('ArrowLeft');
        await page.waitForFunction(
          () =>
            document
              .querySelector('[aria-label="Resize project sidebar"]')
              .getAttribute('aria-valuenow') === '444'
        );
        const box = await handle.boundingBox();
        await page.mouse.move(box.x + 3, box.y + 100);
        await page.mouse.down();
        await page.mouse.move(box.x - 97, box.y + 100, { steps: 5 });
        await page.mouse.up();
        const prior = Number(await handle.getAttribute('aria-valuenow'));
        assert.ok(prior >= 540 && prior <= 548);
        await noOverflow();
        await page
          .getByRole('button', { name: 'Full-width chat', exact: true })
          .click();
        assert.equal(
          await page.locator('.project-space-board').isVisible(),
          false
        );
        await noOverflow();
        assert.equal(
          await textarea.evaluate(
            (node) => node === document.getElementById('dot-draft')
          ),
          true
        );
        assert.equal(await input().inputValue(), 'Project retained draft');
        assert.equal(
          await page.locator('[data-dot-attention-current]').count(),
          1
        );
        assert.equal(await page.locator('.dot-reply-target').count(), 1);
        await page
          .getByRole('button', { name: 'Restore sidebar width', exact: true })
          .click();
        assert.equal(Number(await handle.getAttribute('aria-valuenow')), prior);
        await noOverflow();
        await handle.focus();
        await page.keyboard.press('End');
        assert.equal(
          await handle.getAttribute('aria-valuenow'),
          await handle.getAttribute('aria-valuemax')
        );
        await noOverflow();
        await page.keyboard.press('Home');
        assert.equal(await handle.getAttribute('aria-valuenow'), '320');
        await noOverflow();
      } else {
        assert.equal(
          await page
            .getByRole('separator', { name: 'Resize project sidebar' })
            .count(),
          0
        );
        assert.equal(
          await page.getByRole('button', { name: 'Full-width chat' }).count(),
          0
        );
        assert.equal(await page.locator('[aria-modal="true"]').count(), 1);
      }
      const held = deferred();
      s.threadHolds.set('a', held);
      await route('a');
      await open();
      await wait(() =>
        s.requests.some((r) => r.url.includes('workspace=' + ids.a))
      );
      assert.equal(await page.locator('#message-note-project').count(), 0);
      assert.ok(await page.locator('button[type="submit"]').isDisabled());
      await route('b');
      await ready('b');
      await input().fill('B isolated draft');
      s.threadHolds.delete('a');
      held.resolve();
      await page.waitForTimeout(30);
      assert.equal(await input().inputValue(), 'B isolated draft');
      assert.equal(await page.locator('#message-note-a').count(), 0);
      // Multiple route changes in one event turn select only the final destination.
      await page.evaluate(() => {
        window.fixtureNavigate('a');
        window.fixtureNavigate('project');
        window.fixtureNavigate('b');
      });
      await ready('b');
      assert.equal(await input().inputValue(), 'B isolated draft');
      await route('a');
      await ready('a');
      await input().fill('A pinned reply');
      await page
        .getByRole('button', { name: 'Reply to message 1', exact: true })
        .click();
      const holdSend = deferred();
      s.sendHolds.set('a', holdSend);
      await page.locator('button[type="submit"]').click();
      await wait(() => s.sends.length === 1);
      const original = structuredClone(s.sends[0]);
      await route('b');
      await ready('b');
      holdSend.resolve(503);
      s.sendHolds.delete('a');
      assert.equal(await input().inputValue(), 'B isolated draft');
      await route('a');
      await ready('a');
      await page.waitForFunction(
        () => document.getElementById('dot-draft').readOnly
      );
      assert.equal(await input().inputValue(), 'A pinned reply');
      await page.locator('button[type="submit"]').click();
      await wait(() => s.sends.length === 2);
      await page.waitForFunction(
        () => document.getElementById('dot-draft').value === ''
      );
      assert.deepEqual(s.sends[1], original);
      assert.equal(original.workspace, ids.a);
      assert.equal(original.project, undefined);
      assert.equal(original.in_reply_to, 'note-a');
      await route('project');
      await ready('project');
      assert.equal(await input().inputValue(), 'Project retained draft');
      assert.match(
        await page.locator('.dot-reply-target').textContent(),
        /Conversation project/
      );
      await page.goBack();
      if (width < 768) {
        await page.waitForFunction(() => !document.getElementById('dot-draft'));
        await page.goBack();
      }
      await page.waitForFunction(
        () =>
          document.getElementById('displayed-workspace')?.textContent ===
          'Displayed workspace a'
      );
      await ready('a');
      assert.equal(await input().inputValue(), '');
      await route('project');
      await ready('project');
      await page.reload();
      await ready('project');
      assert.equal(await input().inputValue(), 'Project retained draft');
      assert.equal(await page.locator('.dot-reply-target').count(), 1);
      await page.locator('button[type="submit"]').click();
      await wait(() => s.sends.length === 3);
      assert.equal(s.sends[2].project, ids.project);
      assert.equal(s.sends[2].workspace, undefined);
      assert.equal(s.sends[2].in_reply_to, 'note-project');
      await page.waitForFunction(
        () => document.getElementById('dot-draft').value === ''
      );
      await noOverflow();
      assert.deepEqual(errors, []);
      assert.ok(
        s.requests.every(
          (r) => r.method === 'GET' || r.url === '/api/dot-sidechat/send'
        )
      );
      await page.screenshot({ path: output + `/project-chat-${width}.png` });
      results.push({
        width,
        passed: true,
        lateGet: true,
        rapidSwitch: true,
        inFlightRetryExact: true,
        projectCloseBack: true,
        draftsReplyReload: true,
        dragKeyboardFullRestore: width >= 768,
        mobileSheet: width < 768,
        noOverflow: true,
        realWrites: 0,
      });
      console.log('PASS project chat browser', results.at(-1));
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
  await writeFile(output + '/results.json', JSON.stringify(results, null, 2));
}
