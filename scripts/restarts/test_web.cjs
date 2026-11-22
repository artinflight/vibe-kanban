// Usage: node test_web.cjs /absolute/path/to/playwright [monitor URL]
// Reuse an installed browser; never download a browser as part of this test.
const { chromium } = require(process.argv[2]);
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.RESTART_TEST_BROWSER,
    headless: true,
  });
  try {
    const page = await browser.newPage({ ignoreHTTPSErrors: true });
    if (process.env.RESTART_TEST_APP_JS) {
      await page.route("**/app.js", (route) =>
        route.fulfill({
          path: process.env.RESTART_TEST_APP_JS,
          contentType: "text/javascript",
        }),
      );
    }
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const base = process.argv[3] || "http://127.0.0.1:8190";
    await page.goto(base);
    await page.waitForFunction(() => document.querySelector("#steps .step"));
    assert.notEqual(
      await page.locator("#stage-title").textContent(),
      "Waiting for controller updates",
    );
    for (const viewport of [
      { width: 1440, height: 1100 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
      if (process.env.RESTART_TEST_ARTIFACTS) {
        await page.screenshot({
          path: path.join(
            process.env.RESTART_TEST_ARTIFACTS,
            `restarts-${viewport.width}.png`,
          ),
          fullPage: true,
        });
      }
    }
    const actual = await (await page.request.get(`${base}/api/status`)).json();
    if (actual.status === "completed") {
      await page.locator("#restart-monitor").click();
      assert.equal(await page.locator("#overall-percent").textContent(), "0%");
      await page.waitForTimeout(2300);
      assert.equal(await page.locator("#overall-percent").textContent(), "0%");
      const retained = await (
        await page.request.get(`${base}/api/status`)
      ).json();
      assert.equal(retained.run_id, actual.run_id);
      assert.equal(retained.percent, actual.percent);
      assert.equal(retained.status, "completed");
      await page.evaluate(() =>
        localStorage.removeItem("vibe.restart-monitor.dismissed-run.v1"),
      );
      await page.reload();
      await page.waitForFunction(
        () =>
          document.querySelector("#stage-title").textContent ===
          "Restart complete",
      );
    }
    const now = Date.now() / 1000;
    const fixture = {
      schema: 1,
      run_id: "browser-fixture",
      title: "Synthetic restart",
      status: "running",
      started_at: now - 60,
      updated_at: now,
      source: "Test controller",
      current_step: "restore",
      percent: 25,
      completed_steps: 0,
      remaining_steps: 2,
      skipped_steps: 0,
      eta_seconds: null,
      estimate: {
        lower_seconds: 120,
        upper_seconds: 600,
        basis: "mixed",
        scope: "remaining restart",
        confidence: "low",
        confidence_reason: "Includes an unmeasured allowance.",
        assumptions: [
          "Assume the next step takes 2–10 min; this is not measured.",
        ],
        as_of: now,
        stale: false,
        conditional: true,
        recalibration: {
          trigger: "Next progress observation or stage change",
          due_at: now + 60,
          overdue: false,
        },
      },
      errors: [],
      blockers: [],
      events: [],
      steps: [
        {
          id: "restore",
          label: "Verify restore",
          status: "running",
          percent: 50,
          metric: { done: 50, total: 100, unit: "entries" },
          eta_seconds: 10,
        },
        {
          id: "verify",
          label: "Verify HTTPS",
          status: "pending",
          percent: null,
          eta_seconds: null,
        },
      ],
    };
    let fail = false;
    await page.route("**/api/status", async (route) =>
      fail ? route.abort() : route.fulfill({ json: fixture }),
    );
    await page.reload();
    await page.waitForFunction(() =>
      document.querySelector("#source").textContent.includes("browser-fixture"),
    );
    assert.match(
      await page.locator("#eta-note").textContent(),
      /range for remaining restart; conditional/,
    );
    assert.equal(await page.locator("#eta").textContent(), "2m–10m");
    assert.match(
      await page.locator("#estimate-confidence").textContent(),
      /Low confidence/,
    );
    assert.match(
      await page.locator("#estimate-assumptions").textContent(),
      /not measured/,
    );
    assert.match(
      await page.locator("#estimate-checkpoint").textContent(),
      /Next progress observation/,
    );
    const initial = await page
      .locator("#overall-progress")
      .getAttribute("value");
    await page.waitForTimeout(1100);
    assert.equal(
      await page.locator("#overall-progress").getAttribute("value"),
      initial,
    );
    fixture.stale = true;
    fixture.estimate.stale = true;
    fixture.estimate.recalibration.due_at = now - 60;
    fixture.steps[0].eta_seconds = null;
    await page.waitForFunction(() => !document.querySelector("#notice").hidden);
    assert.match(await page.locator("#notice").textContent(), /delayed/);
    assert.equal(await page.locator("#eta").textContent(), "2m–10m");
    assert.match(
      await page.locator("#estimate-checkpoint").textContent(),
      /overdue/,
    );
    assert.match(await page.locator("#estimate-as-of").textContent(), /stale/);
    fixture.status = "blocked";
    fixture.steps[0].status = "blocked";
    fixture.blockers = ["Waiting for current work to finish."];
    fixture.errors = [
      { kind: "Health check", message: "<img src=x onerror=alert(1)> failed" },
    ];
    await page.waitForFunction(
      () => document.querySelector("#attention-count").textContent === "2",
    );
    assert.equal(await page.locator("#attention-content img").count(), 0);
    assert(await page.locator("#restart-monitor").isDisabled());
    assert.match(await page.locator("#eta").textContent(), /2m–10m/);
    if (process.env.RESTART_TEST_ARTIFACTS) {
      for (const width of [1440, 390]) {
        await page.setViewportSize({ width, height: 900 });
        assert(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        );
        await page.screenshot({
          path: path.join(
            process.env.RESTART_TEST_ARTIFACTS,
            `eta-uncertain-${width}.png`,
          ),
          fullPage: true,
        });
      }
    }
    fail = true;
    await page.waitForFunction(() =>
      document
        .querySelector("#connection")
        .textContent.includes("Reconnecting"),
    );
    assert.equal(
      await page.locator("#overall-progress").getAttribute("value"),
      initial,
    );
    assert.equal(await page.locator("#eta").textContent(), "2m–10m");
    assert.match(
      await page.locator("#estimate-reason").textContent(),
      /Disconnected/,
    );
    fail = false;
    fixture.status = "completed";
    fixture.current_step = null;
    fixture.percent = 100;
    fixture.completed_steps = 2;
    fixture.remaining_steps = 0;
    fixture.errors = [];
    fixture.blockers = [];
    fixture.stale = false;
    fixture.estimate = {
      ...fixture.estimate,
      lower_seconds: 0,
      upper_seconds: 0,
      basis: "confirmed",
      confidence: "high",
      confidence_reason: "Controller completion evidence.",
      assumptions: [],
      stale: false,
      conditional: false,
      recalibration: null,
    };
    fixture.steps.forEach((step) => {
      step.status = "completed";
      step.percent = 100;
    });
    await page.waitForFunction(
      () =>
        document.querySelector("#stage-title").textContent ===
        "Restart complete",
    );
    assert.equal(await page.locator("#remaining").textContent(), "0 remaining");
    assert.equal(
      await page.locator("#overall-progress").getAttribute("value"),
      "100",
    );
    assert.equal(await page.locator("#eta").textContent(), "Complete");
    assert.match(
      await page.locator("#estimate-confidence").textContent(),
      /High confidence/,
    );
    // Restart Monitor must clear a finished view immediately, survive old polls
    // and reloads, and resume only when the controller reports a new attempt.
    assert(await page.locator("#restart-monitor").isEnabled());
    await page.locator("#restart-monitor").click();
    assert.equal(await page.locator("#overall-percent").textContent(), "0%");
    assert.equal(
      await page.locator("#overall-progress").getAttribute("value"),
      "0",
    );
    assert.equal(await page.locator("#elapsed").textContent(), "0s");
    assert.equal(
      await page.locator("#step-count").textContent(),
      "0 of 2 steps completed",
    );
    assert.equal(await page.locator("#steps .completed").count(), 0);
    assert.equal(
      await page.locator("#estimate-confidence").textContent(),
      "Waiting",
    );
    assert.equal(await page.locator("#estimate-as-of").textContent(), "");
    assert(await page.locator("#notice").isHidden());
    await page.waitForTimeout(2300);
    assert.equal(await page.locator("#overall-percent").textContent(), "0%");
    assert(await page.locator("#notice").isHidden());
    await page.reload();
    await page.waitForFunction(
      () =>
        document.querySelector("#stage-title").textContent ===
        "Waiting for the next restart",
    );
    await page.waitForTimeout(2300);
    assert.equal(await page.locator("#overall-percent").textContent(), "0%");
    assert(await page.locator("#notice").isHidden());
    assert(await page.locator("#restart-monitor").isDisabled());
    // A late update belonging to the old attempt must not undo the reset.
    fixture.updated_at += 30;
    await page.waitForTimeout(2300);
    assert.equal(await page.locator("#overall-percent").textContent(), "0%");
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
      if (process.env.RESTART_TEST_ARTIFACTS)
        await page.screenshot({
          path: path.join(
            process.env.RESTART_TEST_ARTIFACTS,
            `monitor-reset-${width}.png`,
          ),
          fullPage: true,
        });
    }
    fixture.run_id = "browser-fixture-next";
    fixture.status = "running";
    fixture.percent = 0;
    fixture.completed_steps = 0;
    fixture.remaining_steps = 2;
    fixture.current_step = "restore";
    fixture.started_at = Date.now() / 1000;
    fixture.updated_at = fixture.started_at;
    fixture.estimate = null;
    fixture.steps.forEach((step) => {
      step.status = "pending";
      step.percent = 0;
      delete step.metric;
    });
    fixture.steps[0].status = "running";
    await page.waitForFunction(() =>
      document
        .querySelector("#source")
        .textContent.includes("browser-fixture-next"),
    );
    assert.equal(await page.locator("#overall-percent").textContent(), "0%");
    assert(await page.locator("#restart-monitor").isDisabled());
    assert.equal(
      await page.evaluate(() =>
        localStorage.getItem("vibe.restart-monitor.dismissed-run.v1"),
      ),
      null,
    );
    fixture.percent = 25;
    fixture.steps[0].percent = 50;
    await page.waitForFunction(
      () => document.querySelector("#overall-percent").textContent === "25%",
    );
    assert.equal(
      await page.locator("#stage-title").textContent(),
      "Verify restore",
    );
    // A failed attempt can also be cleared without replaying its error panel.
    fixture.status = "failed";
    fixture.steps[0].status = "failed";
    fixture.errors = [
      { kind: "Fixture failure", message: "Synthetic acceptance failed" },
    ];
    await page.waitForFunction(
      () => !document.querySelector("#restart-monitor").disabled,
    );
    await page.locator("#restart-monitor").click();
    assert.equal(await page.locator("#overall-percent").textContent(), "0%");
    assert.equal(await page.locator("#attention-count").textContent(), "0");
    assert.deepEqual(errors, []);
    if (process.env.RESTART_TEST_ARTIFACTS)
      fs.writeFileSync(
        path.join(process.env.RESTART_TEST_ARTIFACTS, "browser-results.json"),
        JSON.stringify(
          {
            passed: true,
            viewports: [1440, 390],
            scenarios: [
              "live receipts",
              "conditional ETA range with assumptions and confidence",
              "fixed overdue recalibration checkpoint",
              "no timer progress",
              "stale",
              "blocked",
              "escaped errors",
              "connection failure",
              "automatic reconnect",
              "completed",
              "button resets completed and failed views to zero",
              "reset survives old polls, late updates and reload",
              "new attempt resumes live progress; active reset disabled",
            ],
            pageErrors: errors,
          },
          null,
          2,
        ),
      );
    console.log(
      "Browser checks passed: desktop/mobile, reset to zero across polls and reload, automatic next-attempt tracking, active-run protection, ETA/error/reconnect regressions; no page errors.",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
