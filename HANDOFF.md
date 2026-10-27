# Nightly — current pickup, October27 EDT

Finish the existing Nightly commissioning goal/PR263 in workspace604d. No backend
restart. Scheduling is disabled, next run null. Do not duplicate independent
jobs, accepted carriers, database capture or the completed namespace audit.
Read current RESULT/STOP/STATUS receipts; a progress mirror can predate a STOP.

Private evidence root:
/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261026
Native controls/objects:
B:/vk-backups/vk-nightly-efficiency-20261026/{controls-v1,objects-v1}
All backup bodies/growing indexes/SQLite temporary work belong on B. Local
source observation uses fixed8MiB SQLite plus9MiB reserved rollback and bounded
health/package files. No OS/work-SSD backup payload or fallback is allowed.

## Actual independent ownership

- Source observer V10: vk-nightly-bounded-inode-observer-v10-20261027.service,
  PID1714599/start31642400, epoch2f32f888fa134b9496467b4fba4fc0e7.
  Installed source0524e7d3d, configSHA
  f14cabd137cf99102f41eca3a5170574eed3c56d07b27e88fb8c5213f6c5add8.
  Owner-raised1048576watch ceiling is live. Actual ready/barrier and memory
  acceptance are in b-controls-v1/V10_OWNER_MEMORY_AND_NORMAL_BARRIER_20261027.
  Approximately770k successful watches,467432KiB RSS/1.06GB cgroup including
 511MB file cache/84MB kernel; no high/max/OOM events at that checkpoint.
  This observer stays running independently of Desktop transport.
- Terminal composition V12: vk-nightly-B-current-composition-inodes-v12-20261027.service,
  PID2679296, started11:31:39EDT, sourcea527b909a73bf1e255ac6c2eef3b00309f96d729.
  Package current-composition-B-inodes-v12; configSHA
  49209f00108aeea0760f0de98c40ef02b19a1a7f4f05f0125668ea65a8a36b69.
  CPU25%,High1536MiB/Max2GiB,Swap0,Tasks64; own3h deadline/hard3h5min.
  It stopped11:52EDT on a15s native SMART read timeout; no map/body writer
  remains. All committed B metadata/components survive; no recapture occurred.
  It resumes the retained cursor in8192-name calls, then consumes the actual
  epoch suffix, refreshes staged qualifications and reuses accepted whole bodies.
  B source-event delivery is serial/every120s plus an explicit suffix boundary.
  Check its actual terminal receipt before preparing the next payload phase.

## Newly completed, reusable evidence

- terminal-gap-recovery-inodes-v10 completed10:21EDT, exit0:
  783552metadata paths,98567directories,0errors,282386432B B index.
  Actual normal independent B result reopen passed. Do not repeat this walk.
- qualification-stage-B-inodes-v10 completed10:34EDT, exit0:
  18539points;14031retained body matches;4494pending;13SQL discoveries;
  1deferred. Actual stable hash bytes4971262421; no payload copied.
  Normal independent B stage/cursor reopen passed. Reuse this stage by identity.
- The previous body phase is TERMINAL, not still running: file-points-worker-B-inodes-v1
  stopped10:08EDT at final acceptance on native SQLite BUSY. Its4393phase
  completions and4398total accepted point-history records remain on B. Its
  source5691baa74/config036bca0d was never changed while active. New code retries
  only the verified idempotent acceptance, never the completed upload/readback.

## Preserved gaps and corrected failures

V9 stopped09:12EDT, epoch21487895bcd24324869f9f8e636f8d5e. Its SQLite is
intact through4081780, with1317pending names and B acknowledgement3029482.
It records unknown-watch897862/mask8; the unsealed oversized in-memory report
was not retained, so its duplicate/error-size makeup is unknown. All originals,
spools and fault evidence remain. The later V10 set does not repair that epoch.
Actual B terminal-gap proof42851975fc11ad79e25d214472fc056b2d97cd36c0958cfac41582a16961189b
is in journal-terminal-gap-proofs; normal independent reopen passed.

V10 composition wrapper failed before new-map adoption: it inherited a1GiB
namespace-index cap for an already1258803200B map. SQLite clamped its page
ceiling to existing pages and reported FULL on growth. The corrected4GiB
budget is the previously tested map budget, not a changed physical reserve.
The source now refuses too-small writable budgets before mutation. Actual
native B temporary placement is verified inside controls-v1/sqlite-tmp-v1.

V11 composition later stopped on the required smartctl15s query timeout;
its PROCESS log has the original native stderr trace. Quiet initial+final
full health checks passed11:23EDT in9.06s, unchanged identity/SMART/PHY and
1545595666432B free. V12 preserves that15s deadline and all real controls;
do not overlap extra native admission/inspection probes with its active work.
Native subprocess failures now retain explicit context instead of generic EOF.

## Baseline/commissioning work still required

Resume V12's retained cursor after finite full health requalification; then
independently reopen its completed suffix/current map.
Inspect exact residual states and the single deferred point. Reuse accepted
body matches and existing SQL points; capture only unresolved current versions.
Cold SQL can reuse verified images; live/WAL/always-API sources need actual API
points. The critical alias points to working90.sqlite outside its logical
parent: require the actual target image and always_SQL_API_sources, not raw WAL.
Do not assume204regular SQL points cover all later SQL discoveries/aliases.

Retain accepted162.70GB independent restore, all137/148/204SQL evidence and later
supplements. Original7783archive gaps/6546loose-object IDs stay explicit;
current source resolution never proves original archive inclusion. Current
runtime/served frontend remain a separate later binding. The08:38 source
observation/08:44 gateway readback are preparation, not final-current acceptance.
The prepared runtime-dependencies-20261027-v1 component has two pending bodies
(gateway.mjs3048B and route.json152B); always sample these finite dependencies,
without pretending the117-root kernel plan covers them.

Current-set acceptance still needs final body/SQL/runtime integration, a sealed
authenticated B-backed current descriptor and independent composed restore.
The working-index provider currently imports immutable original checkpoints;
add/test B-native sealing of a completed current working index without SSD
hydration before treating a mutable working index as an accepted descriptor.
Then finish the normal incremental cycle/restart delta interface and actual
installed worker/config/health integration. The older calendar invokes the
legacy supervisor/job path; do not enable it merely because its fixtures pass.
Commission the02:00America/Toronto schedule only after whole acceptance, exact
installed binding, interruption/Desktop-off/low-SSD checks and next-run proof.

## Source/validation continuity

Runtime
packages remain pinned to their recorded commits; later documentation commits
do not alter them. PR263 is the sole integration PR. No generated bytecode is
tracked or approved for tracking. Rust format passes; full format is currently
blocked by missing Prettier. Run narrow relevant checks/ops and record actual
exact-head CI separately from older green heads.

Earlier source/bindings remain in Git/private receipts and the full
[historical archive](HANDOFF_HISTORY_20261017.md), plus the
[Nightly archive](HANDOFF_NIGHTLY_HISTORY_20261027_0124.md).
