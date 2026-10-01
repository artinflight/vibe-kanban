# Faster Pre-Cutover Preparation

## Operator Outcome

Read `VK_PREPARATION_PRODUCTION_AUDIT_20261001.md` for the first full-scale
measurement: 86m39s initial preparation, not 19.37s. Fixture timings below are
not a whole-production preparation estimate.

Preparation time counts from the start of the operator's deployment request,
not from the moment production is paused. Keep production usable while preparing.
Report preparation, the interruption, and post-switch acceptance separately.
The September 30 switch took 39.173 seconds, but that does not account for the
roughly hour-long preparation the operator experienced.

The tools in `scripts/deployment/` reduce repeated work without changing the
established ownership handover or latest-data rollback. They run outside VK and
do not need a backend restart. They do not authorize or perform a cutover.

## What Was Inefficient

- A fixed September 11 backup cutoff made each refresh copy cumulative changes
  rather than changes since the most recent verified checkpoint.
- The September 30 online backup was 5.116 GB and took about 292 seconds. It was
  already over two hours old at the final switch.
- The final boundary copied 13 entire SQLite databases, about 1.17 GB before
  compression. Baseline verification and broad static checks were repeated.
- Preparation used copied, dated tools and serial queue requests for every chat.
- The shared Cargo cache and source-tree-equivalent validation reuse already
  existed; those are not newly implemented improvements.

Evidence: `/mnt/vk-storage/vk-green-refresh-20260930/PROGRESS.md` and
`cutover-20260930T203427Z/status.json` in that task directory.

## Versioned Preparation Runner

Use a clean, isolated checkout of the candidate and the checked-in
`scripts/deployment/vk_prepare.py`, not a consumed historical cutover directory.
Start its durable clock before checkout, build, backup, or validation work:

```bash
python3 scripts/deployment/vk_prepare.py start --root /mnt/vk-storage/vk-next-preparation
python3 scripts/deployment/vk_prepare.py init \
  --source /absolute/clean/candidate --root /mnt/vk-storage/vk-next-preparation \
  --deployed VERIFIED_DEPLOYED_COMMIT
python3 scripts/deployment/vk_prepare.py run \
  --source /absolute/clean/candidate --root /mnt/vk-storage/vk-next-preparation \
  --plan /mnt/vk-storage/vk-next-preparation/plan.json
```

Review the generated private plan against the release. Its commands are trusted
deployment inputs, not sandboxed instructions: no production writes, service
actions, or release-specific functional tests belong in a cacheable step.
Review build environment overrides and dependency availability before starting.
The runner checks declared tool prerequisites before expensive work and records
logs, per-step durations, cache hits, total runner time, and elapsed preparation
time. A failed prerequisite or check is not a readiness pass.

The default local recipe handles docs/preparation-only changes without a server
build. Frontend-only changes do not require a backend cutover. Unknown/shared
changes conservatively require backend preparation. Backend preparation uses
the shared SSD Cargo cache, a frontend build, server and release-matched guard,
and non-Tauri workspace tests. It records its Tauri/remote validation exclusions;
it does not pretend those suites passed. Add remote checks when relevant.
Do not repeatedly run a known failing GTK aggregate suite and then silently
fall back: record that limitation and the actual applicable checks.

### Reuse Only Unchanged Evidence

`/mnt/vk-storage/vk-preparation-cache` holds successful static evidence and
independent copies of artifacts. Source inputs, commands, environment, declared
tool executable/version, helpers, context files, and dependency outputs bind each
entry. Absent ignored configuration files are included in the identity, so adding
one invalidates reuse. Failed checks, dirty source, changed inputs, missing logs,
and changed/missing artifacts require a fresh check. Input changes during a check
also prevent publication of its evidence.

Package release binaries and frontend from `artifact_roots` in the successful
report, not whatever currently occupies a shared Cargo output path. Artifact
copies are checked before reuse and against changes during copying. Materialized
frontend output is confined to the isolated candidate; no live pointer changes.
Source-tree-equivalent promotion can reuse evidence under the same reviewed
recipe and context. A changed checkout path may conservatively invalidate it.
The cache is not an excuse to rerun no checks on a different release identity.

Active executions, queues, ownership, current settings, capacity, journal health,
backup receipts, and the authoritative data boundary are volatile. Never cache
those as permission to switch. The existing model-availability rule remains:
refresh only the bounded seven-model proof when older than 24 hours or when the
exact launcher/account/Codex home differs. Do not repeat the whole V1 acceptance
suite for an unchanged, valid identity.

## Rolling Online Backups

Nested deletion under a continuously watched parent now preserves tombstones.
Exclusion paths resolve once per capture and are checked before publication.
Declare `online_ephemeral_roots` only for known disposable CLI scratch, never
history or work. Tar warnings require journal evidence; unrelated missing files
and every frozen-boundary warning remain failures.

Use `vk_bulk_job.py` for bulky captures/restores outside the Codex memory cgroup.
It defaults to4G/6G memory-high/max and reduced CPU/IO priority; review host
capacity for the job. Production service and agent limits are unchanged. A
direct Desktop address requires both `--desktop-hostname` and the verified
existing `--desktop-host-key-alias`; shared SSH aliases remain unchanged. SFTP
resumes uniquely named partial archives and checks full remote SHA256. Unexpected
sizes or hashes remain failures.

After an online delivery failure, `resume-delivery` accepts the original
`--folder`, plan, root, socket, parent if applicable, and Desktop directory.
It requires the unchanged archive/payload and continuous coverage. It does not
recapture data or certify a frozen boundary. Later writes stay due for another
delta. Keep verified parent chains and applicable restore evidence across turns.
New archives place manifests first to avoid a second full discovery pass; full
recovery validation and legacy archive support remain.

`vk_change_journal.py` and `vk_rolling_backup.py` provide a new, versioned online
checkpoint/delta format. The explicit private plan lists source directories in
`sources`, required
`sqlite_snapshots`, optional `critical_sqlite`, and
`excluded_rebuildable_directories`. Reconcile every source against the actual
production paths, including symlink targets, native histories/indexes, profiles,
messages, goals, attachments, worktrees, dirty/untracked files and Git metadata.
Do not exclude irreplaceable data to make a backup smaller.

Start the read-only watcher independently of VK, with its socket on mounted SSD:

```bash
python3 scripts/deployment/vk_change_journal.py \
  --plan /mnt/vk-storage/vk-next-preparation/backup-plan.json \
  --socket /mnt/vk-storage/vk-next-preparation/journal.sock
```

Once coverage is ready, capture an online checkpoint while production stays live:

```bash
python3 scripts/deployment/vk_rolling_backup.py capture \
  --plan /mnt/vk-storage/vk-next-preparation/backup-plan.json \
  --root /mnt/vk-storage/vk-next-backups \
  --socket /mnt/vk-storage/vk-next-preparation/journal.sock \
  --desktop-directory B:/vk-backups/vk-next-preparation
```

Subsequent captures add
`--parent /mnt/vk-storage/vk-next-backups/latest-result.json`. A child contains
only journal changes since that verified parent. Unchanged SQLite snapshots are
reused only with continuous journal coverage and matching database/WAL generation
evidence. Changed databases still receive full consistent SQLite backups; this
does not implement page-delta SQLite recovery. Writes during capture remain due
for the next child. Missing sources, overflow, replaced watchers, moved watched
directories, changed plans, and unverified parents stop incremental capture.
Reconcile the problem and make a new online checkpoint rather than guessing.

Archives and uniquely named recovery metadata are sent to Desktop and SHA256
verified before advancing `latest-result.json`. A delivery failure leaves the
last verified checkpoint authoritative. Retain the entire required parent chain;
there is no automatic pruning. Directory/file modes and links are preserved.
Restore verification materializes internal hardlinks but records symlinks as
metadata instead of allowing a restored tree to write into production.

Verify the whole chain in a new directory within the isolated backup task:

```bash
python3 scripts/deployment/vk_rolling_backup.py verify-restore \
  --result /mnt/vk-storage/vk-next-backups/latest-result.json \
  --destination /mnt/vk-storage/vk-next-backups/isolated-restore
```

For Desktop recovery, fetch the named result metadata and all parent archives
into SSD staging, then pass `--archive-directory` pointing to those copies.
Keep the isolated restore destination under the task root recorded in the
result; it cannot be an existing directory or any production path. The fixtures
exercise this off-machine round trip. Production recovery remains governed by
the restart protocol: never put an old backup over current production data.

### Final Capture Integration

An online checkpoint is not a quiescent production boundary. The Python
`capture()` API now accepts a `verify_fence` callback from the approving
controller. This mode requires a verified parent and Desktop metadata delivery.
The callback must verify the paused original process and its identity, ownership
release, stopped candidate, and every other writer identified by preflight; it
returns a stable receipt containing `verified: true`. Missing or changed fencing,
actual file writes, changed SQLite generations, archive warnings, lost journal
coverage, or failed delivery reject the boundary and leave the previous verified
backup current. The callback is checked before capture and after archive and
metadata delivery. The CLI does not offer a flag that fabricates this receipt.
Desktop metadata is a restore descriptor, explicitly pending handover acceptance;
only the successful local result certifies the post-delivery fence check. Do not
use an uploaded descriptor from an aborted attempt as a cutover readiness record.

Use the result's `frozen_boundary_verified` and verified delivery receipts in the
existing ownership handover boundary callback. `cutover_authorized` remains false:
the independent controller owns approval, execution, routing, and latest-data
recovery. The capture library does not start, stop, freeze, or route any service.
Consumed historical controllers and their production configuration remain retired;
the next package still needs release-specific inventory and rehearsal.

The October 1 integration uses the existing September 30 ownership primitives
unchanged with real VK binaries, two private filesystem-isolated units, private
routes, and actual Desktop transfer. It proves failed-backup return, successful
handover, same-process cutback preserving subsequent saved-message/settings/model
changes, repeated recovery, and restoration of the checkpoint plus final delta.
The final private switch measured 15.03 seconds, including 14.84 seconds for capture and
fencing; this small fixture does not predict production timing or exercise CU
polling/native inference. All private units were stopped and removed afterward.
Evidence: `/mnt/vk-storage/vk-preparation-20261001/integration/`
`handover-628d03d9d47446efb5295f4d117bc55a/result.json`. This final run binds the
tool hashes and restores from archives and metadata downloaded back from Desktop.

The rehearsal caught SQLite `CLOSE_WRITE` events without content/generation
changes. The journal now retains event types per checkpoint boundary; a close-only
event for a known DB/WAL is accepted only with unchanged file generations and
logical SQLite version where open. Actual writes, missing event-type evidence,
and unexplained changes still reject the boundary. This also avoids recopying an
unchanged database just because a prior reader closed a writable WAL descriptor.
Required databases in `critical_sqlite` cannot silently disappear between captures.

Reproduce with `scripts/deployment/rehearse_vk_backup_boundary.py`, supplying a
new SSD `--root`, the reviewed `--handover-directory`, immutable `--release`, and
private Desktop `--desktop-directory`. The harness checks filesystem isolation,
restricts service actions to its own unique units, and records artifact hashes.
It has no production-cutover entrypoint. Review a different controller's callback
contract before substituting it.

## Faster Fresh Queue Checks

The runner's `queues` action checks every session through the existing direct
loopback API using eight bounded concurrent GET requests, rather than serial
requests. Responses are all checked; one failed or unknown response fails the
inventory. It creates no tasks and consumes no queued work.

```bash
python3 scripts/deployment/vk_prepare.py queues \
  --origin http://127.0.0.1:CURRENT_BACKEND_PORT \
  --database /absolute/authoritative/db.v2.sqlite \
  --out /mnt/vk-storage/vk-next-preparation/fresh-queues.json
```

## Validation And Timing Limits

The regression suite uses real Git, SQLite, tar/zstd, Linux file-change watches,
and private HTTP fixtures. It covers cache invalidation, interrupted coverage,
online writes, failed delivery, corrupted ancestors, and protected-data restore.
All 54 tests passed after final-boundary integration, including late writes
during archive/metadata delivery, changed writer identity, critical DB removal,
and close-only WAL events. Syntax checks, formatting, Ops and diff checks passed.
Application source and build inputs match staging620bd7eb9 exactly, so the broader
Rust/frontend suites were not rerun for these Python deployment tools; their
existing GTK aggregate limitation remains recorded, not represented as passing.
Run it with SSD `TMPDIR`:

```bash
TMPDIR=/mnt/vk-storage/vk-next-preparation PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s scripts/deployment -p 'test_vk_*.py'
```

`benchmark_vk_preparation.py` provides a bounded 17 MiB fixture benchmark and
real Desktop backup/download/full-chain restore, not a production SLA. Results
live outside the repo at `/mnt/vk-storage/vk-preparation-20261001/`.
The successful fixture record is
`benchmark/fixture-d1d382e1d25b49b8af1742f63379480a/benchmark.json` in that root.
Its checkpoint was 17,828,870 bytes (24.54 seconds including Desktop verification).
The two-file catch-up was 789 bytes (13.38 seconds) with zero SQLite snapshots
copied. A subsequent database update copied a 1,051,573-byte delta (12.97 seconds).
Downloading all three archives and metadata from Desktop and restoring the full
chain passed in 34.05 seconds, preserving fixture settings, original-thread
history, dirty work and attachment bytes/mode. Desktop SSH/verification overhead
dominates tiny deltas; byte savings are not equivalent to wall-clock savings.
The first fixture attempt encountered a transient Desktop SSH execution failure;
it did not advance the verified parent after the failed metadata delivery. The
fresh bounded rerun above passed. No production backup or restore was performed.
The live read-only queue comparison covered 1,035 sessions: serial 0.844 seconds,
concurrent 0.456 seconds, with matching results. That modest saving alone does
not explain or fix the hour of preparation. Evidence reuse and smaller online
refreshes address the substantial repeated work. No complete next production
preparation or cutover has been timed with these new tools yet.

The generated preparation-only recipe was executed twice at implementation
commit `e1bf06f7b`: first run 12.24 seconds, repeat 1.46 seconds. The repeat verified
and reused the Python regression/ops evidence, while its uncached diff check ran
again. Reports are under `runner-acceptance/` in the evidence root. The durable
elapsed preparation clock kept running rather than resetting to the short repeat
duration. This measures that recipe, not a cold Rust build or full deployment.
