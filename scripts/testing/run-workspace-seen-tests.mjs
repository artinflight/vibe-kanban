import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { resolve } from "node:path";

const output = process.env.VK_TEST_OUTPUT;
if (!output) throw new Error("Set VK_TEST_OUTPUT to a mounted SSD directory");
await mkdir(output, { recursive: true });
const require = createRequire(import.meta.url);
const outfile = resolve(output, "workspace-seen-tests.cjs");
const fixture = resolve("scripts/testing/workspace-seen.fixture.tsx");
await build({
  entryPoints: ["scripts/testing/workspace-seen.test.tsx"],
  outfile,
  bundle: true,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  tsconfig: "packages/web-core/tsconfig.json",
  plugins: [
    {
      name: "workspace-seen-fixtures",
      setup(builder) {
        builder.onResolve(
          {
            filter: /^(react(?:-dom)?(?:\/.*)?|jsdom|@tanstack\/react-query)$/,
          },
          (args) => ({
            path: require.resolve(args.path, {
              paths: [resolve("packages/web-core"), process.cwd()],
            }),
            external: true,
          }),
        );
        builder.onResolve({ filter: /^@\// }, (args) => {
          if (args.path.endsWith("/useMarkWorkspaceSeen")) return;
          return { path: fixture };
        });
        builder.onResolve(
          {
            filter:
              /^(react-i18next|@phosphor-icons\/react|\.\/KanbanIssuePanelContainer)$/,
          },
          () => ({ path: fixture }),
        );
      },
    },
  ],
});
const result = spawnSync(process.execPath, ["--test", outfile], {
  stdio: "inherit",
});
process.exitCode = result.status ?? 1;
