# Visible reply read correction — 2026-11-02

Live frontend source `9a45a3abf2d99eb44c14ef7a744d6f7bf0fbb73e`; JS `index-DqfYW9pf.js`,
CSS `index-C-pTuj_j.css`, version 0.1.42. Deliberate opening/reselection/reading and
jump to latest clear a loaded visible reply/error after 350 ms of foreground focus,
once running/approval turns settle. Background return/polling/new output alone
preserve unread. Bulk-read fallback remains. Reload all existing tabs/devices.

39 mounted regressions, frontend types/focused lint/format/ops and build pass.
Four candidate/four served layout cases and candidate/served API-verified running
turn guards pass with zero live writes. Earlier premature running reads were
reproduced; the rejected filtered-marker candidate was never published.

All five services/backend hash/DB inode and 99 migrations are unchanged; 874
assets retained in both paired roots. Desktop B recovery/restore pass. Evidence:
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/fix-release-4/`.
Never reuse consumed or rejected controllers; no backend restart or data restore.

[PR #288](https://github.com/artinflight/vibe-kanban/pull/288) is the staging rebase integration
authority through its final checks and merge event. Prior full baseline 41493120165
passes; Rust source is unchanged. Private remote checks skip without a deploy key.
Main promotion is separate. Preserve unrelated dirty canonical work.

The unchanged seen endpoint clears all workspace sessions and retains an arrival
race. Automatic review rejected optional live-state mutation without exact per-turn
restoration. No live persistence, historical unread reconstruction, provider call
or physical-device test is claimed. See VK_DISAPPEARING_UNREAD_FIX.md/manifest.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
