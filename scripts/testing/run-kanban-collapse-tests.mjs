import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const output = process.env.VK_TEST_OUTPUT;
if (!output) throw new Error('Set VK_TEST_OUTPUT on the mounted build volume');
await mkdir(output, { recursive: true });
const outfile = resolve(output, 'kanban-collapse-tests.mjs');
const require = createRequire(import.meta.url);
await build({
  entryPoints: ['scripts/testing/kanban-collapse.test.tsx'],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'esm',
  banner: {
    js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);",
  },
  jsx: 'automatic',
  alias: {
    'react-i18next': resolve('packages/ui/node_modules/react-i18next'),
    i18next: resolve('packages/web-core/node_modules/i18next'),
  },
  plugins: [
    {
      name: 'native-react',
      setup(builder) {
        builder.onResolve({ filter: /^react(?:-dom)?(?:\/.*)?$/ }, (args) => ({
          path: require.resolve(args.path, { paths: [resolve('packages/ui')] }),
          external: true,
        }));
      },
    },
  ],
});
const bootstrap = resolve(output, 'kanban-collapse-bootstrap.cjs');
await writeFile(
  bootstrap,
  `
const { JSDOM } = require(${JSON.stringify(resolve('node_modules/jsdom/lib/api.js'))});
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true });
for (const key of ['window', 'document', 'navigator', 'Node', 'Element', 'HTMLElement', 'MutationObserver', 'getComputedStyle']) {
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true });
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(dom.window);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
require('node:test').after(() => dom.window.close());
import(${JSON.stringify(outfile)});
`
);
const result = spawnSync(process.execPath, [bootstrap], { stdio: 'inherit' });
process.exitCode = result.status ?? 1;
