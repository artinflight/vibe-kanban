import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const { request } = await import(process.env.PLAYWRIGHT_MODULE),
  root = process.env.VK_TEST_OUTPUT;
async function control(action, input = {}) {
  const p = spawn('python3', ['-B', process.env.VK_DOT_QA_CONTROL, action], {
    env: process.env,
    stdio: ['pipe', 'pipe', 'pipe', 'pipe'],
  });
  let data = '',
    error = '';
  p.stdio[3].on('data', (x) => (data += x));
  p.stderr.on('data', (x) => (error += x));
  p.stdin.end(JSON.stringify(input));
  await new Promise((a, b) => {
    p.on('error', b);
    p.on('exit', (c) => (c === 0 ? a() : b(Error(error))));
  });
  return JSON.parse(data);
}
const api = await request.newContext({ ignoreHTTPSErrors: true });
let f;
try {
  f = await control('setup');
  async function call(path, body) {
    const r = await api.fetch('https://vibe.local/api/dot-sidechat/' + path, {
      method: body ? 'POST' : 'GET',
      headers: {
        Cookie: '__Secure-vibe-dot=' + f.token,
        'X-Dot-Request': '1',
        Origin: 'https://vibe.local',
        ...(body
          ? { 'Content-Type': 'application/json', 'X-Dot-CSRF': f.csrf }
          : {}),
      },
      ...(body ? { data: body } : {}),
    });
    assert.equal(r.status(), 200);
    return r.json();
  }
  const page = await call('thread?workspace=' + f.workspace);
  assert.ok(page.capabilities.notifications);
  assert.equal(page.messages.find((x) => x.id === f.reply).seen, false);
  assert.equal((await control('inspect', f)).attention, 1);
  await call('seen', { workspace: f.workspace, messages: [f.reply] });
  let s = await control('inspect', f);
  assert.deepEqual(s, {
    unread: 0,
    attention: 1,
    coding_unchanged: true,
    outbound_attempts: 0,
  });
  await call('attention', {
    workspace: f.workspace,
    message: f.reply,
    action: 'resolve',
  });
  s = await control('inspect', f);
  assert.equal(s.attention, 0);
  await call('attention', {
    workspace: f.workspace,
    message: f.reply,
    action: 'reopen',
  });
  s = await control('inspect', f);
  assert.equal(s.attention, 1);
  assert.ok(s.coding_unchanged);
  const result = {
    passed: true,
    actualLiveAPI: true,
    capabilityAdvertised: true,
    authenticatedReadAndExplicitResolution: true,
    codingFlagsUnchanged: true,
    wakeAttempts: 0,
    qaSessionTtlSeconds: 600,
  };
  await fs.writeFile(
    root + '/dot-live-api-results.json',
    JSON.stringify(result, null, 2)
  );
  console.log(JSON.stringify(result));
} finally {
  await api.dispose();
  if (f) await control('cleanup', f);
}
