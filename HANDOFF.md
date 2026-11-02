# Disappearing unread investigation pickup — 2026-11-02

Requested outcome is investigation plus a proposed fix; both are recorded in
`VK_DISAPPEARING_UNREAD_INVESTIGATION.md`. No application implementation or
publication to the live frontend was attempted.

The confirmed mechanism is automatic workspace-wide acknowledgement on chat
mount/tab return/reselection, before proving a reply was rendered and read.
The backend clears all sessions and can swallow a newly arrived reply; it also
releases manual unread hold. Recommended correction is a separate exact-reply,
revision-checked automatic read path driven by focused visible reply content.
Preserve explicit bulk read and existing connector receipt semantics.

Validation: existing mounted suite 13/13; four evidence-only characterizations
also pass (17/17 together), reproducing current unwanted calls. Disposable SQLite
using actual SQL/migration confirms cross-session/arrival/manual-hold defects,
with changed-summary and unrelated-workspace preservation controls. Full browser,
Rust HTTP, candidate fix and physical-phone acceptance are not claimed.

Evidence: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.
The diagnostic cases assert current defective behavior and must be converted to
fix acceptance tests, not added as desired production behavior.

Live JS is now `index-BvmbFTPN.js` from retained source `800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`.
Fresh byte comparisons confirm all investigated source paths are unchanged.
This branch's October 31 deployment manifest is historical. Preserve the currently
selected newer frontend. Backend PID 645213/hash 137d6cd7… remain unchanged.
No live unread state or device was touched. Do not infer permission to restore
badges, restart services or deploy from the investigation request.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).

Required repository format, ops governance and whitespace checks pass.
