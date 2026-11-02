# Explicit workspace reads — 2026-11-02

Branch `vk/3ad7-vk-disappearing`. The operator requested implementation with a
strict frontend-only boundary. No backend/API/schema or generated type changes.

The existing API clears an entire workspace and cannot acknowledge exact reply
revisions. Therefore all automatic seen calls are removed: opening, polling,
visibility changes, remounting and project workspace reselection preserve unread.
An explicit “Mark all replies read” control is available in project conversations,
Workspaces conversations and workspace actions. It deliberately retains the
existing workspace-wide API contract. Pending duplicate clicks are blocked;
errors remain visible and retry requires another explicit action.

The original exact-reply proposal remains historical investigation context in
`VK_DISAPPEARING_UNREAD_INVESTIGATION.md`; it is not the implementation selected
under the operator’s no-backend-change constraint.

The preserved live base is source `800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`,
previous JS `index-BvmbFTPN.js`. The published preserving build uses that source
plus feature commit `70d7f5b0516a784ca6f27ba9fc6245b441666663`; newer chat notices
are retained exactly. Live JS is `index-CfDh4WtO.js`, CSS `index-C-pTuj_j.css`,
version `0.1.42`.
Evidence root: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.

Seventeen mounted regressions pass. Restoring previous automatic-read project
code reproduces nine failures. A real-browser negative control observes the old
frontend issuing a seen request on opening; every write is intercepted.
Frontend types, focused lint, required format and import guards pass.
Seven adjacent navigation tests and four candidate plus four served browser
cases pass at desktop/phone widths with all writes intercepted. Frontend
publication and public TLS/asset/runtime preservation checks passed. The verified
paired fallback and Desktop B recovery preserve all 717 hashed assets.
No backend restart, DB restoration, historical unread repair or physical-device
operation. Reload all existing tabs/devices. See `VK_DISAPPEARING_UNREAD_FIX.md`.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).
