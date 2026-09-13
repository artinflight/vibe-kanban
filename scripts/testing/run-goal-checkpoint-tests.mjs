import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = process.env.VK_TEST_OUTPUT;
if (!output) throw new Error('Set VK_TEST_OUTPUT to a directory on the mounted build volume');
await mkdir(output, { recursive: true });
const outfile = resolve(output, 'goal-checkpoint-tests.cjs');
await build({
  entryPoints: ['scripts/testing/goal-checkpoint.test.tsx'],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'cjs',
  jsx: 'automatic',
  alias: { react: resolve('packages/ui/node_modules/react') },
});
const result = spawnSync(process.execPath, ['--test', outfile], { stdio: 'inherit' });
process.exitCode = result.status ?? 1;
