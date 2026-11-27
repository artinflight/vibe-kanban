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

Current v2 receipt: ARMED and independently observed active on19November2026; waiting only for execution7d5179da94e040a6a1149cf967ba6106 to finish naturally. This is not completed cutover. Live status and the actual result receipts supersede this preparation note.

# Pickup — fresh v2 cutover and WakeWatch, 19 November 2026

D=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/cutover-20261119-now-v2
Operation875272953765427e996418bdffb0e7c6; service
vk-scoped-writer-cutover-20261119-now-v2.service. This is the newly authorized
repair. Check actual ARMED/RESULT/FAILURE/SUPERVISOR_FAILURE/RECOVERED and service
identity before acting. Never duplicate an uncertain attempt. v1 is consumed.
Main candidate01495f7f… adds protocol1; current main4766246c… is the compatible
fallback. Preserve latest SQL, existing protected5650, GPT6.2 frontend, all old
archive epochs and all settings/queues. Do not infer conversion from cutover.

Live status: https://mcp-server.tail744c4.ts.net/vk-dedup-status . The exact one-file
Serve route stays available during maintenance; existing routes/Funnel unchanged.
Existing resource-guard timer loads D/wakewatch/cutover_source.py with private
config/registry/ledger. It observes one finite operation, creates at most one
issue event and one success event, and uses original shared admission/receipt
machinery. Busy/queued/unknown outcomes retain custody, with no resend. The user's
explicit success/issue request authorizes the wake, not a new goal/worker/loop.
Source/test/timer receipts are in D. No production test wake was sent. Delivery
itself is only verified by its later retained real execution receipt.

On a success wake: independently check live SHA/protocol1/public history and
current receipt, report the cutover, then continue the original authorized online
backward deduplication while leaving the deferred cleanup alone. Full requirement
closure remains conversion, complete normal-B archive graph/SQL/software restore,
ordinary desktop/mobile/review/settings/queue acceptance, growth and handoff.
On a failure wake: reconcile controller/recovery before any service action;
no blind production retry. Prior failed10:06 attempt is preserved below.

Formatting was invoked again: Rust passes; Prettier unavailable remains the web
formatter limitation. No frontend source changed. Ops checks and git diff --check passed on this final run.

# Pickup — cutover aborted, original service restored, 19 November 2026

The 10:06UTC attempt aborted BEFORE switching binaries: the final main-cgroup
check observed an extra process after currentSQL/control backup completed.
The failure did not record that process identity; do not infer it from a later
active-turn helper. No new execution row started during10:02–10:07UTC.
Original mainPID2573710/hash4766246c… remains live. Recovery cleared maintenance
and all owned ingress holds, restarted both ingress services, and retained current
data. Fresh12:10UTC checks confirm all five services running and public/API200.
The controller exited1; no retry is running. Correct/qualify the final drain
check before any newly authorized attempt; preserve this consumed attempt.

D=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/cutover-20261119-now-v1
Controller service: vk-scoped-writer-cutover-20261119-now-v1.service.
D/ARMED.private.json means waiting/running, not success. D/RESULT.private.json
means live switch/public acceptance completed; FAILURE and RECOVERED explain
any abort. Never start another attempt over an uncertain one. Admission expires
within this window; no automatic later-day retry.

Actual production before activation: mainPID2573710 / SHA4766246c…; protected
PID2573723 / server2573735 / SHA40a91f69…; proxy2573727. Five units and inputs
are bound freshly. New main SHA01495f7f911a222f022354d406789ffa7f634f6faab81798828413d3582cc0a0.
Protected current binding is9c812186…, not the obsolete pre17November b59bc14….
Frontend is the existing GPT6.2 release/index-DxHYbG0e.js, preserved unchanged.
Current authoritative DB remains working90.sqlite,99migrations. Latest-data
fallback is the current archive-aware4766246c… binary; no staleDB restoration.

Evidence: D/BACKUP_PREFLIGHT.private.json and CURRENT_MAIN_SQL_ACCEPTED show
normal-B independent restore of188,227,584B. The controller recaptures SQL after
real drain. D/transition-test-*/RESULT records real private-service forward and
fallback, later writes, and injected failures including actual SIGTERM after
candidate start. The earlier main-roundtrip-v4 and runtime-B evidence remains
under ../scoped-activation-20261119-v1. No production log is converted by cutover.
Full formatter ran: Rust passed, web step failed because Prettier is unavailable.

After cutover, full reclamation, production archive-graph closure and ordinary
public desktop/mobile workflow acceptance remain outstanding. Preserve deferred
cleanup and all selected settings. Only historical827,506,688B recovery is credited.
Earlier pickup: deployment-history/20261119-before-authorized-cutover.
Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
