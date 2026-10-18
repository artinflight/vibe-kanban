import { build } from 'esbuild';
export async function bundleNotifications() {
  const result = await build({
    entryPoints: ['scripts/dot-sidechat/notification-fixture.tsx'],
    bundle: true,
    write: false,
    outdir: 'unused',
    jsx: 'automatic',
    define: { 'import.meta.env.VITE_DOT_SIDECHAT': '"1"' },
    alias: {
      '@tanstack/react-query':
        './packages/web-core/node_modules/@tanstack/react-query',
      '@': './packages/web-core/src',
      '@vibe/ui': './packages/ui/src',
      react: './packages/ui/node_modules/react',
      'react-dom': './packages/ui/node_modules/react-dom',
    },
    plugins: [
      {
        name: 'isolated-host-context',
        setup(b) {
          b.onResolve({ filter: /shared\/providers\/HostIdProvider/ }, () => ({
            path: 'host-context',
            namespace: 'fixture',
          }));
          b.onLoad({ filter: /.*/, namespace: 'fixture' }, () => ({
            contents:
              'export function useHostId(){ return window.fixtureHost ?? null; }',
            loader: 'js',
          }));
        },
      },
    ],
  });
  return {
    js: result.outputFiles.find((f) => f.path.endsWith('.js')).text,
    css: result.outputFiles
      .filter((f) => f.path.endsWith('.css'))
      .map((f) => f.text)
      .join('\n'),
  };
}
export function state(long = false) {
  return {
    seen: false,
    manualUnread: false,
    readStates: [],
    resolved: false,
    attention: true,
    reads: [],
    requests: [],
    long,
  };
}
export function transport(s) {
  return async (url, options = {}) => {
    s.requests.push({ url, method: options.method ?? 'GET' });
    if (!url.startsWith('/api/dot-sidechat/'))
      throw Error('Unexpected API: ' + url);
    const route = url.split('/api/dot-sidechat/')[1];
    const result = (body) => ({
      ok: true,
      status: 200,
      json: async () => body,
    });
    if (route === 'session')
      return result({
        csrf: 'fixture-csrf',
        session_id: 'session-fixture',
        expires: null,
      });
    if (route === 'notifications')
      return result({
        issues:
          !s.seen || (s.attention && !s.resolved)
            ? [
                {
                  project_id: 'project-fixture',
                  issue_id: 'issue-fixture',
                  unread_count: s.seen ? 0 : 1,
                  needs_attention_count: s.attention && !s.resolved ? 1 : 0,
                },
              ]
            : [],
      });
    if (route.startsWith('thread?')) {
      const page = {
        thread: { id: 'thread-fixture' },
        scope: {
          issue_label: 'Fixture issue',
          workspace_label: 'Selected workspace',
        },
        messages: s.messages ?? [
          {
            id: 'dot-reply',
            role: 'dot',
            seq: 2,
            body: s.long
              ? 'A long question for the owner.\n'.repeat(90)
              : 'A question for the owner.',
            workspace: '11111111-1111-4111-8111-111111111111',
            created: 1,
            seen: s.seen,
            manual_unread: s.manualUnread,
            attention: s.attention
              ? { kind: 'question', resolved: s.resolved }
              : null,
          },
        ],
        receipts: {},
        through: 2,
        next_after: null,
        capabilities: {
          notifications: true,
          manual_unread: s.supportsManualUnread !== false,
        },
      };
      if (s.holdThread)
        await new Promise((resolve) => {
          s.releaseThread = resolve;
        });
      return result(page);
    }
    const body = JSON.parse(options.body ?? '{}');
    if (options.headers['X-Dot-CSRF'] !== 'fixture-csrf')
      throw Error('Missing CSRF');
    if (route === 'seen') {
      if (JSON.stringify(body.messages) !== '["dot-reply"]')
        throw Error('Unexpected read IDs');
      if (s.manualUnread) return result({ seen: [] });
      s.seen = true;
      s.reads.push(body);
      if (s.holdRead)
        await new Promise((resolve) => {
          s.releaseRead = resolve;
        });
      return result({ seen: body.messages });
    }
    if (route === 'read-state') {
      if (body.message !== 'dot-reply') throw Error('Wrong reply');
      s.readStates.push(body);
      if (s.failReadState)
        return { ok: false, status: 503, json: async () => ({}) };
      s.manualUnread = body.action === 'unread';
      s.seen = !s.manualUnread;
      return result({
        message: body.message,
        seen: s.seen,
        manual_unread: s.manualUnread,
      });
    }
    if (route === 'attention') {
      s.attention = true;
      if (body.message !== 'dot-reply') throw Error('Wrong reply');
      s.resolved = body.action === 'resolve';
      return result({});
    }
    throw Error('Unexpected Dot route ' + route);
  };
}
export const wait = async (fn) => {
  for (let i = 0; i < 180; i++) {
    if (await fn()) return;
    await new Promise((r) => setTimeout(r, 20));
  }
  throw Error('Fixture condition timed out');
};
