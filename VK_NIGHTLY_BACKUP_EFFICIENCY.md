# Nightly backup efficiency integration

October17: Seamus authorizes completion of production restore/integration checks,
publication, deployment and the single nightly schedule. This workspace owns
that package/schedule; restart preflight owns its shared consumer and Staging
owns its backend release. Current production adoption evidence is tracked
separately from the earlier source-only results below.

Tracking: [local Vibe issue T40](https://vibe.local/projects/e2645d00-9bc6-4136-8d6e-0c2fcf032d77/issues/f394eccb-cbb6-4e6a-a0ba-87ba8d51f904), linked
to workspace `604d90d0-0a23-4fde-bcf7-368486a6959b`.

This branch brings the backup portion of PR235, source
`240a7b2c7c626bb941e91f1b1463759a5907af23`, onto current staging. It excludes
the routine restart controller and its automatic handover semantics. Imported
capture/provider/journal, nightly lifecycle/calendar, rebuild proposal and
history experiment modules retain their source contracts. The direct-stream
receipt is historical source provenance, not acceptance of this new package.
The Operations Desktop-backed recovery work is included through that source.
Existing sealed operational packages are never edited in place.

## Integrated behaviour

- Each published nightly has one complete manifest and owns every required
  content object. There is no archive-parent dependency. A verified replacement
  reuses unchanged content by hardlink; separately adopted nightly-only retention
  can remove the previous generation after independent readback. Historical
  recovery chains, incident evidence and unique old versions are outside that
  enrolled namespace. Identical names or newer dates do not prove redundancy.
- `chunked-zlib-1-v1` adds lossless, ordered 1 MiB chunks. A file object holds a
  bounded layout with lengths and hashes; chunk objects use zlib level 1. Every
  new generation owns links to its complete closure. Appending a large history
  rewrites its partial last chunk and small layout, reusing full sealed prefix
  chunks. This stores all original records, duplicates, binary fragments and
  unterminated tails. It does not implement semantic transcript compaction.
- Chunks and complete reconstructed files are independently size/hash checked.
  The native Windows readback path and leased restart reader understand the
  format. Existing raw and whole-file zlib formats remain explicit options;
  encoding changes require a fresh store, not an in-place upgrade.
- `vk_backup_content_audit.py` and `vk_backup_lean_contract.py` bring forward the
  reproducibility findings. Exact roots require preserved hash-bound manifests,
  lockfiles, patches, local source, platform/toolchain and rebuild recipes.
  Protected work, Git objects, runtime artifacts and histories cannot be omitted.
  Proposal validation and a tiny offline rebuild fixture do not establish that a
  real package tree is reproducible. No production dependency/build exclusions
  are enabled here; identical retained bytes can still share storage.
- The restart adapter leases the exact manifest, verifies readback and consumes
  the original capture START journal sequence. Catch-up must use the same
  continuously covering watcher, fresh SQLite snapshots and the controller's
  writer fence. A default private watcher closes after capture; its backup needs
  full reconciliation before a later restart. A baseline grants no cutover.

`build_vk_nightly_job_config.py --compressed-delta --chunked-delta` prepares a
disabled proposal in a fresh chunked namespace. The existing source-bound cron
calendar supports 02:00 America/Toronto and bounded retries. The builder is a
historical host-specific proposal tool: reconcile actual source paths, artifact
pins, capacity and journal ownership before generating an operational package.
It neither enables cron nor changes a service.

## Recovery and validation

Run the focused fixtures only on mounted SSD, with an explicit owned TMPDIR:

```bash
TMPDIR=/mnt/vk-storage/vk-nightly-efficiency-20261016/test-tmp \
  PYTHONDONTWRITEBYTECODE=1 python3 scripts/deployment/run_backup_tests.py
```

The chunked fixtures physically reconstruct complete original bytes and SQLite
images, check database integrity and restart catch-up, and recover a second
current after the first is retired. They cover corrupt/missing/trailing chunks,
wrong order/length/hash, binary tails, empty files, short reads, insufficient
capacity, concurrent leases, journal loss, process death and exact retention.
The rebuild fixture preserves dirty work, attachments, Git and runtime bytes
while rebuilding a pinned offline dependency and generated file.

Current integration validation: 340 tests ran, 339 passed and the opt-in
disposable user-service timeout test was skipped. All eight historical
direct-stream source pins still match; Python syntax, `git diff --check` and
`pnpm run ops:check` pass. `pnpm run format` ran successfully through both Rust
workspaces, then stopped because this worktree has no Prettier executable.
Frontend type/lint checks, full Rust tests, production services and the real B
destination were not exercised by this Python-only integration validation.

A failed publication never advances `current.json`. An append-only, identity-bound
ledger records sealed chunk and layout bytes before linking each candidate name.
Recorded chunks can therefore be reconciled after a guard abort or process death
before the manifest exists. Changed, unknown or incompletely recorded evidence
remains protected and blocks guessing. No age-based or recursive cleanup is
introduced. Complete manifests retain the existing resumable retention path.

The integration also includes preflight's `vk_backup_rebuild_proof.py` from
`4b4ac9ce3`: a proposed exact dependency root must match an independently rebuilt
inventory and actual byte readback, including local patches, additions, absences
and symlink literals. This does not activate a live omission.

Packaging accepts the actual reconciled plan and includes the complete
supervisor/calendar/schedule source closure. The generated cron proposal uses
the fixed 15-minute wake-up pulse and Toronto calendar; it no longer emits a
conflicting UTC-only 02:00 producer. Runtime checks can bind the gateway's actual
served frontend separately from the backend's retained fallback directory.

The October17 real Desktop B fixture passes native Windows complete-file
reconstruction and SQLite integrity/value checks. A post-retirement restore of
all four fixture files succeeds with the preceding fixture generation absent;
the 2,097,204-byte synthetic history adds 1,331 stored bytes. Its first failed
harness run placed verified restore output inside the store; that output was
byte-verified and moved outside the store before resuming the same fixture.
No production recovery generation was retired. This is a bounded physical-device
format check, not whole-plan acceptance, throughput prediction or a live schedule.

Evidence lives outside Git at
`/mnt/vk-storage/vk-nightly-efficiency-20261016/`. Fixture readback labels model
the physical B gate and must not be presented as a new real B acceptance. The
incompressible-prefix fixture checks that an append to a history larger than
2 MiB stores less than 8 KiB of new encoded objects/layout while retaining the
entire original and appended versions logically. That is a fixture assertion,
not a production corpus estimate or a transfer-bandwidth measurement. Changed
files still cross the existing capture transport in full.

## Production boundary

Fresh read-only schedule inspection found no enabled VK nightly user timer;
the historical hourly lean-backup cron row is commented out. This observation
does not establish the absence of external producers. No schedule is installed,
backup source retired, production plan edited, or service restarted by this work.

Before operational adoption, require the exact current source/config/runtime
package, authoritative complete scope, approved continuously covering journal
binding or full reconciliation, measured B replacement overlap and free-space
reserve, and a real whole-plan independent physical restore/readback. Respect
current destination health/stop controls. Full corpus restore, native agent
continuation, Vibe browsing and real Desktop/Windows readback of this new format
are not certified by tiny fixtures. The local source-validation work does not
consume another owner's cleanup/release authority or replace required human QA.

See `scripts/deployment/VK_NIGHTLY_RESTART_CONTRACT.md`,
`scripts/deployment/VK_BACKUP_CONTENT_AUDIT.md` and
`scripts/deployment/VK_HISTORY_ARCHIVAL_CONTRACT.md` for the detailed contracts.
