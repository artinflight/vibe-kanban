// Read-only live running conversation; every application write is intercepted.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "/usr/lib/node_modules/playwright/index.mjs"
);
const base = process.env.VK_TEST_BASE,
  output = process.env.VK_TEST_OUTPUT,
  workspace = process.env.VK_TEST_WORKSPACE,
  project = process.env.VK_TEST_PROJECT,
  issue = process.env.VK_TEST_ISSUE,
  dist = process.env.VK_TEST_DIST;
const reproduce = process.env.VK_TEST_REPRODUCE_PENDING_READ === "1";
assert(base && output && workspace && project && issue);
const processId = process.env.VK_TEST_RUNNING_PROCESS_ID;
assert(processId, "Supply a known running process in the tested workspace");
const checkRunning = async () => {
  const response = await fetch(`${base}/api/execution-processes/${processId}`);
  assert.equal(response.status, 200);
  const value = await response.json();
  assert.equal(value.data.status, "running");
};
await checkRunning();
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    "/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell",
  headless: true,
  args: ["--no-sandbox"],
});
const reads = [],
  errors = [];
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  await context.route("**/*", async (route) => {
    const req = route.request(),
      url = new URL(req.url());
    if (url.origin !== new URL(base).origin) return route.continue();
    if (
      req.method() === "PUT" &&
      url.pathname === `/api/workspaces/${workspace}/seen`
    ) {
      reads.push({ method: req.method(), body: req.postData() });
      return route.fulfill({ json: { success: true, data: null } });
    }
    if (req.method() === "POST" && url.pathname === "/api/workspaces/summaries")
      return route.continue();
    if (!["GET", "HEAD"].includes(req.method()))
      return route.fulfill({ json: { success: true, data: null } });
    if (dist && !/^\/(api|v1)\//.test(url.pathname)) {
      const relative = decodeURIComponent(url.pathname).slice(1);
      assert(!relative.split("/").includes(".."));
      let file = path.join(dist, relative || "index.html");
      try {
        if (!(await fs.stat(file)).isFile())
          file = path.join(dist, "index.html");
      } catch {
        file = path.join(dist, "index.html");
      }
      return route.fulfill({ path: file });
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(
    `${base}/projects/${project}/issues/${issue}/workspaces/${workspace}`,
    { waitUntil: "domcontentloaded", timeout: 60000 },
  );
  await page.locator("[data-row-index]").first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(1500);
  const reply = page.locator("[data-workspace-read-reply]").last();
  await reply.waitFor({ timeout: 60000 });
  await reply.evaluate((el) => el.scrollIntoView({ block: "end" }));
  await page.waitForTimeout(300);
  const rect = await reply.boundingBox();
  assert(rect);
  await page.mouse.move(
    rect.x + Math.min(100, rect.width / 2),
    Math.min(rect.y + rect.height - 5, 940),
  );
  await page.mouse.wheel(0, 1);
  await page.waitForTimeout(1000);
  assert.equal(await page.evaluate(() => document.hasFocus()), true);
  if (reproduce)
    assert(
      reads.length > 0,
      "Previous frontend incorrectly acknowledges while a newer turn is still running",
    );
  else
    assert.equal(
      reads.length,
      0,
      "A running/approval turn must not be acknowledged by an older visible reply",
    );
  assert.deepEqual(errors, []);
  await checkRunning();
  await page.screenshot({ path: path.join(output, "pending-turn.png") });
  const result = {
    passed: true,
    reproducedPrematureRead: reproduce,
    guardedPendingTurn: !reproduce,
    readRequests: reads.length,
    pageErrors: errors,
    liveApplicationWrites: 0,
    runningProcessVerified: true,
  };
  await fs.writeFile(
    path.join(output, "results.json"),
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result));
  await context.close();
} finally {
  await browser.close();
}
