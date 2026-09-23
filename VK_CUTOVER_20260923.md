# September23 Authorized Blue Cutover

## Outcome: Cutover Failed, Green Restored

The authorized attempt at15:42:46UTC returned to the original Green1674994 at
approximately15:44:09UTC. Blue started but capacity reconciliation failed:
Green retained its lifetime exclusive controller.lock while frozen. Blue's
capacity endpoints returned500 with lock acquisition errors. The controller
stopped Blue and thawed Green without copying an old database over production.
Green remains enabled/routed on5091/5092, with the September20 frontend. Blue
is stopped/disabled. This is a failed deployment, not Blue live acceptance.

Readiness is invalidated. Do not repeat this handover. A tested capacity-owner
transfer and latest-state return to paused Green are prerequisites to a new
approved attempt. Do not remove the lock file or bypass reconciliation.

The final frozen backup is Desktop-verified:
`desktop:B:/vk-backups/vk-blue-refresh-20260921/final-boundary-20260923T154253Z.tar.zst`
(106752038bytes, SHA256
`87ba79d9d2555aa76b8f4c0895765bb0f9500f0e289eabd1703b75455ae4b142`).
It supplements the preserved baseline/delta chain; it is not a standalone
full filesystem restore archive. No backup was restored over production.

Rollback preservation passed: database integrity; all pre-boundary IDs across
40projects,936tasks,954workspaces,994sessions and39356executions retained;
12saved messages, drafts, navigation/colors and attachment links unchanged;
5978native index mappings retained;269existing attachment hashes verified;
new attachment upload/download passed. Historical unavailable attachments and
native recovery exceptions remain explicit, not repaired or waived.
The original maintenance conversation and executor configuration resumed;
only its interrupted execution was killed. Labeled acceptance verified real
same-execution steering, native goal completion, and distinct Stop/killed state.
The test session was retained, not substituted for maintenance.

CU's refreshed combined package remains running and connected/reconciled with
Green. Capacity scheduling remains on, reset automation off; no reset credit
or one-time weekly run was enabled by acceptance. Preserved live CU corrections
still need source backfill.

Desktop1440 and mobile390 browser checks passed on vibe.local, including a
second run mapping that same origin to the Tailscale listener100.75.236.43:3443.
Both rendered all12 saved messages, received WebSocket frames, retained GPT-6
Low/Medium/High/Xhigh/Max options, advertised no GPT models below5.6, and had
no page errors. This is host browser testing, not a physical-phone test.
An initial bare-IP-origin test received no WebSocket frames and failed; it
must not be represented as passed. The normal vibe.local origin works.
The first model-selector probe used a replica-only workspace ID; correcting
the probe to the real maintenance workspace passed without changing models.
Saved-message comparison also required normalizing SQL/API timestamp formats.
These were acceptance-script corrections, not application or data rewrites.

Logs retain historical July13 attachment0fa37354 and unknown Codex item warnings
already documented in VK_GREEN_LIVE_20260915.md; they are not claimed repaired.
New checkpoint rendering was not separately re-exercised after rollback; the
unchanged September20 frontend is restored. Staging-only changes remain undeployed.

Final documentation validation: ops:check and diff checks passed. The initial
format invocation lacked Prettier on PATH; rerunning pnpm run format with the
existing SSD-hosted formatter passed without application changes. No GitHub
Actions ran. Full aggregate Rust checks remain limited by the previously
documented missing GTK dependencies; they were not newly claimed passing.

Evidence: `/mnt/vk-storage/vk-blue-refresh-20260921/cutover-20260923T154246Z/`
including status, emergency, capacity-lock-diagnosis, rollback-preservation and
rollback-execution records. The original pre-switch readiness remains archived.

## Preparation Context

The operator authorized the full refresh and cutover while away. The following
records preparation, not a successful switch.

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
