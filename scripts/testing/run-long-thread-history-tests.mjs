// TEST_RENDERER_PATH may point to an external installation on the build SSD.
import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { mkdir } from "node:fs/promises";
const output = process.env.VK_TEST_OUTPUT;
if (!output)
  throw new Error(
    "Set VK_TEST_OUTPUT to a test output directory on the mounted build volume",
  );
await mkdir(output, { recursive: true });
const outfile = resolve(output, "long-thread-history-tests.cjs");
await build({
  entryPoints: ["scripts/testing/long-thread-history.test.tsx"],
  outfile,
  bundle: true,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  tsconfig: "packages/web-core/tsconfig.json",
  alias: {
    react: resolve("packages/web-core/node_modules/react"),
    "react-test-renderer":
      process.env.TEST_RENDERER_PATH || "react-test-renderer",
  },
  define: { "import.meta.hot": "undefined", "process.env.NODE_ENV": '"test"' },
});
const result = spawnSync(
  process.execPath,
  ["--test", "--test-force-exit", outfile],
  { stdio: "inherit" },
);
process.exitCode = result.status ?? 1;
