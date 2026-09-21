# September 21 Rehearsal Retirement

The operator authorized removing the 22 old VK cutover rehearsals if safe.
Scope is limited to `/mnt/vk-storage/vk-cutover-20260911/window-rehearsals`.
The rehearsal launcher explicitly uses disposable data and private ports.
Current production and standby configuration do not depend on these payloads.
No vk-window rehearsal units remain loaded. Readable process command lines,
environments, mappings, mounts and descriptors contain no references to this
tree. Some host authentication and SFTP processes are non-dumpable; those
visibility limits are recorded, not represented as fully inspected.

## Preservation And Removal

The frozen allowlist contains 1,575 copied SQLite files and rehearsal archives,
33,354,200,158 apparent bytes across 22 directories. It excludes source,
worktrees, attachments, logs, screenshots, symlinks and all directory roots.
The whole rehearsal is archived before removing any selected files. Each
archive is compared against its source with tar, copied to Desktop B, and
independently SHA256-verified there. File identities and process references
are checked again before deletion. A failed check aborts further deletion.

Full original rehearsals are preserved at:
`desktop:B:/vk-backups/vk-rehearsal-retirement-20260921/`.
Each retired directory gets a RETIRED-PAYLOADS.txt location/checksum note.
These retired fixtures must not be launched without restoring their payloads.
Restoration is to a private rehearsal directory, never over production data.

Exact allowlist, safety checks, scripts and per-rehearsal receipts are under
`/mnt/vk-storage/vk-rehearsal-retirement-20260921`.
Production data, native histories, attachment roots, retained generation
binaries and production recovery chains are not cleanup targets. Historical
recovery exceptions are unchanged.

## Completion

All 22 rehearsals are retired: 1,575 selected files,33,354,200,158 bytes
(31.06GiB). The 22 verified Desktop archives total15,267,128,763 bytes.
The rehearsal tree now occupies5.9GiB; its retained contents were intentionally
not swept. SSD free space is75GiB at acceptance. Other disk work was concurrent,
so the total free-space increase is not attributed to this cleanup alone.

Live vibe.local attachment upload/download passed with byte equality, artifact
6ad1e996-cb5a-4048-bc66-324e17d160d4. Protected data/native/attachment roots retain
their ownership and permissions. Green PID1674994 remains running and Blue
PID2150526 remains frozen. No service restart or cutover occurred.
Formatting, ops governance and diff checks pass. Logs contain missing-cache
attachment warnings and subscriber broadcast-lag errors; this is not an
application-wide clean bill of health. Both warning types also predate cleanup
(missing attachments at02:21UTC and broadcast lag at00:47UTC).
No deleted file was in the production attachment path or a source/worktree.

This cleanup neither prepares a complete release nor authorizes a cutover.

The final scripts, allowlist, receipts and acceptance evidence are mirrored as
`evidence.tar.zst` in the same Desktop directory. Local and Desktop SHA256 match:
`238f873001fc6da3699f9ff07be437b2d5366c4906174a71962d28e55aa98a93`.
