import { build } from "esbuild";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import assert from "node:assert/strict";

const output = process.env.VK_TEST_OUTPUT;
if (!output || !process.env.PLAYWRIGHT_MODULE) {
  throw new Error(
    "Set VK_TEST_OUTPUT on the mounted SSD and PLAYWRIGHT_MODULE",
  );
}
await mkdir(output, { recursive: true });
await build({
  entryPoints: ["scripts/testing/chat-scroll-browser.tsx"],
  outfile: resolve(output, "chat-scroll.js"),
  bundle: true,
  platform: "browser",
  jsx: "automatic",
  tsconfig: "packages/web-core/tsconfig.json",
  alias: {
    react: resolve("packages/web-core/node_modules/react"),
    "react-dom": resolve("packages/web-core/node_modules/react-dom"),
  },
});
await writeFile(
  resolve(output, "index.html"),
  '<div id="root"></div><script src="chat-scroll.js"></script>',
);
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
});
try {
  const page = await browser.newPage();
  await page.goto(`file://${resolve(output, "index.html")}`);
  const bottom = () =>
    page.waitForFunction(() => {
      const el = document.querySelector("#chat");
      return (
        el && Math.abs(el.scrollHeight - el.clientHeight - el.scrollTop) <= 1
      );
    });
  await bottom();
  console.log("PASS: open a populated conversation at the bottom");
  await page.getByText("Grow", { exact: true }).click();
  await bottom();
  console.log("PASS: remain at bottom as initial content grows");
  await page.locator("#chat").hover();
  await page.mouse.wheel(0, -1600);
  await page.waitForFunction(
    () => document.querySelector("#chat").scrollTop < 4000,
  );
  const before = await page.locator("#chat").evaluate((el) => el.scrollTop);
  await page.getByText("Grow", { exact: true }).click();
  assert.equal(
    await page.locator("#chat").evaluate((el) => el.scrollTop),
    before,
  );
  console.log("PASS: user can read earlier messages without being pulled down");
  await page.getByText("Resume", { exact: true }).click();
  await bottom();
  await page.getByText("Grow", { exact: true }).click();
  await bottom();
  console.log("PASS: instant resume restores bottom following");
  const moveUp = async () => {
    await page.locator("#chat").hover();
    await page.mouse.wheel(0, -1600);
    await page.waitForFunction(() => {
      const el = document.querySelector("#chat");
      return el.scrollHeight - el.clientHeight - el.scrollTop > 500;
    });
  };
  await moveUp();
  await page.getByText("Switch chat", { exact: true }).click();
  await bottom();
  console.log("PASS: switching conversation scope resumes at bottom");
  await moveUp();
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  const hiddenTop = await page.locator("#chat").evaluate((el) => el.scrollTop);
  assert.ok(hiddenTop < 6000);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await bottom();
  console.log("PASS: returning to visible tab resumes at bottom");
  await moveUp();
  await page.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await bottom();
  console.log("PASS: restored browser page resumes at bottom");
} finally {
  await browser.close();
}
