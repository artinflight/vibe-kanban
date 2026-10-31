# Workspace project filters pickup — 2026-10-31

The accepted mobile dropdown and compact desktop abbreviation/color bubbles are
published at `https://vibe.local/workspaces`, version 0.1.42. Production source is
`02a9a993d8d9118ca703a22baa15efcf0c7cc4c9`, public JS `index-Bgdr6hzC.js`.
Read [STATE](STATE.md), [manifest](LIVE_DEPLOYMENT.json) and
[deployment evidence](VK_WORKSPACE_FILTER_DEPLOYMENT.md) before another deployment.

[PR #286](https://github.com/artinflight/vibe-kanban/pull/286) targets staging
using the requested rebase method. Its merge event is authoritative for integration
status and rebased IDs; the original application build IDs remain independent.
The deployment composition is pushed as `deploy/workspace-filters-20261031-311d`.
It preserves all 11 live unread/review/reselect files byte-for-byte and includes
all 15 filter package files byte-for-byte. Main promotion remains separate.

Candidate production browser acceptance passed at 360/412/767/768/1440 px,
including filtering, multi-select/No project/reset, local save/reload, shared
dialog state, resizing, keyboard focus, compact dimensions and exact sidebar
color/abbreviation parity with saved customizations. The harness now waits for
stable named project targets, menu animation completion and preference hydration.
Existing review-flag regression acceptance passed at 393/1440 px. All writes
stayed in disposable browser fixtures. Public mobile/desktop readback passed
through normal WebSockets with 54 workspace cards in each viewport and no page
errors. Old public asset hashes still match. All five service identities,
backend executable, database inode and 99 migrations were preserved.

All four frontend TypeScript checks, frontend ESLint, root formatting, explicit
UI/test Prettier, ops checks and unused-i18n checks passed. Hosted frontend checks
and the deployment artifact build passed on application head `d83e7587a`.
The final PR head must satisfy its own required checks before merge; the GitHub
checks and merge event are the integration evidence. Local aggregate check/lint
and `cargo test --workspace` stop because the offline Cargo registry lacks serde.
No physical-phone UI QA or new provider inference was performed.

Known inherited limitation: Escape from the old dialog's nested project dropdown
can dismiss both layers and leave pointer events blocked. The direct selector
passes Escape/focus acceptance; the old nested path is outside this change.

Fresh deployment evidence is on mounted SSD at
`/mnt/vk-storage/vk-mobile-filters-20261031-311d`. Desktop B independently verified
the source bundle and paired frontend recovery archive before activation. The
atomic frontend pointer switched in 0.033 seconds; no service or data switch
occurred. Keep the paired fallback and all old assets. Preview remains available
at `https://mcp-server.tail744c4.ts.net:8443/workspaces`; preserve its routes.

Dependencies reuse the identical-lockfile SSD installation; workspace package
links and Vite caches belong to each worktree. Both task and deployment source
worktrees remain preserved. The unrelated dirty canonical checkout is untouched.

Prior backend owner pickup (historical record follows):

# Backend owner pickup — 2026-10-30

Current investigation: real project-card opening and reopening on this task's own
workspace returned HTTP 200 and persisted `has_unseen_turns=false`. The prior
request-only test gap is now closed for that path. A second failure was reproduced
in the actual mobile project UI: explicit manual review flags appeared as "Needs
review" even when all linked workspaces were read, with no mobile clear control.
The branch separates manual flags from unread activity and adds a shared desktop/
mobile clear action. Five mounted UI tests and eight seen regressions pass; the
production build and persistent browser acceptance are being completed. No push,
PR or merge is authorized until this correction is verified.

Current status: the operator reports unread clearing remains unresolved. The
requested push/PR/rebase merge was held before any of those mutations occurred.
Do not treat the published change as an accepted resolution. Read-only follow-up
confirmed the same frontend/backend, two independent sources of project Needs
review (workspace unread and explicit issue flag), and possible sibling workspace
aggregation. No cause is confirmed yet. The operator was asked where the
indicator remains; an exact workspace and click path are still needed. No live
read/unread flags were changed by this investigation.

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

The operator-authorized live frontend update is complete at `https://vibe.local`.
Public JS `index-hKvj8yI6.js` was built from `f95bab83836d467f972e904710220eee09406d5b`;
version remains 0.1.42 and CSS is unchanged. The atomic pointer switch took about
6 ms at 2026-10-31 10:38:31 UTC. Backend, history reader/proxy, gateway and static
server PIDs/invocations stayed unchanged. Public HTTPS byte checks and both old
entry assets pass. Built-candidate and live desktop/mobile browser checks pass:
project opening/reopening sends read requests; issue-only views and summary
polling do not. Browser mutations were intercepted; actual persisted unread
transitions were not performed against live data.

Software recovery was independently read back from Desktop B. The old frontend
remains intact; a new paired fallback retains all old/new hashed assets. No
backend restart, DB restore, new inference or device action occurred. Temporary
frontends/browsers are closed. See [deployment evidence](VK_PROJECT_UNREAD_DEPLOYMENT.md)
for exact rollback and evidence paths. Reload existing browser tabs to load the fix.

Full workspace Rust tests, full check/lint and hosted CI were not run. Automatic
approval review rejected the source push and hosted workflow launch as an external
export; no push happened. The exact-source local production build and targeted
validation passed. Before a staging PR, run the full PR baseline from AGENTS.

Current production remains documented in [STATE](STATE.md),
[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json) and
[the backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md). Preserve that deployment's
history, paired assets, settings, queues and existing controls.

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
