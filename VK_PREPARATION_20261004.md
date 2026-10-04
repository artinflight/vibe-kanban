# October 4 Cutover Preparation

## Current State

The current version remains usable on Green3059021,5411/5412 and vibe.local.
CU3921554 is unchanged. No production process was paused, stopped or restarted.
The fresh candidate unit is vibe-kanban-blue-production-20261004.service on5461/5462,
installed but inactive. The prior20261003 unit and its consumed attempt are not reused.
The operator's "go" was followed by a question clarifying whether final cutover
was included; no answer has been recorded at preparation completion.

Evidence root: `/mnt/vk-storage/vk-blue-reprepare-20261004`.
Read readiness.json together with its matching software-package-receipt.json.
A successful package receipt requires a Desktop download, restoration and full
comparison of every bound file. Readiness does not itself authorize cutover.
The verified package is maintenance-software-20261004T142429Z.tar.zst,
408730467bytes, SHA25699783d825839fc19dce93ff636353b933e30f0fa3c8e14da18a7a070cf2c8bf9.
All2488 bound files were restored and checked after downloading from Desktop.
Readiness SHA256 is b5c63ea72c7e92ddd16906e03663da07ed80a09caf1b2db7162e14ad09677ee0.
This package reuses the previous release/source/private-runtime paths through
links; do not delete vk-blue-prepare-20261003 as obsolete while those links exist.

Application main e53ae4a7e, staging86d1c083a and build9c2e04d72 still share
tree6963ed5d5dc174e1f40a84e71e8975cd82c716cc. No application rebuild was needed.
Prior exact-binary frontend/API/Steer/Stop/goals/attachment tests are reused,
not claimed as new production execution tests. VK remains version0.1.42.

## Backup Changes

The previous fallback recopied whole moved directories on every capture, despite
a verified online backup. It also repeatedly scanned unrelated historical events
and rebuilt long ancestor lists. These costs were absent from the old private
timing rehearsal.

The revised capture stores its complete subtree hash inventory in the archive
manifest and Desktop-verified recovery descriptor. A subsequent capture accepts
that baseline only after validating the descriptor checksum, source scope,
journal identity/sequence and archive association. It includes changed/deleted
paths rather than forcing every subtree into the archive. Old parent formats
still force a complete copy. All affected subtrees are independently rehashed
at both final stability checks, so lost directory watches cannot hide changes.
Unknown journal errors, changed coverage, symlinks in protected root positions
and unverified/tampered metadata still fail closed.

Journal reconciliation deduplicates historical watch-removal records and filters
move-event masks before constructing paths. Recreated skill directories and
personal-home temporary launcher directories have explicit bounded coverage,
not blanket ignored errors. The exact owned runtime socket remains the only
non-persistent socket-warning exception.

VK_BACKUP_PREPARATION_20261004.patch records the functional changes and their new
regression tests against the preserved October3 tool package. Its dry-run applies
cleanly; it is for a NEW copy, never modification of a consumed package. The full
working scripts are also bound into the new Desktop software archive. These are
local operational-tool changes, not a merged application-source PR.

## Validation And Timing

All77 backup tests,60 operational tests and one socket test pass. The new tests
cover unchanged incremental captures, changed/deleted files, writes during both
fences, tampered or unverified metadata and legacy-parent fallback.

The complete rehearsal is
scale-optimized-rehearsal/handover-95f41d95a08b4455b04d6ab0eed89dce/result.json.
It uses the actual old/new binaries, current-sized database copies and private
copies of all eight recopy roots. Every timed capture check also exercises the
real production journal parser and hashing workload read-only. Private service
fencing governs the fixture only; this does not claim production was frozen.
All four cases pass: rejected-backup recovery, successful latest-data activation,
post-switch write/model/settings preservation on same-process cutback, and safe
repeated recovery. Recovery from archives downloaded from Desktop passes too.

Measured switch71.517seconds: capture/fencing71.352, activation0.165. The verified
boundary copied19 files rather than whole unchanged subtrees. The90-second final
capture ceiling is unchanged. Allow about90seconds, up to two minutes, not a
guaranteed30-second switch. Actual production outage has not been measured for
this package. The rehearsal services terminated successfully after validation.

## Preservation And Approval

Fresh online baseline ed85125ad88d44b2a14f8f3739ccaebb is Desktop verified,
494468218bytes, SHA256b515fc857800735e62827115e6fc986fe604d54bf68ba53901da06fb3765c299.
It includes9 SQLite snapshots and64 database-generation proofs, plus the verified
parent chain. The new carConsole supplement is separately verified and required.
The pre-preparation review snapshot contains13638 turn flags and is verified on
Desktop with SHA2569b027a7aa2c12706251e7f69ff156d976def3629d85e5a68bfd764b78389ad0c.
No historical review state, source files or database was restored or deleted.

Seven-model availability was refreshed using nine bounded calls against the
unchanged production launcher/account/home. CLI0.159.2 and identical private
VK/CU telemetry paths pass. Broader V1 inference acceptance was not repeated.
The final preflight found only this maintenance execution and no queued messages;
that observation expires and must be checked again before interruption.

Only after explicit cutover permission: refresh the online backup and supplement,
bind current identities/source/queue/review state, and start the NEW independent
controller once. Preserve the original thread and retain the original process
for same-latest-data rollback. Return to this conversation for live acceptance.
Never replay October3 or copy an older backup over production.
