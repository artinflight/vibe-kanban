# Visible conversation read correction — 2026-11-02

The operator rejected manual-only clearing: opening the transcript must clear
unread when the latest reply has actually been displayed. The frontend correction
adds a focus/visibility/content/viewport guard with a 350 ms dwell, intentional
reselection and jump-to-latest support, and preserves unread on background return
and passive polling. The explicit bulk control remains. Backend/API/schema stay
unchanged; server-wide scope and arrival races remain limitations.

The corrected preserving build is being validated before publication and staging
integration. STATE and LIVE_DEPLOYMENT identify the currently serving release.
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
