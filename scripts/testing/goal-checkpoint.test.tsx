import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from '../../packages/ui/node_modules/react-dom/server';
import { ChatAssistantMessage } from '../../packages/ui/src/components/ChatAssistantMessage';
import { splitGoalCheckpoint } from '../../packages/ui/src/lib/goalCheckpoint';

const checkpoint = { requirements: {}, completed: {}, disposition: 'continue', reason: 'Implementation remains unresolved. Next is reconciliation.' };
const block = (value: unknown) => `<vk_goal_checkpoint>${JSON.stringify(value)}</vk_goal_checkpoint>`;
const render = (content: string) => renderToStaticMarkup(<ChatAssistantMessage content={content} workspaceId="workspace" renderMarkdown={({ content, workspaceId }) => <article data-workspace={workspaceId}>{content}</article>} />);

test('renders the reported empty-map checkpoint without raw protocol or false totals', () => {
  const html = render(block(checkpoint));
  assert.match(html, /Goal checkpoint/);
  assert.match(html, /Continuing/);
  assert.match(html, /Implementation remains unresolved/);
  assert.doesNotMatch(html, /vk_goal_checkpoint|requirements|0 of 0|<article/);
});

test('preserves surrounding markdown and workspace context', () => {
  const html = render(`**Work done**\n\n${block(checkpoint)}\n`);
  assert.match(html, /<article data-workspace="workspace">\*\*Work done\*\*<\/article>/);
  assert.match(html, /Goal checkpoint/);
});

test('renders input, evidence, requirements and recovery safely', () => {
  const html = render(block({ ...checkpoint, disposition: 'needs_input', requirements: { build: 'Build app' }, completed: { build: 'Build passed' }, recovery_plan: '<script>alert(1)</script>' }));
  for (const text of ['Needs your input', 'Requirements (1)', 'Verified this checkpoint (1)', 'Build passed', 'Recovery plan', '&lt;script&gt;']) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /<script>/);
});

test('ordinary prose, inline examples, fenced examples and partial streams remain unchanged', () => {
  for (const content of ['Normal **reply**', `Example: ${block(checkpoint)}`, `\x60\x60\x60json\n${block(checkpoint)}`, `~~~\n${block(checkpoint)}\n~~~`, '<vk_goal_checkpoint>{"requirements":', `${block(checkpoint)}\nMore text`]) {
    assert.deepEqual(splitGoalCheckpoint(content), { content });
  }
});

test('a real checkpoint after a closed code fence is recognized', () => {
  assert.ok(splitGoalCheckpoint(`\x60\x60\x60js\nhello\n\x60\x60\x60\n${block(checkpoint)}`).checkpoint);
});

test('malformed and unsupported payloads are preserved', () => {
  for (const value of [null, [], {}, { ...checkpoint, requirements: [] }, { ...checkpoint, completed: { a: 7 } }, { ...checkpoint, disposition: 'done' }, { ...checkpoint, reason: null }, { ...checkpoint, recovery_plan: {} }, { ...checkpoint, reason: 'x'.repeat(450_001) }]) {
    const content = block(value);
    assert.deepEqual(splitGoalCheckpoint(content), { content });
  }
  const content = '<vk_goal_checkpoint>{broken}</vk_goal_checkpoint>';
  assert.deepEqual(splitGoalCheckpoint(content), { content });
});
