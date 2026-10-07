# October 7 Staging Verification Incident

## Current Outcome

No production cutover occurred. The October 5 service, PID3027197, still serves
port5511, version0.1.42, mainfa8122a50. CU414400 remains running. Its retained
previous process1369037 remains the pre-existing fallback; it is NOT approved as
the new v2-hold rollback reader. No old database was copied over production.

This is an incident, not successful release completion. The staging agent
bypassed the reviewed executable isolation boundary and guessed an unsupported
build-information argument. That was a failure to follow the operating rules.

## Cause And Containment

At approximately23:16UTC, the agent executed the candidate rollback server with
`--vk-build-info` directly on the host. The source only handles
`--capacity-build-info`; the unknown argument fell through to normal startup.
The unintended PID2670802 opened the default legacy
`/home/mcp/.local/share/vibe-kanban/db.v2.sqlite`, not the production green-XDG
database. Startup orphan cleanup then treated shared worktrees as untracked.

The agent confirmed the exact executable/arguments, paused that PID, verified
that it had no child processes, then killed that PID. Production and CU were
not stopped. The concurrent private rehearsal failed closed because its working
directory had disappeared; it is NOT a passing handover receipt.

Source evidence is in `crates/server/src/main.rs`'s argument handling,
`crates/local-deployment/src/container.rs::spawn_workspace_cleanup`, and
`crates/workspace-manager/src/workspace_manager.rs::cleanup_orphans_in_directory`
at combined5ec572245. The existing reviewed artifact validator already used the
proper isolated command; the agent incorrectly bypassed it.

## Recovery Evidence

Evidence root: `/mnt/vk-storage/vk-combined-release-20261007/incident-2316`.
The initial backup comparison found106286 missing paths across85 worktree roots.
This is a snapshot comparison, not proof that every missing path was newly lost
in this event. Original journal/history and earlier recovery exceptions remain.

Fresh full hashes of Desktop B full02136af9b9c24c08bccba0868864e597 and
delta430d3a842f5d4216862a1703e33232b8 passed. A private recovery read both complete
compressed streams, checked the actual manifests, and verified116402 regular
files before placement. Links were retained separately and materialized only
after authenticated extraction, never used to write through to live paths.

The exact plan covered85 worktree placements and86 Git-registration operations.
All171 completed using atomic no-replace placement;24016 existing paths were
retained, not overwritten. One metadata-copy attempt stopped because it handled
directories but not individual files. The corrected, tested suffix resumed only
the remaining63 operations. Original plans, failed result and final result remain.
Seven focused no-replace tests pass, including newer-file, empty-directory,
symlink-parent, symlink-target and Git metadata-copy cases.

`post-placement-audit-v2.json` finds ZERO remaining missing paths from the original
106286-path list. Historical no-reflog registrations are checked against their
immutable detached HEADs, not silently dropped. The staging owner's pushed422fe5ba0
and this turn's exact recorded patches reconstructed15 owner files; recovered
preimages and the old index were preserved. The other newer-head workspace,
86ce/art-in-flight atb7984f5e, remains clean and was not overwritten. The original
conversation and one historical malformed transcript line remain preserved.

`unbacked-name-candidates.json` finds zero still-missing new names absent from both
the accepted archive inventory and earlier journal. This does NOT prove all edits
to existing filenames after the22:34 backup survived. Such edits remain an explicit
recovery limitation; do not claim zero data loss or erase older unbacked-edit gaps.

## Accepted Release Work, Not Deployment

Combined draft PR150 is pushed at5ec572245, incorporating the final reviewed
connector repair; CU remains95e7aea47. Independently run33 focused Rust checks,
server compile, installed connector-to-HTTP fixture, four strict historical
replays with exact reply hashes,13 packaged artifact/native cases, four real
CU/HTTP/browser fixture groups, and one actual AutoSwitch reload test passed.
The source's exact CI passed441 tests with10 skipped. These receipts predate
the incident and are retained, not represented as a full production acceptance.

The real frontend has identical inputs to the accepted86f62b2 build;1534 package
files are hash-bound. Candidate and compile-disabled v2 rollback binaries plus
the matching protocol2 AutoSwitch module are inert in `final-package`.
Historical receipt indices78/236 and92/103 remain unreconciled; no live badge
or writer-closure proof was fabricated. Recommend and credit settings were not
changed. No paid-provider test or real Android-goal execution occurred.

All full handover attempts remain failed: adapter signature, connection lifetime,
and isolation-mount setup defects were corrected; the last attempt was interrupted
by this incident. The new checkpoint-payload retirement phase passes27 focused
tests but lacks a successful full-scale handover run. Only exact verified private
test DB copies were retired; original archives and recovery history remain on B.

## Required Next Work

1. Independently reconcile this incident's recovery and remaining post-backup edit
   uncertainty. Do not infer readiness from the currently healthy service alone.
2. Development owner: make unknown server arguments fail before any deployment,
   DB open or cleanup, and make shared-root orphan deletion require positive
   ownership evidence. Add isolated regressions. Do not run another direct host
   server to reproduce this. No competing edits to the combined release here.
3. Operational owner: bind and test the compatible v2 rollback binary in the actual
   new controller. Its current legacy same-process thaw path is unsafe after v2
   holds exist. Passing private paired-reader tests is not production adoption.
4. Reconcile the new journal deletions/recovery moves without dropping protected
   roots, then reinventory and capture current data and files with PR14949cf82d60 or a verified
   descendant, keeping B the retained provider. Complete measured handover and
   Desktop restoration, source promotions, fresh final capture and actual idle
   checks before any conditional cutover. Earlier readiness is not reusable.

The unintended empty legacy database was not in the prior69-DB inventory. It is
preserved separately in the incident packet (zero executions, integrity check
passes); the next inventory must account for it rather than assume the old count.
Live production quick_check is ok, HTTP200 reports0.1.42,12 saved messages remain,
and the only running VK execution is this original maintenance conversation.
Full `pnpm run format` was attempted: Rust formatting passed, but frontend
formatting failed because Prettier is not installed. Ops governance and diff
checks pass; no full workspace suite is claimed.

The incident scripts operate only on this recorded event. Do not replay consumed
placement/cleanup scripts or generalize them into a shared-workspace cleanup hook.
