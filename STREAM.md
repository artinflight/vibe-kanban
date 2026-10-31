# Project workspace unread integration — 2026-10-31

Branch `vk/c097-vk-can-t-clear-u`, original base fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3`, rebased onto staging
`d3d9fa89d45087d1d113f2851d7b2c994c76aec5` after PR #286. The operator accepted the live fix
("Good") and authorized sync, PR and rebase merge. [PR #287](https://github.com/artinflight/vibe-kanban/pull/287)
is the integration record into staging; use its merge event for final status and
rebased staging IDs. Main promotion is separate. Preserve original deployed IDs.

Project conversations share Workspaces' loaded visible-chat read effect.
Explicit same-route nested workspace reselection also reads the displayed chat;
different destinations wait for loaded chat. Polling/background tabs preserve new
unread. Manual issue review flags are independent with mobile/desktop clear controls.
Parent desktop cards ignore interactive child mouse-up to preserve nested navigation.
No backend/schema, generated types or Dot unread changes.

The first two frontend publications were reported unresolved. Fresh reproduction
found the actual nested same-workspace repeat click sent zero seen requests; the
old reselect test clicked a parent issue card and changed routes. The exact new
regression fails before and passes after the correction. The operator accepted the original
publication 12:04:09 UTC from `b990b5939642b1ac7e744a9290840a731fa3f550`,
JS `index-Cy2e9ltd.js`, version 0.1.42. Candidate/live real backend tests at 1440/
393 px verify read persistence, reopening/reselection, reload and completion
preservation. Existing flag preservation gates pass; test flags/body restored.
All live service/data identities remain unchanged.

Current public frontend is the preserving filter composition
`02a9a993d8d9118ca703a22baa15efcf0c7cc4c9`, JS `index-Bgdr6hzC.js`, CSS
`index-DL7rKLPs.css`, version 0.1.42. It preserves all unread/review/reselect source
files exactly. The rebased package tree matches this deployed composition. Keep
PR #286's filter code, latest production manifest and existing preview routes.

Twenty mounted regressions now run in frontend CI. Local frontend types/lint,
format/ops, workflow/UI formatting and production build pass. The local full Rust
check was stopped during a fresh dependency rebuild to protect host storage; it
is not claimed passed. [Full hosted validation](https://github.com/artinflight/vibe-kanban/actions/runs/41204050237)
passed on `be20b829502e1d24c72a944d3a7a06409cf75fb4`: frontend, workspace tests,
Rust lint, schema/SQLx, Tauri and storage/watcher/steering/scheduling integrations.
All PR checks also passed on pre-rebase `054199ec6057a57e22ab0c47d221341de6ca61bb`
([run](https://github.com/artinflight/vibe-kanban/actions/runs/41205867748)). Staging
advanced during that run; the branch is now rebased without changing package bytes
from the current deployed composition. Latest PR checks/merge event are the final
integration authority.

See [HANDOFF](HANDOFF.md), [STATE](STATE.md), [manifest](LIVE_DEPLOYMENT.json) and
[release evidence](VK_PROJECT_UNREAD_DEPLOYMENT.md). PR integration does not redeploy
the accepted frontend or restart the backend. Keep canonical main/staging current
with the fork while preserving the dirty original checkout and this active worktree.

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md).
