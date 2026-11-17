# Production reclamation pickup — 2026-11-17

Read STREAM.md. No production conversion/recovery has happened while this root
turn is active. Do not report preparation as reclaimed space. The native build
PASSED; the original first Nov17 launcher failed read-only preflight because its
plan was group-writable. Original readers were unchanged and WakeWatch restored
exactly with all5 ordinary ticks. Never replay that consumed launcher.

The corrected finite native operation IS RUNNING:
`vk-log-dedup-full-20261117-d6ed2cee.service`, invocation
`f90df6f2c300401490821d9706654fd4`, initial PID1845038. It waits for current root
9f358e27 to finish naturally. Private root case:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117` (`P`).
`SEALED_OPERATION.private.json` / `CURRENT_OPERATION.private.json` point to
operationd6ed2cee's exact `INPUTS.v2.private.json` (SHAad0e7771...),
`controller-v2.private.py` (SHAbd02e8f8...), and operation receipts. The prior
sealed epoch is preserved under its original operation folder. No new goal,
agent, pipeline, build, owner approval or repeated request is needed.

The correction reuses the old immutable byte-identical PLAN, preserving the
writable original and the exact pin guard. Main artifact4766246c and protected
40a91f69 are ready. Actual complete module/class/callback/artifact preflight and
4 controller regressions pass; independent existing data-progress supervision
has600s idle/300s recovery, no total cutoff. Read actual RESULT/FAILURE/RECOVERY_FAILURE
and full reclamation, physical release, SQL, software/frontend/all-object B closure,
public/browser and WakeWatch restoration receipts before claiming any success.

FRESH WakeWatch pause belongs to the operation-local `wakewatch-pause` directory.
All5 ordinary monitor ticks advanced with unchanged configs/attempt counts,
no unsettled deliveries, resource-guard timer active. Monitoring/notifications/
reconciliation remain active. Supervisor restores exact source/configs only after
ordinary service recovery, verifies all5 ordinary ticks plus status/check, then
submits at most ONE existing-root continuation with exactly the saved configuration.
All32 pending uncertain inputs remain preserved; current durable queue is empty.

The full native job MUST complete first4 acceptance THEN ALL positive-benefit
current closed batches, independent normal B original/sidecar/current-main SQL/
software/current frontend/complete object-store closure (unreferenced included),
Python+production Rust EOF, actual allocation and original FD release, and resumed
ordinary desktop/mobile/history/review/settings/queue/public service. Newly created
staging replicas retire only after publication+B proofs; preserve primary CAS,
old epochs, originals/sidecars and every backup. Never boot archive-unaware code
while ANY manifest remains. Never restore an old DB over later writes.

Vibe handoff: `/mnt/vk-storage/vk-log-reader-release-20261104/refresh-20261117-v1/HANDOFF_MANIFEST.private.json`.
Nightly handoff: dedup case `nightly-coordination-20261117/ROOT_HANDOFF.private.json`.
Both owner turns finished. Nightly batch-source-v3/BASE_PROVIDER_CATALOG and exact
old Reader class are required. Serial context switching only, genuine fence,
immutable per-batch custody epochs, no second producer. Shared question revision54
has the corrected job and complete owner contracts.

Measure actual resumed production wire capture/version with
`P/measure_resume.private.py`; retained closest baseline is
`P/MEASURED_PREDEPLOYMENT_CURRENT_RESUME.private.json`:8turns/10,746,496B,
reported0.159.2. Prior baseline7turns/7,729,679B. The actual isolated0.166 fixture
is qualified but is NOT proof of deployed0.166. Do not issue extra inference for QA.

The exact32,579 missing raw paths are explained by Disk's separate completed
Nov14 retirement (31,572,000,768 allocatedB); do not recapture or credit it again.
Accepted18 older private views remain restore-before-view, not locally available.

Public source d007c88d2 contains exact-version resume guard and subsequent batches;
8 actual Rust tests/build,74 Python tests,13 helper tests passed. PR291 draft into
staging. Preserve latest frontend/current99-migration DB, selected model/route/
permission, all pending prompts and backup epochs. Keep notes truthful after each
actual result; zero current recovery is still the prelaunch checkpoint.

Historical scope: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
