// Fresh, unpaired browser and isolated fixture server; no production API access.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { sidebarActivityBundle } from './sidebar-activity-test-support.mjs';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);
const bundle = await sidebarActivityBundle();
let css = '';
if (process.env.DOT_BASELINE_RELEASE) {
  const release = process.env.DOT_BASELINE_RELEASE;
  const html = await readFile(release + '/index.html', 'utf8');
  css = await readFile(
    release + html.match(/href="(\/assets\/[^\"]+\.css)"/)[1],
    'utf8'
  );
}
const server = createServer((req, res) => {
  if (req.url === '/fixture.js') {
    res.setHeader('Content-Type', 'text/javascript');
    res.end(bundle.outputFiles[0].text);
  } else if (req.url === '/fixture.css') {
    res.setHeader('Content-Type', 'text/css');
    res.end(css + '\nbody{margin:0}.new-design{height:100vh}');
  } else if (req.url === '/') {
    res.end(
      '<html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/fixture.css"><body class="new-design"><div id="root" style="height:100%"></div><script src="/fixture.js"></script></body></html>'
    );
  } else {
    res.statusCode = 404;
    res.end();
  }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
  args: ['--no-sandbox'],
});
const expected = {
  Running: [
    'Running unread',
    'Running attention',
    'Running approval',
    'Active subagent',
    'Unresolved subagent',
    'Subagent approval',
    'Subagent attention',
  ],
  Attention: [
    'Running attention',
    'Running approval',
    'Subagent approval',
    'Subagent attention',
    'Idle unseen',
    'Idle Dot unread',
    'Idle approval',
    'Idle attention',
    'Dispatch target',
  ],
  Ready: ['Idle clean', 'Dispatch sibling'],
};
try {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({
      viewport: { width, height: 950 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.route('**/api/**', () => {
      throw Error('Production API route forbidden');
    });
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.locator('.mobile-workspace-card').first().waitFor();
    async function assertReadable() {
      const rows = await page
        .locator('.mobile-workspace-card > button:first-of-type')
        .evaluateAll((buttons) =>
          buttons.map((button) => {
            let opacity = 1;
            for (let node = button; node; node = node.parentElement)
              opacity *= Number(getComputedStyle(node).opacity);
            return {
              opacity,
              actionable: !button.disabled,
              normalText: button.classList.contains('text-normal'),
            };
          })
        );
      assert.ok(rows.length > 0);
      assert.ok(rows.every((row) => row.actionable && row.opacity === 1));
      if (width >= 768) assert.ok(rows.every((row) => row.normalText));
    }
    await assertReadable();
    await page.evaluate(() => window.fixtureSelect('idle'));
    await page.locator('[aria-current="page"]').waitFor();
    await assertReadable();
    await page.evaluate(() => window.fixtureSelect('running-unread'));
    await assertReadable();
    await page.evaluate(() => window.fixtureSelect(null));
    for (const [category, names] of Object.entries(expected)) {
      let root;
      if (width < 768) {
        await page
          .locator('.phone-workspace-tabs button')
          .filter({ hasText: new RegExp('^' + category + '\\d+$') })
          .click();
        root = page.locator('.phone-workspace-scroll');
      } else {
        const label =
          { Attention: 'Needs Attention', Ready: 'Idle' }[category] ?? category;
        root = page
          .getByRole('button', { name: label, exact: true })
          .locator('..')
          .locator('..');
      }
      await page.waitForTimeout(50);
      await assertReadable();
      assert.deepEqual(
        await root
          .locator('.mobile-workspace-card')
          .evaluateAll((nodes) =>
            nodes.map(
              (n) =>
                (
                  n.querySelector('.phone-workspace-name') ??
                  n.querySelector('button > div')
                ).textContent
            )
          ),
        names
      );
      if (process.env.VK_TEST_OUTPUT) {
        await mkdir(process.env.VK_TEST_OUTPUT, { recursive: true });
        await page.screenshot({
          path: `${process.env.VK_TEST_OUTPUT}/sidebar-${category}-${width}.png`,
          fullPage: true,
        });
      }
      if (category === 'Running') {
        assert.equal(
          await root.locator('[aria-label="Dot unread replies: 5"]').count(),
          1
        );
        assert.ok(
          await root.locator('[aria-label="Dot unread replies: 1"]').count()
        );
        assert.ok(
          await root.locator('[aria-label="Dot Needs Attention: 1"]').count()
        );
        assert.ok(
          width < 768
            ? await root.getByText('Approval needed', { exact: true }).count()
            : await root.locator('[aria-label="Pending approval"]').count()
        );
      }
    }
    // A managed clean row remains readable and labeled after read/clear and reload.
    async function section(category) {
      if (width < 768) {
        await page
          .locator('.phone-workspace-tabs button')
          .filter({ hasText: new RegExp('^' + category + '\\d+$') })
          .click();
        return page.locator('.phone-workspace-scroll');
      }
      return page
        .getByRole('button', {
          name: category === 'Attention' ? 'Needs Attention' : category,
          exact: true,
        })
        .locator('..')
        .locator('..');
    }
    for (const isRunning of [false, true]) {
      await page.evaluate(
        (running) =>
          window.fixtureUpdate('running-unread', { isRunning: running }),
        isRunning
      );
      for (const category of ['Running', 'Attention']) {
        const root = await section(category);
        const row = root
          .locator('.mobile-workspace-card')
          .filter({ hasText: 'Running unread' });
        const present = category === (isRunning ? 'Running' : 'Attention');
        await row.waitFor({ state: present ? 'attached' : 'detached' });
        assert.equal(await row.count(), Number(present));
        if (await row.count()) {
          assert.equal(
            await row.locator('[aria-label="Dot unread replies: 5"]').count(),
            1
          );
          assert.equal(
            await row.locator('[aria-label="Dot Needs Attention: 1"]').count(),
            0
          );
        }
      }
    }
    if (width < 768) await section('Ready');
    const clean = page
      .locator('.mobile-workspace-card')
      .filter({ hasText: 'Idle clean' });
    assert.equal(await clean.locator('[data-dot-managed]').count(), 1);
    assert.equal(
      await clean.locator('[data-dot-indicators]').textContent(),
      ''
    );
    assert.equal(
      await page
        .locator('.mobile-workspace-card')
        .filter({ hasText: 'Dispatch sibling' })
        .locator('[data-dot-managed]')
        .count(),
      0
    );
    for (const change of [
      { dotUnreadCount: 2, dotNeedsAttentionCount: 1 },
      {
        dotUnreadCount: 0,
        dotNeedsAttentionCount: 0,
        hasUnseenActivity: false,
      },
    ]) {
      await page.evaluate(
        (change) => window.fixtureUpdate('idle', change),
        change
      );
      if (width < 768)
        await page
          .locator('.phone-workspace-tabs button')
          .filter({ hasText: /^All\d+$/ })
          .click();
      await clean.locator('[data-dot-managed]').waitFor();
      assert.equal(await clean.locator('[data-dot-managed]').count(), 1);
      await assertReadable();
    }
    await page.reload();
    if (width < 768)
      await page
        .locator('.phone-workspace-tabs button')
        .filter({ hasText: /^Ready\d+$/ })
        .click();
    await clean.locator('[data-dot-managed]').waitFor();
    assert.equal(
      await clean.locator('[data-dot-indicators]').textContent(),
      ''
    );
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth
      )
    );
    if (process.env.VK_TEST_OUTPUT) {
      await mkdir(process.env.VK_TEST_OUTPUT, { recursive: true });
      await page.screenshot({
        path: `${process.env.VK_TEST_OUTPUT}/sidebar-grouping-${width}.png`,
        fullPage: true,
      });
    }
    assert.deepEqual(errors, []);
    await context.close();
    console.log(
      `PASS Chromium ${width}: actual Running/Attention/Idle membership, approvals and Dot badges retained, target/sibling dispatch attribution.`
    );
  }
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
