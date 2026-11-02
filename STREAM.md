# Disappearing unread notifications — 2026-11-02

Branch `vk/3ad7-vk-disappearing`. Scope: investigate reports that workspace unread
notifications disappear without reading the update, and propose a fix. This turn
changes documentation only; implementation and deployment are outside this request.

Confirmed overly broad automatic read behavior: chat mount, tab return and
same-route reselection call bodyless workspace-wide `/seen`. Project record
readiness is insufficient to establish session/transcript readiness. Server SQL
clears unseen turns across sibling sessions and replies arriving before the read
transaction, and the same path releases manual unread hold.

Fresh served JS is `index-BvmbFTPN.js`, SHA256
`fc683d01d272989dffb7ad107f185faaf26d434731b754e48485a7a6786e4e6b`,
from retained source `800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`. Five affected
source files match. Backend PID/hash remain the October 30 identity. Existing
October 31 production manifests in this branch are historical, not fresh live
frontend truth. Preserve the newer release and all runtime state.

Existing 13 mounted tests pass; four added evidence-only characterizations confirm
premature read calls (17/17 total). In-memory production SQL reproduces three
backend defects plus a passing changed-summary/unrelated-workspace control.
No live unread mutations, device actions, backend restart or deployment occurred.
No claim attributes a specific historical disappearance to these mechanisms.

Proposal: exact rendered-reply acknowledgements, focus/content visibility gates,
transactional revision/intent checks, manual unread preservation, and a separate
explicit bulk action. See `VK_DISAPPEARING_UNREAD_INVESTIGATION.md` for evidence,
limits and acceptance gates. Raw evidence:
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.

Prior unread integration remains recorded in `DELTA.md`, `STATE.md`,
`VK_PROJECT_UNREAD_DEPLOYMENT.md` and the historical deployment manifest.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).

Required repository format, ops governance and whitespace checks pass.
