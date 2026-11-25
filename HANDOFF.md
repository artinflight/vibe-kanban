# Dedup file-count repair — preserve live history

November25: allthree reader-pin builds accepted (36Rust tests/18EOF checks).
Guarded packed publication, safe retirement and direct forward packing/reuse pass
14focused tests. One12-stage `packed-transaction-rehearsal-v1` is running with
fresh copied SQL and actual isolated-server custody. Existing WakeWatch is armed.
Live history, owners and daily hold remain unchanged. Production integration,
activation and final acceptance are open. Read CONTEXT for exact receipts/job ID.

Read dedicated WakeWatch CONTEXT.md first. User wants dedup completion and rejects
Nightly commissioning. The speed objective is NOT met: previous conversion made
1,065,426files from38,791. Shared pieces must be packed, with real recovery and
compatible serving readers, before removing proven-unreferenced loose objects.

[Design/validation/remaining work](VK_DEDUP_PACKED_LAYOUT.md). Private evidence:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
The original main build-only receipt remains historical. Its candidate was later
disqualified by the replay defect; use only the repaired artifacts listed below.
Compatibility success5b9ac81d-60f8-4344-a815-2a1825472aeb accepted once.
COMPATIBILITY_BUILD_ACCEPTED verifies both2959-file base seals/overlays,10tests
per variant, exact binaries/probes/build info and unchanged live identities.
Failureb7079ae7-dd0d-4f17-a6f5-726b7bcfc5a0 independently reconciled once.
CURRENT_DATA_V1_FAILURE_RECONCILED proves old unit terminal/empty, source pins,
private snapshots and serving hashes unchanged. Existing-reader baseline changed
only2copied running rows to failed/completed_at, as normal isolated orphan cleanup;
all other rows/fields/tables and main3history/settings/review/queue/frontend passed.
Packed-reader phases had not begun. Original failed evidence remains immutable.

Recovery1 failureceff03c2-cc86-470c-8f6c-3c03c55f88fc independently reconciled.
CURRENT_DATA_RECOVERY1_FAILURE_RECONCILED proves original source/pack/snapshot
pins and live owners intact, unit terminal/empty. Real API difference: one history
109versus103entries/different replies; both baseline and candidate log broadcast
input drops. Actual compiled full-EOF hash/length are identical (1,814,677bytes).
Fix replay; never weaken comparison or deploy the old packed main/fallback builds.

Proven protected-source-v1 differs from main base in only container.rs/msg_store.rs.
Its bounded Codex replay/failure handling and tests are applied to the branch and
new main/fallback overlays; scoped writer/private/native inputs remain intact.
Replay-build success5248d22b-de5e-421f-8aeb-5589fb4921fa independently accepted.
REPLAY_REPAIR_BUILD_ACCEPTED proves both source seals/overlays/artifacts,28focused
tests per reader, full-EOF samples and unchanged serving identities. Main artifact
SHAc4895660de59f1624205c1868301afaf0c1659189103230b274eb2e854330406; fallback
SHAc6362dd1c9b5285dec1413ba7ec0ed195369ae3f1dfaf915dfcd9ec3c482d290.
Older main/fallback packed binaries must not be deployed; protected is unchanged.

Failurea42d06f2-a84a-425f-96ac-f1156bea2339 independently reconciled; old job terminal.
No replay loss, content difference or table/later-write mutation. Four isolated
starts reproduce only the same leading system/error diagnostic swap at indices0/1;
every other entry/body/order/metadata matches, and both failed hashes explained.
CURRENT_DATA_REPAIRED_V1_FAILURE_RECONCILED and page-difference-diagnosis-v1 hold proof.
Eight tests validate the narrowly pinned2entry/2history comparison policy; raw
page hashes retained separately. No arbitrary sorting or relaxed content checks.

Failurebd227f38-7601-4dd8-82d6-e31094781566 independently reconciled. Five main
phases passed exact API/all-table/later-write checks. Protected failed at first
retained recovery: all18original capture dependencies are missing live, records
remain. Direct serving API also refuses them. Exact hash-matching saved originals
exist (16,713,100bytes); disappearance cause is unknown. See
CURRENT_DATA_REPAIRED_V2_FAILURE_RECONCILED and protected-originals-diagnosis-v1.

Successa6495901 independently accepted: CURRENT_DATA_ORIGINALS_ACCEPTED verifies
all11stages; five main transitions, protected6+18replies, exact pages/pagination,
settings/review/queues/frontend, original tables and later writes,3corruption
refusals, terminal/PIDgone and every input/live identity. Isolated proof only.

Both original restore attempts are terminal; never replay. Initial source0664
refusal published nothing. Recovery1 restored all18files and passed36normal
protected/public reply checks, then failed only on final resource PSI .18>.10.
LIVE_ORIGINAL_RESTORE_ACCEPTED independently revalidated all18bytes/inodes/sidecars,
source copies, SQL targets/settings/live owners and36API receipts with fresh PSI .01.
All recovered replies retain notices and original_capture_complete=false. Payload
allocation16,752,640B,parent delta4,096B,private SSD copies16,752,640B; account at end.
Original failure receipts retained, no re-publication or cleanup. Cause unresolved.

Packing success bdd7a069 independently accepted: all 274 groups, 3,639 source/SQL
bindings, 580 pack hashes and actual production-reader EOF proofs reconciled.
Selected files 1,057,171 -> 4,219 prepared files; staging allocation6,768,685,056B.
This has not changed the live layout or realized new net savings.

Normal-B success734d8efa accepted in PACKED_NORMAL_RECOVERY_ACCEPTED:223 complete
checkpoint triples,5,862actual restores/7,504,774,098B, both SQL points,5binaries,
1,465frontend files and root index verified. Old unit empty/PIDgone. All4,219packed
files restored with metadata. Current owners/artifacts/pointer preserved. Reuse
these accepted packed-data proofs; do not retransmit the unchanged whole tree.

Real retirement gap: both Rust archive readers dropped manifest descriptors after
parsing while reading chunks lazily. They now retain the original inode through
reader drop and advertise executionLogArchiveReaderPinProtocol=1. Two actual Linux
lease tests prove retirement refusal across manifest replacement, before read and
after EOF, until drop; exact bytes preserved. All12main archive tests passed.

ONE job: vk-dedup-reader-pin-build-v1.service, PID2439585,
invocation0072da5d1db04e59ac35bc5c173937f9. Evidence reader-pin-build-v1;
CONFIG/STARTED/PROGRESS/RESULT/FAILURE/SOURCE/COMMANDS plus per-variant ARTIFACT/READS.
Nine serial steps for main/fallback/protected: archive tests, sealed server, real
EOF probe. Same shared target/owned-build lease/resource bounds, two-hour cap and
600s progress guard. Existing checkpoint-monitor-reader-pin1 owns next wake.
No live reader change, V2 publication, loose retirement or Nightly commissioning.

After success accept all3builds, add only changed artifacts to normal-B recovery,
then implement/qualify guarded forward/backward publication and retirement. Retain
replaced manifest inodes in journals and hold their exclusive kernel leases before
retiring any unreferenced loose pieces; require complete pin-aware reader/consumer
qualification plus per-object guards. Old byte-compatible builds lack that proof.
Migration/forward publisher remain unimplemented. Then complete measured authorized
live activation/latest-data fallback, ordinary behavior and full net/file-count/
performance accounting including all staging and B growth. Daily hold stays.

Original operation6d4d022ab2f84d1ea72f39d6a6382d1c, catch-up
 e3787e2e49124284a1f023d061f967f7 and automatic8d866da98492464f9867137092623b20
remain accepted and immutable. No V2 source manifests have been installed.
Main70372/invocation81dd8bb21f894aa1bd286f8f0029b770 and protected2573723/
server2573735/invocation9c0b08030aa445318309e41dff070786 remain the serving owners.

The ordinary daily timer was stopped, then restarted by mcp-boot-recovery.
Final TIMER_MAINTENANCE_HOLD_ACCEPTED pins its owned condition/drop-in/flag,
preserving enabled schedule and blocking conversion during repair. Earlier
runtime-mask proof failed because user-unit precedence won; that mask is removed.
Release only exact owned hold after qualification, then start same timer.

No Nightly successor, calendar, new agent, goal or polling loop. Preserve every
backup epoch, failed input, pending draft, selection and other owner. Previous
68.82GiB net accounting predates new qualification/build staging; refresh at end.
Privileged3731-inode audit publication was rejected by automatic approval;
retain that limitation and never claim zero open originals or bypass it.

Previous handoff: [before packed repair](deployment-history/20261124-before-packed-repair/HANDOFF.md).
Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).

Optimized read checkpoint now passed: all five histories/three samples match at
full EOF; summed medians3.877s loose versus3.769s packed(about2.8% faster, warm
cache only). Large live/UI speedups are not demonstrated. Main build is accepted;
compatible pair/current-data and packed recovery passed; reader-pin builds are running.
