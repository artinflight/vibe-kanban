# October 4 Evening Cutover Preparation

## Authorization And Safe Drain

Seamus explicitly says Go after the parent confirms accounting is safely idle.
Executionafe094a1-8dea-442e-acf9-77bb4fd72bc2 completed exit0 at19:12:38UTC,
with pushed8f985c20212ffc8a27561f33bfca19b92f6d2257. The parent holds that session
idle. Failed follow-up e3134eee is not pause confirmation. Native process checks
show the original accounting writer has exited; only the original VK maintenance
execution remains and queues are empty. No competing follow-up or abrupt stop
was used. The latest confirmation supersedes the earlier hold. No HYROX or
accounting release is in deployment scope.

## Release And Backup Corrections

Current production remains Green3059021 on5411 and gateway4720. The new candidate
is inactive vibe-kanban-blue-production-20261004 on5461/5462. Main e53ae4a7e,
staging86d1c083a and build9c2e04d72 share tree6963ed5d5dc174e1f40a84e71e8975cd82c716cc.
This published application release is reused; no unpushed application work ships.
Fresh audit of19 In Staging issues finds no new discrepancies. Retained historical
exceptions are not silently recategorized as merged work.

Two worktree folders moved across parent directories during the long pause.
The backup checker incorrectly required their source-removal event under the
destination parent. Exact old/new paths now have explicit mappings; each source
must be in protected scope with an observed directory-removal event and covering
watch. The whole destination subtree is independently hashed at both fences.
Source tombstones and all journal changes remain included. Missing evidence,
unknown moves, source-root loss and unverified metadata still block capture.

The recopy path-membership check now uses equivalent component-boundary prefixes
instead of repeatedly constructing path ancestors. A sibling-prefix regression
checks that similarly named unrelated paths are excluded. Supplemental backup
covers dot connector code/runtime/private configuration as well as carConsole.
Its existing read-only connector calls through gateway4720 pass before cutover.
VK_BACKUP_RESUME_20261004.patch records the revision against the earlier154759Z
package; dry-run against its Desktop-downloaded software restore passes.

Fresh online backup19694b2a0baf46e5a109f60ddb5327a6 and metadata are Desktop
verified under B:/vk-backups/vk-autoswitch-scope-release-20261001. Archive is
751079465bytes, SHA256ac03033be84d54a8a0278660429dbb70742c7565b12879fe85832be4b51d997c.
It contains9SQLite snapshots,64generation proofs and10046copiedfiles. Supplemental
checkpoint060f043dbb7a425ab4589e610f6af5e0 is verified separately under
B:/vk-backups/vk-blue-reprepare-20261004/supplemental. Keep the parent chain and
authenticated recopy metadata; never restore an old database over production.

## Validation And Remaining Work

All77 backup regressions were rerun with mounted-SSD temporary storage, including
closed/no-WAL and committed-WAL cases. All78 operational tests and the socket
regression pass. Formatting, Ops Playbook checks and diff checks pass. Published
release refs, CLI0.159.2, exact model-proof identity/age and shared private VK/CU
telemetry path are freshly checked. No new inference qualification was necessary.

Full twelve-root rehearsal uses the actual old/new binaries, current-sized private
database copies and the actual production journal/hash workload read-only. All
four cases pass: rejected-backup recovery, latest-data activation, post-switch
write/model/settings preservation through same-process cutback and repeated
recovery. Archives downloaded from Desktop restore successfully. Rehearsal
services stopped successfully. Result is under
scale-resume-rehearsal/handover-6d256a056b8c48dfa5ce30366802389a.

Measured total switch100.304seconds, capture/fencing100.156seconds, activation
0.148seconds. This supersedes the prior127.47second timing. Capture deadline
remains150seconds and controller watchdog360seconds. Allow about two to three
minutes; actual production interruption is not measured yet.

Software maintenance-software-20261004T193909Z.tar.zst is verified on Desktop
B:/vk-backups/vk-blue-reprepare-20261004 and downloaded restoration validates
all2491 bound files. Archive408744478bytes has SHA256
b2bb6b190ebc731ab44685769f24c2f74c337cb38f70c073c269d2f2a57ecded.
Matching readiness SHA256 is
e34c2af97a64eef4143c99a6bb14bb87ae78cf7ec2f9a4dabc5733f9bf80db50.
This replaces, but does not delete, prior preparation receipts.

Refresh the online backup after committing this record, bind fresh drain/process
identities and execute
the authorized independent controller once. The original process stays loaded
and paused for latest-data rollback. Resume this same conversation for live
acceptance, including current route/version, existing sessions, review markers,
model settings, saved messages, attachment round-trip and dot connector calls.
No October4 handover has occurred at this writing; do not claim deployment yet.
