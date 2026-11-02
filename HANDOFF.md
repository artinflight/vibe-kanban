# Visible conversation read correction — 2026-11-02

The operator rejected manual-only clearing: opening the transcript must clear
unread when the latest reply has actually been displayed. The frontend correction
adds a focus/visibility/content/viewport guard with a 350 ms dwell, intentional
reselection and jump-to-latest support, and preserves unread on background return
and passive polling. The explicit bulk control remains. Backend/API/schema stay
unchanged; server-wide scope and arrival races remain limitations.

The corrected preserving build is published: JS index-C2FVxMt6.js, CSS
index-C-pTuj_j.css, version 0.1.42. All five services/backend hash/DB identity
are unchanged; 99 migrations and 822 retained assets pass readback. Desktop B
recovery is verified. Source integration uses [PR
#288](https://github.com/artinflight/vibe-kanban/pull/288) into staging with the
requested rebase method. Its final checks and merge event are authoritative.
The operator authorized push, staging PR and rebase merge after validation.
Keep main promotion separate and preserve unrelated dirty canonical work.

Read-view mounted tests pass; real-layout validation found Workspaces can restore
an older scroll position, which must stay unread until deliberate reading reaches
the latest reply. The actual jump-to-latest buttons are included in browser QA.
All browser application writes are intercepted. Automatic approval review rejected
an optional live read-state test because old per-turn bits cannot be exactly
restored; no live mutation or persistence certification is claimed.

Preserving source, paired fallback, software recovery and all receipts belong to
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/fix-release-2/`.
The original manual-only deployment receipts remain historical under release-1.
Do not reuse consumed activation controllers. No backend restart/device work.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).

Four candidate and four served browser cases now pass on both chat surfaces at
1440/393 pixels, with zero page errors and all application writes intercepted.

The full hosted Test baseline 41493120165 passes, including workspace tests,
Rust lint, schema/SQLx, Tauri checks and storage/watchers/scheduled persistence.
Private remote checks skip without the deploy key. Final PR checks and merge
event remain the integration authority.
