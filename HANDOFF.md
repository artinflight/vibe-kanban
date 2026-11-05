# Workspace status-row actions pickup — 2026-11-05

Feature `ee435a75c` is live at <https://vibe.local>, published
2026-11-05T10:46:08.024061+00:00. Reload tabs. Read Later and the three-dot menu
share the status/time line on desktop and phone; titles use full available width.
All prior bookmark behavior, unread state, section heights and Dot-disabled build
setting remain. No backend restart, push, PR or agent/device launch.

Current evidence: `/mnt/vk-storage/vk-read-later-20261105-status-row`.
1,324 verified inputs, one changed production file, 417 output files, 1,190 paired
assets. 15 interactions, UI types/lint, format/ops, bounded production build,
four candidate/public geometry/persistence cases and five scrolling layouts pass.
Zero read/application writes/Dot polls; stable five services/backend/DB inode and
99 migrations. Full software restore and independent Desktop B readback passed.
See LIVE_DEPLOYMENT.json and VK_WORKSPACE_STATUS_ACTIONS_DEPLOYMENT.md.

Pending: user reports desktop Read Later not reflected on mobile. The current
store is browser-local, scoped by host/user. No synchronization exists. The
async question asks whether to add shared sync; no answer received at this record.
Durable preferences currently support project order/colors only; scratch has no
Read Later payload. Do not send unknown fields (they are dropped), hijack read
flags, or overwrite unrelated preferences. A proper shared-store implementation
needs backend work and its deployment protocol; this frontend release adds none.
Preserve existing local bookmarks during any future migration, and test two
independent browser contexts plus removal without resurrecting stale bookmarks.

Current layout publication is complete. Source integration still requires a
fresh branch/full staging baseline. Physical device/provider/Rust baseline was
not exercised. Existing preview routes and previous software remain retained.

Prior continuity: [full historical archive](HANDOFF_HISTORY_20261017.md) and
[pre-reconciliation record](deployment-history/20261030-before-reconciliation/HANDOFF.md).
