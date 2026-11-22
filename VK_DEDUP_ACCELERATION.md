# Dedup acceleration — deployed November22,2026

The user authorized faster fresh checks, bounded temporary-copy cleanup and
parallel preparation on MCP/Desktop/Laptop. Preserve the existing finite operation,
all original/backup data, per-file locks and real restoration; no Vibe restart,
model-worker delegation, new goal or continuation loop. Current native goal is paused.
The accelerated converter is running; its first complete production batch passed.

Operation: online-20261119-v1 under the efficiency-20261118 production evidence.
Current recovery1 PID2054584 / invocation221dd13e67f04147a3113740f9267240.
Current controls: checkpoint-controls-20261122-recovery. This supersedes accelerated2
following the Desktop SSH outage; see [recovery evidence](VK_DEDUP_OFFLINE_RECOVERY.md).
Read actual state before any change.
Batch37 has an isolated staging override that must survive all continuations.

## Qualified changes

- `fast_online.py` reads five fresh systemd properties over the existing owned
  D-Bus socket, reuses a read-only SQLite connection with a completed autocommit
  SELECT each time, and checks all current mount entries. It caches no ownership,
  SQL, mount or resource observation. Existing kernel execution locks remain.
- `fast_retirement.py` retains every per-object custody, primary/staging hash,
  inode and exclusive lease check. It flushes affected directories every64
  deletions and before a result. Only this attempt's duplicate staging retires;
  primary data and all B epochs remain. Crash, corruption, open-consumer, lost
  custody and failed-directory-flush tests passed.
- `remote_pack.py`, `remote_dispatch.py`, `remote_preparation.py` and
  `parallel_prepare.py` prepare copied closed history on Desktop and Laptop.
  MCP independently verifies every returned object and complete reconstructed
  source, including exact sidecars/metadata, before using an archive. Remote
  helpers cannot publish live history. Existing primary compressed encodings
  stay authoritative; new objects are charged at their actual compressed sizes.
- One unconsumed job per host, at most512MiB raw per batch, two-batch lookahead,
  existing memory limits and SSD reserve,35GiB remote free-space floor and finite
  3300s remote work deadline. Small batches (<64MiB) remain local. Remote failure
  disables that host and retains its exact dispatch for reconciliation; it never
  automatically replays a remote job or duplicates conversion. Missing/malformed
  returned data cannot bypass import validation. Laptop uses its existing standard
  account and queue, including native successful terminal evidence before cleanup.
- `upgrade_controlled_worker.py` replaces only the finite converter after its
  exact live pause, complete installed checkpoint and released backup descriptors
  are verified. It preserves batch37's isolated mapping. It cannot target a Vibe
  backend. The replacement starts paused; an explicit retained resume is separate.
  Existing watcher configuration changes only its checkpoint-control location.

Qualification:83 focused tests ran,81 passed and2 optional unchanged Rust-probe
cases were skipped. These cover concurrent WAL visibility, source replacement,
reader identity, open consumers, corruption, failed flush/crash, bounded remote
preparation, native queue outcomes and completed-job adoption without dispatch. A real disposable systemd controller acknowledged pause, passed
exact process/cgroup/checkpoint checks, and exited with no surviving controller;
no production/serving unit was targeted. Exact sealed acceleration imports and
fresh production-reader checks passed without conversion or remote dispatch.

Actual complete fresh-owner check median:28.85ms→4.91ms (5.88×),25 samples each.
This is a check benchmark, not a full-batch speed or ETA claim. Previous five-batch
means were1556s total,807s temporary-copy handling,517s backup/recovery and112s
conversion. The first complete production-batch result is recorded below.

Desktop's32MiB synthetic archive reconstructed exactly; compute2.08s,
transfer+compute56.10s, independent MCP import1.83s. Local scan+pack4.26s, so
remote overhead makes small standalone jobs slower. Remote preparation is used
for larger work prepared ahead while conversion continues. Laptop became reachable
and its existing `vibeworker` queue completed the same copied fixture with exit0
and1.38s computation. Python/zlib compressed sizes differed, while every source
identity, sidecar, manifest and reconstructed byte matched; actual sizes are used.
Both hosts' accepted test transfer payloads were retired with exact identity/hash
checks; test sources, imported archives and recovery evidence are retained.

Evidence: `acceleration-20261122` beside the operation, including
FRESH_CHECK_BENCHMARK, REAL_PAUSED_MIGRATION_FIXTURE, RUNTIME_IMPORT_ACCEPTANCE and
Desktop/Laptop qualification receipts. The first Desktop test failed before payload
processing; its exact process exit was reconciled and its evidence retained.
The initial Desktop-only package `checkpoint-controls-20261122-fast` was never
activated. Its SUPERSEDED_UNACTIVATED receipt points to the two-host candidate
`checkpoint-controls-20261122-fast-v2`; both retain the same pending pause UUID.
Do not replay either package's activation or an uncertain remote dispatch.

No finite selection regrouping or increased batch/memory bounds was made. Tests
and preparation do not count as converted history. No provider/model calls, extra
agent, backend restart, Nightly enablement or deferred-cleanup action occurred.
Rust formatting and Ops Playbook checks passed. Required web formatting was
attempted but could not run because this worktree lacks Prettier.

## Production acceptance and current operation

The first two-host attempt activated at01:07UTC November22 after exact clean
pause/lease/installed-checkpoint proof. controlled1 PID1316160 exited; accelerated1
PID3651668 / invocation4980a45bd2d64bfe9e37ebb2f8ef2f24 acknowledged the same
65-batch/264-file checkpoint and resumed once. Its batch65 is fully accepted:
470,157,093 raw bytes,460,996,608 allocated live-log bytes released including
objects/directories,12,622 temporary duplicate objects retired,1154.66s conversion
and recovery. Original B bytes/metadata, the complete selected archive graph,
dynamic recovery records and actual production-reader full EOF all passed.

The preceding similar batch64 processed479,344,883 raw bytes in1907.60s and
recovered440,745,984 allocated bytes. Observed duration fell39.47% (31.8→19.2min).
Both timings exclude subsequent next-batch preparation. Different data and
concurrent qualification I/O limit extrapolation; this is not a complete-backlog
ETA. Remaining small/large batches and final closure still need their normal work.

Laptop completed actual batch68 (484,252,707 bytes) through its standard queue,
exit0,6.23s remote computation. Its returned checksum and native terminal receipt
are retained. Desktop's batch67 raw transfer timed out before any dispatch intent,
script or STARTED receipt; the exact transfer process was gone. No processing was
replayed. Compressed transfer of the exact515MB copied input then passed an actual
remote checksum in160.30s. Only that new test copy was retired; the old partial
copy and failure evidence remain for final task-staging accounting. Copy deadline
is now600s, with no automatic retries. First-attempt batch67 will prepare locally.

Completed copied transfers were also causing page-cache pressure inside the
unchanged converter limit. fsync followed by POSIX_FADV_DONTNEED on only those
exact completed input/output copies reduced observed cgroup memory by472,678,400
bytes while preserving each file's identity/size/timestamps. The final transport
adapter performs that cache release after transfer/hash verification. It does
not clear global caches, alter data or increase selected resource limits.

After full batch65 commitment and next-batch preparation, accelerated1 acknowledged
pause at66 batches/270 logs. The final immutable package
`checkpoint-controls-20261122-fast-v4` activated accelerated2, PID3918687 /
invocation0afe61e507a94b1195f3b8dd55e36951, and retained resume request
0d8c2908-7298-4069-8cd9-a406d6af2f3c continued batch66. Completed Laptop batch68
was adopted by exact pinned receipts without another dispatch; Desktop prepares
batch69. All serving identities and selected limits are unchanged. Unactivated
packages fast and fast-v3 have SUPERSEDED_UNACTIVATED receipts; never launch them.

Current package evidence: PREPARATION, VALIDATION, PAUSED_BOUNDARY, HANDOFF,
CONTROLLER_SEAL, ACTIVE, RESUME_INTENT, RESUME_RECEIPT and LIVE_ACCEPTANCE. The
prior fast-v2 package retains the real Desktop transfer, page-cache and Laptop
receipts. The exact sealed acceleration imports passed60 full reader checks over
3 concurrent threads. Native terminal, malformed result, replay and adoption
checks passed; actual MCP import remains mandatory for every prepared batch.

Existing WakeWatch changed only its checkpoint_controls path and observed
accelerated2 through the normal timer, no source error,8 delivered events/8
attempts preserved. Public status returned HTTP200. No new watcher, synthetic
wake, provider turn, backend restart or Nightly enablement occurred. The same
Rainmeter feed continues. On any later issue reconcile both the finite batch and
exact remote receipts; never rerun consumed attempts. A pause can retain remote
preparation, so check cgroup children and terminal receipts before a future upgrade.

Full selected conversion, remaining eligible-log inventory, complete archive-tree
and current-SQL/software/frontend restoration, ordinary UI/monitoring acceptance
and net filesystem/growth accounting remain. Existing per-batch restoration does
not by itself close that full objective. Deferred workspace/archive cleanup stays
separate; no original or immutable backup epoch was retired here.

## Workspace archiving correction

November22 read-only SQL found616 remaining selected logs /7,940,309,364 bytes in
62 workspaces currently marked archived (72 selected batches). The original frozen
inventory excluded80 logs in already-archived workspaces and5 in completed ones;
later archival flags do not alter the selection. OP::Archive completed work is
workspace329e500e-ee5f-43d5-8160-ac5169bbc9ba; its stated task is review→Done→archive
across repos, not cold-history relocation. Read its current artifacts before any
coordination decision. No new messages or alterations to that task are authorized
by this assessment. Deferred archive cleanup remains separate; don't silently skip
selected history or assume status archival proves a recoverable backup.
