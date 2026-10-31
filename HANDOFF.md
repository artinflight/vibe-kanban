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

Start with [STATE](STATE.md), [live manifest](LIVE_DEPLOYMENT.json),
[backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md), [activation recipe](ACTIVATION_RECOVERY_20261030.md)
and [validation checklist](DEPLOYMENT_CHECKLIST_20261030.md).

Antigravity is deployed and available. Live binary `137d6cd7b647…`, source
`9a4179e8b`, accepted 03:18:14 UTC; observed PID 645213. The matched public JS is
`index-DNMY17oB.js`. These are observations, never authority to stop a future owner.
Existing-account native approval/denial/resume/cancel passed; no further login or
provider call is needed to complete this release. Four-turn test budget is spent.

Successful package: `/mnt/vk-storage/vk-deployment-reconcile-20261030/activation-release-2`.
It retained current DB/history, 17 uncertain inputs without replay and the original
protected reader/CU process. Six native DBs plus nine changed rollouts (15 files,
3,607,837,269 bytes) and application SQLite were verified on Desktop B. Large-image
reuse authenticates prior body proofs and fresh native identities, not a fictitious
new capture. The first package's failure/recovery evidence is retained separately.

Immediate fallback is October 29 `ddaaf64a`/`a63eb3a68173…` with its paired frontend.
Fresh roundtrip preserved all 60 tables including later-write probe, 99 migrations,
18 protected/four recent histories. Both frontend pairs retain both asset sets.
Future cutback must drain/recheck compatibility and preserve latest data; it disables
Antigravity execution. Never restore a stale snapshot or rerun a consumed controller.

Public Git lacks private retained-history bindings; bind the exact retained input
for production. Canonical checkout is dirty and untouched. Source/docs/tooling sync
is tracked in [PR #284](https://github.com/artinflight/vibe-kanban/pull/284), targeting
staging via the requested rebase merge. Its merge event records final integration
status/IDs; main promotion is separate. All eight workflows passed on `a421381321`;
see [exact validation runs](BACKEND_DEPLOYMENT_HANDOFF.md#hosted-validation-and-source-integration).
Read-only live verification passed at 09:20:33 UTC. Retain the original branch and
build receipts because rebase changes commit IDs without changing the live release.
Automatic provider failover, AG reset/fork/non-supervised modes remain unqualified/disabled.

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
