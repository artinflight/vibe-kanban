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

The corrected frontend is live at `https://vibe.local`, version 0.1.42, from
`3366b015155bfa1857b898e263a6d966aabbe452`. Public JS: `index-9ssuLQsW.js`;
CSS: unchanged `index-CUBB2mA2.css`. Accepted 11:15:55 UTC with a roughly 15 ms
atomic frontend pointer replacement. Backend/history reader/proxy/gateway/static
service identities and database identity/migrations are unchanged.

The first frontend publication was reported unresolved. Its tests only intercepted
seen requests. Follow-up real backend tests verified native read persistence, then
reproduced the remaining misleading manual Needs review marker with no mobile clear
control and premature parent desktop mouse-up navigation from nested controls.
Manual issue flags now use a separate accessible clear action on mobile/desktop;
workspace unread/approval remains independent. Parent cards ignore interactive
children so workspace navigation and flag actions do not also open the issue.

Validation: eight seen regressions plus seven mounted UI tests pass. The old parent
handler fails the nested workspace regression. The old live mobile UI reproduces
the false Needs review/missing-clear condition. Production build, shared/local/UI
types, focused ESLint, format/ops and diff checks pass. Final candidate and live
393/1440 px checks persist clearing to disposable SQLite, preserve unrelated flags,
retain navigation and verify reload. A separate real live test on ONLY this task's
own issue/workspace proves manual flag clear persists after reload, preserves a
second flag and native unread, then opening the conversation clears native unread.
Original flags and task body were restored. No page errors. Backend-managed task
metadata formatting is distinct from task body. No unrelated live writes occurred.

Evidence root: `/mnt/vk-storage/vk-unread-reselect-20261031-c097/final`.
Key receipts: `own-live-verified.json`, `browser-live-review/results.json`,
`after-live-pinned.json`, `activation.json`, `Desktop-B-recovery-verified.json`.
Both frontend roots retain 507 assets; software recovery was independently read
back from Desktop B. Previous frontend and immutable rollback index remain intact.
Temporary test frontends/browsers are closed. Reload browser tabs to load the fix.

Nothing was pushed. Push/PR/rebase merge remain held; the operator explicitly asked
to get behavior working before pushing. Full workspace Rust/full PR baseline and
hosted CI have not run for these corrections; no PR has been opened. Do not claim
Git integration from a successful live frontend publication. Preserve original
source/release commit IDs if later rebase assigns new IDs.

See [release record](VK_PROJECT_UNREAD_DEPLOYMENT.md), [STATE](STATE.md) and
[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json). Prior pickup:
[previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
