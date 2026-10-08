import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { build } from 'esbuild';

const output = process.env.VK_CHAT_UI_ARTIFACT_DIR;
if (!output) throw new Error('Set VK_CHAT_UI_ARTIFACT_DIR to a mounted SSD task directory');
await mkdir(output, { recursive: true });
await build({
  entryPoints: ['scripts/testing/supervisor-ui-fixture.tsx'],
  outfile: `${output}/fixture.js`, bundle: true, platform: 'browser', format: 'iife', jsx: 'automatic',
  nodePaths: [resolve('packages/web-core/node_modules')],
  tsconfig: 'packages/web-core/tsconfig.json',
  define: { 'process.env.NODE_ENV': '"test"', 'import.meta.env': '{}', 'import.meta.hot': 'undefined' },
});
const requireWeb = createRequire(resolve('packages/local-web/package.json'));
const postcss = requireWeb('postcss');
const tailwind = requireWeb('tailwindcss');
const loadConfig = requireWeb('tailwindcss/loadConfig');
const root = process.cwd();
const cssInput = resolve('packages/web-core/src/app/styles/new/index.css');
const configPath = resolve('packages/local-web/tailwind.new.config.js');
process.chdir(resolve('packages/local-web'));
try {
  const css = await postcss([tailwind(loadConfig(configPath))]).process(await readFile(cssInput,'utf8'), {from:cssInput});
  await writeFile(`${output}/fixture.css`, css.css);
} finally { process.chdir(root); }
const { chromium } = await import(process.env.VK_CHAT_PLAYWRIGHT_MODULE ?? 'playwright-core');
const browser = await chromium.launch({
  executablePath: process.env.VK_CHAT_CHROMIUM,
  args: ['--no-sandbox'],
  env: { ...process.env, TMPDIR: output },
});
const results = [];
try {
  for (const viewport of [{width:1360,height:900},{width:390,height:844}]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/*', (route) => route.abort());
    await page.route('https://fixture.invalid/', (route) => route.fulfill({contentType:'text/html',body:'<!doctype html><html><body class="new-design"><div id="root"></div></body></html>'}));
    await page.goto('https://fixture.invalid/');
    await page.addStyleTag({content:await readFile(`${output}/fixture.css`,'utf8')});
    await page.addScriptTag({content:await readFile(`${output}/fixture.js`,'utf8')});
    const launcher = page.getByRole('button',{name:'Supervisor',exact:true});
    await launcher.click();
    const dialog = page.getByRole('dialog',{name:'Supervisor',exact:true});
    await dialog.getByText('The Android agent matched onboarding to web.',{exact:true}).waitFor();
    await dialog.getByText('Source reports',{exact:true}).click();
    await dialog.getByText('Original report 1',{exact:false}).click();
    assert.equal(await dialog.locator('pre').innerText(),await page.evaluate(() => window.__supervisorFixture.raw));
    const bounds = await dialog.boundingBox();
    assert.ok(bounds.x >= -1 && bounds.x + bounds.width <= viewport.width + 1);
    assert.ok(bounds.y >= -1 && bounds.height <= viewport.height + 1);
    await page.screenshot({path:`${output}/supervisor-${viewport.width}.png`});
    await dialog.getByRole('textbox',{name:'Message the supervisor'}).fill('Keep this draft while I change projects.');
    await page.keyboard.press('Escape');
    await dialog.waitFor({state:'hidden'});
    assert.equal(await launcher.evaluate((node) => node === document.activeElement),true);
    await page.getByRole('button',{name:'Navigate project'}).click();
    await launcher.click();
    const input = dialog.getByRole('textbox',{name:'Message the supervisor'});
    assert.equal(await input.inputValue(),'Keep this draft while I change projects.');
    await dialog.getByRole('button',{name:'Send',exact:true}).click();
    await dialog.getByRole('button',{name:'Retry the same message'}).click();
    await page.waitForFunction(() => window.__supervisorFixture.postIds.length === 2);
    const ids = await page.evaluate(() => window.__supervisorFixture.postIds);
    assert.equal(ids[0],ids[1]);
    assert.equal(await dialog.getByText('Keep this draft while I change projects.',{exact:true}).count(),1);
    await dialog.getByRole('button',{name:'Activity and preferences'}).click();
    await dialog.getByRole('button',{name:'Delete supervisor data',exact:true}).click();
    await dialog.getByText('Delete this supervisor conversation, saved preferences and retained report copies?',{exact:false}).waitFor();
    await dialog.getByRole('button',{name:'Delete supervisor data',exact:true}).last().click();
    await page.waitForFunction(() => window.__supervisorFixture.messageCount === 0);
    await dialog.getByText('Ask about your work, give an instruction, or pick up where you left off.',{exact:true}).waitFor();
    await page.keyboard.press('Escape');
    await dialog.waitFor({state:'hidden'});
    assert.equal(await page.locator('main pre').innerText(),await page.evaluate(() => window.__supervisorFixture.raw));
    assert.deepEqual(errors,[]);
    results.push({viewport,passed:true,scope:'Real UI with fixture transport; not live model/backend acceptance',checks:['owned local transport','raw source drill-down','viewport bounds','escape and restored focus','draft across navigation','idempotent retry after lost acknowledgement','confirmed supervisor deletion preserves raw workspace text']});
    await page.close();
  }
} finally {
  await browser.close();
  await writeFile(`${output}/results.json`,JSON.stringify(results,null,2)+'\n');
}
console.log(JSON.stringify(results,null,2));
