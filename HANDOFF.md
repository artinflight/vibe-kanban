# Dedup file-count repair — preserve live history

Read dedicated WakeWatch CONTEXT.md first. User wants dedup completion and rejects
Nightly commissioning. The speed objective is NOT met: previous conversion made
1,065,426files from38,791. Shared pieces must be packed, with real recovery and
compatible serving readers, before removing proven-unreferenced loose objects.

[Design/validation/remaining work](VK_DEDUP_PACKED_LAYOUT.md). Private evidence:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
Main recovery1 is independently accepted4/4 with terminal unit/process and exact
source/binary/probe hashes. MAIN_BUILD_ACCEPTED retains the success wake receipt.
Main candidate SHA4a14b76bc3f0ce85c702f099e901b89fe6cc962df3221ab476845a80d3d87957.
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
One script:vk-dedup-packed-replay-repair-build-v1.service,PID3051193,
invocationf9501ac898304b1d8610f5fb986f365f, same operation6cfd3d05308b431aa7e3a9a51d60b131.
Ten steps: replay input/output/archive tests, sealed server/probe and full EOF for
main/fallback. Same shared target/lease and resources; two-hour/600second guards.
Existing checkpoint-monitor-replay-repair1 owns next result/problem. Read exact
CONFIG/STARTED/PROGRESS/RESULT/FAILURE and unit; never replay uncertain dispatch.
No serving deployment or current-data acceptance in this build.

Next use bounded protected replay as a lossless reference on the same raw/loose
fixture data, compare repaired main loose/packed/fallback/return and protected
histories, require exact replies/pagination/table/settings/queue preservation and
corruption rejection. Old main's lossy page is diagnostic, not canonical history.
Guarded forward/backward migration, compatible live deployment, real B restore,
ordinary qualification and net staging accounting still remain. Daily hold stays.

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
