# September23 Authorized Blue Cutover

The operator authorized the full refresh and cutover while away. This note is
pre-cutover context, not evidence of a successful switch.

VK staging remains df49b020706e831ae203d05b1b89723dc2321cc8. The candidate
server/guard hashes equal the validated September21 release. Green1674994 is
the incumbent; new Blue uses the already prepared September21 service on5121.
Runtime evidence remains in /mnt/vk-storage/vk-blue-refresh-20260921; dated
September23 archives and the cutover-attempt/status records identify this run.

CodexUsage staging advanced to5fa797d. A separate cu-20260923 package combines
that source with existing live manual-reset API/UI/guards, Android download page
and other local corrections. The combined suite initially exposed missing
manual-reset safeguards; preserving those three guards yields131 passing tests.
These preserved live corrections still need source backfill into CU staging;
do not deploy CU staging wholesale and lose them. The package is archived with
the cutover software. No reset credits are spent by validation. Existing capacity
scheduling is on and reset automation off; neither is newly enabled here.

The old journal is invalid following moved workspaces. A fresh September23
journal and online baseline replace it. Required existing native rollout paths
remain inside backup coverage. No stale test replica or backup becomes production.
Fresh Desktop verification, current writer inventory, bound approval and final
frozen capture remain mandatory before activation. Green must stay loaded and
paused for latest-data cutback, not stopped/restarted.

The independent controller resumes the original maintenance thread. Inspect its
status before any actions, then finish live thread/model/saved-message/attachment,
desktop/mobile, Steer/Stop/goal and CU acceptance. Historical recovery exceptions
remain. Report completion only after those checks and durable final evidence.
