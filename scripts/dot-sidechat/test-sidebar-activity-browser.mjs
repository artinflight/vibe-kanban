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
