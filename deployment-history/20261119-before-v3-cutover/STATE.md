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

# Authorized cutover repair — 19 November 2026

The operator explicitly requested fixing and completing the cutover, live progress,
and WakeWatch wakes on both issues and success. A fresh v2 attempt is prepared;
v1 remains a consumed failed attempt, never reused. Production is still the
archive-aware4766246c… writer until current v2 RESULT and live identity prove a switch.
The new host check records helper identity, waits for natural exit, and thaws only
the same owned main if a helper races its freeze. Genuine queues/owner/capacity
checks remain. Real disposable-service drain/race and four switch/fallback tests
passed; ordinary WakeWatch timer loaded the exact new source with no test wake.
The progress URL is https://mcp-server.tail744c4.ts.net/vk-dedup-status and survives
Vibe maintenance. Current frontend, protected reader, data and previous watcher
configurations remain unchanged. Only cutover is being armed; full online log
conversion and final recovery/UI validation remain afterward. No new reclamation
is credited. See HANDOFF and actual v2 ARMED/RESULT/FAILURE receipts.

# Authorized scoped writer cutover — 19 November 2026

The authorized morning cutover ABORTED before switching binaries at10:06UTC.
CurrentSQL/normal-B restore passed, then the final main-cgroup check found an
extra process. Its identity was not recorded. Recovery restored ordinary access
and current data; original mainPID2573710/hash4766246c… remains live. Fresh12:10UTC
checks confirm five services running and public/API200. No retry is running.
See STREAM/HANDOFF and LIVE_DEPLOYMENT for failure/recovery evidence.
No new log reclamation or deferred cleanup is part of this software cutover.
The current GPT6.2 frontend and protected reader are preserved. Full deduplication
still requires online conversion, complete recovery closure and UI acceptance.
Earlier pickup files: deployment-history/20261119-before-authorized-cutover.

# Current production — 17 November 2026

Takeover continuation (17 November, late UTC): production still has only the four
previously converted logs. The lost-capacity-reply defect is fixed in a NEW inert
host helper, with 111 focused tests including three exact retained-host method
tests. It is not deployed or armed. Fresh serving/public/five-watcher checks pass.
Read-only remaining-log sizing and exact backup-demand preparation are underway;
see STREAM/HANDOFF for the live job and receipts. No new reclamation is claimed.

The compatible log readers are deployed. Main executable SHA256 is
`4766246c477fd8d73367969bee9b705586c5b580ddf786515409d977b48ce104`;
protected reader is `40a91f69f31c1b9751f8f5a699fc8dfaa6f20138ba1b0ab528788aecb7ddd000`.
The build is base087319cc4 plus the exact d007c88d2 native-resume overlay;
it is not a plain build of either commit. [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json)
records current hashes/provenance and retains historical releases separately.

Four original paths now contain verified lossless VKLOGCAS1 manifests. Net
allocated recovery is827,506,688 bytes including all canary objects and their
object-directory blocks. This first batch is NOT full reclamation. Preserve every
old epoch, sidecar, complete object store, pending prompt and selected setting.
NEVER select any historical archive-unaware fallback over remaining manifests.
The current99-migration authoritative DB and latest existing frontend are preserved;
public TLS/assets and all five serving/ingress services were verified after recovery.
Blue remains retired. No provider settings or concurrency guard was changed.

The actual continued native runtime is0.159.2: its initial resume now returns
zero historical turns/5,126 response bytes versus8turns/10,746,496 bytes before
deployment. The isolated0.166 fixture is qualification evidence, not deployed
runtime evidence. No extra provider request was made for measurement.

The operator-approved follow-up moved ONLY two inactive build archives to
independently verified Desktop B copies, preserving restore metadata and removing
only their unchanged SSD originals.303,202,304 allocatedB released; SSD postcheck
3,492,601,856B exceeds3GiBfloor. The full current history recheck passes22responses,
including exact7page/49entry reconstruction, plus public TLS/assets. Its334.782s
run used existing600s completed-data supervision; older failure receipts remain.
No production conversion was armed or started. See STREAM/HANDOFF for receipts.

Full production deduplication remains unfinished. The transfer-ready
[agent handoff](VK_LOG_AGENT_HANDOFF.md) describes the objective, verified progress, known recovery defect, source/test
map, evidence and success criteria; it leaves the approach to the receiving agent. This documentation
transfer does not authorize maintenance or launch another agent. The preceding
[go/no-go plan](VK_LOG_PRODUCTION_GO_NO_GO.md) records the prepared design
assessment; its proposed procedure is not a mandate for a new approach. Historical capacity/queue samples must be refreshed before admission.

Today's continuation state: the exact history mismatch
was workspace-path rendering context, independently reproduced on raw and archive
inputs. The prepared continuation adopts compatible readers without reactivation,
excludes the completed batch and separates strict history acceptance from lossless
service recovery. WakeWatch's previous dispatcher and all five configurations
were restored exactly; ordinary monitoring continues. No new maintenance was
started for this preparation. See [STREAM](STREAM.md), [HANDOFF](HANDOFF.md) and
[OP::Disk Space procedure](VK_LOG_RECLAMATION_READINESS.md) for actual readiness,
resource gates and outstanding full-scope/UI/normal-B closure acceptance.

[PR291](https://github.com/artinflight/vibe-kanban/pull/291) remains the source
integration record; commit/push does not deploy the prepared operation. Required
branch checks and private deployment qualification are distinct. Earlier source,
frontend/scrolling integration and provider qualification remain in
[the preserved November3 state](deployment-history/20261117-before-log-reader-continuation/STATE.md).
Their historical deployment IDs and acceptance budgets are not rewritten.

Full historical archive: [STATE history](STATE_HISTORY_20261017.md).
