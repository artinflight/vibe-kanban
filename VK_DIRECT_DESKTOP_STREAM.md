# Direct-to-Desktop backup capture — October 8, 2026

## Outcome and ownership

New `vk_rolling_backup.capture` calls stream the **complete compressed archive
directly to Desktop B:**. No full archive or SQLite snapshot is staged or retained
on Linux. This is an isolated operational-tooling change, not a deployment,
restart, archive cleanup, or full-production-restore acceptance.

Owning repository: `artinflight/vibe-kanban`. Branch:
`fix/vk-direct-desktop-stream-20261008`. Base is staging
`5a887abf8bbedfbfb01ce7f8898fed07102fa1e3`, with published PR149 prerequisites
`49cf82d603b765b4ceaf5a8b4462f046e6181c0f` merged at `f639c97a6`.
Neither the canonical dirty checkout nor Staging's worktree was edited.

## Contract

- The existing scope, exclusions, change journal, database discovery/required
  databases, parent-chain checks and final writer-fence checks remain authoritative.
  This does not remove generated material from a backup plan or waive any proof.
- SQLite online snapshots use a read transaction and the backup API into RAM,
  one database at a time, including committed WAL contents. A fenced database
  without WAL/journal sidecars is read into RAM without opening live SQLite;
  integrity validation changes a WAL header only in the private RAM validation
  image. The archived fenced bytes remain identical to the original.
- GNU tar supplies PAX Linux permissions, numeric ownership, timestamps, ACLs,
  xattrs, SELinux information, symlinks and hardlinks for non-database payloads.
  SQLite snapshot members carry original file mode, ownership, mtime and xattrs.
  Tar headers and snapshots join one streamed tar, compressed by `zstd -T2 -3`.
- Existing authenticated `ssh desktop` is the only write transport. No new key,
  route, service, mount or security setting is installed. Destination remains
  `B:/vk-backups/<task>`. B unavailable means failure, not SSD fallback.
- Receiver writes a unique `.partial-<uuid>`, checks the sender's byte count and
  SHA256, fsyncs, then rereads the complete B file and verifies its identity/hash.
  Atomic no-replace hardlink publication cannot overwrite a previous archive.
  Only that successfully published transfer's temporary name is removed.
- Capture then streams the remote archive back through the existing verified
  archive reader, checks the manifest and every SQLite snapshot hash, rechecks
  journal/fence continuity, and verifies recovery metadata delivery before
  publishing the local result/head. A remote archive alone is not acceptance.
- Interrupted transfer, checksum/validation failure or publication uncertainty
  retains diagnostic material and leaves the previous good head/backup intact.
  Fresh streams always use new names. A failed direct stream requires a fresh
  capture; it cannot be concatenated/resumed as if it were a fixed local file.
  Existing legacy archive recovery/resume remains supported and tested, but
  production capture has no legacy local-staging fallback.

## Capacity and limits

Per capture: path inventory <=64 MiB, manifest <=32 MiB (unchanged reader bound),
tar warnings <=8 MiB, each receipt <=64 MiB, and new capture metadata-file budget
including atomic-save scratch/new head <=256 MiB (directory/filesystem overhead
is additional). This is a hard ceiling,
not a claim that production needs that much. Prior metadata/evidence is preserved;
there is no automatic historical cleanup or retry loop. All local metadata lives
under a named directory on verified mounted `/mnt/vk-storage`.

The default single SQLite image bound is 1 GiB (`--max-snapshot-bytes` can be
explicitly configured). Exceeding it fails closed, never omits the DB or spills
to disk. RAM is not just the serialized size: allow several image-sized copies
(up to roughly three during fenced WAL-image validation) plus SQLite/Python,
source inventory, tar and compressor overhead. All databases are not accumulated
in RAM together. The current audited largest database is about 788 MiB; production
memory/cgroup fit still needs confirmation by the integration owner. The stream
is bounded at 128 GiB compressed; exhaustion fails without accepting a backup.

The live synthetic test at 20:05 UTC streamed a 2 MiB attachment plus a SQLite DB,
uncommitted text, a failed-metadata delta and its fresh replacement to existing B.
Across 292 samples at 25 ms intervals, local backup metadata files peaked at 61,440 bytes
allocated /24,241 logical; observed local archive/snapshot payload was **zero**.
Python peak RSS was 335,757,312 bytes. These are fixture measurements, not an 82 GiB
production extrapolation. Final backup-directory usage including directories was 86,016 bytes. There is also a test rejecting any local payload-file
open, rather than relying only on sampled measurements.

## Verification receipts and limitations

See `scripts/deployment/receipts/direct-stream-20261008.json` for exact commands,
source hashes, test results and the live receipt. Coverage includes normal
capture/restore, unavailable B, producer/receiver interruption, checksum/readback
failure, validation failure, immutable previous archives/head, SQLite memory and
metadata limits, WAL consistency, fence invalidation, scope/journal changes,
metadata/link preservation and no local archive accumulation.

Because the SSD has less than the unchanged 2 GiB production restore floor,
unit restore tests use an explicitly private capacity substitute (<=8 MiB fixture,
>=32 MiB actual free). A separate test runs the real floor and confirms rejection.
No production capacity check was lowered. The live test used `--archive-only`;
it did **not** perform or certify a full restore. The separate full-state Linux
restore environment/capacity problem remains unresolved by this fix. Cleanup,
human QA, sealed-package integrity and cutover approval gates are unchanged.

Full Rust/workspace fixtures, service lifecycle tests and production handover
were not run. The normal application format/check/lint commands cannot complete
in this deliberately sparse, dependency-free checkout. No shared Cargo build,
tool install, new CI workflow, workflow dispatch or unrestricted cleanup hook
was used. CI status must be read from the draft PR, not inferred from local tests.

The first live test completed its transfers but failed its harness assertion
because SQLite SHM bookkeeping was incorrectly treated as stable user content.
The harness now explicitly verifies non-DB bytes plus SQLite logical contents and
integrity. Both new test directories on B and their local synthetic sources are
retained; neither old backups nor any recovery evidence was deleted.

## Integration handoff — Root coordinates, Staging owns adoption

Integrate the focused stream-fix commit onto the combined release only with its
PR149 dependency present. The draft branch contains that dependency explicitly;
do not replace Staging's prepared release tree with this branch or replay its
prerequisite merge over already integrated work. Pin the final reviewed source.

The new package must contain and hash-bind `vk_archive_stream.py`,
`vk_direct_capture.py`, `vk_desktop_transport.py` and the changed
`vk_rolling_backup.py`, using the existing operational packaging workflow.
The required-module checks enforce this. Existing `mirror_desktop`, CLI capture,
benchmark/rehearsal adapters and packaged capture callbacks support streaming.
Custom callbacks expecting a filesystem archive must adopt the stream interface;
they fail explicitly rather than materializing a local copy.

Prepared/sealed packages do not change when a PR is merged. Use the existing
fresh-package/reseal and validation rules; do not hot-edit or weaken a sealed
package. Preserve its exact full source scope, journal and owner state, approved
frontend/backend artifacts, prior B recovery chains and rollback material.
Re-establish the required backup/restore/readiness evidence before the existing
human-QA/cutover gate. This change removes local archive staging, not the full
restore requirement or its storage need. This agent has not contacted or started
Staging, deployed these tools, merged anything or restarted VK.
