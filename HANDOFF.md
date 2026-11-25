# Dedup file-count repair — preserve live history

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

One job:vk-dedup-packed-current-data-repaired-v2.service,PID3955951,
invocationda8b0c5ce8574fae96fbffb67158c4d1, same operation6cfd3d05308b431aa7e3a9a51d60b131.
Same accepted binaries and11steps, fresh DB copies/reused packs. Exact same-data
reference/loose/packed/fallback/return, protected replies/pagination, all tables/
later writes/settings/queues/review/frontend; rejects broadcast loss/corruption.
Only strict expected initial orphan bookkeeping and proven diagnostic pair ordering
are allowed. Existing checkpoint-monitor-current-data-repaired2 owns next wake.
Read CONFIG/STARTED/PROGRESS/RESULT/FAILURE/unit first; never replay uncertain work.
Same two-hour/600second/resource/namespace guards. No live changes or full acceptance.
After success complete guarded migration, deployment, actual B recovery, ordinary
qualification, retirement and net staging accounting. Daily hold remains.

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
compatible pair passed; actual current-data/recovery acceptance remains unfinished.
