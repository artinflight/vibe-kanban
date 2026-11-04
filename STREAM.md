# Read Later — 2026-11-04

Branch `vk/f57c-read-later`, based on fork/staging `ee2efee4d`.
Issue: VK Dev T91 (`dde01894-a5fe-4f5e-81dd-8b8163acb598`).
The operator explicitly lifted the issue-only execution hold on November 4 and
requested implementation in this existing workspace. No additional agent launch.

Scope: unread workspace/issue activity, project Dot notices and inbox notifications
can be deferred without marking them read. Sidebar order is Attention, Read Later,
Running, Completed (the existing idle/history collection). Read Later starts folded
in the all-items view so deferred history does not bury running work. Desktop,
flat, accordion and phone views share the grouping. Issue actions also work in
Kanban and list views; issue lifecycle statuses are unaffected.

Read Later is a browser-local preference scoped by host and signed-in user, with
separate IDs for workspaces, issues, projects and notification records. It survives
reloads; unavailable browser storage falls back to memory. It does not synchronize
between devices. Return to Attention removes the preference. An item whose unread
activity is cleared no longer occupies Read Later; new inbox messages in a deferred
thread bring the regrouped notification back to Attention.

This is frontend-only source work. No API/migration/generated-type change, backend
restart, production publication, PR, push or device action. The operator
authorized a local commit of this implementation and its continuity notes. Current runtime
truth remains in STATE and LIVE_DEPLOYMENT.json. Use the current live-source
preservation gate before any future publication; this branch alone is not a
replacement for newer live inputs.

Validation and pickup details are in HANDOFF.md. Previous scrolling integration
and runtime preservation history remain in STATE.md and
VK_SCROLLING_PROJECTS_DEPLOYMENT.md.

Prior continuity: [pre-reconciliation record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [full historical archive](STREAM_HISTORY_20261017.md).
