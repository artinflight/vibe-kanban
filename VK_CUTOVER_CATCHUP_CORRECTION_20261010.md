# Approved cutover catch-up correction — October 10, 2026

The 17:30:25 UTC retry failed before candidate start with AssertionError:
“Measured recent-state catch-up exceeds bounded allocation; no scope reduction”.
The earlier 17:00:41 invalid `worktree_path` query is corrected to actual
`container_ref`/`agent_working_dir` paths. Both failed attempts, original evidence
and B backups remain preserved. No old DB restore, cleanup or imports occurred.

At this checkpoint, incumbent PID1254186 remains healthy on current data:
server SHA256 `2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f`.
Trusted-CA HTTPS and API info return200. Served HTML SHA256:
`d690b1bf3ab5f3e7e6dfc2a53d3235b10cf94b58f87101f282467a4d2d563f80`.
Recovery-status still returns HTML: the reader has NOT been published.

## Diagnosis and tested correction

The estimated8GiB uncompressed bound was smaller than genuine recent execution
histories. Actual same-scope selection plus retained consistent SQLite images:
15,628,225,777 bytes
(14.55GiB),
460 unique source paths plus five SQLite images.
Original and corrected selected path sets match; no input was omitted. Private
names/content remain withheld. This failure does not establish ENOSPC/data loss.

The corrected actor separately checks raw payload <=24GiB, tar estimate <=26GiB,
B free >=26GiB stream bound +2GiB reserve, and SSD free >=native snapshot/primary
preimage allocation +2GiB reserve. Actual B free 73,927,860,224 bytes;
SSD free 18,620,133,376 bytes; snapshot/preimage allowance
1,724,860,528 bytes. All pass. Archive payload streams directly
to B; no SSD archive staging. Measurements run before service effects, again after
execution drain, and before native snapshots. Final measurement is saved before
the guard so a failure remains diagnosable. No scope reduction or guard waiver.

Eight schema fixtures pass; actual current query resolves1775bases/35attachment
directories. In-memory copied DB with exact prepared migration resolves identical
paths and integrity passes. Actual prepared artifact/incumbent guards pass.
Nine budget/order/redaction/readback regressions pass, including oversized raw,
tar estimate, insufficient B/SSD and exact boundaries. The formerly failing sum
now passes with real inputs. Actual tar-producer AST remains unchanged, binding
prior path/symlink/metadata fixture acceptance. Full compressed streaming remains
pending the quiet attempt; no new candidate start is claimed.

Actor SHA256 `2a13aa6a66d4e589ce6df67a2e8abd3894933bb8ea79e31f6832418b6688f9af`.
Prepared Staging `2693c46d4725878f8e11310cb528b6665e916ff3` has the same built tree
as `de8dc3d527d927fbcdb98ff60769a1002ad5b0a4`. Backend SHA256
`0b236be6ed9dfe858511293131fc3fc890d716e963435844f08db7b1d00926a1`;
latest-data compatible backstop SHA256
`46522be95b2650a11a05065fa528e6e82011b3ac1f33299380834cffaf164002`.
No application rebuild/settings/permission change. Recommend-only remains;
queue draft/Git enforcement activation stay excluded; historical exceptions stay
unresolved. The eight-agent capacity and global watcher are unchanged.

## Fresh approved attempt and durable outcome

Fresh directory `attempt-measured-catchup-20261010T1740` under
`/mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness`.
B destination
`B:/vk-backups/vk-next-restart-full-reader-20261010/final-cutover/measured-catchup-20261010T1740`.
The actor waits for actual execution rows/units; preserves queued user text and
current roots; takes fresh B-verified DB/review/native preimages; verifies actual
backend identity and HTTPS HTML/JS/CSS/manifest plus both original protocol1 JSON
routes before claiming publication. Old incumbent is protected. After migration,
rollback uses the compatible backstop on latest data, never the old c3 executable
or stale DB. Existing Restore Missing Chats owner alone performs genuine imports.
No broad workers launch during handoff, no cleanup before human QA.

The terminal success/failure and actual served readback will be posted to existing
[PR242](https://github.com/artinflight/vibe-kanban/pull/242), with GitHub readback
verification. Native chat final capture is not relied on. Local/B receipts also
remain. An uncertain GitHub write is not repeated. Existing Staging callback is
secondary; Seamus must be told after verified publication. This document records
preparation, not a deployed release; consult the later terminal checkpoint.

Repository formatting: `pnpm run format` completed Rust formatting, then failed
because this existing worktree has no Prettier executable (`spawn ENOENT`).
No dependency installation/build was attempted. Python AST/compilation and
focused tests passed; no Rust/TypeScript application source changed.
