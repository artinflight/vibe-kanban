# Scrolling projects menu — 2026-11-02

Branch `vk/9cb7-vk-scrolling-pro`, original base `aceb355e9`, now rebased onto fork/staging `c3c1dc9d6`.
Scope: bound the desktop shell's content row and AppBar so long project lists
scroll internally, hide scrollbars, and contain overscroll. Keep the footer and
project actions visible. Apply the same behavior to expanded project names and
the mobile project drawer; its content layout override preserves other drawers'
default scrolling. Preserve project selection, drag ordering and activity badges.

The operator accepted the restored fix ("Good") and authorized PR/rebase merge
into staging. Preserve the newer live workspace-visibility frontend, which keeps
all three scrolling source files exactly. Git integration does not redeploy.

The original publication passed on November 2, then a newer unread release
omitted the three scrolling files. The operator reported no change. The November 3
restoration preserves every other current live input and passes the exact failing
public regression plus real-project boundary scrolling. Published at 09:59:20 UTC;
JS index-BRto7v9M.js, CSS index-BDlsFLgm.css. Added a source-preservation gate and
five regressions to reject omitted live fixes before publication. No backend,
API, generated types, device work or service restart. See
[release evidence](VK_SCROLLING_PROJECTS_DEPLOYMENT.md), [STATE](STATE.md),
[manifest](LIVE_DEPLOYMENT.json) and [HANDOFF](HANDOFF.md).

Prior stream history: [previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM history](STREAM_HISTORY_20261017.md). The preceding unread integration
is recorded in STATE and DELTA.
