import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { chromium } from '/mnt/vk-storage/codexusage-capacity/format/node_modules/playwright-core/index.mjs';
const root = '/mnt/vk-storage/codexusage-capacity/vk-continuation-http-9uy_k779';
const output = '/mnt/vk-storage/codexusage-capacity/pr112-repair';
const f = JSON.parse(await readFile(`${root}/fixture.json`, 'utf8'));
const browser = await chromium.launch({executablePath:'/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox'],env:{...process.env,TMPDIR:`${root}/tmp`}});
const results=[];
try {
  for (const viewport of [{width:1360,height:1000},{width:390,height:844}]) {
    const page=await browser.newPage({viewport}); const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:49173/workspaces/${f.workspaceId}`,{waitUntil:'networkidle'});
    await page.getByRole('region',{name:'Goal checkpoint'}).first().waitFor({timeout:30000});
    assert.ok(await page.getByRole('region',{name:'Goal checkpoint'}).count());
    assert.deepEqual(errors,[]);
    await page.screenshot({path:`${output}/checkpoint-${viewport.width}.png`,fullPage:true});
    results.push({viewport,checkpoints:await page.getByRole('region',{name:'Goal checkpoint'}).count(),errors,assets:await page.evaluate(()=>[...document.scripts].map(s=>s.src).filter(Boolean))});
    await page.close();
  }
} finally { await browser.close(); await writeFile(`${output}/browser-results.json`,JSON.stringify(results,null,2)+'\n'); }
