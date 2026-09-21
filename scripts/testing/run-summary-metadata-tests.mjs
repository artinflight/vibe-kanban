import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const output = process.env.VK_TEST_OUTPUT;
if (!output)
  throw new Error(
    "Set VK_TEST_OUTPUT to a directory on the mounted build volume",
  );
await mkdir(output, { recursive: true });
const outfile = resolve(output, "summary-metadata-tests.cjs");
await build({
  entryPoints: ["scripts/testing/summary-metadata.test.ts"],
  outfile,
  bundle: true,
  platform: "node",
  format: "cjs",
  alias: {
    lexical: resolve("packages/web-core/node_modules/lexical/Lexical.dev.mjs"),
  },
});
const result = spawnSync(process.execPath, ["--test", outfile], {
  stdio: "inherit",
});
process.exitCode = result.status ?? 1;
