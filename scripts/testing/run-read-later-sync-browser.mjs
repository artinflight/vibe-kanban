// Focused browser integration: production hook/API/store/sidebar and real Rust
// routes, with test-only authentication and deployment wrappers. No live writes.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
import { build } from 'esbuild';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { chromium } from '/usr/lib/node_modules/playwright/index.mjs';
const output = process.env.VK_TEST_OUTPUT,
  api = process.env.VK_TEST_READ_LATER_API,
  assets = process.env.VK_TEST_ASSETS;
assert(output && api && assets);
await mkdir(output, { recursive: true });
process.env.TMPDIR = output;
const fixture = resolve('scripts/testing/read-later.fixture.tsx');
await build({
  entryPoints: ['scripts/testing/read-later-sync.fixture.tsx'],
  outfile: join(output, 'fixture.js'),
  bundle: true,
  format: 'esm',
  jsx: 'automatic',
  tsconfig: 'packages/web-core/tsconfig.json',
  define: { 'import.meta.env': '{}' },
  plugins: [
    {
      name: 'auth-only',
      setup(b) {
        b.onResolve(
          { filter: /^(react(?:-dom)?(?:\/.*)?|react-i18next|i18next)$/ },
          (args) => ({
            path: require.resolve(args.path, {
              paths: [resolve('packages/ui'), resolve('packages/web-core')],
            }),
          })
        );
        b.onResolve(
          {
            filter:
              /^@\/shared\/(hooks\/auth\/useAuth|providers\/HostIdProvider)$/,
          },
          () => ({ path: fixture })
        );
      },
    },
  ],
});
const unexpected = [],
  errors = [];
const server = createServer(async (request, response) => {
  try {
    const path = new URL(request.url, 'http://fixture').pathname;
    if (path.startsWith('/api/read-later/')) {
      let body = '';
      for await (const chunk of request) body += chunk;
      const upstream = await fetch(api + path, {
        method: request.method,
        headers: { 'Content-Type': 'application/json' },
        ...(body ? { body } : {}),
      });
      response.writeHead(upstream.status, {
        'Content-Type': 'application/json',
      });
      response.end(await upstream.text());
      return;
    }
    if (path.startsWith('/api/')) {
      unexpected.push(path);
      response.writeHead(400);
      response.end();
      return;
    }
    if (path === '/fixture.js') {
      response.setHeader('Content-Type', 'application/javascript');
      response.end(await readFile(join(output, 'fixture.js')));
      return;
    }
    if (path.startsWith('/assets/')) {
      assert(!decodeURIComponent(path).split('/').includes('..'));
      response.setHeader(
        'Content-Type',
        path.endsWith('.css') ? 'text/css' : 'application/octet-stream'
      );
      response.end(await readFile(join(assets, path)));
      return;
    }
    response.setHeader('Content-Type', 'text/html');
    response.end(
      '<html class="new-design"><head><link rel="stylesheet" href="/assets/index-DeUaYq-8.css"></head><body><div id="root" style="height:100vh"></div><script type="module" src="/fixture.js"></script></body></html>'
    );
  } catch (e) {
    response.writeHead(500);
    response.end(String(e));
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  executablePath:
    '/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',
  args: ['--no-sandbox'],
});
const scope = JSON.stringify(['local', 'owner']),
  item = { kind: 'workspace', id: 'premiere', name: 'Premiere Pro to mobile' };
const legacy = {
  state: { items: { [JSON.stringify([scope, item.kind, item.id])]: item } },
  version: 0,
};
const header = (page, count) =>
  page
    .locator('button[aria-expanded]')
    .filter({ hasText: new RegExp('^Read Later\\s*' + count) });
const focus = async (page) => {
  await page.bringToFront();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
};
async function context(width, seed) {
  const c = await browser.newContext({
    viewport: { width, height: 1000 },
    isMobile: width < 768,
    hasTouch: width < 768,
  });
  if (seed)
    await c.addInitScript(
      (value) =>
        localStorage.setItem('vk-read-later-v1', JSON.stringify(value)),
      seed
    );
  const page = await c.newPage();
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(base);
  return { c, page };
}
try {
  const desktop = await context(1440, legacy);
  await header(desktop.page, 1).waitFor();
  const mobile = await context(393);
  await header(mobile.page, 1).waitFor();
  const mobileHeader = header(mobile.page, 1);
  if ((await mobileHeader.getAttribute('aria-expanded')) === 'false')
    await mobileHeader.click();
  await mobile.page
    .getByRole('button', { name: 'Remove from Read Later', exact: true })
    .click();
  await header(mobile.page, 0).waitFor();
  await focus(desktop.page);
  await header(desktop.page, 0).waitFor();
  const stale = await context(393, legacy);
  await header(stale.page, 0).waitFor();
  await stale.page.waitForFunction(() =>
    Object.values(
      JSON.parse(localStorage.getItem('vk-read-later-v1')).state.migratedScopes
    ).includes(true)
  );
  assert.equal(
    (await (await fetch(api + '/api/read-later/owner')).json()).data.find(
      (r) => r.item.id === 'premiere'
    ).saved,
    false
  );
  await focus(desktop.page);
  await desktop.page
    .getByRole('button', { name: 'Read Later', exact: true })
    .click();
  await header(desktop.page, 1).waitFor();
  await focus(mobile.page);
  await header(mobile.page, 1).waitFor();
  await mobile.page.reload();
  await header(mobile.page, 1).waitFor();
  await mobile.c.setOffline(true);
  await mobile.page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await mobile.page
    .getByRole('alert')
    .filter({ hasText: 'Read Later has not synced' })
    .waitFor();
  await mobile.c.setOffline(false);
  await mobile.page.evaluate(() => window.dispatchEvent(new Event('online')));
  await mobile.page.getByRole('alert').waitFor({ state: 'detached' });
  assert.deepEqual(errors, []);
  assert.deepEqual(unexpected, []);
  await mobile.page.screenshot({ path: join(output, 'mobile-synced.png') });
  const result = {
    passed: true,
    independentBrowserContexts: 3,
    legacyDesktopImported: true,
    desktopSaveVisibleOnMobile: true,
    mobileRemovalVisibleOnDesktop: true,
    staleImportDoesNotResurrect: true,
    reloadPersists: true,
    offlineWarningAndRecovery: true,
    unexpectedRequests: unexpected,
    pageErrors: errors,
    scope:
      'Production hook, API client, store, sidebar and Rust routes with isolated SQLite; authentication/deployment wrappers are test shims. Full production build is separate.',
  };
  await writeFile(
    join(output, 'results.json'),
    JSON.stringify(result, null, 2)
  );
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
}
