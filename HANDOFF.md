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

- Source observer V10 is terminal13:10:23EDT, MainPID0/exit1, epoch
  2f32f888fa134b9496467b4fba4fc0e7. Unknown watch779294/mask8; intact SQLite
  SHA61977f098f9dcb58b1bd804c40c635ce585e0dfeaf361a8be602af2b786be89d,
  cursor5807284/B ACK5803171/64pending names. Receipt b-controls-v1/
  INODE_V10_TERMINAL_GAP_20261027.private.json. Preserve the epoch and spools.
  A later corrected observer and metadata gap reconciliation must precede
  current baseline acceptance; prior journal component proof stays historical.
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

## Retained component inputs

- terminal-gap-recovery-inodes-v10:783552paths/0errors, completed10:21EDT.
- qualification-stage-B-inodes-v10:18539points,14031retained/4494pending,
  13SQL discoveries/1deferred,4971262421hashed bytes; completed10:34EDT.
  Both normal independent B reopens passed. Do not repeat these phases.
- file-points-worker-B-inodes-v1 is terminal after10:08EDT SQLite BUSY;
  all4398accepted history points remain. The successor retries only final
  idempotent metadata acceptance, never a completed upload/readback.

## Preserved gaps and corrected failures

V9 stopped09:12EDT, epoch21487895bcd24324869f9f8e636f8d5e. Its SQLite is
intact through4081780, with1317pending names and B acknowledgement3029482.
It records unknown-watch897862/mask8; the unsealed oversized in-memory report
was not retained, so its duplicate/error-size makeup is unknown. All originals,
spools and fault evidence remain. The later V10 set does not repair that epoch.
Actual B terminal-gap proof42851975fc11ad79e25d214472fc056b2d97cd36c0958cfac41582a16961189b
is in journal-terminal-gap-proofs; normal independent reopen passed.

V10 inherited a1GiB cap for a1258803200B map; SQLite FULL was a wrapper
budget error. The corrected4GiB phase budget and verified B temporary placement
retain all physical floors. Full diagnosis/proofs are in the Nightly guide.

V11/V12 stopped on native15s SMART read timeouts; original traces survive.
V13 completed after the tested finite full requalification fix, with unchanged
STOP/access/counter checks and command deadline. No blind denied-write retry.

Body phase vk-nightly-B-file-points-inodes-v2-20261027.service is terminal
13:12:40EDT, MainPID0/exit1: source observer no longer ready. STOP is authoritative.
STATUS retained604completed points,4735398282source bytes/1398510917encoded sent,
0SSD payload/index bytes. All completed points/partial CAS objects survive;
reuse their actual B acceptance ledger, never repeat completed transfers.
Installed source028c45e14f8ecdc7346ac8fb9ba3775f577eb01b, configSHA
50c2f289a1963ec70c51db8dd511b3ea070716513ea8e68ef4ea8b099f058735.

RAM stress reproduced late inode events after IN_IGNORED. Corrected tracking
retains a bounded8192-name retirement ledger and reobserves known dirty names;
unknown WDs/overflow/access/root loss remain faults. Pinned FD enrollment fixes
symlink ABA/transient name races.198 focused tests pass, including5000 mixed
mutation rounds. Do not overwrite old packages or claim old epochs repaired.

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
runtime/served frontend remain a separate later binding. Old runtime observations are preparation, not final-current acceptance.
The runtime-dependencies-20261027-v1 component still needs gateway.mjs3048B
and route.json152B; always sample them outside the117-root kernel plan.
Fresh13:02EDT 3200B source qualification is in b-controls-v1/
RUNTIME_DEPENDENCY_CURRENT_SAMPLE_20261027.private.json; no B body copied.

Current-set acceptance still needs final body/SQL/runtime integration, a sealed
authenticated B-backed current descriptor and independent composed restore.
B-native sealing, complete descriptor construction and separate finite runtime
component adoption are implemented/tested. Adopt fresh gateway/route points
after body ownership releases; kernel117-root scope stays separate. Then use
the normal independent reader; source tests are not actual current acceptance.
Then finish the normal incremental cycle/restart delta interface and actual
installed worker/config/health integration. The older calendar invokes the
legacy supervisor/job path; do not enable it merely because its fixtures pass.
Commission the02:00America/Toronto schedule only after whole acceptance, exact
installed binding, interruption/Desktop-off/low-SSD checks and next-run proof.

## Source/validation continuity

Installed packages remain pinned; later source/docs commits do not alter them. PR263 is the sole integration PR. No bytecode tracking. Rust format passes; full format is currently
blocked by missing Prettier. Run narrow relevant checks/ops and record actual
exact-head CI separately from older green heads.

Earlier source/bindings remain in Git/private receipts and the full
[historical archive](HANDOFF_HISTORY_20261017.md), plus the
[Nightly archive](HANDOFF_NIGHTLY_HISTORY_20261027_0124.md).
