# Deduplication state — November25 packed-layout qualification

The original finite log conversion and catch-up are accepted. Full deduplication
acceptance remains open because the first layout reduced bytes while increasing
file count from38,791 to1,065,426. The user requires storage AND performance repair.
Nightly commissioning and deferred workspace/archive cleanup are excluded.

All274 prepared session groups,3,639 histories and580 packs are independently
verified. Selected files go from1,057,171 to4,219 in preparation, using
6,768,685,056allocated bytes including directories. This is staging, not a live
file-count reduction or additional net savings.

Allthree reader-pin binaries are accepted:36Rust archive tests and18actual full
EOF checks pass. They retain manifest descriptors for safe lazy-reader retirement.
The repaired bounded replay behavior/private/native/scoped inputs are preserved.
Only these newest candidates should be used; prior packed candidates are history.
Live main/protected readers and frontend remain unchanged; see LIVE_DEPLOYMENT.json
and actual process/hash checks. No packed manifests are published live.

The12-stage current-data/transaction rehearsal is independently accepted. Main
reference→candidate→migration→packed→fallback→candidate and protected comparisons
preserve60/59original tables and9/4later-write sentinels. Histories, pagination,
settings/review/queues/frontend match; allthree corrupted packs are refused.
Actual isolated scoped publication survives interruption and busy old readers;
7,854copied loose objects retire safely across three sessions. This is isolated
qualification, not live deployment or whole-objective completion.

Normal Desktop-B recovery already covers all4,219packed files, both recorded SQL
points, five earlier software artifacts and1,465frontend files:223checkpoint
triples and5,862independent file restores are accepted. New reader artifacts and
new migration metadata/tools need their own bounded recovery closure. Current
SQL points must still be refreshed at the final boundary; never overwrite later data.

Production admission now binds the exact B-restored plan, original metadata,
sidecars, actual reader root/database mounts, both SQL owners, scoped locks and
fresh immutable B bodies. Eleven tests pass, including corrupt/missing remote
bytes with good local copies, owner loss and foreign file/metadata refusal.
Prepared session groups are split into311transactions within64files/2GiB each;
shared packs and all old backup epochs remain unchanged.

The completed311-plan mapping is preserved and freshly revalidated against all
3,639original files/metadata/sidecars, both SQL owners and4,219unchanged prepared
members. Recovery1 stopped before any B connection because the shared lease was
busy. Recovery2 restored the9,676,076-byte map through actual normal B, then
rejected a lowercase software checkpoint name before any software capture.
Both exact terminal jobs and all receipts are independently reconciled; there
are no uncertain captures. Live history/readers remain unchanged.

One finite `packed-admission-recovery3` is running. It reopens the accepted map
checkpoint read-only, protects only new reader software/tools, checks three
actual B admission groups, and seals the index. It never recaptures the map or
unchanged6.77GB packed data. A five-minute lease-availability preflight preserves
other owners; the original recovery context is still attempted only once.
Every generated checkpoint name is checked before the connection opens. Twelve
focused tests pass for lease ownership and checkpoint bounds/no-replay/names.
Existing WakeWatch owns its next event; no extra watcher/goal/agent/polling loop.

Daily conversion remains held with its saved enabled05Toronto calendar preserved.
Still required: accept current recovery, finish finite migration/forward controller
integration and the measured serving-owner activation/fallback package, perform
live publication/retirement and ordinary desktop/mobile/history/review/settings/
queues/monitoring checks, and finish current recovery plus net space/count/
performance/growth accounting including ALL staging and B growth.

All18previously missing historical originals are restored and their36normal
protected/public replies verified. Why they disappeared remains unresolved.
Previous net reduction73,893,642,640bytes(68.82GiB) predates new packing/build/test
staging. Privileged old-open-file visibility and remote directory allocation are
not fully verified; maximum savings/exclusive filesystem attribution are unclaimed.

[Packed design/evidence](VK_DEDUP_PACKED_LAYOUT.md).
[Previous state](deployment-history/20261125-before-packed-admission/STATE.md).

Full historical archive: [STATE history](STATE_HISTORY_20261017.md).
