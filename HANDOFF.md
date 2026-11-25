# Dedup completion — current pickup

Read dedicated WakeWatch CONTEXT.md first. User excludes Nightly commissioning,
deferred cleanup, uncertain replay, duplicate jobs/watchers/goals/agents and model
polling. Use finite scripts and the existing watcher. No native goal is active.

Evidence root:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
Wake0c3ea9f7/admission3 accepted in PACKED_ADMISSION_RECOVERY_ACCEPTED.private.json:
25triples,94restored files/341,068,615B,331,392,539new control bytes,3binaries,
reused map,3actual B admission groups. All311plans/3,639originals/4,219prepared
versions/both SQL bindings/live owners reconcile. Exact old unit empty/PIDgone.
Do not replay or recapture retained data.

PACKED_CONTROLLER_REHEARSAL_ACCEPTED.private.json accepts all4stages/3API phases,
60original tables/four later writes, both reader EOF probes, latest-copy fallback,
31explicitly fixture-only journal restores. Copied histories7,826files/71,741,440
allocated bytes become18files/54,546,432bytes. Two backward+one raw-forward
transactions use real isolated writer/reader protocols and kernel locks. Exact
old unit empty/PID4125186 gone. Delayed success wakes must not repeat it.

packed_controller/packed_live/packed_plan now enforce finite selection, existing
owner inode, intent-before-batch/no automatic replay, real writer/pinned readers,
actual B-backed mapping and both qualified EOF probes before original retirement.
Forward inventory checks both SQL owners, excludes active/pending/unbound/recent
captures and prepares raw captures directly as packs with session reuse.
packed_forward_recovery captures only new bodies and restores the new mapping/
metadata/catalog through actual B; aliases retain immutable existing selectors.
Four new recovery tests pass, including corruption rejection despite good local
copies. Eleven new controller/selection tests, eleven admission regressions and
fourteen existing publication/forward tests also pass; no duplicate test counting.

PACKED_FORWARD_NORMAL_ACCEPTED.private.json accepts the completed actual-B check:
6triples/84restored files/5,948,994B;1,577,508-byte source unchanged;212,719-byte
packed graph reused with zero additional body captures. All receipts/source/live
owners reconcile, exact unit empty/PID180142 gone. Delayed wakes must not replay.

packed_incremental.Adapter connects direct packing, normal-B recovery, actual
publication/EOF/journal seal to existing incremental/automatic ownership and
monitoring. One recovery context/run; per-session batches; prior catalog points
retained.3new integrated SQL/kernel/remote-fixture tests and7runner/9automatic
regressions pass. Existing daily hold/calendar unchanged. Runtime configuration
must bind actual post-activation reader PIDs/mounts; it is not deployed yet.

ONE job:packed-daily-rehearsal-v1; operation6cfd3d05308b431aa7e3a9a51d60b131;
unit vk-dedup-packed-daily-rehearsal-v1.service; PID311927;
invocation037e7a0964ed4ee7b767ae5d4676ad9c; CONFIG SHA
632a1210ceb673e56cb3bf9ef84caa392f68483752d5231f2ad42838603ebfc5.
Read CONFIG/STARTED/PROGRESS/RESULT/FAILURE, phase API/TABLES and main/
MIGRATION_RESULT.private.json, daily-state run journals, fixture recovery proofs.
Four stages: fresh main SQL/three raw-history copies; current reader baseline;
actual daily runner under candidate; latest-copy fallback. Both reader-build
EOF probes and actual isolated writer/reader protocols/kernel leases apply.
Verify automatic.verify_run accepts all controls and the next inventory is idle.
Backups in THIS rehearsal are explicitly isolated fixtures, NOT Desktop B.
Accepted actual normal-B proof is reused; no new backup payload is transmitted.
High4G/Max5G/Swap0/CPU100/Nice15/Tasks160,2h/600s progress watchdog.
Existing checkpoint-monitor-packed-daily1 binds exact STARTED/config/PID/invocation
under the same resource-guard hook, owner/session/ledger/activation settings.
No live publication/retirement/service switch, schedule or Nightly commissioning.
End the turn while healthy work runs; use WakeWatch instead of model polling.

After success independently reconcile this job and all B receipts. Finish the
post-activation daily configuration and measured serving-owner activation/fallback package,
then follow VK_BACKEND_RESTART_PROTOCOL's explicit cutover contract with a concrete
reviewable proposal. Live migration, current recovery, ordinary desktop/mobile/
history/review/settings/queues/monitoring and final allocation/filesystem/count/
performance/growth accounting including ALL staging/B growth remain open.
Preserve all inputs/settings/backup epochs/other owners and daily hold/calendar.

Rust format passes; web format lacks Prettier. Ops and whitespace checks are
recorded in DELTA with the final turn check. No new live net-saving claim.
[Design/evidence](VK_DEDUP_PACKED_LAYOUT.md).
[Earlier pickup](deployment-history/20261125-before-packed-admission/HANDOFF.md).
Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
