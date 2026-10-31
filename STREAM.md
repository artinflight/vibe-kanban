# Project workspace unread notifications — 2026-10-31

The operator reports the defect is still present. Hold push, PR creation and
merge until the actual failing workspace/click path is reproduced and fixed.
Existing browser evidence verifies request emission only, not persisted clearing.

Branch `vk/c097-vk-can-t-clear-u`, based on current fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3` (fresh fetch confirmed).

Opening an existing workspace conversation on the project page did not call
`workspacesApi.markSeen`; only the Workspaces layout owned that effect. Extract
that existing behavior into `useMarkWorkspaceSeen` and call it from the project's
loaded workspace session panel. Invalidate workspace summaries after success so
all badges refresh. Keep Workspaces mobile/panel visibility gates, background-tab
protection, cleanup on navigation and no clearing on summary polling.

Scope: frontend read marking, focused mounted React regressions and the
operator-authorized frontend-only live update. No backend, schema, generated
types or Dot sidechat changes. The public frontend was switched atomically at
2026-10-31 10:38:31 UTC; all service identities remained unchanged. Both candidate
and frontend fallback retain old/new hashed assets. See
[deployment evidence](VK_PROJECT_UNREAD_DEPLOYMENT.md).

Validation and remaining rollout steps are in [HANDOFF](HANDOFF.md). Production
context remains in [STATE](STATE.md) and [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json).
Prior deployment reconciliation is recorded in Git at the branch base and
[the backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md).

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md).
