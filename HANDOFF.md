# November24 checkpoint wakes replace model polling

The user requested WakeWatch checkpoints/problems instead of long model polling.
Existing resource-guard hook now uses dedup completion-20261124/checkpoint-monitor-v1.
Same timer, ledger, chat, owner/settings and admission; no new controller or agent.
NORMAL_TICK_ACCEPTED proves a real timer check with no extra attempts and unchanged
prior batch receipts. The already accepted catch-up success was settled using its
pinned acceptance/result, preventing a redundant wake. Import-v2 itself is unchanged.

The sensor pins its CONFIG/STARTED and PID/invocation, reads actual progress, and
wakes on terminal result, failure, changed identity, missing/corrupt evidence,
600s without progress or its original deadline. Healthy progress never wakes.
Current config covers import-v2 only. At the actual checkpoint reconcile every
receipt, start the next prepared finite phase once, and arm the SAME hook for that
phase's actual receipt format before ending the model turn. Never force a manual
tick, duplicate a running script or resume repeated model polling. Full Nightly
restore/ordinary qualification/calendar and final accounting remain unfinished.
See dedicated CONTEXT.md first; subsequent notes retain current job identities.

# November24 completion — automatic conversion accepted, Nightly gap accepted, import running

Read dedicated WakeWatch CONTEXT.md before alerts. Original finite operation
6d4d022ab2f84d1ea72f39d6a6382d1c is complete and immutable; never replay it.
Its archive/current-SQL/runtime/frontend recovery and ordinary UI proofs remain.

Catch-up e3787e2e49124284a1f023d061f967f7 is terminal/inactive:110batches,
374resolved,278converted/96nonbeneficial preserved. In dedup completion-20261124,
CATCHUP_TERMINAL_ACCEPTANCE verifies59journals,590B-restored control bindings,
full manifest/original EOF and metadata. Additional automatic qualification
8d866da98492464f9867137092623b20 accepted one converted log; no newly eligible
closed files remained. Active/pending/invalid captures are untouched.

Sealed automatic-v3 is installed under production-20261117/incremental-20261124.
Config SHA24ad8dc495b28fa62d37ded36a4c289384c3b2b1f02308079973adfc273e9b60.
vk-log-dedup-daily.timer enabled05:00Toronto; nextNov25 10:00UTC. Actual run uses
the original production/B locks and pinned adapter. Never replay ACTIVE or
AUTOMATIC_HOLD. Same WakeWatch timer/ledger/chat preserves pending finite success;
source/event errors null. Actual unchanged Rainmeter PID128024 shows WAITING,
resolved3731. Routine healthy daily jobs create no model continuation.

Nightly prior owner execution is terminal/idle. Current packages are under
vk-nightly-efficiency-20261017/commissioning-20261103/completion-20261124.
Existing observer-v22 fully ready:PID1266882/start274355047,
invocation589ec42327a146d7b932f8c8d46a6498, instanceabd172673978422cb0bc3db939ec0958.
All125roots/2,289,027watches covered, zero errors. Full memory qualification passed
under unchanged1536MiB high/2GiB max/zero swap. Runtime watchlimit3145728 verified;
persistent sysctl question is pending. Do not ask again to raise the live limit.
Existing journal-v40 unit and timer passed real independent B reopen/exact ACK.

Gap-v22 passed17:07UTC:2,449,223paths/150,028directories, zero pending/replay
errors; independently reopened normal-B result. Gap unit is inactive/Main0/exit0.
One existing-checkpoint import now runs:vk-nightly-converter-import-v2-20261124.service,
PID2526912/invocation2f90588c2a4e41ec8c64dcab81912e90. Config SHA
 948cd315b60b439138d96945882cb2957e5cfd44744b2f2f878cfa29c185c0ee.
Read actual v2 STARTED/RECOVERY_ADMISSION/PROGRESS/RESULT and unit. V1 stopped
at its4GiB catalog ceiling after222commits; all exact bindings/next absence and
native quick_check passed. V2 reuses those records with16GiB ceiling,>=40GiB free
admission and unchanged20:07:44UTC deadline/other guards. V1 artifacts survive.
Never replay current STARTED. Scope456components/3635logs/1194existing B checkpoints.
Next: accept imports, compose current namespace, qualify files/SQL/runtime and
independent full restore, then ordinary incremental/interruption qualification
before22–04Toronto/hard04 activation. Current-v41 definitions remain unstarted.
Nightly calendar remains OFF. Old outboxes/latches/epochs and B ownership survive.

Final accounting must include all new staging and growth. Exactly24 temporary
closure carriers were retired with independent B proof/exclusive inode leases:
440,885,248allocated bytes. New accepted runs retired101,183,488more duplicate
carrier bytes. Keep catalogs, failed remote inputs and deferred workspace/archive
cleanup. Privileged old-original descriptor audit sharing/execution permission is
pending after automatic approval rejected publication; never bypass that hold.

Main writer70372/invocation81dd8bb21f894aa1bd286f8f0029b770 and protected server
2573735/unit2573723/invocation9c0b08030aa445318309e41dff070786 remain unchanged.
Public TLS/index/health/download checks and earlier desktop/mobile viewport and
semantic history acceptance are retained; no physical-phone test is claimed.
See VK_DEDUP_COMPLETION.md and fixed private WORKPLAN. No new goal, agent, model
loop, backend restart or Git push. Full objective remains unfinished.

Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
