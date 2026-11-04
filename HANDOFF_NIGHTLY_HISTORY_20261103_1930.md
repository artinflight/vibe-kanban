# Nightly restore verified — October28,08:13EDT

Current goal SATISFIED: restore verification completed, discovered bugs fixed,
verified dependency handoff delivered to existing Staging. No backup recapture,
backend restart, production switch or schedule activation occurred. Recurring
Nightly commissioning is a SEPARATE unfinished task: schedule OFF, nextNONE.
Original22–04Toronto capture cycle remains expired; its pointer was not advanced.

## Actual acceptance

Source09327026008464ebb9ffcc4507631da50b2a62ce (solePR263) passed the actual normal
UID1000 consumer on existing B-backed VK-Candidate-20261009. Result at
2026-10-28T08:13:34.667609-04:00; measured normal-only phase1349.8s.
798077namespace members,660381files/200777178777logical bytes,
221SQL proof records.15mandatory actual readbacks/368903595B passed
fullhash/Linuxmetadata; working90 SQL integrity OK + schema matched. Sequential
RAM payload peak169500672B. All15sample receipts match the final result.
Previous162.70GB cold restore and all valid layers/images remain; no fresh full
200GB decode/copy is claimed. Original7783archive gaps and supplemental epochs
stay explicit; captured points are not a live writer fence.

D=/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261026
P=D/restore-only-093270260-20261028; C=D/b-controls-v1.
P/RESULT.private.json SHA48eca5b2efdf4c4b8544855dd40bac3d84beae783e4b6fa1eab49050a2fc5f6b.
P/READBACK_PROOFS.private.json holds15actual sample receipts; SOURCE_VALIDATION
holds151focused tests +13applicable exact-head hosted checks (consent job skipped).
Rust/ops/diff checks pass. Full local format stops only at missing Prettier.
Former owner1103083/start39592858/unitvk-nightly-retained-restore-093270260-20261028
is terminal/MainPID0/emptycgroup. No consumer/retry/timer was left armed by this work.

## Durable B proof and delivered Staging interface

P/DURABLE_B_PROOF.private.json: immutable B controls image
0720a45cade8fc4e5fd3a30dda10f409bc23b5bcc762c2f696517e416c2daace.sqlite,3207168B;
B:/vk-backups/vk-nightly-efficiency-20261026/controls-v1. Independent full stream
readback + separate SQLpart reopen/hash/count PASSED. Payload includes candidate,
exact packet/descriptors/proofs, actual result, pinned normal-reader source,
source validation and current runtime metadata observation.0new source bodies.

Matching shared receipt:
/mnt/vk-storage/vk-git-recurrence-release-20261017/NIGHTLY_RESTORE_VERIFIED_20261028.private.json
and C/VERIFIED_RESTORE_CONSUMER_HANDOFF_20261028.private.json;
SHA70c40501ceb7798a62f61e914fba73a57717990d05fa2bb63c7e4f0148271ce4.
Old authoritative NIGHTLY_RELEASE_CONSUMER_HANDOFF.private.json remains untouched.
Verify capsule/header/part digests, then consume its pinned source/packet under
fresh ordinary B identity/STOP/health/access/capacity/lease and finite read-only
admission. Never reuse the expired packet deadline as a new admission.
Staging still owns current-live pin comparison and a consistent bounded final
journal/file/SQL delta before any separately approved cutover. No global source
inventory or repeat cold restore is needed merely to recover this accepted set.
Runtime observation around07:55EDT:14/14captured pins +frontend/DB links unchanged;
that metadata observation is not current SQL freshness or a writer fence.

## Actual failures and fixes preserved

C0 native audit completed06:30 (P's native_proof_reused_from pins its exact
candidate/source). Normal C0 then hit its separate90min verification admission
at07:37:12 inside local-RAM SQLite checking; no drive fault. It queried B paths
per1000SQL ops and duplicated provider checks. Current source coalesces only
nested checks, pins external root IDs directly and keeps resource/time checks
inside local SQLite plus full dependency checks at archive access/acceptance.
Outer native B STOP/identity/health/capacity and kernel leases remain. No numeric
resource threshold or security policy was relaxed. Earlier provider/base-name/
ordered-history fixes also passed the complete native audit. Native audit/map/
SQLAPI/images/bodies were reused, not recaptured or relabelled.

The failed169.5MB temporary RAM duplicate was absent after VM idle; its sealed
B original remains. Old failed run/diagnostics/native proof and earlier recovery
sources stay preserved. Do not treat old partial/timeout receipts as accepted.
D/LATEST_STATUS.private.json now records this actual accepted restore and shared
handoff; it is not recurring-service commissioning acceptance.

Earlier details survive in [06:08history](HANDOFF_NIGHTLY_HISTORY_20261028_0608.md),
[03:46history](HANDOFF_NIGHTLY_HISTORY_20261028_0346.md), private
D/HANDOFF_BEFORE_NORMAL_ONLY_20261028.md and [original history](HANDOFF_HISTORY_20261017.md).
See [Nightly contract](VK_NIGHTLY_BACKUP_EFFICIENCY.md) and
[overnight contract](VK_NIGHTLY_OVERNIGHT_ACCEPTANCE.md).
