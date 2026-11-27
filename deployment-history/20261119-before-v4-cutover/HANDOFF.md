# Recovery only — production restored; dedup stopped — 2026-11-19 14:12:17 UTC

The operator explicitly requested production recovery only and to leave dedup
stopped. This supersedes every earlier armed/continue instruction below.
Do not rerun v3, re-enable its wake hook, activate the scoped writer, convert logs,
or resume the dedup goal without a new user instruction.

v3 failed after freezing production, before installing either candidate drop-in.
Both main-candidate.conf and main-paused.conf were mode 0664, rejected by the
existing strict source-file check; automatic recovery encountered the same defect.
The recovery preserved those failed inputs and all original failure/progress records.

Production was recovered on the exact original main PID 2573710, protected reader
PID 2573735 (unit main 2573723), and proxy PID 2573727. No backend restart, binary
switch, database restore, log conversion, or cleanup occurred. Original authenticated
capacity ownership, ingress services, public TLS and exact current frontend assets
were restored and checked. The public session/history/queue APIs and connector
latest-reply readback passed; the latest dedup execution remains completed.

All 60 SQL tables matched the pre-freeze hashes before thaw. After thaw, 59 stayed
exact; existing turn_github_sync retries advanced ordinary waiting/blocked job
bookkeeping. Recovery preserved those writes and verified its request/identity
projection, histories, all selected settings/executors, review state, empty queues,
and all 35 unresolved incoming records. No pending input was replayed. No new model
execution or full rendered-browser acceptance was performed for this recovery.

Dedup's dedicated resource-guard ExecStartPost drop-in was retained in the private
recovery evidence and removed from systemd. Its v3 config now has activation_approved
and connector_transport.enabled false. Other watcher configurations and hooks,
existing incident/delivery ledger, selected executor settings and original native
goal state were preserved. The failed cutover has no live process.

Completed dedup progress remains: four installed VKLOGCAS1 manifests, all four exact
manifest hashes independently checked. Historical measured net allocated recovery
is 827,506,688 bytes; this recovery reclaims nothing new. Archive-aware readers,
objects, sidecars, backup epochs, source changes, sealed candidate and qualification
records remain. The new scoped writer is still undeployed; backward conversion,
normal-B archive-graph closure and full dedup completion remain unfinished.

Private recovery evidence: /mnt/vk-storage/vk-production-recovery-20261119
Fresh v3 receipt: /mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/cutover-20261119-now-v3/RECOVERED.private.json
The v2 recovery receipt is historical and was not used as proof of v3 recovery.
Original v3/current SQL and 47-file normal-B restore receipts were retained.

---

Earlier preparation notes (historical; not current authorization):

v3 is ARMED and independently observed active, waiting for exact current
execution8b0039f6e47f4649916d2f8629d54070 to finish naturally. ARMED is not success.

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

Earlier attempt details: [pre-v3 archive](deployment-history/20261119-before-v3-cutover/HANDOFF.md).
Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).

Validation this turn:11 capacity release/recovery tests pass; operation event
isolation passes; fresh preflight opens both capacity files through the unchanged
strict guard; normal timer loaded v3 without duplicate wake. Rust formatting
passes; web formatting is unavailable because Prettier is missing. Only controller
preflight differs from prior real-systemd qualification. Full backup runtime-file
union is retained (32files), including original recovery and new monitoring controls.
