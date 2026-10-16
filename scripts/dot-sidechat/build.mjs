import { build } from "esbuild";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
await mkdir(path.join(here, "dist"), { recursive: true });
await build({
  absWorkingDir: root,
  entryPoints: ["scripts/dot-sidechat/fixture.tsx"],
  bundle: true,
  outfile: "scripts/dot-sidechat/dist/app.js",
  alias: {
    "@vibe/ui": "./packages/ui/src",
    react: "./packages/ui/node_modules/react",
    "react-dom": "./packages/ui/node_modules/react-dom",
  },
  jsx: "automatic",
});
await writeFile(
  path.join(here, "dist/index.html"),
  '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vibe · Dot sidechat prototype</title><link rel="stylesheet" href="/app.css"></head><body><div id="root"></div><script src="/app.js"></script></body></html>',
);
console.log("Built isolated sidechat fixture.");
