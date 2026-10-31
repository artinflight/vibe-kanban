# Workspace project filters — 2026-10-31

Branch `vk/311d-vk-mobile-filter`, based on fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3` (remote head verified October 31).

Scope: make project filters directly accessible from workspace lists. The accepted
phone toolbar exposes a project dropdown plus sort/filter buttons without the
Options gate (commit `03d5f308e`). The operator-requested desktop extension uses
bubble toggles in one horizontally scrollable row directly below Search. Both
layouts use the existing project options, multi-project/No project filtering,
All projects reset and scratch persistence. Desktop chips are compact 28 px
bubbles using the left menu's project abbreviations and pastel colors, including
saved customizations. Full names remain available through hover titles and
accessible labels; selected checkmarks, pressed states and keyboard focus remain.
Phone selection text and 48 px targets remain unchanged. The existing filter
dialog remains available. Labels cover all seven locales with no new keys.
No API, Rust, schema, production deployment or device setting change is included.

Validation and remaining gates are recorded in HANDOFF.md. Browser acceptance
intercepts all application writes and emulates preference snapshots locally.
The frontend preview uses the existing public gateway on 4720 because the preview
guide's old 4511 endpoint is absent; current runtime authority remains STATE.md.

Prior deployment stream (historical branch scope follows):

# Deployment reconciliation and Antigravity activation

Branch `fix/deployment-reconciliation-20261030`, based on fork/staging
`2bf2676d2d3841c252fa7f2a9b4e7993128bb093`.
[PR #284](https://github.com/artinflight/vibe-kanban/pull/284) reconciles the actual
October 29 recovery/409/history work and the October 30 Antigravity activation.
The operator requested a rebase merge into staging; the PR merge event is the
authoritative integration record. Main promotion is separate. Original deployed
commit IDs and the dirty canonical checkout remain preserved.

The matched activation release is live: backend source `9a4179e8b`, binary
`137d6cd7b647…`, accepted 03:18:14 UTC. Public/frontend and backend root use the
new bundle; old/new hashed chunks remain reachable. Exact identity, backup,
fallback and limitations are in [the manifest](LIVE_DEPLOYMENT.json).

Existing-account auth and actual native Vibe adapter acceptance passed: approved
write, denied writes, exact-token native resume and pending-approval cancellation
with process reaped in about 40 ms. Four model turns total; post-deployment checks
used zero inference. Availability is installation-based and launch remains
supervised. Service-scoped runtime/model defaults preserve saved profiles.

A real final-backup refusal exercised automatic recovery before any binary switch.
SQLite read-only opening created an empty WAL; a detached repro and regression
fix allow only that exact transition. Fresh data/ownership checks preceded the
successful package. Current data, protected history, original reader/CU and all
17 uncertain inputs were retained. No old snapshot was restored or input replayed.

Repository custody includes 134 deployed source records, 27 inert incident
sources, 50 paired connector files, bounded ACP diagnostics/native runner,
current-data rehearsal, owned activation/recovery, RAM SQLite backup, B proof
reuse, frontend asset retention, release mirroring and operational documentation.
Private history/account material stays outside Git. Old source catalogs remain
historical; the new release provenance is recorded separately.

Validation: 13 offline Antigravity regressions; native provider acceptance above;
130 recovery/custody checks pass with 22 private/optional skips; 13 auth/privacy
checks; 24 steering/stop and 30 connector contracts. Hosted Test plus seven other
workflows passed on `a4213813210ea15affb1d91a306883cb27f452e3`, including the final
recovery and mirror tooling. Exact run links and skipped/private coverage are in
[the backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md#hosted-validation-and-source-integration).
Read-only live verification passed again at 09:20:33 UTC. Documentation successors
must pass their own PR checks before merge. These checks do not claim every feature
had paid-provider QA.

Prior stream: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md).
