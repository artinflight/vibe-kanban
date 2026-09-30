import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { mkdir } from "node:fs/promises";
const output = process.env.VK_TEST_OUTPUT;
if (!output || !process.env.TEST_RENDERER_PATH)
  throw new Error("Set VK_TEST_OUTPUT and TEST_RENDERER_PATH on mounted SSD");
await mkdir(output, { recursive: true });
const outfile = resolve(output, "routing-selection-tests.cjs");
await build({
  entryPoints: ["scripts/testing/routing-selection.test.tsx"],
  outfile,
  bundle: true,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  tsconfig: "packages/web-core/tsconfig.json",
  alias: {
    react: resolve("packages/web-core/node_modules/react"),
    "react-test-renderer": process.env.TEST_RENDERER_PATH,
  },
  plugins: [
    {
      name: "preset-query-fixture",
      setup(builder) {
        builder.onLoad({ filter: /usePresetOptions\.ts$/ }, () => ({
          contents:
            "export function usePresetOptions() { return {data: null}; }",
          loader: "ts",
        }));
      },
    },
  ],
  define: { "import.meta.hot": "undefined", "process.env.NODE_ENV": '"test"' },
});
const result = spawnSync(process.execPath, ["--test", outfile], {
  stdio: "inherit",
});
process.exitCode = result.status ?? 1;
