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

Evidence: `/mnt/vk-storage/vk-unread-reselect-20261031-c097/reselect-release`.
Key receipts: `browser-candidate-reselect.json`, `browser-live-reselect.json`,
`own-candidate-verified.json`, `browser-candidate.json`, `after-live-pinned.json`,
`activation.json`, `Desktop-B-recovery-verified.json`. Both paired roots retain 559
assets. The 43,244,856-byte frontend/source software recovery package was independently
read back from Desktop B. The previous runtime/full-state recovery is preserved.
Temporary candidate frontends and browsers closed. No backend/device action.

The operator accepted the live fix ("Good") and requested PR, sync and rebase
merge into fork/staging. The integration hold is lifted. Fresh fork/staging is
already an ancestor; full PR validation is running before publication. Hosted CI
and physical-phone interaction are not yet claimed. Reload existing operator tabs for the new bundle.
Direct backend/history frontend roots still serve October 30 UI; only the public
origin is certified. Do not change those entrypoints without identifying usage.
See [STATE](STATE.md), [manifest](LIVE_DEPLOYMENT.json) and
[release record](VK_PROJECT_UNREAD_DEPLOYMENT.md).

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).

Integration validation: all frontend type checks, local/UI lint, UI/workflow
formatting, ops and 20 mounted regressions pass. The local full check was stopped
during a fresh Cargo dependency rebuild to avoid further system-disk downloads on
the live host; it is not reported as passed. The established Test workflow will
supply the full hosted baseline in validation-only mode before PR creation. Both
regression runners are now wired into frontend CI. No live deployment change.
