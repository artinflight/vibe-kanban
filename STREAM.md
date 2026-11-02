# Deliberate visible reply reads — 2026-11-02

Branch `vk/3ad7-vk-disappearing`. Frontend only: no Rust/API/schema/generated-type
changes. Normal clearing is restored after the operator rejected manual-only reads.

An opened/reselected conversation, reading gesture or jump to latest acknowledges
once the latest loaded reply/error end is unobscured and visible with foreground
focus for 350 ms, after running/approval turns settle. The underlying derivation's
pending/running state is used before renderer filtering. Background return,
passive polling and new output alone do not arm reads; a changed reply cancels a
captured dwell. Explicit workspace-wide bulk read remains available with visible
failures and no optimistic acknowledgement/automatic retry.

Current serving feature: `9a45a3abf2d99eb44c14ef7a744d6f7bf0fbb73e`; JS `index-DqfYW9pf.js`;
CSS `index-C-pTuj_j.css`, version 0.1.42. Source composition retains live base
800011bd573e2869d6ea4c0e5bfba4d9046d9cbe and the earlier 70d7f5b05/b8bad2179
frontend work. Git-preservation notices remain exact. Evidence and paired fallback:
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/fix-release-4/`.
Both roots retain 874 assets; backend/five services/DB identity/99 migrations
are unchanged. Reload every existing tab/device; no historical unread repair.

39 mounted regressions, types/focused lint/format/ops and production build pass.
Four candidate/four served layout cases and candidate/served running-turn guards
pass with intercepted writes. The previous view bundle's premature running-turn
read was reproduced with an API-verified process. An intermediate candidate using
a filtered metadata marker failed completed-view QA, was rejected and never served;
its controller is permanently disabled. Software recovery is verified on Desktop B.

The API remains workspace-wide; cross-session scope and arrival race remain.
Automatic approval review rejected an optional live state mutation without exact
restoration; no live persistence, provider or physical-device QA is claimed.

[PR #288](https://github.com/artinflight/vibe-kanban/pull/288) targets staging using the requested
rebase method. Final checks and merge event govern integration; original deployed
IDs remain immutable. The prior full Test baseline 41493120165 passes on b8bad2179;
backend source is unchanged. Private remote checks skip without a deploy key.
Main promotion is separate; Git integration does not restart/redeploy services.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).
