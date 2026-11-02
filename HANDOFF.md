# Frontend-only unread correction pickup — 2026-11-02

The operator authorized implementation with no backend changes. Frontend source
now removes automatic reads from workspace/project chat mounting, visibility
changes and same-route reselection. Explicit “Mark all replies read” controls in
both conversations and workspace actions retain the existing workspace-wide API.
The control prevents duplicate pending requests and shows failures without
optimistically clearing badges or automatically retrying.

Seventeen mounted regressions, seven adjacent nested-card tests, affected frontend
type checks, focused ESLint, required formatting and import guards pass. Old
project/reselection code fails nine of the new regressions. The existing live
frontend also emits an unwanted seen request in a mobile browser negative control;
all writes were intercepted.

The preserving frontend release is published under
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/fix-release-1/`.
It starts from currently served frontend source 800011bd573e2869d6ea4c0e5bfba4d9046d9cbe,
then applies only this frontend patch. Current live git-preservation notices are
byte-preserved. All four candidate and all four served browser acceptance cases pass with
intercepted writes, at 1440/393 pixels on project and Workspaces views. Public
TLS/index/asset/health readback passes. The frontend pointer switch took 0.012907
seconds; all five service identities, backend hash, DB inode and 99 migrations
are unchanged. Live JS `index-CfDh4WtO.js`, CSS `index-C-pTuj_j.css`, version 0.1.42.
717 assets retained in both paired roots. The 78,181,682-byte software recovery
archive was independently read back from Desktop B; local restore verified
3,293 files and permissions. Feature commit: 70d7f5b0516a784ca6f27ba9fc6245b441666663.
No push or PR; upstream promotion remains separate. See
`VK_DISAPPEARING_UNREAD_FIX.md` and `LIVE_DEPLOYMENT.json`.

No Rust/API/schema/type-generation changes, backend restart, physical-device
operation, provider call or historical unread repair is part of the correction.
All existing VK tabs must reload: old loaded bundles can retain
the previous automatic read behavior. Exact-reply conditional acknowledgements
from the original proposal are intentionally not implemented under this scope.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
