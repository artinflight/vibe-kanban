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
- Composition V13 is successfully terminal at12:10:30EDT, unit
  vk-nightly-B-current-composition-inodes-v13-20261027.service, MainPID0/exit0.
  Source2b540cf4dd826414fa25b00688fc0776d4dc2638; package current-composition-B-inodes-v13,
  configSHAd9f06f90af8b5742e0687371ff65d367c3c568bd12b34f80bfcc09ab24ed8b72.
  Normal independent B reopen passed; native map1284141056B. It consumed
  actual epoch suffix284178..3944253:3225changed/7065replayed paths,
  unchanged source paths scanned0. Reused8624file points/44269832049raw B
  bytes without any body recapture/copy. All4398accepted history points remain.
  Initial residual demand:61251pending files/23247891411logical B,
  6928unqualified/1503231416logical B,218SQL sources (not net transfer).
  First index/reuse completed file-history bodies too; later qualification can
  otherwise demote the same completed body to pending. Do not repeat namespace.

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

V11/V12 stopped on native15s SMART read timeouts; original traces survive.
V13 completed after the tested finite full requalification fix, with unchanged
STOP/access/counter checks and command deadline. No blind denied-write retry.

Current sole body phase is vk-nightly-B-file-points-inodes-v2-20261027.service,
PID3167974, started12:22EDT; package file-points-worker-B-inodes-v2.
Source028c45e14f8ecdc7346ac8fb9ba3775f577eb01b; worker configSHA
50c2f289a1963ec70c51db8dd511b3ea070716513ea8e68ef4ea8b099f058735;
controllerSHA0c21d2909653cdcafb2bd9e29d14a8984e7d4a27a7d6318fb56d70474bf33467.
CPU25%,High1536MiB/Max2GiB,Swap0,Tasks64,3h own/3h5min hard deadline.
Existing phase bounds8192files/16GiB source reads remain. It reuses actual
completed histories before transfer and delivers source events serially at
completed-component boundaries, replacing the old background health stream.
Read STOP/RESULT before STATUS; do not duplicate it or run another native
inspection/health probe alongside it. Latest status includes measured memory.

## Baseline/commissioning work still required

Reuse the accepted V13 namespace/suffix result; next perform the finite
completed-file-history lookup and residual-only qualification/capture.
Inspect exact residual states and the single deferred point. Reuse accepted
body matches and existing SQL points; capture only unresolved current versions.
The critical alias points to working90.sqlite outside its logical
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
B-native immutable snapshot plus independent stream/hash/SQLite acceptance
and normal typed-reader reopening are now implemented/tested. Apply only to
the completed current map; tests alone are not its actual descriptor acceptance.
Then finish the normal incremental cycle/restart delta interface and actual
installed worker/config/health integration. The older calendar invokes the
legacy supervisor/job path; do not enable it merely because its fixtures pass.
Commission the02:00America/Toronto schedule only after whole acceptance, exact
installed binding, interruption/Desktop-off/low-SSD checks and next-run proof.

## Source/validation continuity

Runtime
packages remain pinned to their recorded commits; later documentation commits
do not alter them. PR263 is the sole integration PR. No bytecode tracking. Rust format passes; full format is currently
blocked by missing Prettier. Run narrow relevant checks/ops and record actual
exact-head CI separately from older green heads.

Earlier source/bindings remain in Git/private receipts and the full
[historical archive](HANDOFF_HISTORY_20261017.md), plus the
[Nightly archive](HANDOFF_NIGHTLY_HISTORY_20261027_0124.md).
