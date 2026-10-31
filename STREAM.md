# Workspace project filters — 2026-10-31

Branch `vk/311d-vk-mobile-filter`, based on fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3`.
[PR #286](https://github.com/artinflight/vibe-kanban/pull/286) integrates this
concern into staging using the operator-requested rebase method. Its merge event
records integration status and rebased IDs; main promotion is separate.

Mobile workspace lists expose a project dropdown and direct sort/filter controls.
Desktop provides one horizontally scrollable row of compact 28 px project bubbles
below Search, using the left menu's abbreviations and colors, including saved
customizations. Full names, pressed states, keyboard focus, multi-selection,
No project, reset and existing scratch persistence remain available.

The combined production frontend is published at `https://vibe.local/workspaces`.
It combines the feature's exact 15 package files at `d83e7587a` with the live
unread/review/reselect source at `b990b5939`, preserving those 11 files exactly.
Deployment source `02a9a993d` is retained on
`deploy/workspace-filters-20261031-311d`; this deployment composition does not
promote the other stream's source into staging through the filter PR.
No API, Rust, schema, backend restart or device setting change was made.

See [deployment evidence](VK_WORKSPACE_FILTER_DEPLOYMENT.md), [manifest](LIVE_DEPLOYMENT.json)
and HANDOFF.md for validation and limitations. The branch-only lightweight preview
continues to use the existing green gateway on 4720; production uses the new paired
frontend through the existing gateway/static service. Existing routes are preserved.

Prior stream: [deployment reconciliation](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md).

Integration validation: all frontend type checks, local/UI lint, UI/workflow
formatting, ops and 20 mounted regressions pass. The local full check was stopped
during a fresh Cargo dependency rebuild to avoid further system-disk downloads on
the live host; it is not reported as passed. The established Test workflow will
supply the full hosted baseline in validation-only mode before PR creation. Both
regression runners are now wired into frontend CI. No live deployment change.
