# Scrolling projects menu — 2026-11-02

Branch `vk/9cb7-vk-scrolling-pro`, base `aceb355e9` (fork/staging at task start).
Scope: bound the desktop shell's content row and AppBar so long project lists
scroll internally, hide scrollbars, and contain overscroll. Keep the footer and
project actions visible. Apply the same behavior to expanded project names and
the mobile project drawer; its content layout override preserves other drawers'
default scrolling. Preserve project selection, drag ordering and activity badges.

No backend, API, generated types, runtime publication, device work or service
restart. Production truth remains in [STATE](STATE.md) and the live manifest.
Validation and pickup details: [HANDOFF](HANDOFF.md).

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md). The preceding unread integration
is recorded in STATE and DELTA.
