// Branch UI + real product comment routes on disposable SQLite. Other writes
// are blocked. No agent is launched and no production discussion is changed.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
const { chromium } = await import("/usr/lib/node_modules/playwright/index.mjs");
const base = process.env.VK_TEST_BASE;
const backend = process.env.VK_TEST_BACKEND;
const discussion = process.env.VK_TEST_DISCUSSION;
const output = process.env.VK_TEST_OUTPUT;
if (!base || !backend || !discussion || !output)
  throw Error(
    "Set VK_TEST_BASE, VK_TEST_BACKEND, VK_TEST_DISCUSSION and VK_TEST_OUTPUT on SSD",
  );
const issue = "b1fcd23b-b6b0-440c-80dd-ac646dbbec09";
const project = "48c03c77-4207-48c1-86ed-686262c1116a";
const browser = await chromium.launch({
  executablePath:
    "/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell",
  headless: true,
  args: ["--no-sandbox"],
});
const reports = [];
await fs.mkdir(output, { recursive: true });
try {
  for (const width of [1440, 393]) {
    const context = await browser.newContext({
      viewport: { width, height: 950 },
      isMobile: width < 768,
      hasTouch: width < 768,
    });
    const writes = [],
      feeds = [],
      baselineHtml = [],
      errors = [];
    let simulateFeedFailure = false;
    let startRequest = null;
    const scratch = new Map();
    const reads = [];
    try {
      await context.route(/\/(api|v1)\//, async (route) => {
        const req = route.request(),
          url = new URL(req.url());
        if (
          /^\/v1\/(?:fallback\/)?issue_comment(?:s|_reactions)(?:\/|$)/.test(
            url.pathname,
          )
        ) {
          if (simulateFeedFailure && url.pathname.includes("/fallback/"))
            return route.fulfill({
              contentType: "text/html",
              body: "<!doctype html><html><body>Original feed fault fixture</body></html>",
            });
          const response = await context.request.fetch(
            discussion + url.pathname + url.search,
            {
              method: req.method(),
              ...(req.postDataBuffer() && { data: req.postDataBuffer() }),
              headers: { "content-type": "application/json" },
            },
          );
          const entry = {
            path: url.pathname,
            method: req.method(),
            status: response.status(),
            contentType: response.headers()["content-type"],
          };
          if (req.method() === "GET") feeds.push(entry);
          else writes.push(entry);
          return route.fulfill({ response });
        }
        // Keep draft scratch in this browser, including reads after reload.
        if (
          url.pathname.includes("/api/scratch/") &&
          !["GET", "HEAD"].includes(req.method())
        ) {
          if (req.method() === "DELETE") scratch.delete(url.pathname);
          else
            scratch.set(url.pathname, {
              id: url.pathname.split("/").pop(),
              ...req.postDataJSON(),
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            });
          return route.fulfill({ json: { success: true, data: null } });
        }
        if (
          ["GET", "HEAD"].includes(req.method()) ||
          (req.method() === "POST" &&
            url.pathname === "/api/workspaces/summaries")
        ) {
          const response = await context.request.fetch(
            backend + url.pathname + url.search,
            {
              method: req.method(),
              ...(req.postDataBuffer() && { data: req.postDataBuffer() }),
              headers: {
                origin: new URL(backend).origin,
                "content-type": "application/json",
              },
            },
          );
          reads.push({ path: url.pathname, status: response.status() });
          if ((response.headers()["content-type"] ?? "").includes("text/html"))
            baselineHtml.push(url.pathname);
          return route.fulfill({ response });
        }
        if (url.pathname === "/api/workspaces/start") {
          startRequest = req.postDataJSON();
          return route.fulfill({
            status: 400,
            json: {
              success: false,
              message: "Browser test captured startup; no agent launched",
            },
          });
        }
        writes.push({
          path: url.pathname,
          method: req.method(),
          blocked: true,
        });
        return route.fulfill({ json: { success: true, data: null, txid: 0 } });
      });
      await context.routeWebSocket("**/api/**", (route) => {
        const path = new URL(route.url()).pathname.replace("/stream/ws", "");
        if (path.includes("/scratch/")) {
          route.send(
            JSON.stringify({
              JsonPatch: [
                {
                  op: "replace",
                  path: "/scratch",
                  value: scratch.get(path) ?? null,
                },
              ],
            }),
          );
          route.send(JSON.stringify({ Ready: true }));
        } else route.close();
      });
      const page = await context.newPage();
      page.on("pageerror", (e) => errors.push(e.message));
      const open = async () => {
        console.log("Opening issue", width);
        await page.goto(`${base}/projects/${project}`, {
          waitUntil: "commit",
          timeout: 60000,
        });
        await page
          .getByText("OP::Zonnic Labels", { exact: true })
          .first()
          .waitFor({ timeout: 60000 });
        await page
          .getByText("OP::Zonnic Labels", { exact: true })
          .first()
          .click();
        await page
          .getByRole("button", { name: "Comments", exact: true })
          .waitFor({ timeout: 120000 });
      };
      const section = () =>
        page
          .getByRole("button", { name: "Comments", exact: true })
          .locator("../..");
      const read = async (table) =>
        (
          await context.request.get(
            `${discussion}/v1/fallback/${table}?issue_id=${issue}`,
          )
        ).json();
      const until = async (predicate) => {
        for (let i = 0; i < 100; i++) {
          if (await predicate()) return;
          await new Promise((r) => setTimeout(r, 100));
        }
        throw Error("Discussion persistence did not converge");
      };
      await open();
      console.log("Panel ready", width);
      const message = `Verified ${width} discussion`;
      const input = section().locator('[contenteditable="true"]').last();
      await input.fill(message);
      await input.press("Control+Enter");
      await until(async () =>
        (await read("issue_comments")).issue_comments.some(
          (c) => c.message === message,
        ),
      );
      await open();
      await section().getByText(message, { exact: true }).waitFor();
      // Author name and menu prove local identity participates in edit rights.
      await section().getByText("Seamus", { exact: true }).waitFor();
      await section().locator('button[aria-haspopup="dialog"]').last().click();
      await page.getByRole("button", { name: "👍", exact: true }).click();
      await until(
        async () =>
          (await read("issue_comment_reactions")).issue_comment_reactions
            .length === 1,
      );
      await open();
      const reaction = section().getByRole("button", { name: /👍\s*1/ });
      await reaction.waitFor();
      assert.match(await reaction.getAttribute("class"), /border-brand/);
      await reaction.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${output}/comments-${width}.png` });
      await reaction.click();
      await until(
        async () =>
          (await read("issue_comment_reactions")).issue_comment_reactions
            .length === 0,
      );
      await section().locator('button[aria-haspopup="menu"]').last().click();
      await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
      await section()
        .locator('[contenteditable="true"]')
        .first()
        .fill(message + " edited");
      await section()
        .getByRole("button", { name: "Save", exact: true })
        .click();
      await until(async () =>
        (await read("issue_comments")).issue_comments.some(
          (c) => c.message === message + " edited",
        ),
      );
      await open();
      await section()
        .getByText(message + " edited", { exact: true })
        .waitFor();
      await section().locator('button[aria-haspopup="menu"]').last().click();
      await page.getByRole("menuitem", { name: "Delete", exact: true }).click();
      await until(
        async () => (await read("issue_comments")).issue_comments.length === 0,
      );
      assert(feeds.some((f) => f.path.endsWith("issue_comments")));
      assert(feeds.some((f) => f.path.endsWith("issue_comment_reactions")));
      assert(
        feeds.every(
          (f) => f.status === 200 && f.contentType.includes("application/json"),
        ),
      );
      assert(writes.filter((w) => !w.blocked).every((w) => w.status === 200));
      assert.equal(errors.length, 0, errors.join("\n"));
      if (process.env.VK_TEST_START === "1") {
        simulateFeedFailure = true;
        await open();
        const workspaceSection = page
          .getByRole("button", { name: "Workspaces", exact: true })
          .locator("../..");
        await workspaceSection
          .getByRole("button", { name: "Create", exact: true })
          .click();
        await page.waitForURL("**/workspaces/create/**");
        const start = page
          .getByRole("button", { name: "Create", exact: true })
          .last();
        await start.waitFor();
        assert.equal(await start.isEnabled(), true);
        await start.click();
        await until(async () => startRequest !== null);
        assert.equal(startRequest.linked_issue.issue_id, issue);
        assert.equal(startRequest.linked_issue.remote_project_id, project);
        assert(startRequest.repos.length > 0);
        assert(startRequest.prompt.includes("ZONNIC"));
        await fs.writeFile(
          `${output}/start-request-${width}.json`,
          JSON.stringify(startRequest, null, 2),
        );
      }
      reports.push({
        width,
        result: "passed",
        verified: [
          "create",
          "reload persistence",
          "author/edit permissions",
          "add reaction",
          "reload selected reaction",
          "remove reaction",
          "edit",
          "delete",
        ],
        startWithFailedFeeds: startRequest !== null,
        feeds,
        writes,
        baselineHtml: [...new Set(baselineHtml)],
      });
    } catch (error) {
      await fs.writeFile(
        `${output}/requests-${width}.json`,
        JSON.stringify({ reads, feeds, writes, errors }, null, 2),
      );
      const pages = context.pages();
      if (pages.length) {
        await fs.writeFile(
          `${output}/failure-${width}.txt`,
          await pages[0].locator("body").innerText(),
        );
        await pages[0].screenshot({ path: `${output}/failure-${width}.png` });
      }
      throw error;
    } finally {
      await context.close();
    }
  }
} finally {
  await fs.writeFile(
    `${output}/browser-results.json`,
    JSON.stringify(reports, null, 2),
  );
  await browser.close();
}
console.log(
  JSON.stringify(
    reports.map(({ width, result, verified, baselineHtml }) => ({
      width,
      result,
      verified,
      baselineHtml,
    })),
    null,
    2,
  ),
);
