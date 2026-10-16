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

HTML viewer links include a version query so later viewer updates can change
the cache key of immutable static responses.

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
`packages/public/vk-artifact-viewer.html`, included in later builds.
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
file is uploaded by these tests. The publication tests run in frontend CI, which also compares the viewer bytes
in both actual frontend build outputs against the shared public source.

## Current rollout

Implemented at `ae41a599b` on staging baseline `805aa7741`, then installed and
verified on October 16. The existing Dot frontend remains selected at
`/mnt/vk-storage/vk-dot-notification-rollout-20261016/release`.
Only `vk-artifact-viewer.html` was added, SHA256
`608ff558710727d459ec5cb9479e4a6692aac830eedb85a0451e1947d5af0dfd`.
The unchanged index SHA256 is
`f842a0df7e2c6d30ac8fa2fd1afebf0bb29631a603f33d95e7bca96274c0a5bd`;
existing JS/CSS, pointer, API version0.1.42 and all service PIDs were preserved.
No backend restart or experimental database was required.

The installed helper and public TLS certificate are versioned outside task
worktrees under `/mnt/vk-storage/vk-published-artifacts/releases/` with a
`current` pointer. The shared Codex-home `AGENTS.md` requires publication before
the first reply. Every previous instruction was preserved; its exact rollback
was mirrored and hash-verified on Desktop B at
`B:/vk-backups/vk-artifact-links-20261016/AGENTS.before.md`.

The exact original 1.7 MB self-contained print report was uploaded in its own
workspace. Native and operator-facing SHA256 match the source. Its returned
first-response Markdown was clicked in the actual production-editor fixture
at1440px and393px, opening the real served viewer and uploaded report. Embedded
images loaded and Next/Previous frame controls worked. No page errors occurred;
browser QA used only GET requests. This is viewport acceptance, not physical
phone testing. The source file and original conversation are unchanged.

Activation, rollback and exact-report private receipts are under
`/mnt/vk-storage/vk-artifact-links-20261016/`. They contain the delivered URL;
it is intentionally not published to GitHub. Rollback removes only the added
viewer/helper and restores the shared instruction backup, without restoring
application data or restarting services. Do not delete uploaded report files as
part of that rollback; attachment retention is a separate operation.
