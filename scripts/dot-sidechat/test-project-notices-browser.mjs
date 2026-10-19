// Fresh browser, real sidebar/layout/chat components, synthetic GET-only data.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import {
  projectRoutingBundle,
  routingState,
  routingTransport,
  ids,
} from './project-routing-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const output = process.env.VK_TEST_OUTPUT;
if (!output || !process.env.DOT_BASELINE_RELEASE)
  throw Error('Set mounted SSD output and retained baseline CSS root');
await mkdir(output, { recursive: true });
const root = process.env.DOT_BASELINE_RELEASE;
const html = await readFile(root + '/index.html', 'utf8');
const css = await readFile(
  root + html.match(/href="(\/assets\/[^\"]+\.css)"/)[1],
  'utf8'
);
const bundle = await projectRoutingBundle(
  'scripts/dot-sidechat/project-notice-fixture.tsx'
);
let s;
const server = createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/')) {
      const result = await routingTransport(s)(req.url, { method: req.method });
      res.setHeader('Content-Type', 'application/json');
      res.statusCode = result.status;
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
          `
      *{box-sizing:border-box}body{margin:0}.fixture-notices{height:100dvh;display:flex;flex-direction:column;overflow:hidden}
      #fixture-controls{display:flex;flex-shrink:0}#fixture-controls button{min-height:44px;padding:4px}
      .fixture-body{display:flex;flex:1;min-height:0;min-width:0}[data-workspace-pane]{width:300px;flex-shrink:0;height:100%}
      @media(max-width:767px){[data-workspace-pane]{width:100%}[data-view=chat] [data-workspace-pane]{display:none}[data-view=workspaces] .project-space-layout{display:none}}
    `
      );
    }
    res.end(
      '<html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/fixture.css"><div id="root"></div><script src="/fixture.js"></script></html>'
    );
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
  for (const width of [390, 1440]) {
    s = routingState();
    s.projectNotices = [
      { project_id: ids.project, unread_count: 3 },
      { project_id: '55555555-5555-4555-8555-555555555555', unread_count: 0 },
    ];
    const original = JSON.stringify(s.messages);
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    // Auto-read stays inactive: the test must never mutate real or fixture flags.
    await page.addInitScript(() => {
      document.hasFocus = () => false;
    });
    try {
      await page.goto(
        `http://127.0.0.1:${server.address().port}/projects/${ids.project}`
      );
      const notice = page.locator(`[data-project-dot-notice="${ids.project}"]`);
      if (width < 768)
        await page
          .locator('.phone-workspace-tabs button')
          .filter({ hasText: 'Attention' })
          .click();
      await notice.waitFor();
      assert.match(
        await notice.textContent(),
        /Synthetic project Alpha.*Project · Dot Chat.*3 unread/
      );
      const visual = await notice.evaluate((n) => ({
        height: n.getBoundingClientRect().height,
        padding: getComputedStyle(n).padding,
        lines: [...n.children].map(c=>({height:c.getBoundingClientRect().height,font:getComputedStyle(c).fontSize,lineHeight:getComputedStyle(c).lineHeight})),
        rowBorder: getComputedStyle(n).borderLeftWidth,
        rowBackground: getComputedStyle(n).backgroundColor,
        badgeColor: getComputedStyle(
          n.querySelector('[data-project-dot-badge]')
        ).color,
        badgeWidth: n
          .querySelector('[data-project-dot-badge]')
          .getBoundingClientRect().width,
        rowWidth: n.getBoundingClientRect().width,
        badge: getComputedStyle(
          document.querySelector(
            '[data-workspace-pane] [data-dot-indicators] [aria-label]'
          )
        ).color,
        overflow: document.documentElement.scrollWidth > innerWidth,
      }));
      console.log('Project notice geometry', width, JSON.stringify(visual));
      await page.screenshot({ path: output + `/project-notices-${width}.png` });
      assert.ok(visual.height >= 44);
      assert.ok(
        visual.height <= 52,
        'Project notice stays a compact two-line row'
      );
      assert.equal(visual.rowBorder, '0px');
      assert.equal(visual.rowBackground, 'rgba(0, 0, 0, 0)');
      assert.ok(
        visual.badgeWidth < visual.rowWidth / 3,
        'Color is confined to a small badge'
      );
      assert.notEqual(visual.badgeColor, visual.badge);
      assert.equal(visual.overflow, false);
      await page.screenshot({ path: output + `/project-notices-${width}.png` });
      await notice.focus();
      await page.keyboard.press('Enter');
      const input = page.getByRole('textbox', {
        name: 'Message Dot',
        exact: true,
      });
      await input.waitFor();
      await page.waitForFunction(() =>
        document
          .querySelector('.dot-scope')
          ?.textContent.includes('Project-wide')
      );
      await input.fill('Project draft');
      await page
        .getByRole('button', { name: 'Reply to message 1', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Jump to Needs Attention', exact: true })
        .click();
      assert.equal(
        await page.locator('[data-dot-attention-current]').count(),
        1
      );
      await page.getByRole('tab', { name: 'Shared plan', exact: true }).click();
      if (width < 768) await page.locator('#show-workspaces').click();
      await notice.click();
      await input.waitFor();
      assert.equal(await input.inputValue(), 'Project draft');
      assert.match(
        await page.locator('.dot-reply-target').textContent(),
        /Conversation project/
      );
      await page.locator('#route-workspace').click();
      if (width < 768)
        await page
          .getByRole('button', { name: 'Open project sidebar', exact: true })
          .click();
      await page.waitForFunction(() =>
        document
          .querySelector('.dot-scope')
          ?.textContent.includes('Workspace a')
      );
      await input.fill('Workspace draft');
      await page
        .getByRole('button', { name: 'Reply to message 1', exact: true })
        .click();
      await page.locator('#show-workspaces').click();
      await notice.click();
      await page.waitForFunction(() =>
        document
          .querySelector('.dot-scope')
          ?.textContent.includes('Project-wide')
      );
      assert.equal(await input.inputValue(), 'Project draft');
      assert.match(
        await page.locator('.dot-reply-target').textContent(),
        /Conversation project/
      );
      assert.equal(
        await page.evaluate(() => history.state.destination),
        'project'
      );
      assert.equal(
        s.requests
          .filter((r) => r.url.startsWith('/api/dot-sidechat/thread?'))
          .at(-1)
          .url.includes('project=' + ids.project),
        true
      );
      await page.locator('#show-workspaces').click();
      s.projectNotices = [{ project_id: ids.project, unread_count: 7 }];
      await page.evaluate(() =>
        dispatchEvent(new CustomEvent('dot-sidechat-changed'))
      );
      await page.waitForFunction(() =>
        document
          .querySelector('[data-project-dot-notice]')
          ?.textContent.includes('7 unread')
      );
      assert.equal(
        await page
          .locator('[data-workspace-pane] [aria-label="Dot unread replies: 1"]')
          .count(),
        1
      );
      s.projectNotices = [
        { project_id: ids.project, unread_count: 0, needs_attention_count: 5 },
      ];
      await page.evaluate(() =>
        dispatchEvent(new CustomEvent('dot-sidechat-changed'))
      );
      await notice.waitFor({ state: 'detached' });
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth
        )
      );
      assert.equal(JSON.stringify(s.messages), original);
      assert.ok(s.requests.every((r) => r.method === 'GET'));
      assert.equal(s.sends.length, 0);
      assert.equal(errors.length, 0, errors.join('\n'));
      results.push({
        width,
        pass: true,
        visual,
        scope: 'project despite workspace selection',
        counts: '3→7→0; workspace stays1',
        state: 'draft/reply restored, flags unchanged',
        requests: 'GET only',
      });
      console.log('PASS project notice browser', width);
    } finally {
      await context.close();
    }
  }
  await writeFile(
    output + '/project-notices-browser-results.json',
    JSON.stringify(results, null, 2) + '\n'
  );
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
}
