# Dedup file-count repair — preserve live history

Read dedicated WakeWatch CONTEXT.md first. User wants dedup completion and rejects
Nightly commissioning. The speed objective is NOT met: previous conversion made
1,065,426files from38,791. Shared pieces must be packed, with real recovery and
compatible serving readers, before removing proven-unreferenced loose objects.

[Design/validation/remaining work](VK_DEDUP_PACKED_LAYOUT.md). Private evidence:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
The main-build-recovery1 job reuses main-build-v1 frozen source/native/private inputs;
only the packed reader and qualification probe change. Reconcile CONFIG,
STARTED,PROGRESS,RESULT/FAILURE and actual unit before any action. No uncertain
relaunch. Build does not deploy. Existing WakeWatch will handle its checkpoint.
V1 stopped on its45-minute cap while progressing, with10 optimized reader tests
passed and no compiler errors. Old job is terminal; original receipts retained.
Recovery unit vk-dedup-packed-main-build-recovery1.service/PID2109474/invocation
2b2f09983334496691cc5d1bc95d3c98 runs the optimized probe first, then resumes server
compilation using the same artifacts.60-minute finite cap and600-second stall
stop; memory/SSD/ownership guards unchanged. No model polling.

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
cache only). Large live/UI speedups are not demonstrated. Server build continues;
normal existing WakeWatch tick sees recovery1 at3/4 with no errors.
