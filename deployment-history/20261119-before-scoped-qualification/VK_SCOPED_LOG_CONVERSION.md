# Scoped conversion of closed execution logs

Status: implementation and qualification in progress, 18 November 2026. This is
an unreleased alternative to the global maintenance converter. The current
production backend does not advertise the required writer protocol; online
admission must refuse it. No production conversion or interruption is claimed.
The operator authorized resolving this blocker and deferred service interruption
until the evening. That authorization persists; do not ask for it again.

## Scope and writer contract

Active workspaces retain their identities, native transcripts, complete visible
history, current executions, queued/pending inputs, pins and settings. Convert
only exact closed execution logs, not entire workspaces. Read-only inventory found
82,424,827,904 allocated bytes across 2,223 closed terminal-execution logs in active
In Progress workspaces. This is input volume, not a savings forecast. Unknown and
pending captures remain excluded, including the invalid OP::Disk Space sidecar.

`utils::log_mutation` protocol 1 uses a permanent sibling
`<execution-uuid>.mutation.lock`. Writers and the converter acquire the same
exclusive OS lock. Never unlink or replace that lock, including on interruption:
a second inode would create an independent lock domain. Locks are execution-local;
other execution IDs in the same session remain writable. Existing readers keep
reading their original descriptors across atomic replacement; new readers use the
existing archive-aware decoder and the already published immutable objects.

Covered application mutation paths:

- Ordinary/raw capture and error-message append hold the lock from before the
  archive check until the data descriptor is released. Waiting is asynchronous
  and cancellation leaves no background acquisition task. Any reopened raw log
  invalidates an old closed sidecar before appending.
- Legacy SQL-log migration takes the same lock and rechecks existence after
  acquisition, before publishing its migrated file.
- Historical recovered-final publication uses a nonblocking lock and returns a
  conflict without changing the record if that execution is busy.

`--build-info` advertises `executionLogMutationLockProtocol: 1` on Linux. Every
actual writer must be a source-qualified build implementing that protocol. The
capability is checked by invoking the exact executable of the live PID, bound to
its binary hash, inode and process birth. A flag from an unrelated binary, a JSON
readiness assertion or an old source hash is not sufficient. The trusted owner
must also prove the complete writer/reader roster, disabled incompatible cleanup,
backup ownership and resource limits. Unsupported external repair/append tools
cannot mutate these files during scoped operation.

## Converter and recovery

The existing `controller.py` gains `--online`. It exclusively calls the verified
owner adapter's `admit_online`; it never calls the global `admit` fallback. Existing
global admission remains available separately and keeps its previous quiet-session
requirements. An online owner context must provide:

- A held `scoped_fence.ClosedLogFence`, bound to a single workspace and the exact
  selected paths in the authoritative database, with all selected locks held.
- `recovery`: current original versions through the existing normal Desktop B
  reader, consumed to exact full length and SHA256 by the converter.
- `archive_recovery`: independent normal-B access to every staged physical
  manifest, object and sidecar. The controller verifies the complete reference
  graph before publishing a manifest. Preserve all earlier backup epochs.
- `reader_guard` and `reserve_bytes`: the existing qualified owner/resource and
  archive-aware reader checks; no default resource exemption or fake ready flag.

`online_owner.py` is the source-pinned production adapter. Its configuration binds
both current serving readers, actual PID/invocation/binary identities, data/native
mounts, all three cleanup-disable settings, selected capacity8, the exact plan and
one workspace. The protected reader must have a kernel read-only log mount without
nested writable overrides. The main writer must advertise protocol1 and disabled
automatic cleanup. Busy/changed owners or resource pressure fail admission without
service actions. Bind this configuration freshly after activation; old operation
PIDs are deliberately invalid.

`nightly_graph.py` reuses the existing held Nightly owner's checkpoint producer and
independent normal restore consumer, bounded to48 members/24MiB per checkpoint and
2GiB per graph. It reopens actual immutable B parts for the converter, with no local
fallback. Durable receipt epochs permit a complete graph to be reopened after an
interruption. Partial preparation receipts fail closed for explicit reconciliation;
no source replacement happens before the complete graph passes. Existing backup
epochs and the original selected-version recovery context are retained.

Preparation, compression and archive backup can happen before acquiring the
execution locks. Under custody, recheck exact terminal DB rows, closed capture,
sidecars, original versions, recovery and actual capacity. Busy locks cause an
immediate deferral; never stop another execution to obtain one. A different
running execution in the same session is allowed only by the scoped fence.

The existing bounded batch limit (64 files/2 GiB), object-first durable publication,
atomic manifest replacement, metadata preservation, journal identities and raw
rollback are retained. Pending/unknown captures, foreign replacements, changed
owners and incomplete B graphs refuse conversion. In an interrupted operation,
keep compatible readers running, preserve the journal and all objects, reacquire
fresh scoped custody and resume or restore that exact operation. Do not clear
queues, stop services, reuse old epochs or roll an old database over current writes.

Use a single resource-owned conversion worker to process workspace selections
sequentially. Model turns are not required to supervise byte transfer and hashing.
This change neither launches an automatic worker nor commissions a nightly policy.
A workspace owner can nominate closed IDs and verify its history afterward; it
must not trim/truncate JSONL or substitute a summary for original bytes.

## Qualification and activation

The dependency-free production Rust lock and a test-only child built from the
same module support cross-language tests against Python `flock`. The suite checks
same-file exclusion in both directions, unrelated writes, live old-descriptor
reads, exact raw rollback, pending-input preservation, busy-lock deferral, foreign
lock replacement, changed owners, corrupt B data and process death immediately
after manifest replacement. It also proves that an old live writer is rejected
before creating any mutation locks. Synthetic recovery fixtures are not evidence
of production Desktop B acceptance.

Actual async writer integration tests cover cancellation, continued writes to
another log, archive recheck after waiting and invalidation of a stale closure.
Run those from the real utils crate, plus the complete focused Python suite and
format/governance checks. Build the new backend as a minimal overlay on the exact
retained current source, preserving the native-resume correction, private history
bindings and frontend. The old reader-compatible backend is an operational
fallback; if it is selected, online conversion must be disabled because it lacks
the new mutation protocol.

Before the first live batch: activate qualified lock-aware writers at the deferred
maintenance boundary, verify their actual identities, bind the existing normal-B
owner context to the selected originals and complete staged graph, then qualify a
small beneficial batch through the ordinary public history/review/settings/queue
paths with concurrent unrelated work. Record actual allocated recovery, including
objects, directory blocks, retained staging and old descriptors. Full reclamation
and nightly automation remain separate acceptance outcomes.

## Recorded qualification on 18 November

154 focused Python tests ran:151 passed and3 optional host probes skipped. Actual
utils integration passed9 Rust tests. The existing normal Desktop B owner stored
and independently restored a four-member/1,505B fixture graph; reopening with the
local archive path absent also passed. All native reader/owner contexts closed.
This proves the new adapter path with fixture content, not a production batch.
The actual protected reader log mount is read-only. Current production writer
protocol admission is negative; an additional complete host check refused elevated
memory pressure without changing its threshold. No production histories, inputs,
queues, settings, or service identities were changed.

Candidate build and current evidence are retained under the task's mounted SSD
production-20261117/efficiency-20261118 directory. Fresh activation identities,
selected-version B configuration, one ordinary public-flow canary and actual
reclamation accounting remain necessary before operational readiness is claimed.
