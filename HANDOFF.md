# Mobile workspace filters pickup — 2026-10-31

Current branch: `vk/311d-vk-mobile-filter`; see STREAM.md for scope.
The mobile workspace list now shows its project selector and sort/filter controls
directly. `WorkspaceProjectFilter` shares the existing project selection state
with `WorkspacesFilterDialog`; switching projects never changes the PR filter.
All projects clears only project selection. Desktop controls retain their layout.

Validation passed: UI, web-core, local-web and remote-web TypeScript checks;
focused UI ESLint; `pnpm run format` plus explicit UI/test Prettier; ops governance,
legacy frontend path guard, diff whitespace, and nine existing workspace
assignment/pagination regressions. Large type checks used a bounded 2 GiB Node
heap after the inherited 768 MiB limit failed.

Browser acceptance (`scripts/testing/mobile-workspace-filters-browser.mjs`) passed
at 360, 412, 767, 768 and 1440 px against the branch-only frontend and existing
green gateway. It verified actual workspace rows match the selected project,
48 px targets, multi-select/No project, All projects reset, shared dialog badge,
locally emulated save/reload, search/archive access, keyboard focus return and
viewport fit. All application writes were intercepted; subscription bridges only
forwarded backend-to-client frames. Sanitized results and screenshots remain in
the ignored `.vk-preview/mobile-filter-tests/` on SSD. The temporary preview was
stopped after acceptance; no public preview route was changed.

Known inherited limitation: Escape from the old dialog's nested project dropdown
can dismiss both layers and leave pointer events blocked. The new direct selector
passes Escape/focus acceptance without that nesting. The shared-state check reads
the old dialog badge and closes with its normal button; it does not certify that
old nested Escape path. Rust/full-workspace lint tests and physical-phone UI QA
were not run for this frontend-only stream.

Dependencies reuse the identical-lockfile SSD installation at
`/mnt/vk-storage/vk-t63-release-20261018/candidate-source` through ignored local
links. Workspace package links and Vite caches belong to this worktree.
The lightweight preview targets existing gateway 4720; no backend was started.
S25 read-only status verified exact identity and Tailscale transport on October 31;
Wi-Fi is enabled, so no cellular or physical-phone UI acceptance is claimed.
The local feature commit includes source, browser acceptance and continuity notes.
No push, PR, promotion or deployment has been performed for this stream.

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
