# Backward deduplication: scoped execution custody — 18 November 2026

## Current instruction

The operator explicitly authorized resolving the blocker to converting closed
logs individually while active workspaces continue. The large workspaces are
active; do not retire them. Earlier overnight `cut over now` approval was real and
persists. The operator subsequently deferred interruption until tonight because
Vibe is needed during the day. No exact evening start was agreed; do not invent
one or request the same authorization again. Prepare/test now; preserve running
work, pending inputs, settings, pins, all recovery epochs and ordinary monitoring.

The native goal is paused. This separately authorized blocker fix does not imply
that full backward deduplication is complete. No new production conversion,
retirement, pause, dispatch hold, service restart or backup capture has occurred.
Only the four historical manifests are installed; net827,506,688B is historical.

## Implementation

[Scoped conversion contract](VK_SCOPED_LOG_CONVERSION.md) describes the new
per-execution permanent `.mutation.lock` protocol. Raw/error capture, migration
and recovered-final writers participate. The new `ClosedLogFence` binds exact
closed terminal execution IDs to one workspace and acquires their OS locks
without waiting. Other executions in the same session remain writable. The
existing journaled converter now has an explicit `--online` admission route;
it cannot fall back to global maintenance. Both original normal-B recovery and
the complete staged archive object graph are required before replacement.

Production lacks protocol1: the read-only live probe rejected it before creating
any mutation locks. PID2573710/invocation74e3735e38574268a329ee5a31280227 remained
active/running. One qualified writer activation is needed at the deferred boundary;
subsequent bulk conversion uses scoped locks and needs no global pause. Do not
start the old v9 whole-system operation automatically.

## Current validation and running job

154 focused Python tests ran:151 passed,3 optional host tests skipped. The real
utils crate passed9 Rust lock/async capture tests, including cancellation and
archive recheck. Real Rust/Python exclusion, concurrent unrelated writes/inputs,
rollback, owner loss, corrupt B bytes and process death after replace are covered.
Formatting, governance and diff whitespace checks pass.

The existing Nightly owner context checkpointed a four-member/1,505B fixture graph
and independently restored it through the normal B consumer. A second reopen
passed with local staging absent (50.329s total). This is real B integration with
synthetic fixture content, not acceptance of any production batch. Source adapters
online_owner.py and nightly_graph.py now connect scoped custody to those existing
normal recovery interfaces; no new backup transport or schedule was introduced.
Actual protected-reader session mount is kernel read-only with no nested writable
override. Full live online admission additionally refused elevated memory PSI;
no threshold was relaxed. Current writer still lacks protocol1.

RUNNING: sole bounded candidate build vk-scoped-log-release-v1-0815.service,
wrapper exec58681. E/scoped-release-v1 contains immutable source overlays, build
log and RESULT/ARTIFACT.private.json. It retains the existing build lock/shared
Cargo target, one CPU/job,4G high/5G max memory, zero swap and3GiB SSD/memory floors.
Do not duplicate it. Utils job v2 is terminal/successful; v1 sandbox failed before
compilation and was corrected. Need collect candidate build; fresh runtime owner
bindings, exact selected-version normal-B config and first public-service live
batch acceptance remain activation-bound work. No model/provider test calls.

Five edited existing Rust files exactly matched retained production source before
our overlay. Preserve source087319cc4 plus the existing d007c88d2 client overlay,
private history bindings and current frontend when building the lock-aware release.
The original declared archive-aware current binary hashes remain in STATE and
LIVE_DEPLOYMENT.json. Existing source changes are uncommitted; draft PR291 unchanged.

## Measurement and earlier preparation

E/ACTIVE_WORKSPACE_CLOSED_LOGS.private.json records82,424,827,904 allocatedB across
2,223 closed logs;311,156,736B across10 pending/unknown logs are excluded, including
one invalid OP::Disk Space sidecar. These histories are on the ROOT volume, not
SSD staging. Archived/unpinned plus additional Done histories total only0.297GB.
Do not infer retirement from absence of a currently running execution.

Earlier finite B benchmarks:200,819,810B verified read47.126s baseline versus12.469s
with the isolated1MiB decoder candidate (3.8x). SSH compression/near-data full
restore were slower. All jobs terminated. That decoder is NOT production qualified
or integrated. Local packer avoids redundant compression passes; separate tests
pass but no production throughput/savings claim is made. Do not keep models active
to supervise bulk byte copying; use the resource-owned finite script.

The old completion-package-v9 remains UNARMED, operation99ac6cd5d1b84fe893d5a1501d32c35d,
inputsSHA4f0c9db5d6f80b5200dbfc017f466b55cf17a465d4530efdacd0911dc3547757.
Its completed sizing/lookup covers3,366logs/91,104,810,328rawB; do not rerun it.
Full reclamation, original/resulting-graph B recovery, actual physical recovery and
ordinary desktop/mobile/service/WakeWatch acceptance remain open for the full goal.

Model polling has ended to avoid supervising compilation with paid agent turns.
The resource-owned build continues independently and records success/artifact or
failure in E/scoped-release-v1. Collect that result before activation; a running
job is not a passing build. No cutover is scheduled and no new permission is
needed for the already-authorized work; preserve the deferred evening boundary.
Public page/API both returned200 with verified TLS in21ms/39ms during compilation.
This was availability only, not post-activation UI acceptance. Metadata-only audit
found no individual log above2GiB (largest324,499,915B); no body scan was repeated.

P=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117.
E=P/efficiency-20261118; D=P/completion-20261117-demand.
Current procedures: VK_LOG_DEDUPLICATION.md, VK_SCOPED_LOG_CONVERSION.md.
Earlier details/receipts and operator corrections are preserved in the dated
pickup archive above and deployment-history/20261117-before-completion-takeover/.

Full historical archive: [STREAM history](STREAM_HISTORY_20261017.md).
