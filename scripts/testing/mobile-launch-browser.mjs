// Launch-only acceptance. CDP intercepts API writes without disabling asset cache.
// Use a fresh, task-owned persistent profile; never use an operator profile.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { resolve } from "node:path";
import { randomUUID, createHash } from "node:crypto";

const base = process.env.VK_LAUNCH_BASE;
const output = process.env.VK_LAUNCH_OUTPUT;
const backend = process.env.VK_TEST_BACKEND;
const expectedRoot = process.env.VK_LAUNCH_EXPECT_ROOT;
const expectedTabRoute = process.env.VK_LAUNCH_EXPECT_TAB_ROUTE;
assert(base && output && backend && expectedRoot && expectedTabRoute);
assert(output.startsWith("/mnt/vk-storage/"));
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const { default: bundle } = await import(process.env.PLAYWRIGHT_WS_BUNDLE);
await fs.mkdir(output, { recursive: true });
const results = [];

for (const width of [390, 412]) {
  const profile = resolve(output, `profile-${width}-${randomUUID()}`);
  const steps = [];
  let blockedWrites = 0;
  let restoredUrl;
  for (const restart of [false, true]) {
    const context = await chromium.launchPersistentContext(profile, {
      executablePath: process.env.CHROMIUM_PATH,
      headless: true,
      ignoreHTTPSErrors: true,
      viewport: { width, height: 844 },
      isMobile: true,
      hasTouch: true,
      userAgent:
        "Mozilla/5.0 (Linux; Android 15; SM-S936W) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    });
    const sockets = new Set();
    let closing = false;
    const interceptErrors = [];
    try {
      await context.routeWebSocket("**/api/**", (route) => {
        const source = new URL(route.url());
        const target = new URL(source.pathname + source.search, backend);
        target.protocol = target.protocol === "https:" ? "wss:" : "ws:";
        const socket = new bundle.ws(target, {
          origin: new URL(backend).origin,
        });
        sockets.add(socket);
        socket.on("message", (data) => route.send(data.toString()));
        socket.on("error", () => route.close());
        socket.on("close", () => {
          sockets.delete(socket);
          route.close();
        });
        route.onClose(() => socket.close());
      });
      const page = context.pages()[0] ?? (await context.newPage());
      page.setDefaultTimeout(60000);
      const cdp = await context.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Fetch.enable", {
        patterns: ["*/api/*", "*/v1/*"].map((urlPattern) => ({
          urlPattern,
          requestStage: "Request",
        })),
      });
      await cdp.send("Network.setCacheDisabled", { cacheDisabled: false });
      cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
        try {
          const path = new URL(request.url).pathname;
          if (
            ["GET", "HEAD"].includes(request.method) ||
            (request.method === "POST" && path === "/api/workspaces/summaries")
          ) {
            await cdp.send("Fetch.continueRequest", { requestId });
          } else {
            blockedWrites++;
            const payload = request.postData
              ? JSON.parse(request.postData)
              : null;
            await cdp.send("Fetch.fulfillRequest", {
              requestId,
              responseCode: 200,
              responseHeaders: [
                { name: "Content-Type", value: "application/json" },
              ],
              body: Buffer.from(
                JSON.stringify({ success: true, data: payload }),
              ).toString("base64"),
            });
          }
        } catch (error) {
          if (!closing) interceptErrors.push(error.message);
        }
      });
      const cacheRequests = new Set();
      const requests = new Map();
      const responses = [];
      cdp.on("Network.requestWillBeSent", ({ requestId, request }) => {
        requests.set(requestId, new URL(request.url).pathname);
      });
      cdp.on("Network.requestServedFromCache", ({ requestId }) => {
        cacheRequests.add(requestId);
      });
      cdp.on("Network.responseReceived", ({ requestId, response }) => {
        const path = new URL(response.url).pathname;
        if (!path.startsWith("/api/") && !path.startsWith("/v1/"))
          responses.push({
            requestId,
            path,
            diskCache: response.fromDiskCache ?? false,
            serviceWorker: response.fromServiceWorker ?? false,
          });
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      const goto = (path) =>
        page.goto(new URL(path, base).href, {
          waitUntil: "domcontentloaded",
          timeout: 90000,
        });
      const capture = async (name, expectedPath, expectedView) => {
        await page.waitForURL((url) => url.pathname === expectedPath);
        const search = page
          .getByRole("textbox", { name: /search workspaces/i })
          .filter({ visible: true });
        const composer = page.locator('[contenteditable="true"]').filter({
          visible: true,
        });
        await (expectedView === "workspaces" ? search : composer).waitFor();
        const script = await page
          .locator('script[type="module"][src]')
          .last()
          .getAttribute("src");
        const response = await context.request.get(new URL(script, base).href);
        assert.equal(response.status(), 200);
        const manifestUrl = await page
          .locator('link[rel="manifest"]')
          .getAttribute("href");
        const manifestResponse = await context.request.get(
          new URL(manifestUrl, base).href,
        );
        const manifest = await manifestResponse.json();
        if (process.env.VK_LAUNCH_EXPECT_MANIFEST_START) {
          assert.equal(
            manifest.start_url,
            process.env.VK_LAUNCH_EXPECT_MANIFEST_START,
          );
          assert.equal(new URL(manifestUrl, base).search, "?v=workspaces-home");
        }
        const worker = await page.evaluate(async () => ({
          controller: navigator.serviceWorker?.controller?.scriptURL ?? null,
          registrations: navigator.serviceWorker
            ? (await navigator.serviceWorker.getRegistrations()).map(
                (registration) => registration.active?.scriptURL ?? null,
              )
            : [],
          cacheNames: "caches" in window ? await caches.keys() : [],
        }));
        const cachedAssets = responses
          .filter(
            (row) =>
              row.path.startsWith("/assets/") &&
              (row.diskCache || cacheRequests.has(row.requestId)),
          )
          .map((row) => row.path);
        steps.push({
          name,
          url: page.url(),
          view: expectedView,
          module: script,
          moduleSha256: createHash("sha256")
            .update(await response.body())
            .digest("hex"),
          manifestUrl,
          declaredStartUrl: manifest.start_url ?? null,
          cachedAssets: [...new Set(cachedAssets)],
          ...worker,
          errors: [...errors],
        });
        assert.deepEqual(errors, []);
        assert.deepEqual(interceptErrors, []);
        await page.screenshot({
          path: resolve(output, `${name}-${width}.png`),
        });
        console.log(`PASS ${width}px ${name}: ${expectedPath}`);
      };
      const rootView = expectedRoot === "/workspaces" ? "workspaces" : "create";
      if (!restart) {
        await goto("/");
        await capture("cold-root", expectedRoot, rootView);
        await page.reload();
        await capture("reload", expectedRoot, rootView);
        await goto("/");
        await capture("warm-root", expectedRoot, rootView);
        await goto("/workspaces");
        await capture("workspaces-link", expectedRoot, rootView);
        await goto("/workspaces/create");
        await capture("explicit-create", "/workspaces/create", "create");
        restoredUrl = page.url();
      } else {
        await goto(restoredUrl);
        await capture("restored-create-url", "/workspaces/create", "create");
        await page
          .getByRole("navigation", { name: "Primary navigation" })
          .getByRole("button", { name: "Workspaces", exact: true })
          .click();
        await capture("workspaces-tab", expectedTabRoute, "workspaces");
        await page.reload();
        await capture(
          "reload-after-workspaces-tab",
          expectedTabRoute,
          expectedTabRoute === "/workspaces" ? "workspaces" : "create",
        );
        await goto("/");
        await capture("restarted-root", expectedRoot, rootView);
      }
    } finally {
      closing = true;
      for (const socket of sockets) socket.close();
      await context.close();
    }
  }
  results.push({
    width,
    passed: true,
    steps,
    blockedWrites,
    promptSubmitted: false,
  });
  await fs.writeFile(
    resolve(output, "results.json"),
    JSON.stringify(results, null, 2) + "\n",
  );
}
