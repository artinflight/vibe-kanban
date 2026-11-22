import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const output = process.env.VK_TEST_OUTPUT;
if (!output) throw new Error('Set VK_TEST_OUTPUT to a mounted SSD directory');
await mkdir(output, { recursive: true });
const require = createRequire(import.meta.url);
const outfile = resolve(output, 'read-later-tests.cjs');
const fixture = resolve('scripts/testing/read-later.fixture.tsx');
await build({
  entryPoints: [
    process.env.VK_TEST_SUITE ?? 'scripts/testing/read-later.test.tsx',
  ],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'cjs',
  jsx: 'automatic',
  tsconfig: 'packages/web-core/tsconfig.json',
  plugins: [
    {
      name: 'read-later-fixtures',
      setup(builder) {
        builder.onResolve(
          { filter: /^(react(?:-dom)?(?:\/.*)?|react-i18next|i18next)$/ },
          (args) => ({
            path: require.resolve(args.path, {
              paths: [resolve('packages/ui'), resolve('packages/web-core')],
            }),
            external: true,
          })
        );
        builder.onResolve(
          {
            filter:
              /^(@tanstack\/react-router|@\/shared\/(hooks\/(useNotifications|useNotificationMembers|auth\/useAuth|useReadLaterSync)|providers\/HostIdProvider)|@vibe\/ui\/components\/UserAvatar)$/,
          },
          () => ({ path: fixture })
        );
      },
    },
  ],
});
const bootstrap = resolve(output, 'read-later-bootstrap.cjs');
await writeFile(
  bootstrap,
  `
const { JSDOM } = require(${JSON.stringify(require.resolve('jsdom'))});
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true, url: 'https://vk.test' });
for (const key of ['window', 'document', 'navigator', 'Node', 'Element', 'HTMLElement', 'MutationObserver', 'getComputedStyle', 'localStorage']) Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.fetch = () => { throw new Error('Component tests must use fixtures; sync has a separate integration suite'); };
require('node:test').after(() => dom.window.close());
require(${JSON.stringify(outfile)});
`
);
const result = spawnSync(process.execPath, [bootstrap], { stdio: 'inherit' });
process.exitCode = result.status ?? 1;
