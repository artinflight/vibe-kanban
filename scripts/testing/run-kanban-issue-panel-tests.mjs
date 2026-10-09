import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { mkdir } from 'node:fs/promises';

const output = process.env.VK_TEST_OUTPUT;
if (!output || !process.env.TEST_RENDERER_PATH) {
  throw new Error('Set VK_TEST_OUTPUT and TEST_RENDERER_PATH');
}
await mkdir(output, { recursive: true });
const outfile = resolve(output, 'kanban-issue-panel-tests.cjs');
const fixture = resolve('scripts/testing/kanban-issue-panel.fixture.tsx');
await build({
  entryPoints: ['scripts/testing/kanban-issue-panel.test.tsx'],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'cjs',
  jsx: 'automatic',
  tsconfig: 'packages/web-core/tsconfig.json',
  alias: {
    react: resolve('packages/web-core/node_modules/react'),
    'react-test-renderer': process.env.TEST_RENDERER_PATH,
  },
  plugins: [
    {
      name: 'panel-api-fixture',
      setup(builder) {
        // Keep the actual panel, composer store, scratch hook and creation workflow.
        // Replace network/providers and unrelated sections with controllable requests.
        builder.onResolve(
          {
            filter:
              /^(fixture|@\/shared\/|@tanstack\/|react-i18next|react-dropzone|@vibe\/ui\/components\/ConfirmDialog)/,
          },
          (args) => {
            if (
              /useKanbanIssueComposer(Store|Scratch)|issueCreation/.test(
                args.path
              )
            )
              return;
            return { path: fixture };
          }
        );
        builder.onResolve(
          {
            filter:
              /^\.\/Issue(Comments|SubIssues|Relationships|Workspaces)SectionContainer$/,
          },
          () => ({ path: fixture })
        );
        builder.onLoad({ filter: /usePhoneLayout\.ts$/ }, () => ({
          contents: 'export const usePhoneLayout = () => false;',
          loader: 'ts',
        }));
      },
    },
  ],
  define: { 'import.meta.hot': 'undefined', 'process.env.NODE_ENV': '"test"' },
});
const result = spawnSync(
  process.execPath,
  ['--test', '--test-reporter=tap', '--test-timeout=30000', outfile],
  { stdio: 'inherit' }
);
process.exitCode = result.status ?? 1;
