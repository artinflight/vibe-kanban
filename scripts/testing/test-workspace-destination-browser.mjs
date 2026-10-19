// Hosted Chromium, production components/hooks and built candidate CSS; synthetic APIs only.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import { bundleDestinationFixture } from './workspace-destination-support.mjs';
const { chromium } = await import(
  pathToFileURL(process.env.PLAYWRIGHT_MODULE).href
);
const dist = resolve('packages/local-web/dist');
const index = await readFile(resolve(dist, 'index.html'), 'utf8');
const css = index.match(/href="([^"]+\.css)"/)[1];
const bundle = await bundleDestinationFixture();
const server = createServer(async (req, res) => {
  try {
    if (req.url === '/') {
      res.setHeader('Content-Type', 'text/html');
      res.end(
        `<link rel="stylesheet" href="${css}"><div id="root"></div><script src="/fixture.js"></script>`
      );
    } else if (req.url === '/fixture.js') {
      res.setHeader('Content-Type', 'text/javascript');
      res.end(bundle.outputFiles[0].text);
    } else {
      const file = resolve(
        dist,
        '.' + new URL(req.url, 'http://fixture.invalid').pathname
      );
      assert.ok(file.startsWith(dist + sep));
      res.setHeader(
        'Content-Type',
        file.endsWith('.css')
          ? 'text/css'
          : file.endsWith('.woff2')
            ? 'font/woff2'
            : 'application/octet-stream'
      );
      res.end(await readFile(file));
    }
  } catch {
    res.statusCode = 404;
    res.end();
  }
});
await new Promise((done) => server.listen(0, '127.0.0.1', done));
const base = 'http://127.0.0.1:' + server.address().port;
const browser = await chromium.launch({
  executablePath: process.env.CHROME_BIN,
  headless: true,
  args: ['--no-sandbox', '--disk-cache-size=1', '--media-cache-size=1'],
});
try {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
    });
    try {
      await context.route('**/*', (route) =>
        route
          .request()
          .url()
          .startsWith(base + '/')
          ? route.continue()
          : route.abort()
      );
      await context.addInitScript((phone) => {
        const name = (id) =>
          'Human workspace ' + id + ' — ' + 'synthetic recipient '.repeat(9);
        let releaseB;
        const waitB = new Promise((done) => {
          releaseB = done;
        });
        const row = (id) => ({
          id,
          name: name(id),
          branch: 'vk/opaque-branch-' + id,
        });
        const f = (window.fixture = {
          workspaceId: 'B',
          mobile: phone,
          showNavbar: true,
          calls: [],
          renders: [],
          navigations: [],
          local: { activeWorkspaces: [row('A')], archivedWorkspaces: [] },
          remote: [
            {
              id: 'remote-A',
              local_workspace_id: 'A',
              project_id: 'project',
              issue_id: 'issue',
              name: name('A'),
            },
          ],
          getWorkspace: (id) => (id === 'B' ? waitB : Promise.resolve(row(id))),
          getSessions: async (id) => [
            { id: id + '-session', workspace_id: id },
          ],
          createSession: async ({ workspace_id }) => ({
            id: workspace_id + '-new',
            workspace_id,
          }),
          followUp: async (id, body) => {
            f.calls.push({ id, body });
          },
          releaseB: () => releaseB(row('B')),
          filterParams: {
            issues: [],
            issueAssignees: [],
            issueTags: [],
            issueRelationships: [],
            issuesById: new Map(),
            doneStatusIds: new Set(),
            showSubIssues: true,
            hideBlocked: false,
          },
        });
      }, width < 768);
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.goto(base);
      await page.waitForFunction(
        () => window.fixture.composer?.mode === 'placeholder'
      );
      assert.deepEqual(
        await page.evaluate(() => window.fixture.navigations),
        []
      );
      await page.evaluate(() => window.fixture.releaseB());
      await page.waitForFunction(
        () => window.fixture.composer?.session?.workspace_id === 'B'
      );
      const header = page.getByRole('button', {
        name: 'Open workspace',
        exact: true,
      });
      assert.match(await header.textContent(), /^Human workspace B/);
      assert.equal(
        await header.getAttribute('title'),
        await header.textContent()
      );
      const sizes = await page.evaluate(() =>
        [...document.querySelectorAll('.text-xl')]
          .filter((n) => n.textContent.startsWith('Human workspace B'))
          .map((n) => ({
            size: getComputedStyle(n).fontSize,
            weight: getComputedStyle(n).fontWeight,
          }))
      );
      assert.ok(
        sizes.length >= 2,
        'Full and embedded workspace headers are visible'
      );
      for (const item of sizes) {
        assert.equal(item.size, '20px');
        assert.ok(Number(item.weight) >= 600);
      }
      assert.ok(
        await page.evaluate(() => document.body.scrollWidth <= innerWidth + 1),
        'Long name does not overflow viewport'
      );
      await page.locator('#composer input').fill('Synthetic B browser prompt');
      await page
        .getByRole('button', { name: 'Synthetic send', exact: true })
        .click();
      await page.waitForFunction(() => window.fixture.calls.length === 1);
      assert.equal(
        await page.evaluate(() => window.fixture.calls[0].id),
        'B-session'
      );
      await header.click();
      assert.deepEqual(await page.evaluate(() => window.fixture.navigations), [
        ['goToWorkspace', 'B'],
      ]);
      await page.evaluate(() => {
        window.fixture.workspaceId = 'C';
        window.fixture.render();
      });
      await page.waitForFunction(
        () => window.fixture.composer?.session?.workspace_id === 'C'
      );
      assert.match(await header.textContent(), /^Human workspace C/);
      await page.locator('#composer input').fill('Synthetic C browser prompt');
      await page
        .getByRole('button', { name: 'Synthetic send', exact: true })
        .click();
      await page.waitForFunction(() => window.fixture.calls.length === 2);
      assert.deepEqual(
        await page.evaluate(() => window.fixture.calls.map((c) => c.id)),
        ['B-session', 'C-session']
      );
      assert.deepEqual(errors, []);
      console.log(
        `PASS hosted Chromium ${width}: full/embedded20px human headers, long-name containment, delayed record, displayed destination and exact synthetic prompt recipient.`
      );
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
