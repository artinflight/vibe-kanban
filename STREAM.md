# Project workspace unread/review correction — 2026-10-31

Branch `vk/c097-vk-can-t-clear-u`, based on fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3`. Push, PR and rebase merge remain held
under the operator's instruction to fix live behavior first. Nothing was pushed.

The original missing project conversation read effect is shared with Workspaces
through `useMarkWorkspaceSeen`. Real backend tests now confirm persisted clearing
on project-board opening/reopening. The first publication's intercepted-request
checks were insufficient to certify persistence; the operator reported unresolved
behavior and integration stopped.

Follow-up reproduces two additional project UI defects: manual issue review flags
masqueraded as native unread "Needs review" on mobile without a clear control;
parent desktop cards also opened the issue on mouse-up before nested controls
received clicks. Separate manual flags from workspace attention; provide shared
clear controls; ignore interactive children in parent mouse-up navigation.

The complete correction is live from `3366b015155bfa1857b898e263a6d966aabbe452`,
accepted 11:15:55 UTC. No backend, schema, generated types or Dot unread changes.
Fifteen mounted regressions, type/lint checks, production build, actual desktop/
mobile UI persistence/reload and bounded real backend acceptance pass. Only this
task's own issue/workspace was used for live writes; original flags/body restored.

See [HANDOFF](HANDOFF.md), [STATE](STATE.md), [live manifest](LIVE_DEPLOYMENT.json)
and [deployment evidence](VK_PROJECT_UNREAD_DEPLOYMENT.md). Before eventual Git
integration, run the full PR baseline and recheck staging freshness. Production
Git promotion is separate; do not alter the live backend for this frontend fix.

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md).
