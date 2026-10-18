import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  classifierInvocation,
  compactClassifierConfig,
} from '../codex-classifier-compat.mjs';

const classifierArgs = [
  'app-server',
  ...[
    'project_doc_max_bytes=0',
    'skills.include_instructions=false',
    'features.skip_host_skill_discovery=true',
    'features.shell_tool=false',
    'features.multi_agent=false',
    'features.hooks=false',
    'features.plugins=false',
  ].flatMap((flag) => ['-c', flag]),
];

test('large config response fits the reader and retains native restrictions', () => {
  assert.equal(classifierInvocation(classifierArgs), true);
  const features = { shell_tool: false, hooks: false, plugins: false, multi_agent: false };
  const servers = { private: { enabled: false } };
  const message = { id: 3, result: { config: { features, mcp_servers: servers, profiles: 'x'.repeat(70000) } } };
  compactClassifierConfig(message, true);
  assert.ok(JSON.stringify(message).length < 65536);
  assert.equal(message.result.config.features, features);
  assert.equal(message.result.config.mcp_servers, servers);
});

test('enabled and missing restrictions are never made safe by the adapter', () => {
  const message = { result: { config: { features: { shell_tool: true }, mcp_servers: { live: { enabled: true } } } } };
  compactClassifierConfig(message, true);
  assert.equal(message.result.config.features.shell_tool, true);
  assert.equal(message.result.config.mcp_servers.live.enabled, true);
  const missing = { result: { config: { profiles: {} } } };
  compactClassifierConfig(missing, true);
  assert.equal(missing.result.config.features, undefined);
  assert.equal(missing.result.config.mcp_servers, undefined);
});

test('ordinary execution and native identity/settings/usage frames are unchanged', () => {
  assert.equal(classifierInvocation(['app-server']), false);
  assert.equal(classifierInvocation(classifierArgs.slice(0, -2)), false);
  assert.equal(classifierInvocation([...classifierArgs, '-c', 'features.multi_agent=true']), false);
  for (const frame of [
    { id: 3, result: { config: { profiles: 'x'.repeat(70000) } } },
    { id: 4, result: { thread: { id: 'native' }, model: 'gpt-6-luna', reasoningEffort: 'medium' } },
    { method: 'thread/tokenUsage/updated', params: { inputTokens: 10 } },
    { id: 3, error: { message: 'rejected' } },
  ]) {
    const original = JSON.stringify(frame);
    compactClassifierConfig(frame, false);
    assert.equal(JSON.stringify(frame), original);
    if (!frame.result?.config) {
      compactClassifierConfig(frame, true);
      assert.equal(JSON.stringify(frame), original);
    }
  }
});
