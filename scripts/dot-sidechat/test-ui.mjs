// DOM contract tests against the isolated fixture only; not visual browser acceptance.
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
const origin = process.env.DOT_FIXTURE_ORIGIN || "http://127.0.0.1:18973";
const waitFor = async (fn) => {
  for (let i = 0; i < 100; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 30));
  }
  throw new Error("DOM condition timed out");
};
async function load() {
  return JSDOM.fromURL(origin, {
    runScripts: "dangerously",
    resources: "usable",
    pretendToBeVisual: true,
    beforeParse(window) {
      window.fetch = (url, opts) => fetch(new URL(url, origin), opts);
      window.HTMLElement.prototype.scrollIntoView = function () {};
    },
  });
}
let dom = await load();
await waitFor(() => dom.window.document.querySelector("#dot-draft"));
const d = dom.window.document;
assert.equal(
  d.querySelector('[aria-label="Private Dot conversation"]') !== null,
  true,
);
assert.equal(
  [...d.querySelectorAll("summary")].some((x) => x.textContent === "Notes"),
  true,
);
assert.match(d.body.textContent, /fixture replies only/);
const separator = d.querySelector('[role="separator"]');
const before = Number(separator.getAttribute("aria-valuenow"));
separator.dispatchEvent(
  new dom.window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }),
);
await waitFor(
  () => Number(separator.getAttribute("aria-valuenow")) === before + 20,
);
const textarea = d.querySelector("#dot-draft");
await waitFor(
  () => !d.querySelector(".dot-history").textContent.includes("Loading"),
);
const marker = "DOM fixture " + Date.now();
Object.getOwnPropertyDescriptor(
  dom.window.HTMLTextAreaElement.prototype,
  "value",
).set.call(textarea, marker);
textarea.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
await waitFor(() => !d.querySelector('button[type="submit"]').disabled);
d.querySelector('button[type="submit"]').click();
await waitFor(() =>
  d.querySelector(".dot-history").textContent.includes(marker),
);
assert.match(
  d.querySelector(".dot-history").textContent,
  /Saved · awaiting delivery/,
);
d.querySelector(".dot-test-controls").open = true;
[...d.querySelectorAll("button")]
  .find((x) => x.textContent === "Simulate webhook acceptance")
  .click();
await waitFor(() =>
  d.body.textContent.includes("Webhook accepted · awaiting reply"),
);
[...d.querySelectorAll("button")]
  .find((x) => x.textContent === "Append labeled fixture reply")
  .click();
await waitFor(() => d.body.textContent.includes("Dot · fixture"));
assert.match(d.body.textContent, /Reply persisted/);
dom.window.close();
dom = await load();
await waitFor(() => dom.window.document.body.textContent.includes(marker));
assert.match(dom.window.document.body.textContent, /Dot · fixture/);
dom.window.close();
console.log(
  "PASS: Notes placement, fixture labeling, keyboard resize, composer, distinct delivery/reply states, retained history after reload.",
);
