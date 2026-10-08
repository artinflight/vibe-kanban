import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

if (!process.env.VK_TEST_OUTPUT)
  throw new Error(
    "Set VK_TEST_OUTPUT to a directory on the mounted build volume",
  );
await mkdir(process.env.VK_TEST_OUTPUT, { recursive: true });
const outfile = resolve(process.env.VK_TEST_OUTPUT, "mcp-ui-tests.cjs");
await build({
  entryPoints: ["scripts/testing/mcp-approval-ui.test.tsx"],
  outfile,
  bundle: true,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  alias: {
    react: resolve("packages/ui/node_modules/react"),
    "@tanstack/react-query": resolve(
      "packages/web-core/node_modules/@tanstack/react-query",
    ),
  },
  plugins: [
    {
      name: "offline-approval-api",
      setup(build) {
        build.onResolve({ filter: /^@\/shared\/lib\/api$/ }, () => ({
          path: resolve("scripts/testing/mcp-approval-ui-api.ts"),
        }));
      },
    },
  ],
});
const result = spawnSync(process.execPath, ["--test", outfile], {
  stdio: "inherit",
});
process.exitCode = result.status ?? 1;
