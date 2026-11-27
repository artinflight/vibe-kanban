# Deduplication state — November25 packed-layout qualification

The original finite log conversion and catch-up are accepted. Full deduplication
acceptance remains open because the first layout reduced bytes while increasing
file count from38,791 to1,065,426. The user requires storage AND performance repair.
New operator scope (November25): prepare workspace archive separation, automatic
movement on future archive actions, automatic message-triggered revival, and
Nightly active-payload selection before the managed restart. Nightly scheduling
remains off. Actual backend restarts belong to the external managing agent.
[Archive integration status](VK_WORKSPACE_ARCHIVAL.md): source-only durable intent
outbox and metadata inventory implemented; mover/revival/Nightly integration is
unfinished. Eleven fixture tests pass. Read-only inventory:1,052 archived,
244 active;1,016 metadata candidates, with no movement or exclusion authority.
No live schema migration or payload movement occurred. The sealed dedup-only
activation package does not include this new feature.

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

The paired private switch rehearsal is independently accepted. Both current-copy
SQL images (306,405,376bytes) restore through actual normal B; eight receipts
reconcile and all private units are empty. The complete private switch took54.423s,
including33.189s recovery and13.399s activation. Backup refusal and latest-copy
fallback also passed. This is private loopback/empty-ledger evidence, not a public
host outage guarantee or final current SQL capture.

A new unarmed paired-reader package passes read-only owner/configuration checks.
It preserves both current SQL paths and refuses an unapproved worker invocation.
The matched guard and existing settings are packaged; post-activation process/
mount bindings will prepare the existing daily configuration without releasing
its hold. Six transition ownership/uncertainty tests pass. The first exact-engine test failed on a private port collision; both journals,
180 source pins and complete test-unit cleanup reconcile. No B capture began and
production stayed unchanged. A bounded diagnostic found two npm discovery
processes behind the repeated69s helper wait. The isolated fixture now reserves
ports outside the ephemeral range and uses offline npm discovery; three port
regressions pass. PACKED_PAIR_PACKAGE_ACCEPTED now accepts all five corrected stages. The private
switch13.678s and fallback15.525s preserve later writes; both test units are empty.
Two B checkpoint triples restore93files/1,260,029bytes and add1,576,960encoded bytes.
The source-sealed finite publication entrypoint now binds the accepted actual
activation, existing lease and B mapping and refuses uncertain replay. Five new
activation/custody tests pass. PACKED_FINITE_PACKAGE_ACCEPTED verifies all three source-package stages and
188source pins. Actual read-only production preflight passes; two B triples
restore87files/759,101bytes, adding1,060,864encoded bytes. The exact mapping was
reopened without recapture. All scripted units are inactive/empty. A concrete
activation/fallback plan is prepared and unapproved invocation is refused before
dispatch. Fresh explicit cutover approval is now required by the restart protocol. No live packed conversion is admitted before actual paired activation.
The failed test took151.979s for its successful first transition, so the earlier
54.423s private result is not a current interruption promise.

Daily conversion remains held with its saved enabled05Toronto calendar preserved.
Still required: explicitly approved live reader activation, its actual capacity
check and daily post-activation binding, followed by
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
