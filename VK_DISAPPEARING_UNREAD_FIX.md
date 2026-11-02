# Deliberate visible reply reads — frontend-only correction

Published at 2026-11-02T18:28:43.114247+00:00 on `https://vibe.local`.
Corrective feature source: `9a45a3abf2d99eb44c14ef7a744d6f7bf0fbb73e`. Version 0.1.42;
entry `index-DqfYW9pf.js` and `index-C-pTuj_j.css` identify the serving build.

## Behavior

Deliberate conversation opening/reselection, reading gestures and jump to latest
acknowledge after the latest loaded assistant reply/error end is visible and
unobscured in a focused foreground window for 350 ms. Restored older scroll
positions stay unread until the reader reaches latest. Running and approval turns in the displayed conversation wait until settled; an older
reply cannot acknowledge its still-arriving output.
The existing derivation exposes approval state before render-only filtering.
A changed captured reply cancels the dwell. Background return, passive polling
and new output alone do not arm reads. Hidden panels cannot acknowledge replies.

The explicit **Mark all replies read** control remains in both conversation
surfaces and Workspace Actions. Duplicate bulk requests are blocked; failures
preserve unread and require a deliberate retry. No backend/API/schema/generated
changes are included. The unchanged seen API clears all workspace sessions; its
server arrival race remains a frontend-only limitation. Exact reply revisions
and historical unread reconstruction are not implemented. Reload all old tabs.

## Validation

- 15 mounted view regressions, 17 explicit/readiness and 7 adjacent navigation
  regressions pass. Types, focused lint, required formatting/ops and preserving
  production build pass; the renderer's two existing lint warnings are unchanged.
- Four candidate and four served browser layout cases pass at 1440/393 pixels
  across project and Workspaces views: completed clearing, saved scroll/jump,
  reselect/reopen, passive preservation, failure and bulk fallback. No page errors.
- Candidate and served running-turn checks confirm zero read requests while an
  API-verified current process runs and its older reply is visible. The prior view
  bundle reproduces premature read requests in the same isolated browser test.
- All application writes are intercepted; disposable SQLite models unread state
  and real metadata/history are read-only. Automatic approval review rejected an
  optional real-server state test because original per-turn bits cannot be exactly
  restored. No real database unread mutation or persistence acceptance is claimed.
- [Prior full Test baseline](https://github.com/artinflight/vibe-kanban/actions/runs/41493120165)
  passes on b8bad21792f863bce31c42742f7439cc8539503a. Rust source is unchanged.
  Current source validation is governed by [PR #288](https://github.com/artinflight/vibe-kanban/pull/288)
  final checks/merge event. Private remote checks skip without the deploy key.
- Public TLS/index/assets/health, five service identities, backend hash, DB
  path/device/inode and 99 migrations pass unchanged. No restart or DB restore.
- 100,295,574-byte software recovery passed local restore of
  3,566 files and permissions plus independent Desktop B readback.
  Both paired roots retain 874 assets. Pointer switch: 0.011763 seconds.
- Optional Sentry upload authentication is unavailable and upload is not certified.
  Provider execution and physical S25 interaction are not claimed.

## Source and recovery

The build preserves live frontend base 800011bd573e2869d6ea4c0e5bfba4d9046d9cbe,
initial 70d7f5b0516a784ca6f27ba9fc6245b441666663 and b8bad2179 view work, then
applies the settled-turn correction. Newer git-preservation notices are exact.
Evidence root: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.
Serving source/artifact, paired fallback, backup and activation use `fix-release-4`.
Historical manual-only release-1 was rejected by the operator; release-2 restored
viewing but lacked the running-turn guard. Candidate-3 failed completed-view QA
because the renderer filters its metadata marker; it was never served and its
activation controller is permanently disabled. Only the accepted final build above
is current. Backend/history direct roots retain prior assets; use the public route.

The operator authorized push, staging PR and rebase merge through PR #288.
Original deployed source IDs remain immutable. Git integration does not republish
assets or restart services. Main promotion remains separate.
