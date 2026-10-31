# Unread/review correction pickup — 2026-10-31

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
