# First-response links to generated files

The OP::3D Print Issues reply used valid Markdown with an absolute host path:
`[Frame-by-frame HTML review](/mnt/vk-storage/.../failure-review.html)`.
That file had never been uploaded or served. The web-link repair was still
present in the newer Dot release; it deliberately disables filesystem links.
Enabling that href alone would navigate to a nonexistent application route.

## Deliver a file before offering it

On this MCP host, run:

```sh
/home/mcp/.local/bin/vk-publish-artifact /absolute/path/report.html --label "Open report"
```

Paste the returned `markdown` value into the **first** reply that offers the
file. Do not substitute the source path, `file://`, `sandbox:` or an unverified
URL. A storage path can be supplementary provenance, not the deliverable link.
Publish only the explicit intended deliverable. No directory is shared.

The helper uploads through the running VK attachment API, verifies the stored
and operator-facing bytes against SHA256, and returns an HTTP(S) Markdown link.
HTML opens in `/vk-artifact-viewer.html`; other files use the native download
endpoint. `--download` requests the original HTML instead of a preview.
The source file and original conversation remain unchanged.
The existing `VK_WORKSPACE_ID` and `VK_SESSION_ID` scope the upload to its task,
so it is retained as a workspace attachment rather than an orphan. Outside a
VK task, pass both IDs explicitly. No status, prompt or attention state changes.

HTML reports must embed their images, styles and scripts. Explicit external
resource references are rejected before upload; the viewer blocks network
resources. Bundle a multi-file report deliberately rather than sharing its
parent directory or presenting a broken preview. The helper accepts one file
up to 50 MiB. Attachment retention follows VK's existing attachment lifecycle.

## Boundaries and verification

The viewer accepts only an attachment UUID, never an arbitrary path or URL.
It fetches that file through VK's existing API and renders it in an opaque
`sandbox="allow-scripts"` iframe. A restrictive content policy permits embedded
report controls and images while blocking requests, external resources, forms,
and access to the parent application. Original HTML downloads keep the API's
existing attachment disposition. No general filesystem reader is added.

Publication receipts under `/mnt/vk-storage/vk-published-artifacts/receipts`
record source hash, attachment ID and verified link. Repeat publication reuses
an acknowledged upload. An uncertain upload is retained as pending and blocks
blind retry; reconcile its hash/attachment before changing that receipt.

Defaults are the existing loopback gateway `http://127.0.0.1:4720` and operator
origin `https://vibe.local`. `VK_ARTIFACT_API_BASE` and
`VK_ARTIFACT_PUBLIC_ORIGIN` override them. Uploads require a loopback origin.
For local HTTPS, the installed wrapper sets `VK_ARTIFACT_CA_FILE` to the public
vibe.local certificate retrieved through trusted Homelab SSH. TLS and hostname
verification stay enabled; no global trust or server configuration changes.

The source helper is `scripts/vk-publish-artifact.py`; the standalone viewer is
`packages/local-web/public/vk-artifact-viewer.html`, included in later builds.
The durable host installation must live outside a disposable task worktree.
The shared Codex-home `AGENTS.md` and repository rule require publication before
the first reply. This is an agent instruction plus a verified publication tool,
not a server-side guarantee that every historical/local path is rewritten.
Already emitted filesystem links remain disabled. Agents must use the helper;
an already running turn cannot be assumed to have read newly installed rules.

## Acceptance

```sh
python3 scripts/testing/test-publish-artifact.py
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs CHROMIUM_PATH=/path/to/chromium node scripts/testing/artifact-viewer-browser.mjs
```

Seven real HTTP tests cover first-response Markdown, byte verification,
acknowledged reuse, uncertain uploads, missing viewer, unpublished resources
and origin validation. Sandboxed Chromium exercises report controls, parent and
network isolation, invalid IDs, downloads and phone/desktop layouts. No live
file is uploaded by these tests. The publication tests run in frontend CI.

## Current rollout

Prepared on current staging `805aa7741`. The existing live Dot release and all
hashed app assets must be preserved. Only the standalone viewer needs an
additive static-file installation; no backend, gateway or agent restart is
required. Activation and exact-report acceptance are pending at this source
checkpoint; record their actual receipts before claiming the current report
is available.
