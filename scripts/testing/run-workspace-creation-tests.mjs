import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = process.env.VK_TEST_OUTPUT;
if (!output) throw new Error('Set VK_TEST_OUTPUT to a mounted SSD directory');
await mkdir(output, { recursive: true });
const outfile = resolve(output, 'workspace-creation-tests.cjs');
await build({
  entryPoints: ['scripts/testing/workspace-creation.test.ts'],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'cjs',
  tsconfig: 'packages/web-core/tsconfig.json',
  plugins: [{
    name: 'workspace-creation-fixtures',
    setup(builder) {
      builder.onResolve({
        filter: /^(?:@tanstack\/react-query|@\/shared\/(?:lib\/(?:api|workspaceLinkRefresh)|hooks\/workspaceSummaryKeys))$/,
      }, () => ({ path: resolve('scripts/testing/workspace-creation.fixture.ts') }));
    },
  }],
});
process.exitCode = spawnSync(process.execPath, ['--test', outfile], { stdio: 'inherit' }).status ?? 1;
