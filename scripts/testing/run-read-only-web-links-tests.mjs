import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const output = process.env.VK_TEST_OUTPUT;
if (!output)
  throw new Error(
    'Set VK_TEST_OUTPUT to a directory on the mounted build volume'
  );
await mkdir(output, { recursive: true });
const outfile = resolve(output, 'read-only-web-links-tests.cjs');
const require = createRequire(import.meta.url);
await build({
  entryPoints: ['scripts/testing/read-only-web-links.test.tsx'],
  conditions: ['development'],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'cjs',
  jsx: 'automatic',
  plugins: [
    {
      name: 'native-react-scheduler',
      setup(build) {
        build.onResolve({ filter: /^react(?:-dom)?(?:\/.*)?$/ }, (args) => ({
          path: require.resolve(args.path, { paths: [resolve('packages/ui')] }),
          external: true,
        }));
      },
    },
  ],
  alias: {
    lexical: resolve('packages/ui/node_modules/lexical/Lexical.dev.mjs'),
  },
});
// Lexical detects browser APIs at import time, before the mounted tests run.
const bootstrap = resolve(output, 'read-only-web-links-bootstrap.cjs');
await writeFile(
  bootstrap,
  `
const { JSDOM } = require(${JSON.stringify(resolve('node_modules/jsdom/lib/api.js'))});
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true });
for (const key of ['window', 'document', 'navigator', 'Node', 'Element', 'HTMLElement', 'HTMLAnchorElement', 'Text', 'MutationObserver', 'getComputedStyle']) {
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true });
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
require('node:test').after(() => dom.window.close());
require(${JSON.stringify(outfile)});
`
);
const result = spawnSync(
  process.execPath,
  ['--test', '--experimental-test-isolation=none', bootstrap],
  { stdio: 'inherit' }
);
process.exitCode = result.status ?? 1;
