# October 4 Updated Version Live

## Outcome

The updated version serves https://vibe.local through gateway4720 to5461.
Candidate vibe-kanban-blue-production-20261004.service is PID1369037, running
and enabled for future boots. Original PID3059021 remains loaded/frozen and
disabled for boot, with latest-data same-process cutback available. No old
database was restored and no handover was repeated. No HYROX/accounting release
was deployed. Accountingafe094a1 completed exit0 at19:12:38UTC and the parent
confirmed it held idle before the operator's explicit Go. The final drain had
no other active executions and no queued messages.

Release main e53ae4a7e5c8c05642f7bf3b9e3921bc8ebcd434 and staging
86d1c083a1b4bf8590c9d71d91d6c82de1bd1aeb share tree6963ed5d5dc174e1f40a84e71e8975cd82c716cc.
Application version remains0.1.42; do not infer deployment identity from that
number alone. Actual backend SHA256fb70e951621b4ca85de09c8cd0fbf7ab2ef863d47810e2daef4122f9770f6b6c
and frontend index SHA2569bfb651e955be2a4b95cb0b1632f0a30a355c09aa7649bdb5faceebe10cd721f
match the accepted build. Browser entry is index-Va7ho6jA.js.

## Finalization Incident

Attempt /mnt/vk-storage/vk-blue-reprepare-20261004/cutover-20261004T194755Z
successfully captured latest data, activated the candidate and passed preservation,
runtime and capacity checks. The outer controller then failed because the new
service's drop-in directory did not exist when writing zz-active-owner.conf.
The mocked test used an existing parent, so it missed this installation error.
Automatic recovery put routing in maintenance and stopped CU, then refused to
interrupt this already-resumed maintenance execution. It did not restore a DB,
stop the healthy updated backend or thaw the old backend.

Acceptance repaired only finalization: verified the already-running owner and
same original frozen PID, created the missing directory/boot override, enabled
the candidate, routed to that existing owner and restarted CU. External processes
resumed. Original controller-failure.json and emergency.json remain intact;
finalization-repair.json records the repair. Do not replay the consumed attempt.

Standby receipt19:48:04.536UTC and restored public route19:50:30.356UTC bound
the interrupted window at approximately2minutes26seconds. Final backup itself
took43.675seconds, not the100.304second rehearsal. Backend activated19:48:55UTC.
These are actual handover timings, not total preparation duration. The resumed
evening task began19:24:47UTC; preparation to controller start19:47:37 took
approximately23minutes, including fixes, tests, full rehearsal and Desktop proof.
This does not include earlier failed preparation, agent-drain waiting or the
subsequent acceptance/documentation. Do not describe it as a seconds-long restart.

## Acceptance Evidence

live-acceptance.json verifies current routing/binary/frontend, SQLite quick_check,
all existing IDs and protected tables,367 existing attachment hashes and6061
native history references. Historical2282 missing references remain unchanged;
they are not new losses or claimed recovered. All12 saved messages and original
executor/model/reasoning configuration survive. The original session75bc68d4-aa55-4914-a695-f20c46a13e4c
continues native thread01a03e74-2c1a-72f0-9e00-8e4293fe910d in execution
764419a7-cc32-4c7d-88da-ef35341fc421. No replacement conversation was created.

Review snapshots retain13665 existing turn flags. One new turn explains13666
afterward through the review event journal; no stale flags were restored. Public
1440/390 browser checks show the actual five-workspace Needs Attention list,
opening/foreground clear behavior, no polling/hidden clearing, all12 messages,
seven models, four reasoning levels and live WebSocket frames without page errors.
The read-only browser harness intercepted seen writes; it did not clear actual
operator flags. These are mobile-sized browser checks, not physical-phone tests.

Live unique attachment upload/download/delete passes, and all three required
attachment roots retain owner mcp and0755 permissions. Only the test upload was
removed. Existing dot connector get_execution/get_agent_replies/list_projects
calls work through the same gateway; its service PID2433192 is unchanged.
CU PID1387869 runs with VK on CLI0.159.2 and the identical private routing feed.
The resumed turn's decision/binding is imported by CU. Seven-model qualification
is current and exact-identity; no broader suite or new inference probe was needed.

Turn Steer versus Stop and native-goal behavior passed earlier private testing
against this exact application artifact, not new synthetic production executions.
monitor-local1179, fitrdy-manager1147 and external native processes resume; older
standbys remain frozen and dead legacy services remain inactive. Logs retain
preexisting missing July screenshot cache, unknown native-item and lagged
subscriber warnings, also present before the switch. Do not claim empty logs.

Final frozen backup c37409afa0154405a5d3a04bf4c7b68b is Desktop-verified under
B:/vk-backups/vk-autoswitch-scope-release-20261001,60372506bytes, SHA256
bfe4edd6efcfa0e6cd2f833b87d55912dd30f966fb6931eb9abc978c7fc45d6e.
Keep its parent chain, authenticated recopy metadata, supplemental dot/carConsole
backup060f043d and software193909Z archive. Software restoration verified2491 files.

## Next Preparation

VK_HANDOVER_FINALIZATION_20261004.patch records the isolated correction: inert
installation creates the boot directory, preflight checks it, finalization creates
it idempotently, and emergency handling retains an already healthy/preserved
routed owner instead of disrupting it after conversation continuation. Fourteen
controller tests pass, including missing nested-parent and healthy-owner recovery
regressions; patch dry-run passes. The consumed sealed controller is deliberately
unchanged. Incorporate and reseal this patch in the next unconsumed preparation.
No additional production interruption is necessary for these operational fixes.
