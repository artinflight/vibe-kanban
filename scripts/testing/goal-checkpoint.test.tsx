import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "../../packages/ui/node_modules/react-dom/server";
import { ChatAssistantMessage } from "../../packages/ui/src/components/ChatAssistantMessage";
import { splitGoalCheckpoint } from "../../packages/ui/src/lib/goalCheckpoint";

const checkpoint = {
  requirements: {},
  completed: {},
  disposition: "continue",
  reason: "Implementation remains unresolved. Next is reconciliation.",
};
const block = (value: unknown) =>
  `<vk_goal_checkpoint>${JSON.stringify(value)}</vk_goal_checkpoint>`;

test("renders completion reports with completed styling and preserves evidence", () => {
  const value = {
    requirements: {},
    completed: {
      delivery:
        "All required platform/content changes integrated via #626/#627, #628 and #629/#630. Production main c6b9bc13f990bd82fb03cc70450a5f70ee97dc34 deployed; healthy build 2026-09-14T14:08:40.205Z. Staging deploy 34853459851 succeeded; healthy build 2026-09-14T14:06:48.118Z. All 236 local tests and required CI passed. Live source receipts recognize all Sep15–19 sections; unchanged-feed check launches no duplicate job, while a read-only changed-Friday probe requires Friday/Saturday review. Main/sidecar remain identical to integrated #628, Monday hash unchanged. Native goal marked complete.",
    },
    disposition: "complete",
    reason:
      "Corrected week is live and integrated; strict novelty, video validation, published locks, paired publication, retry/cancellation and source-refresh behavior are tested and deployed.",
  };
  const html = render(block(value));
  assert.match(html, /text-success/);
  assert.match(html, />Completed</);
  assert.match(html, /Verified this checkpoint \(1\)/);
  assert.ok(html.includes(value.completed.delivery));
  assert.ok(html.includes(value.reason));
  assert.doesNotMatch(html, /vk_goal_checkpoint|Continuing|Needs your input/);
  assert.deepEqual(splitGoalCheckpoint(block(value)).checkpoint, value);
});

test("completion remains display-only and does not hide examples or invalid fields", () => {
  const value = { ...checkpoint, disposition: "complete" };
  assert.match(render(`Finished.\n\n${block(value)}`), /Finished\./);
  for (const content of [
    `Example: ${block(value)}`,
    `~~~json\n${block(value)}`,
    block({ ...value, completed: { delivery: false } }),
  ]) {
    assert.deepEqual(splitGoalCheckpoint(content), { content });
  }
});
const render = (content: string) =>
  renderToStaticMarkup(
    <ChatAssistantMessage
      content={content}
      workspaceId="workspace"
      renderMarkdown={({ content, workspaceId }) => (
        <article data-workspace={workspaceId}>{content}</article>
      )}
    />,
  );

test("renders the reported empty-map checkpoint without raw protocol or false totals", () => {
  const html = render(block(checkpoint));
  assert.match(html, /Goal checkpoint/);
  assert.match(html, /Continuing/);
  assert.match(html, /Implementation remains unresolved/);
  assert.doesNotMatch(html, /vk_goal_checkpoint|requirements|0 of 0|<article/);
});

test("preserves surrounding markdown and workspace context", () => {
  const html = render(`**Work done**\n\n${block(checkpoint)}\n`);
  assert.match(
    html,
    /<article data-workspace="workspace">\*\*Work done\*\*<\/article>/,
  );
  assert.match(html, /Goal checkpoint/);
});

test("renders input, evidence, requirements and recovery safely", () => {
  const html = render(
    block({
      ...checkpoint,
      disposition: "needs_input",
      requirements: { build: "Build app" },
      completed: { build: "Build passed" },
      recovery_plan: "<script>alert(1)</script>",
    }),
  );
  for (const text of [
    "Needs your input",
    "Requirements (1)",
    "Verified this checkpoint (1)",
    "Build passed",
    "Recovery plan",
    "&lt;script&gt;",
  ])
    assert.ok(html.includes(text));
  assert.doesNotMatch(html, /<script>/);
});

test("ordinary prose, inline examples, fenced examples and partial streams remain unchanged", () => {
  for (const content of [
    "Normal **reply**",
    `Example: ${block(checkpoint)}`,
    `\x60\x60\x60json\n${block(checkpoint)}`,
    `~~~\n${block(checkpoint)}\n~~~`,
    '<vk_goal_checkpoint>{"requirements":',
    `${block(checkpoint)}\nMore text`,
  ]) {
    assert.deepEqual(splitGoalCheckpoint(content), { content });
  }
});

test("a real checkpoint after a closed code fence is recognized", () => {
  assert.ok(
    splitGoalCheckpoint(
      `\x60\x60\x60js\nhello\n\x60\x60\x60\n${block(checkpoint)}`,
    ).checkpoint,
  );
});

test("malformed and unsupported payloads are preserved", () => {
  for (const value of [
    null,
    [],
    {},
    { ...checkpoint, requirements: [] },
    { ...checkpoint, completed: { a: 7 } },
    { ...checkpoint, disposition: "done" },
    { ...checkpoint, reason: null },
    { ...checkpoint, recovery_plan: {} },
    { ...checkpoint, reason: "x".repeat(450_001) },
  ]) {
    const content = block(value);
    assert.deepEqual(splitGoalCheckpoint(content), { content });
  }
  const content = "<vk_goal_checkpoint>{broken}</vk_goal_checkpoint>";
  assert.deepEqual(splitGoalCheckpoint(content), { content });
});
