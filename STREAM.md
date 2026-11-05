# Read Later — 2026-11-04

Branch `vk/f57c-read-later`, based on fork/staging `ee2efee4d`.
Issue: VK Dev T91 (`dde01894-a5fe-4f5e-81dd-8b8163acb598`).
The operator explicitly lifted the issue-only execution hold on November 4 and
requested implementation in this existing workspace. No additional agent launch.

Scope: read or unread workspaces, unread issue activity, project Dot notices and
inbox notifications can be deferred without marking them read. Sidebar order is Attention, Read Later,
Running, Completed (the existing idle/history collection). Read Later starts folded
in the all-items view so deferred history does not bury running work. Desktop,
flat, accordion and phone views share the grouping. Issue actions also work in
Kanban and list views; issue lifecycle statuses are unaffected.

Read Later is a browser-local preference scoped by host and signed-in user, with
separate IDs for workspaces, issues, projects and notification records. It survives
reloads; unavailable browser storage falls back to memory. It does not synchronize
between devices. Remove from Read Later removes the preference. Saved workspaces
remain until explicitly removed, even after their unread activity clears; new
inbox messages in a deferred thread bring the regrouped notification back to Attention.

The operator authorized deployment. Read Later was published on November 4 at
15:11:24 UTC using a separate composition of the exact current live source plus
this feature patch. Visibility, scrolling, notices and unread protections are
preserved. No backend/API/migration/generated-type change, restart, PR, push or
device action. See STATE.md, LIVE_DEPLOYMENT.json and VK_READ_LATER_DEPLOYMENT.md.
Future publications must use the preservation gate against the then-current live
source; the feature branch alone is not a replacement for newer live inputs.

Validation and pickup details are in HANDOFF.md. Previous scrolling integration
and runtime preservation history remain in STATE.md and
VK_SCROLLING_PROJECTS_DEPLOYMENT.md.

Prior continuity: [pre-reconciliation record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [full historical archive](STREAM_HISTORY_20261017.md).

The operator requested icon-only Read Later controls inline with each notification.
Commit `b1f609719` implements this on workspaces, project notices, saved issues
and Kanban headers. Published 2026-11-04T20:16:46.412428+00:00; no extra action row.
The operator also reported resurfaced cleared Dot notices. Exact bundle/browser
comparison found accidental build-flag drift (disabled before, enabled in first
Read Later release). The correction restores VITE_DOT_SIDECHAT=0 without modifying
stored acknowledgement state. Future builds must preserve runtime flags too.

The operator requested bookmarking already-read workspaces. `449819b1e` removes
workspace unread eligibility from the action/grouping, retains saved read entries
beyond pagination, and labels removal accurately in all locales. Saved workspaces
remain until explicitly removed. Published 2026-11-05T10:18:22.737137+00:00, with current inline design,
source preservation and VITE_DOT_SIDECHAT=0 unchanged. No read-state writes.

The operator requested moving Read Later and the three-dot menu onto the existing
status/last-updated line. `ee435a75c` implements full-width titles and independent
metadata/action controls on desktop and phone. Published 2026-11-05T10:46:08.024061+00:00;
see VK_WORKSPACE_STATUS_ACTIONS_DEPLOYMENT.md. No read-state or Dot flag change.

The operator also reported a bookmark missing on mobile. Browser-local storage
is confirmed; cross-device sync is absent. Existing shared preferences lack a
Read Later field. A sync-scope question is pending; no backend change/restart or
shared-storage workaround has been made.
