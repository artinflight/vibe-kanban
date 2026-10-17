import { build } from 'esbuild';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const output = process.env.VK_TEST_OUTPUT;
if (!output || !process.env.CHROMIUM_PATH)
  throw new Error(
    'Set VK_TEST_OUTPUT on mounted SSD, PLAYWRIGHT_MODULE and CHROMIUM_PATH'
  );
await build({
  entryPoints: ['scripts/testing/prompt-submission-browser.tsx'],
  outfile: output + '/guard.js',
  bundle: true,
  platform: 'browser',
  jsx: 'automatic',
  alias: {
    react: process.cwd() + '/packages/web-core/node_modules/react',
    'react-dom': process.cwd() + '/packages/web-core/node_modules/react-dom',
  },
});
await writeFile(
  output + '/guard.html',
  '<div id="root"></div><script src="guard.js"></script>'
);
const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
try {
  const page = await b.newPage();
  await page.goto('file://' + output + '/guard.html');
  const out = page.locator('output');
  await page
    .getByText('Concurrent Send and correction', { exact: true })
    .click();
  assert.equal(await out.innerText(), '1:true:false');
  await page.getByText('Send', { exact: true }).click();
  assert.equal(await out.innerText(), '1:true:false');
  await page
    .getByText('Finish request and draft cleanup', { exact: true })
    .click();
  assert.equal(await out.innerText(), '1:false:false');
  await page.getByText('Fail', { exact: true }).click();
  assert.equal(await out.innerText(), '2:false:true');
  await page.getByText('Send', { exact: true }).click();
  assert.equal(await out.innerText(), '3:false:true');
  console.log(
    'PASS: same-event concurrent calls; request/cleanup admission; rejection releases guard; explicit retry'
  );
} finally {
  await b.close();
}
