# Scrolling projects menu — 2026-11-02

Branch `vk/9cb7-vk-scrolling-pro`, base `aceb355e9` (fork/staging at task start).
Scope: bound the desktop shell's content row and AppBar so long project lists
scroll internally, hide scrollbars, and contain overscroll. Keep the footer and
project actions visible. Apply the same behavior to expanded project names and
the mobile project drawer; its content layout override preserves other drawers'
default scrolling. Preserve project selection, drag ordering and activity badges.

The operator authorized deployment. The frontend was published at 17:28:06 UTC
on November 2 using the current live source plus the exact scrolling patch.
The newer explicit-unread and chat-notice fixes are preserved. No backend, API,
generated types, device work or service restart. See [release evidence](VK_SCROLLING_PROJECTS_DEPLOYMENT.md),
[STATE](STATE.md), [manifest](LIVE_DEPLOYMENT.json) and [HANDOFF](HANDOFF.md).

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md). The preceding unread integration
is recorded in STATE and DELTA.
