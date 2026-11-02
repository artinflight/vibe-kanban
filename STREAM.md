# Visible conversation reads — 2026-11-02

Branch `vk/3ad7-vk-disappearing`. Frontend only; no backend/API/schema or
generated-type change. The operator reported the manual-only release stopped
normal clearing, and the corrected frontend is now published; Staging source integration uses the operator-authorized PR/rebase method; final PR checks and merge event are authoritative.

A deliberate conversation opening, reselection, reading gesture or jump to latest
may acknowledge once the loaded latest assistant reply's end is visible, focused
and unobscured for 350 ms. Hidden panels, background return, passive polling and
new output alone do not acknowledge. A reply changing during the dwell cancels
that intent. The explicit workspace-wide bulk control remains available.

The existing bodyless seen API still clears the entire workspace across sessions.
Exact-reply conditional acknowledgement and the server arrival race cannot be
fixed within the operator's no-backend-change boundary. Historical unread flags
are not reconstructed. Browser writes are intercepted: a real-server state test
was rejected by automatic approval review because the original per-turn state
cannot be exactly restored. No live unread mutation test is claimed.

The preserving candidate starts from release-1's source (live base
800011bd573e2869d6ea4c0e5bfba4d9046d9cbe plus feature 70d7f5b0516a784ca6f27ba9fc6245b441666663).
Newer git-preservation notices must remain byte-identical. Evidence root:
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.
Current serving truth is STATE/LIVE_DEPLOYMENT: JS index-C2FVxMt6.js, CSS
index-C-pTuj_j.css, version 0.1.42. Paired roots retain 822 assets; all five services,
backend hash and DB identity/99 migrations are unchanged. Desktop B software recovery is
verified.

The operator authorized push, PR into fork/staging and rebase merge. Fresh staging
was aceb355e965c27c93e0a83d719bcdbccf84f4bcc; the initial rebase was a no-op.
Full hosted validation-only baseline and final PR checks precede integration.
Main promotion is separate. Git integration does not restart the backend.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).

Four candidate and four served browser cases now pass on both chat surfaces at
1440/393 pixels, with zero page errors and all application writes intercepted.

The full hosted Test baseline 41493120165 passes, including workspace tests,
Rust lint, schema/SQLx, Tauri checks and storage/watchers/scheduled persistence.
Private remote checks skip without the deploy key. Final PR checks and merge
event remain the integration authority.
