# October 1 Deployment Storage Cleanup

## Scope And Authority

The operator requested space reclamation on the SSD and Desktop B:. This is
cleanup, not another deployment, database restore, service retirement or history
retention change. Blue remains live on main329963d18/version0.1.42/Codex0.159.2.
Original Green remains frozen for recovery using the same latest production data.

Audit directory: `/mnt/vk-storage/vk-cleanup-20261001`.
Exact frozen allowlists, file inventories, checksums, deletion receipts and
validation results live there. Never rerun its deletion commands blindly.

## SSD Result

Removed 26 reviewed paths representing 98,152,095,744 allocated bytes
(98.15 GB / 91.41 GiB). These were the completed October 1 isolated restoration,
SQLite backup preparation and verification copies, six software restoration
directories, six superseded software packages and a superseded generated frontend.
No worktree, source checkout, live attachment store or current session was removed.

The largest copy was the 77.71 GB isolated restoration. Its full backup archive
and descriptor remain independently verified on SSD and Desktop. Its successful
restore receipt is historical evidence; the extracted directory is now retired.
Location notes beside removed paths explain this distinction. SQLite copies were
also checked against their recorded snapshot hashes before removal.

The exact file sets were checked again before deletion. Process cwd, executable,
open-file, mapped-file and environment references, plus service configuration
references, found no consumers of the selected paths. Attachment/upload matches
were classified as isolated backup copies or generated software, not live roots.

## Desktop Preservation

The historical loose files selected for compaction are:

- `B:/vk-backups/vk-desktop-restore-20260626T105545Z/share-vibe-kanban`
- `B:/vk-backups/vk-cutover-20260911T1854Z/failed-online-refresh-20260912T111504Z`
- `B:/vk-backups/vk-cutover-20260911T1854Z/failed-online-refresh-20260912T111928Z`

These were old backup copies, not current production data or the October 1
cutover backup. All 6,311 files, totaling 26,634,841,206 bytes, are now preserved
in `B:/vk-backups/cleanup-20261001/desktop-historical-extracts-20261001.tar.zst`.
The archive is 2,031,037,025 bytes, SHA256
`ec3d5ce46c1297933a9a1682a1fb2b61e338ce6f2c62583c99065cad1b467c5c`.
Every member matched its source checksum, the Desktop archive checksum matched,
and the source file inventory was unchanged before the loose copies were removed.
The six superseded software packages were a separate exact allowlist; the final
Blue and Green packages remain.

Net logical savings on Desktop were 26,408,031,161 bytes (26.41 GB). B: free space
rose from 26.83 GB to 53.06 GB; filesystem allocation and concurrent work mean
free-space change need not equal logical bytes. B: remains near capacity. This
pass did not remove unrelated Desktop files or unique historical recovery archives.
Compaction preserves bytes; it does not repair incomplete database snapshots
from historical failed attempts.

`desktop-deleted.json` records the nine exact Desktop paths removed.
`desktop-predelete.json`, also on Desktop beside the archive, retains source
hashes and restore-relative paths. Location notes replace the loose-copy paths.
The new archive's temporary SSD copy was retired after Desktop verification.
`result.json` records final capacities and retained-backup checks.
Final readback found about150.47GB free on the SSD and52.89GB on Desktop; other
agents continued working during this cleanup, so these values can change.

## Retained Recovery Material

- October 1 full checkpoint `d5073c889c0b4930826e142ca9ee5be3` and all five deltas
  through `6e483d86268740f3ab672e29cfc6b424`, with their descriptors on both drives.
- Independent live backup journal, plan, current result pointer and source tools.
- Final Blue package `prepared-software-20261001T132702Z.tar.zst` and final Green
  package `prepared-software-20260930T203014Z.tar.zst`, verified on both drives.
- Live Blue release, frozen Green release, CU runtime, frontend pointers,
  production data/configuration, both Codex homes and native histories.
- Historical thread-recovery archives and exceptions, dirty/untracked agent work,
  other projects, shared Cargo build output and reusable dependencies.

Never restore an old backup over production as a cutback. Historical compressed
copies must be inspected or restored into an isolated directory.

## Validation

Following SSD cleanup, Blue1504649 stayed running, Green2506054 stayed frozen,
CU1504725 and journal3356537 stayed running. Required protected directory identity,
ownership and permissions matched the before-cleanup inventory. All 12 saved
messages matched their prior content hash. A real upload and byte-identical
retrieval passed with attachment `9b8bd81f-2a10-40bb-b5df-ce4a169e4771`.

Blue logs since cleanup began had no matching missing-path, permission, upload,
HTTP500 or database-lock errors. This is a cleanup-specific check, not a claim
that historical warnings or missing-rollout exceptions have been resolved.
Formatting and Ops Playbook checks passed; no application code changed and broad
application tests were not repeated.
