# Current repair and v3 readiness — 19 November 2026

v2 failed before capacity release or binary switch: its strict guard rejected
controller.lock mode0664. Recovery restored ordinary access, original main
PID2573710/hash4766246c…, unchanged protected/proxy, currentSQL/frontend and inputs.
WakeWatch actually delivered batchd0b6ea12-e2aa-4a9c-9c3e-8766a8bc88f5 exactly once,
execution8b0039f6-e47f-4649-916d-2f8629d54070. This is live delivery proof, not success.

The exact empty lock inode2065:24021559 was verified held only by mainPID2573710
under its private0700 parent. Its mode was repaired to0600 without replacing the
inode, touching contents or releasing/acquiring capacity. The unchanged guard now
passes; both lock/state permission checks moved into pre-maintenance preflight.
11 capacity recovery tests pass. Switch/recovery/worker AST and helper-drain code
are unchanged from v2's real disposable-systemd tests. A focused source test proves
old-operation events are not reissued when the same WakeWatch ledger is reused.

Fresh v3 root:
/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/cutover-20261119-now-v3
Operatione3bfa01aa9634917947b4857adf7bf4e, service
vk-scoped-writer-cutover-20261119-now-v3.service. Current preflight passes; actual
ARMED/RESULT/FAILURE receipts determine state. No new reclamation is claimed.
The already-authorized repair continues within this current window. Controller
admits only after exact current execution8b0039f6… finishes naturally; unrelated
new work aborts admission. No blind replay of consumed v2 occurs. The single
existing WakeWatch hook now points to v3, retaining v2's ledger/receipts and
unchanged saved owner/configuration. Same live progress URL remains available.

On the next wake, reconcile this v3 operation and live backend before reporting.
Success means writer cutover only. Full backward conversion, normal-B archive graph
closure, UI/queue/settings acceptance and measured growth/handoff remain. Deferred
archive cleanup is still excluded. Native goal remains paused; no duplicate goal.

# Current work — cutover repair and outcome monitoring

Fresh v2 operation875272953765427e996418bdffb0e7c6 reuses the already qualified
01495f7f… candidate, current-data recovery and normal Desktop-B backup machinery.
The operator authorized this repair and requested issue AND success wakes. The
single controller waits for this exact current turn to finish naturally before
any maintenance. It rejects new work and retains600s verified-progress/300s
recovery supervision. It does not convert logs or run deferred archive cleanup.
New helper-drain/race tests and actual disposable-systemd transition/fallback
passed. No production restart has happened during preparation. Read current
v2 receipts rather than inferring success from preparation or ARMED. WakeWatch
uses one extra source on the existing resource-guard timer and exact saved
Astra/xhigh/AUTO/Recommend selection; it creates no worker, goal or second loop.

# Scoped writer cutover — 19 November 2026

The operator explicitly said “cutover now” at the current morning window.
The task is the main writer software cutover. Preserve all logs, active work,
pending inputs, settings, backup epochs, protected reader and the latest frontend.
Deferred cleanup remains untouched; bulk backward reclamation follows separately.
The native goal remains paused; do not create another goal or agent.

The fresh controller is in
/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/cutover-20261119-now-v1.
The controller aborted before binary switch at10:06UTC and recovered the original
service. FAILURE/RECOVERED and current service identity supersede ARMED. The
final cgroup check found an unrecorded extra process after backup; no retry runs.
No successful cutover is inferred from an armed controller. It waits for this
exact execution to finish naturally, rejects unrelated new work and expires its
admission within the current window. It retains the real writer/capacity/ingress
boundary and independent600s no-progress/300s recovery supervision.

Qualification: candidate SHA01495f7f…; fresh61-table current-data roundtrip;
normal-B software restore; current188,227,584B SQL backup independently restored;
real disposable-systemd switch/fallback with preserved later writes and failure
injections including supervisor termination after candidate startup. A fresh
consistent SQL capture is still required at the actual drained boundary.

Fresh preflight reconciled the newer GPT6.2 frontend (index-DxHYbG0e.js), whose
own normal-B recovery is retained, and the actual protected-reader working99
binding9c812186…. Main remains4766246c… until RESULT proves otherwise.
All five current WakeWatch configs are pinned without changing their activation.
Rust formatting passed; full format remains blocked by missing Prettier.

Full backward dedup remains unfinished: only the previous four manifests and
827,506,688B historical net recovery are credited. Next, read the cutover result,
then bind real protocol1 online custody and process eligible beneficial logs
with normal-B original/graph closure and ordinary UI validation.

Earlier pickup files: deployment-history/20261119-before-authorized-cutover.
Full historical archive: [STREAM history](STREAM_HISTORY_20261017.md).
