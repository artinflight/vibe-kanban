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

Normal Desktop-B recovery covers all4,219packed files, both recorded SQL points,
five earlier artifacts and1,465frontend files. The new reader binaries and exact
311-plan mapping are now independently accepted too:25checkpoint triples,
94restored files/341,068,615bytes, including21software parts. New control input
was331,392,539bytes; the9,676,076-byte map was reopened without recapture. Three
actual normal-B admission groups passed. All current selected originals,
metadata/sidecars/both SQL bindings/prepared versions and live owners reconcile.
The exact successful unit is inactive/empty; PID3805715 is gone. Do not replay it.
Recorded SQL snapshots must still be refreshed at the final boundary.

The finite packed controller now retains one exact selection under the existing
converter lease, writes intent before each batch, refuses automatic replay and
seals the completed journal. Its production adapter binds actual live readers,
writer custody and normal B, and requires full-EOF verification through probes
from both exact reader builds before original retirement. Reader verification
is reused after retirement only while published manifest versions remain unchanged.
Forward selection checks both SQL owners and preserves active/pending/unbound
captures. It prepares raw histories directly as packs, reusing session chunks;
no loose-object fanout is created. Production forward/daily invocation
wiring is still unfinished. Eleven new tests, eleven admission regressions and
fourteen existing publication/forward regressions pass.

The finite controller rehearsal is independently accepted. Two backward and one
raw-forward transaction reduced7,826copied files/71,741,440allocated bytes to
18files/54,546,432bytes. Three ordinary API phases preserve60original tables,
four later-write sentinels, histories/pagination/settings/review/queues/frontend;
only one legitimate startup orphan correction occurs. Both exact reader probes
verify full EOF before retirement. Latest-copy fallback passes. All31fixture
journals reconcile; their recovery is explicitly not normal Desktop B.

The forward recovery adapter captures only new bodies and restores its mapping
and catalog from actual Desktop B. Identical existing bodies retain their old
selectors, with new names/metadata in the separately restored mapping. Four new
tests cover reuse, new-body capture, nonbeneficial refusal and remote corruption
without local fallback. Actual forward recovery is independently accepted:
six checkpoint triples/84files/5,948,994bytes restored; one1,577,508-byte original
remains unchanged. Its212,719-byte prepared graph was restored, then reused in
a second namespace with zero new body captures. Exact unit empty/PID180142 gone.

packed_incremental.Adapter now connects these functions to the existing daily
runner/lock, failure hold, saved daytime window and monitoring result contract.
One normal-B context serves the run; new body catalog entries preserve earlier
selectors. Batches stay within one session. Measured selected-file/pack/directory
allocation is separate from staging/whole-filesystem savings. Three new integration
tests and7runner/9automatic regressions pass. The daily timer remains held.
The actual daily runner rehearsal is independently accepted: four stages, three
ordinary API phases,60original tables/four later writes, three raw histories and
both reader EOF probes. Monitoring verification and the second idle run pass.
All16fixture checkpoints/70restored files reconcile. Fixture restoration remains
explicitly distinct from accepted actual normal-B recovery. Old unit empty/PIDgone.

One packed-switch-rehearsal-v1 job now qualifies a matched capacity guard, paired
private service activation, backup-refusal recovery and compatible fallback with
latest private SQL. Its successful path restores both fresh detached SQL copies
through actual normal B (384MiB total cap). It measures backup and activation
separately, preserving production service/data/route/capacity ownership. Private
loopback and empty capacity fixtures are not final production qualification.

Daily conversion remains held with its saved enabled05Toronto calendar preserved.
Still required: accept paired-switch qualification and finish the actual activation/
fallback supervisor, bind the daily post-activation configuration, perform
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
