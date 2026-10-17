import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || 'playwright-core'
);

const viewer = await readFile('packages/public/vk-artifact-viewer.html');
const id = 'e4be627d-9de5-4861-8a60-746ffb9f2478';
const requests = [];
const report = `<!doctype html><h1>Frame review</h1><button onclick="document.querySelector('h1').textContent='Next frame'">Next</button><button onclick="location.href='https://escape.invalid/report'">Escape</button><script>try { parent.document.body.dataset.leaked='yes'; } catch { window.parentBlocked=true; } fetch('/api/should-never-be-called',{method:'POST'}).catch(()=>{});</script>`;
const server = createServer((req, res) => {
  requests.push([req.method, req.url]);
  if (req.url.startsWith('/vk-artifact-viewer.html')) {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(viewer);
  } else if (req.url === `/api/attachments/${id}/file`) {
    res.writeHead(200, { 'Content-Type': 'application/octet-stream' });
    res.end(report);
  } else {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  headless: true,
  chromiumSandbox: true,
  executablePath: process.env.CHROMIUM_PATH,
});
try {
  for (const width of [1440, 393]) {
    const page = await browser.newPage({ viewport: { width, height: 852 } });
    const escapes = [];
    await page.route('https://escape.invalid/**', (route) => {
      escapes.push(route.request().url());
      return route.fulfill({ status: 200, body: 'Unexpected escape' });
    });
    await page.goto(
      `${origin}/vk-artifact-viewer.html?id=${id}&name=Review.html`,
    );
    const frame = page.frameLocator('iframe');
    await frame.getByRole('heading', { name: 'Frame review' }).waitFor();
    await frame.getByRole('button', { name: 'Next' }).click();
    await frame.getByRole('heading', { name: 'Next frame' }).waitFor();
    assert.equal(
      await page.locator('iframe').getAttribute('sandbox'),
      'allow-scripts',
    );
    assert.equal(
      await page.evaluate(() => document.body.dataset.leaked),
      undefined,
    );
    assert.equal(
      await page.frames()[1].evaluate(() => window.parentBlocked),
      true,
    );
    assert.equal(
      await page.locator('#download').getAttribute('href'),
      `/api/attachments/${id}/file`,
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    await frame.getByRole('button', { name: 'Escape' }).click();
    await page.waitForTimeout(200);
    assert.deepEqual(escapes, []);
    await page.goto(`${origin}/vk-artifact-viewer.html?id=../../etc/passwd`);
    await page
      .getByText('This report link has no valid attachment ID.')
      .waitFor();
    assert.equal(await page.locator('iframe').isVisible(), false);
    await page.close();
    console.log(
      `PASS report controls, isolation and invalid-ID handling at ${width}px`,
    );
  }
  assert.ok(requests.every(([method]) => method === 'GET'));
  assert.ok(
    !requests.some(
      ([, url]) =>
        url.includes('should-never-be-called') ||
        (url.includes('etc/passwd') && !url.startsWith('/vk-artifact-viewer')),
    ),
  );
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
