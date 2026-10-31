# Project unread reselection pickup — 2026-10-31

Current live frontend `https://vibe.local`: combined filter composition
`02a9a993d8d9118ca703a22baa15efcf0c7cc4c9`, published 13:07:50 UTC,
JS `index-Bgdr6hzC.js`, CSS `index-DL7rKLPs.css`, version 0.1.42. This preserves
all 11 unread/review/reselect source files exactly from accepted original
`b990b5939642b1ac7e744a9290840a731fa3f550` (12:04:09 UTC publication). Backend/
service/database identities are unchanged. Keep the latest combined release and
filter deployment records; Git integration does not redeploy either feature.

Operator reported "no change" after both earlier frontend candidates. Fresh real
live reproduction found same-route nested workspace reselection emits zero seen
requests and leaves unread true. Earlier reselect test clicked the parent issue
card, causing a route transition and concealing the missed path. The shared project
workspace navigation helper now explicitly reads deliberate selection of the
already displayed workspace. Initial navigation waits for loaded chat; polling and
background tabs preserve subsequent unread. Manual issue flags and Dot stay separate.

Twenty mounted regressions, shared TypeScript, focused ESLint, required format/
ops and production build pass. Exact real-browser regression fails on previous
live bundle and passes on candidate and published live frontend: desktop nested
workspace selection with no URL change, mobile close/reopen, real read persistence,
reload, and a newly unread completion remaining unread during polling. No page
errors. Existing candidate desktop/mobile review persistence plus actual backend
manual-flag/unrelated-flag/unread preservation tests retained and pass. All writes
bounded to this task's own issue/workspace; original flags/task body restored.

Evidence: `/mnt/vk-storage/vk-unread-reselect-20261031-c097/reselect-release`.
Key receipts: `browser-candidate-reselect.json`, `browser-live-reselect.json`,
`own-candidate-verified.json`, `browser-candidate.json`, `after-live-pinned.json`,
`activation.json`, `Desktop-B-recovery-verified.json`. Both paired roots retain 559
assets. The 43,244,856-byte frontend/source software recovery package was independently
read back from Desktop B. The previous runtime/full-state recovery is preserved.
Temporary candidate frontends and browsers closed. No backend/device action.

PR #286 advanced staging during the passing checks on 054199ec6. This branch
was rebased onto d3d9fa89d45087d1d113f2851d7b2c994c76aec5; its package tree matches
the deployed combined composition exactly. Preserve PR #286 code and continuity.

The operator accepted the live fix ("Good") and authorized sync, PR and rebase
merge. [PR #287](https://github.com/artinflight/vibe-kanban/pull/287) is the staging
integration record; its merge event gives final status and rebased IDs. Original
application source b990b5939642b1ac7e744a9290840a731fa3f550 remains immutable.
Main promotion is separate. Full hosted baseline passed on be20b829502e1d24c72a944d3a7a06409cf75fb4:
[validation run](https://github.com/artinflight/vibe-kanban/actions/runs/41204050237).
It includes frontend, workspace tests, Rust lint, schema/SQLx, Tauri and native
storage/watcher/steering/scheduling checks. Final PR checks remain the integration
authority. Local full Rust compilation was stopped to avoid fresh registry growth
on the system disk; it is not claimed passed. All 20 mounted regressions are wired
into frontend CI. Physical-phone interaction is not claimed. No new deployment
or backend restart is part of this PR. Reload existing tabs for the accepted UI.
Direct backend/history frontend roots still serve October 30 UI; only the public
origin is certified. Do not change those entrypoints without identifying usage.
See [STATE](STATE.md), [manifest](LIVE_DEPLOYMENT.json) and
[release record](VK_PROJECT_UNREAD_DEPLOYMENT.md).

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
