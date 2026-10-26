import { resolve } from 'node:path';
import { build } from 'esbuild';
export async function bundleDestinationFixture() {
  const fixture = resolve('scripts/testing/workspace-destination.fixture.tsx');
  const realHooks =
    /useWorkspace(Sessions|Record)$|workspaceSessionKeys$|workspaceSummaryKeys$|useUiPreferencesStore$|shared\/types\/attempt$/;
  return await build({
    entryPoints: ['scripts/testing/workspace-destination-harness.tsx'],
    bundle: true,
    write: false,
    format: 'iife',
    platform: 'browser',
    jsx: 'automatic',
    tsconfig: 'packages/web-core/tsconfig.json',
    define: {
      'import.meta.hot': 'undefined',
      'process.env.NODE_ENV': '"test"',
    },
    alias: {
      '@': resolve('packages/web-core/src'),
      '@tanstack/react-query': resolve(
        'packages/web-core/node_modules/@tanstack/react-query'
      ),
      react: resolve('packages/ui/node_modules/react'),
      'react-dom': resolve('packages/ui/node_modules/react-dom'),
    },
    plugins: [
      {
        name: 'synthetic-destination-boundaries',
        setup(b) {
          b.onResolve({ filter: /^@\/shared\// }, ({ path }) =>
            realHooks.test(path) ? undefined : { path: fixture }
          );
          b.onResolve(
            {
              filter:
                /^(react-i18next|@tanstack\/react-router|@vibe\/ui\/components\/|@\/features\/|\.\/KanbanIssuePanelContainer$|\.\/useSessionQueueInteraction$)/,
            },
            ({ path }) =>
              path.endsWith('/useSessionSend') ||
              path.endsWith('/useCreateSession')
                ? undefined
                : { path: fixture }
          );
          b.onResolve(
            { filter: /^\.\/(Tooltip|MobileDrawer|SyncErrorIndicator)$/ },
            () => ({ path: fixture })
          );
          b.onResolve({ filter: /^@phosphor-icons\/react$/ }, () => ({
            path: 'icons',
            namespace: 'fixture',
          }));
          b.onLoad({ filter: /.*/, namespace: 'fixture' }, () => ({
            contents:
              'export const ArrowDownIcon=()=>null,ArrowsOutIcon=()=>null,XIcon=()=>null,LinkIcon=()=>null,PlusIcon=()=>null,Layout=()=>null,ChatsTeardrop=()=>null,ChatCircleDots=()=>null,GitDiff=()=>null,Terminal=()=>null,Desktop=()=>null,GitFork=()=>null,List=()=>null,Gear=()=>null,Kanban=()=>null,CaretLeft=()=>null,DotsThree=()=>null,SidebarSimple=()=>null;',
            loader: 'js',
          }));
        },
      },
    ],
  });
}
