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

## October17 index-scale and capacity follow-up

The sealed census has 1,219,860 paths. The nightly producer now has an explicit
1,500,000-entry / 512 MiB index bound, leaving the historical candidate provider
at 256 MiB. Encoding hashes canonical blocks without a whole-index Unicode copy.
Windows/POSIX readback loads entry rows through a bounded reader and shares only
the fixed schema vocabulary. The complete authenticated table is reused within
a producer, rather than deeply copied. Baseline transfer, hashing and loading
also stream; its actual input bytes reduce the remaining capture budget.

The shared B allocation reserves four bounded metadata files plus 1 MiB: the
candidate manifest, object ledger, old job record and atomic replacement. The
registered proof/baseline are charged as capture inputs. Actual sealed input and
new object sizes share the remaining allocation while preserving the 6 GiB floor.
The old 98.25 GiB envelope was not a measured minimum; summing independent hard
ceilings does not establish what the current cold backup actually needs.

`vk_nightly_capacity.py` measures a full real production tar stream without
retaining its archive or object payload. It uses ordinary registered consistent
B SQLite snapshots and the normal source/journal/tar paths. SSD SQLite counts
exact compressed stream bytes, deduplicated chunk/layout encoded sizes and
cluster-rounded object costs, plus full-tree regular-file allocation with
hardlinks represented once. Filesystem metadata and growth remain explicit
additional costs. This tool intentionally issues no backup publication receipt.
Its small independent fixture matches an actual chunk store and whole-stream
zstd output. Production measurement is still pending.

Current regression evidence: 392 deployment tests, 391 passing and one explicit
opt-in skip. Ops governance, Python syntax and diff checks pass. Rust formatting
passes; aggregate formatting stops at missing Prettier. No new Rust compile is
started alongside Staging. The previous large synthetic attempt was stopped at
01:25:57 after its whole-file reload hit the unchanged 2 GiB soft limit, without
OOM; it is not acceptance evidence. The bounded streaming replacement awaits
Staging's final compiler window before its next two-generation rehearsal.
No production capture, restore, activation or cron installation is claimed.

B coordination confirms all 34 reviewed originals remain intact and deletion is
unapproved. Their allocated 172,649,721,856 bytes are potential capacity only.
The latest observed B free space is 35,676,405,760 bytes; NTFS allocation unit is
4,096 bytes. Fresh checks must precede any actual production run. All 18 Staging
original finals and the invalid old journal evidence remain preserved.

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

Current integration validation: 359 tests ran, 358 passed and the opt-in
disposable user-service timeout test was skipped. All eight historical
direct-stream source pins still match; Python syntax, `git diff --check` and
`pnpm run ops:check` pass. `pnpm run format` ran successfully through both Rust
workspaces, then stopped because this worktree has no Prettier executable.
Frontend type/lint checks and full Rust tests were not exercised by this
Python-only integration validation. The separate physical B evidence follows.

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
all four fixture files succeeds with the preceding fixture generation absent.
The 2,097,204-byte synthetic history adds 1,331 stored bytes. A second fresh
physical fixture also injects an interruption after a real chunk link, reconciles
that exact owned job, publishes a replacement and restores all four files again
(the final complete history is 2,097,230 bytes). The fixture provider is explicitly
synthetic; this does not exercise the whole production capture provider. Its first failed
harness run placed verified restore output inside the store; that output was
byte-verified and moved outside the store before resuming the same fixture.
No production recovery generation was retired. This is a bounded physical-device
format check, not whole-plan acceptance, throughput prediction or a live schedule.

Evidence lives outside Git at
`/mnt/vk-storage/vk-nightly-efficiency-20261016/` and
`/mnt/vk-storage/vk-nightly-efficiency-20261017/`. Earlier modeled readback
labels remain distinct from the October17 physical B fixture receipts. The
incompressible-prefix fixture checks that an append to a history larger than
2 MiB stores less than 8 KiB of new encoded objects/layout while retaining the
entire original and appended versions logically. That is a fixture assertion,
not a production corpus estimate or a transfer-bandwidth measurement. Changed
files still cross the existing capture transport in full.

## October 17 production admission result

The read-only census completed in 942.5 seconds under 25% CPU, 1 GiB RAM and
idle-I/O limits: 92 roots, 1,219,860 paths, 1,090,388 files and 156,501,564,345
logical bytes. It found 108 SQLite databases (5,135,511,552 bytes), including all
72 declared databases, with no vanished members. Inventory SHA256:
`e026c85cac5d22cb6109b8738a9565f4b9a268d1ec084ec8afc74c92bcda0016`.
This is a complete online metadata census, not a coherent application backup.

The exact source/config package is staged, disabled, outside the worktree. Its
current backend and 1,971 immutable runtime/frontend files were hash-verified;
the gateway frontend matches the selected local index. This establishes package
and runtime binding, not production backup adoption. Full-plan admission fails:
the file count exceeds the existing 1,000,000 generation-entry limit, and B has
36.2 GiB free against the configured 98.25 GiB cold reservation. The reservation
is not a measured minimum; lowering it requires guarded whole-plan evidence.
No source was omitted to force these checks through.

No heavy restore window is admitted, running or queued. The census exited zero;
Staging received its exact seal/hash and can sequence its guarded build. The
private shared packet is `PRODUCTION_NIGHTLY_HANDOFF.private.json` under the
October 17 evidence directory. Address index scale within bounded resources and
B capacity before complete capture/independent restoration and activation of
the single 02:00 Toronto schedule. No production generation, schedule or backend
change is claimed.

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
