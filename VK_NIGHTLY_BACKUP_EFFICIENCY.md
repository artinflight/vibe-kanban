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

## October17 current B lower bound — 13:03UTC

SSD free9,161,347,072bytes meets8GiB individual planning headroom; full scratch
peak remains unmeasured. Fresh capture admission fails at B6,173,691,904bytes,
below unchanged6GiB floor. No heavy phase was started; Staging remains idle in
its latest completed reply and has the available window while capacity is blocked.

A bounded0.294s read-only BEGIN/schema/page-count audit covers all108 known
databases, missing0/errors0: snapshot spans5,216,837,632bytes, largest2,298,052,608.
This does not discover new databases or establish a coherent full backup. With
T26's protected8GiB B retention floor, Nightly's unchanged2GiB+1MiB metadata
allowance and245-byte descriptor, the known-input lower bound is15,955,304,693
free bytes,9,781,612,789more than observed. Even using only the configured6GiB
floor gives7,634,129,141bytes short. Neither figure includes compressed archive,
generation objects, proof/growth or full restore. Disk Space receives exact
timestamped evidence through its existing private coordination; no source,
recovery or retained offload originals are removed. Existing acceptance fixtures
are reused. Full production fit/restore, deployment and schedule remain pending.

## Historical result collection and storage blocker — 12:25UTC

R3 ended10:50:10UTC, guard_aborted after466s: consecutive samples counted8
coding entries against maximum7. Only245-byte descriptor sealed, no SQLite
payload or full capacity result. Staging released the window10:43:39UTC;
its12:04 readiness still has private build/acceptance pending and no heavy phase.

Current lane count3 passes, but Sidebar activation11:39 changed the frontend
and Dot-current target. A derived plan adds both canonical current release roots
while preserving all old roots/exclusions;94 declared roots,2120 owner-manifest
files verified and4109 runtime files pinned. Source/runtime/health validation
passes; the sealed92-root census, old plans/packages and main packet remain.

R4 briefly started12:24:16UTC then was stopped12:24:58UTC before meter/capture
creation after SSD free was found below1GiB (942,870,528bytes). Full temporary
index/ledger allocation is unverified; all old data remain. No heavy retry or
restore is queued. Restoring previous8GiB working headroom needs7,647,064,064
additional bytes; this is a planning allowance, not a measured minimum. Current
B free15,338,422,272bytes is not proof of backup/restore fit. Coordinate safe
working capacity with the storage owner, then fresh admission and Staging window.
R3 terminal and r4 binding/storage receipts are retained; no completed fixture
work needs repeating. Production deployment and schedule remain unverified.

## Historical corrected r3 launch — 10:42UTC

The10:09:40–10:39:40UTC hold elapsed. Staging's running turn received active
window coordination (HTTP200/empty, no new execution); no explicit release ack
was received. No heavy host compiler/acceptance phase was observed, original
admission passed, and all39 package files/eight historical hashes revalidated.
The single detached r3 measurement started10:42:25UTC, PID3690479/start33804395,
unitvk-nightly-capacity-r3-receipts.service, bounded4h with unchanged guards.
B free27,876,061,184bytes. Existing index/WAL/two-copy evidence is reused and
all old inputs are preserved. Current receipts live under capacity-r3-receipts;
no physical restore, operational deployment or schedule activation is claimed.
Collect this exact job's terminal/capacity/failure evidence rather than replacing
it. Private build acceptance remains Staging-owned and pending in its live update.

## Historical packaging correction and Staging hold — 10:09UTC

R2 ended07:04:41UTC, exit1/233s before payload capture: the derived package
omitted receipts/direct-stream-20261008.json. No full capacity result exists.
A new r3 package recursively includes the original verified receipt directory;
all8 historical source hashes and26 targeted capacity/adapter tests pass.
Capacity main now checks that provenance before opening B jobs/watchers.
The failed package and all previous recovery data remain preserved.

Staging requested the heavy-work window and leads release completion. Nightly
holds capacity/restore launches10:09:40–10:39:40UTC unless released earlier.
No Nightly heavy unit is running and r3 is prepared, unlaunched, with no timer.
Recheck current Staging state and fresh resource admission before launch. The
operator's separate~246-credit ceiling remains distinct from included weekly0%.
PR264 public checks are green per Staging; private candidate/rollback acceptance
remains Staging-owned. No production switch, deployment or schedule is claimed.

## Historical corrected background capacity continuation — 07:00UTC

After the two passing source copies, the user authorized a complete corrected
capacity check and requested no agent turn wait on a long measurement. The
single detached unitvk-nightly-capacity-r2-45a7799cf.service started07:00:49UTC,
measurementPID1455995/start32474761. The original four-hour supervisor and
resource/health guards remain. B30,246,600,704bytes and SSD8,601,911,296bytes
were available at admission. No Staging compiler/nightly overlap was observed.

Current package/profile, census, scale lifecycle and WAL/fixture evidence are
reused. Prior incomplete images have no completed manifest/source binding, so
fresh consistent inputs are required; all old captures and probe images remain
preserved. The stream counts/discards archive/object payload rather than
publishing an operational backup. No physical restore or activation is queued.

Private capacity-r2-45a7799cf receipts include durable terminal/result or original
failure diagnostics and a successful-stream space assessment. The assessment
includes rounded transient inputs/archive, unique object allocation, fixed
metadata reserve, preserved floor and restore payload. Proof/filesystem/growth
allocation is explicitly incomplete, so it does not certify fit or restoration.
Collect this existing run's result rather than starting another measurement;
HANDOFF.md gives exact names and the next acceptance step.

## October17 bounded affected-source copy — complete

The corrected diagnostic package, derived from sealed6bfd27244 with the two
45a7799cf source corrections and refreshed exact source pins, completed the
authorized single-source probe06:54:36.034402–06:56:10.523929UTC. PID1395618,
start32437411, exit0; no replacement production measurement was launched.
Two independent registered B SQLite images each contain32,395,264bytes and
pass native Windows full hash/integrity verification. Both SHA256 values are
`bef198d1c0b41361d97d2f76fde67cdc2545559e7db5565e4d4c315a3ef6402f`.
Per-copy times14.859s and13.351s; adapter38.501s, supervised phase95.555s.
The source's data identity/mtime matches across both copies. This demonstrates
two successful captures of the inferred source, not universal reliability or
whole-plan acceptance. The original producer failure did not reproduce; its
exact cause cannot be established from the discarded exception.

The six-minute supervisor bound,90s per-copy deadline, CPU25%,High2G/Max3G,
Swap0,Tasks32 and original host/B/live-health admission were retained. All9
samples pass, unit peak482.5MiB with no swap. Source/runtime bindings validate;
no Staging compiler unit was observed. The owned mount was reaped at completion.
Native read-only inspection confirms all31 original seals still have their
registered lengths, the original unsealed input remains empty and no current
pointer exists. Both new images are retained in their separate fresh B root.

Receipts:single-source-45a7799cf/{phase.safe.json,terminal.safe.json,
supervisor.private.json,original-input-preservation.safe.json,
result/registered-adapter.private.json} under the existing private evidence root.
No further source/transport change is supported by these passing trials. A later
full measurement must retain corrected producer diagnostics and original guards;
total cold space, whole-plan restore, deployment and schedule remain unverified.

## October17 producer failure diagnosis

The original capacity run exited1 at04:36:15UTC, after6,934s, rather than timing
out. Its original producer exception was lost: the meter raised a missing
manifest at EOF before checking the producer thread's errors. This proves an
error-reporting defect, not the original SQLite/transport failure's cause.

Read-only native B inspection confirms the retained unsealed d801ab35 input is
zero bytes. Creation order and sealed image sizes align with the first30 sorted
census databases. The next candidate is the historical July14T161515Z
ui-pref-critical-restore snapshot (32,395,264bytes); its current source schema,
page count and read-only integrity_check pass (1.23s). No content was copied,
no old input changed, and no new production measurement started. The30 sealed
SQLite images total4,024,520,704bytes; reuse their prior independent verification.

The minimal correction raises the original producer error before secondary TAR
or compressor errors, saves its private traceback and attached SQLite diagnostic,
and attaches source/stage diagnostics to bounds/timeouts as well as SQLite errors.
Regression tests cover missing/truncated manifests and independent parser errors;
the successful full-stream counting fixture is retained. A private failure
receipt never constitutes a successful measurement or backup.

Validation:26 capacity/adapter tests pass, including real compression/counting
and committed-WAL snapshot fixtures; ops and diff checks pass. Rust formatting
passes; the repository format command stops because Prettier is unavailable.

Next action: a bounded single-source registered-B snapshot probe of the inferred
candidate with corrected diagnostics, leaving old inputs untouched. Current
evidence cannot guarantee the next complete measurement will succeed. Full cold
space, whole-plan restore, operational adoption and schedule remain pending.

## October17 recovered lifecycle and integration follow-up — 02:40 UTC

Recovery-r2 finished successfully02:35:55.957881UTC after335.324s, from
02:30:20.200095UTC. PythonPID2991720/start30851828 is quiescent. It loaded and
independently verified all1,219,860 saved candidate rows at SHA256
`a17e5cf1dc3c7e52233897fb689a311a2bdd5a4cd6a5e8251ef1b42a3f9a921c`,
retired only its recorded synthetic predecessor and cleared the attempt.
The current candidate remains. This completes the retained synthetic lifecycle;
the initial1800s timeout remains recorded separately. Peak cgroup memory was
2,147,745,792bytes; high983, hardmax/OOM0, cumulative stalls0.136s. Source pins
for all five index handlers are unchanged. No production/B recovery changed.

WAL fixture follow-up preserves and publishes the exact two sidecars at551e24c49.
Prior in-memory reconstruction passed SQLite integrity and the expected single
synthetic text row. Their hashes match committed bytes. Existing actual two-copy
MCP-to-B receipts remain valid; no completed transport test is repeated.

The owned private journal now drains during watch enrollment, inventory, SQLite
copying and streaming, rather than waiting for capture checkpoints. Reader errors
invalidate coverage, and shutdown joins the thread before capture completion.
External readers remain untouched; the original START sequence/instance/scope
and restart lease/fresh-SQLite/writer-fence requirements are unchanged. This
prevents a long quiet-report interval from filling the finite kernel queue.

Current Dot1.5 adapter/stop_control/credit_budget dependencies are covered by the
existing connector source root. Observed adapter78ad962b, stop_control13c8eff8
and credit_budgetd8619d20 hashes match the owner-confirmed small Dot1.5 addendum;
the old1.4 chat hash was superseded. The derived measurement profile d0434347
binds all1974runtime files. No new census, source exclusion, sealed main packet
edit or Staging adoption claim is needed for this binding update.

The counted/discarded full production stream started02:40:41UTC. Measurement
PythonPID3107838/start30914068, supervisor3107804/start30913909, own unit
vk-nightly-capacity-6bfd27244.service; four-hour supervisor and existing resource
limits. Its immutable source package6bfd27244 remains unchanged while the PR
is normally refreshed with the merged PR262 shared consumer atc0ac5d081. The
source refresh passes ops/diff and all hosted checks atc0ac5d081, including
backend tests, frontend checks, branch freshness and isolated recovery.
No archive/object payload is retained and no publication receipt is issued.

Fresh02:31 capacity admission validates the frozen runtime/profile and unchanged
B identity, SMART/attribute/PHY counters. B free34,347,749,376bytes; SSD free
8,356,765,696bytes. Full counted-stream evidence remains pending. No operational
nightly deployment or schedule activation is claimed from synthetic acceptance.

## Historical phase evidence — 02:10 UTC

The original fixed30-minute index command ended02:05:38, exit124. Both synthetic
1,219,860-row generations passed publication readback, but final lifecycle
recovery/retirement was unfinished. The last cgroup snapshot records a2.000GiB
peak, zero hard-limit/OOM events and1.877s cumulative memory stalls over the
whole30-minute phase. This demonstrates the bounded index path reached both
publications, not a complete two-generation lifecycle pass. Both generations
and the recorded attempt remain intact. No production/B payload was involved.

A separate600s reconciliation using the exact unchanged source started02:08:36
and was stopped02:09:50 when Staging announced r5. It had zero memory stalls or
limit events. Finish that recorded recovery after Staging's compiler/acceptance
window; do not repeat construction of both large tables. The counted/discarded
production stream remains unstarted and is bounded to four hours with the
existing supervisor. No production restore window or cron activation is armed.

The exact registered-input adapter also passed two actual MCP-to-B copies from
a tiny committed-WAL source. Normal SQLite backup API, resident registration,
SSHFS transfer and native Windows full hash/integrity all pass; separate native
queries recover both expected WAL values. Runtime13.99s. Diagnostic admission
now includes the real metadata allowance and preserved B floor, with explicit
512MiB input and450s initial timeout caps. All diagnostic files on B remain.
This tests the actual transport, not the production plan.

The previously skipped disposable service timeout passed separately in2.483s,
including forced termination after its finite grace. All392 local deployment
cases therefore have passing evidence across the main run and this opt-in run.
Hosted checks pass at3c422d808. Full production capacity, restore, deployment
and schedule remain pending; source publication is not operational adoption.

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
OOM; it is not acceptance evidence. The bounded streaming replacement reached both publications in index-scale-4;
its remaining reconciliation is paused for Staging r5, as recorded above.
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
