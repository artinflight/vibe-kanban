import { build } from 'esbuild';
export const ids = {
  project: '11111111-1111-4111-8111-111111111111',
  issue: '22222222-2222-4222-8222-222222222222',
  a: '33333333-3333-4333-8333-333333333333',
  b: '44444444-4444-4444-8444-444444444444',
};
export async function projectRoutingBundle(
  entry = 'scripts/dot-sidechat/project-routing-fixture.tsx'
) {
  const stubs = {
    'shared/hooks/useProjectContext': `export function useProjectContext(){return {issues:[],getIssue:()=>null,getStatus:()=>null,getAssigneesForIssue:()=>[],getWorkspacesForIssue:()=>[]}}`,
    'shared/hooks/useOrgContext': `export function useOrgContext(){return {membersWithProfilesById:new Map()}}`,
    'shared/hooks/useAppNavigation': `export function useAppNavigation(){return {}}`,
    'shared/providers/HostIdProvider': `export function useHostId(){return null}`,
  };
  const result = await build({
    entryPoints: [entry],
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
        name: 'isolated-project-context',
        setup(b) {
          b.onResolve(
            {
              filter:
                /shared\/(hooks\/use(ProjectContext|OrgContext|AppNavigation)|providers\/HostIdProvider)/,
            },
            (args) => {
              const key = Object.keys(stubs).find((k) => args.path.endsWith(k));
              return key ? { path: key, namespace: 'fixture' } : null;
            }
          );
          b.onResolve({ filter: /^react-i18next$/ }, () => ({
            path: 'i18n',
            namespace: 'fixture',
          }));
          b.onResolve({ filter: /^@tanstack\/react-router$/ }, () => ({
            path: 'router',
            namespace: 'fixture',
          }));
          b.onLoad({ filter: /.*/, namespace: 'fixture' }, (args) => ({
            contents:
              args.path === 'i18n'
                ? `export function useTranslation(){return {t:k=>({'common:workspaces.needsAttention':'Needs Attention','common:workspaces.running':'Running','common:workspaces.idle':'Idle'}[k]??k)}}`
                : args.path === 'router'
                  ? `export function useRouter(){return {history:window.fixtureHistory}}`
                  : stubs[args.path],
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
export function deferred() {
  let resolve;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
}
export function routingState() {
  return {
    requests: [],
    sends: [],
    threadHolds: new Map(),
    sendHolds: new Map(),
    accepted: new Map(),
    messages: Object.fromEntries(
      ['project', 'a', 'b'].map((d) => [
        d,
        [
          {
            id: 'note-' + d,
            seq: 1,
            role: 'dot',
            body: 'Conversation ' + d,
            workspace: ids[d],
            created: 1792281600,
            seen: false,
            manual_unread: true,
            attention: { kind: 'question', resolved: false },
          },
        ],
      ])
    ),
  };
}
export function routingTransport(s) {
  return async (url, options = {}) => {
    const route = url.split('/api/dot-sidechat/')[1];
    if (!route) throw Error('Unexpected API ' + url);
    const result = (body, status = 200) => ({
      ok: status === 200,
      status,
      json: async () => structuredClone(body),
    });
    s.requests.push({ url, method: options.method ?? 'GET' });
    if (route === 'session')
      return result({
        session_id: 'routing-fixture',
        csrf: 'fixture',
        expires: null,
      });
    if (route === 'notifications')
      return result({
        issues: [],
        projects: s.projectNotices ?? [],
        workspaces: [],
      });
    if (route.startsWith('project-plan?')) return result({ entries: [] });
    if (route.startsWith('thread?')) {
      const q = new URL(url, 'http://fixture').searchParams;
      const d = q.has('project')
        ? 'project'
        : Object.keys(ids).find((k) => ids[k] === q.get('workspace'));
      if (!s.messages[d]) throw Error('Unknown target');
      const page = {
        thread: {
          id: d === 'project' ? 'project-thread' : 'shared-issue-thread',
        },
        scope: {
          issue_label: d === 'project' ? 'Synthetic project' : 'Shared issue',
          workspace_label:
            d === 'project'
              ? 'Scope: Project-wide conversation'
              : 'Workspace ' + d,
        },
        messages: structuredClone(s.messages[d]),
        receipts: {},
        through: s.messages[d].length,
        next_after: null,
        capabilities: {
          notifications: true,
          manual_unread: true,
          message_replies: true,
        },
      };
      const hold = s.threadHolds.get(d);
      if (hold) await hold.promise;
      return result(page);
    }
    if (route === 'send') {
      const body = JSON.parse(options.body);
      const d = body.project
        ? 'project'
        : Object.keys(ids).find((k) => ids[k] === body.workspace);
      if (!d || Boolean(body.project) === Boolean(body.workspace))
        throw Error('Ambiguous send destination');
      s.sends.push(body);
      if (!s.accepted.has(body.request)) {
        s.accepted.set(body.request, structuredClone(body));
        s.messages[d].push({
          id: 'owner-' + body.request,
          seq: s.messages[d].length + 1,
          role: 'owner',
          workspace: ids[d],
          created: 1792281600,
          body: body.body,
          ...(body.in_reply_to
            ? {
                in_reply_to: body.in_reply_to,
                reply_reference: {
                  id: body.in_reply_to,
                  seq: 1,
                  role: 'dot',
                  created: 1792281600,
                  excerpt: 'Conversation ' + d,
                },
              }
            : {}),
        });
      } else if (
        JSON.stringify(s.accepted.get(body.request)) !== JSON.stringify(body)
      )
        throw Error('Changed idempotent request');
      const hold = s.sendHolds.get(d);
      const status = hold ? await hold.promise : 200;
      return result({ id: 'owner-' + body.request }, status);
    }
    throw Error('Forbidden mutation ' + route);
  };
}
