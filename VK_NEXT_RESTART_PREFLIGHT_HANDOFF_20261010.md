# PR235 next-restart source handoff — source only

Source revision: `d1737767dacf996758991d40099b025c0c462e86`. Published PR235 owns only the restart
consumer/adapter; Gitowner 14331e35 owns authoritative inventory/original ledgers
and copied-data controller acceptance. No live changes or scheduling occurred.

Readiness manifest: `/mnt/vk-storage/vk-next-restart-20261010/pr235-source-readiness.safe.json`
SHA256: `bf8dc67092ffa0fb8307f0e7736e5bb7cdbf8b0abea2876cdf766ed2b4215738`

| Source/API | SHA256 |
| --- | --- |
| vk_nightly_job.py — runnable CLI, disabled configuration | 3fce345fcdd559025bf512a6735f025e8861f099707d49bc76a7873f66a5c138 |
| vk_routine_restart.py — driver-facing run(), no standalone executor | 1ff2c9d22714028506c66a0409b3f0c8c43a86502dbc52ac6e1a28fc02a9a025 |
| vk_restart_git_boundary.py — conditional held check-all consumer | faf287f6402a9ee65b68b36a24f57c1177b10d4abf5f1538eae3b3090e47cfef |
| test_vk_restart_git_boundary.py — synthetic fixtures only | 3610604127340963f95ead6f2a9565dc2be83e98735d69cc5fb9210aac540b7e |

The JSON pins every dependency, configuration, existing package, receipt and
schedule template. All 25 nightly code files still match the tested 53aaada46
package. Its read-only `--check-config` passed with adoption false. Existing cron
proposal passed `crontab -n` syntax validation; nothing was installed. The new
user-service/timer templates here are disabled source proposals, 02:00 UTC,
oneshot TimeoutStartSec=7200 / TimeoutStopSec=30, 25% CPU, low IO/nice and 2G/3G
memory limits. Their command uses the disabled configuration and exact hash.
Before adoption, bind global host/swap/B/health guards to the actual scheduled
job lifetime; the old test-only guard names an old test unit and is not reusable
unchanged. Cgroup limits alone cannot establish host headroom. No routine LLM.

Fresh checks: 22 small source/fixture tests passed in 0.130 s. Real fixture kernel
lock contention, check-all bounded transport, pending/malformed/nonzero/wrong
schema, missing/changed ledger/inventory/owner and unfenced booleans are covered.
No production helper/controller was invoked. Three extra local lifecycle/codec
fixtures stopped before work because SSD free is below the unchanged 256MiB
manifest reservation. They remain resource-blocked, not source regressions; no
reserve was mocked or reduced. Native Windows B is not an interchangeable local
Linux test directory (these tests use fork, kernel locks and Linux journals).
An equivalent existing B fixture runner may run them later without overriding
those semantics or touching the retained fixture current.

Existing actual-B two-generation acceptance is pinned: changed SQLite recovery,
unchanged history/hardlinks, deletions and one independent current after old
retirement passed. A fresh read-only check of that EXISTING current verified all
3 file entries / 1,308,206 decoded bytes; no new snapshot/restore. All 79 actual
SQL images passed the prior whole-plan attempt; it was subsequently aborted by
swap guard, so full-plan archive/current/independent recovery is NOT accepted.
The verified compressed recovery copy, failed attempts, incident/fallback and
old backup evidence remain protected. Atomic publication verifies the complete
self-contained new generation, renames/fsyncs current, then retires only the
previous normal generation under separately adopted normal-nightly retention.
It never depends on a baseline that retention removes. No cleanup before QA.

Current small-probe B free: 88475803648 bytes; required cold
reserve remains 105495134208 bytes. SSD is about 120MiB; swap remains below
512MiB. No heavy acceptance/build is admitted. Production data remains current;
its successful 9.94 s handoff is not a ten-minute full release measurement.

Exact next actions, owned scopes:

1. Gitowner publishes its API and hashed 73-fixture/scanner/copied-data receipts;
   request/consumer interface is in `pr235-git-api-request.safe.json`. Its helper
   schema uses `version: 2`, not a new receipt schema. The consumer invokes fixed
   hash-pinned helper `check-all` only inside its real controller writer fence,
   requires exit0 + verified schema2 output, exact policy/original-ledger/complete
   inventory/operation-owner pins, and carries the witness through handover.
   Source callback contracts are implemented; real driver/API/fence acceptance
   is unrun. Keep activation disabled until per-scope policies and acceptance;
   never apply VK-only policy as a global gate on unrelated projects. Same-UID
   secondary review is advisory, not protected authorization.
2. Staging binds reviewed driver authorization/build/validation/final-B backup/
   review/held/boundary/handover/latest-data recovery to its existing current-data
   user-service and real ownership/queue gates. No fabricated execution status,
   stale disaster-recovery restore or protected archive retirement. Its driver
   must preserve selected AutoSwitch history module from live-bindings.safe.json,
   Recommend-only/model/effort, current data and compatible latest-data cutback.
   Preparing backup artifacts does not automatically authorize a handover.
3. When real resource guards and approved evidence reconciliation genuinely
   permit it, finish one whole-plan independent current/recovery/runtime/reserve
   acceptance. Only then review exact normal scope enrollment/retention/config/
   guard adoption and user-job scheduling, with verified test-run/schedule receipt.
   No owner manual command is part of this handoff. Nightlies remain disabled.
4. Measure warm/cold real release builds preserving caches, and total FIX READY
   through build + validation + deploy + blocked work resumed, mandatory same-host
   timestamp and 600 s goal. Build while incumbent is online; compatible actual
   frontend-only changes may use that route. Nightlies cannot compile future
   fixes. Disaster recovery restoration remains a separate workflow.

Artifacts are metadata only. No production/root/security changes, backup or
full-plan rehearsal, cleanup, worker spawn, module activation or owner command.
Ops check passed. Rust formatting passed; Prettier is absent, so web format did
not run. Historical receipt/source scope remains explicit in the JSON.
