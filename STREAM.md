# Project workspace unread notifications — 2026-10-31

Branch `vk/c097-vk-can-t-clear-u`, based on current fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3` (fresh fetch confirmed).

Opening an existing workspace conversation on the project page did not call
`workspacesApi.markSeen`; only the Workspaces layout owned that effect. Extract
that existing behavior into `useMarkWorkspaceSeen` and call it from the project's
loaded workspace session panel. Invalidate workspace summaries after success so
all badges refresh. Keep Workspaces mobile/panel visibility gates, background-tab
protection, cleanup on navigation and no clearing on summary polling.

Scope: frontend read marking and focused mounted React regressions. No backend,
schema, generated types, Dot sidechat or production deployment changes. Do not
restart or replace the live instance for this fix.

Validation and remaining rollout steps are in [HANDOFF](HANDOFF.md). Production
context remains in [STATE](STATE.md) and [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json).
Prior deployment reconciliation is recorded in Git at the branch base and
[the backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md).

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md).
