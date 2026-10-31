# Project workspace unread fix pickup — 2026-10-31

The project workspace session panel now uses the same `useMarkWorkspaceSeen`
hook as Workspaces. It waits for a loaded record matching the requested workspace
ID. A successful seen request invalidates workspace-summary queries; opening an
issue or create panel does not clear workspace activity. Visibility and polling
semantics are unchanged from Workspaces.

Focused test command (reuse existing SSD dependencies; do not duplicate installs):
`VK_TEST_OUTPUT=<mounted-SSD-directory> node scripts/testing/run-workspace-seen-tests.mjs`.
The suite mounts the actual project sidebar with unrelated providers/UI stubbed,
using real React, React DOM, jsdom and React Query. The API is stubbed. Eight cases
cover opening/invalidation, loading/missing/wrong records, switching, background
visibility/closing, both create modes, shared hook reopening and request failure.

Validation passed: all eight focused regressions; web-core and local-web TypeScript
checks (bounded 3 GiB Node heaps); ESLint for the three changed source files;
`pnpm run format`; `pnpm run ops:check`; frontend legacy-path guard and
`git diff --check`. Removing the project's seen-hook call reproduces five failing
regressions; restoring it passes all eight. Initial default-heap checks exhausted
Node's heap; final checks use this checkout's workspace package sources with
shared SSD third-party dependencies. No duplicate dependency install was needed.

No live/backend/device/provider mutation or deployment was done. Full workspace
Rust tests, full check/lint, hosted CI and live browser/API badge readback were not
run for this frontend-only fix. Before integration, run the full PR baseline from
AGENTS and validate a branch frontend against the existing live backend.

Current production remains documented in [STATE](STATE.md),
[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json) and
[the backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md). Preserve that deployment's
history, paired assets, settings, queues and existing controls.

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
