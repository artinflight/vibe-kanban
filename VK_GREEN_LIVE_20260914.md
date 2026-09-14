# Green Live: September 14

## Current Runtime

The separately approved cutover completed at15:26UTC. Green production
`vibe-kanban-green-production-20260914.service` is active/enabled, PID2778969,
ports4511/4512. Gateway4720 and `https://vibe.local` route to Green; frontend
entry is index-Ca4e1mj1.js. Staging is32676919b (PR112 and PR113 merged), version
0.1.42. Backend inputs are unchanged from503dbad74; tested binaries were reused.
Blue `vibe-kanban-paused-blue-20260912.service` retains PID2590517, frozen and
boot-disabled. It is the latest-data cutback option, not a stale database copy.
Retired original Green and old4311 services are stopped and disabled; current
systemd inspection reports loaded/disabled, not runtime-masked. Do not start them.
The isolated4911 replica is stopped; its18466 test URL is not production.

Authoritative data remains in the same green-named XDG directory, Codex home
and attachment cache. No copied test data or old database was restored. The
three idle external native processes were paused then thawed; no child work was
terminated. Only maintenance execution5ad34ed4-c573-4d90-bfec-6b72d6ebe934 was
interrupted and is correctly marked killed. This ORIGINAL maintenance session
75bc68d4-aa55-4914-a695-f20c46a13e4c resumed native thread
01a03e74-2c1a-72f0-9e00-8e4293fe910d with the same GPT-6/xhigh configuration.

## Validation

Controller-recorded interruption was26.00seconds including final backup and
fencing; activation itself took0.51seconds. This is the measured switch, not an
estimate of future windows or time spent on acceptance.

Live database integrity passed. All frozen IDs remain:40projects,902tasks,
916workspaces,63repos,951sessions,38,739executions,12,225coding turns and780
attachments. All5,902 pre-switch native index paths are unchanged. All208 saved
scratch preference/draft payloads matched after the live tests. Saved messages,
project navigation, colors and attachment/repository links matched the boundary.
The236 currently available cached attachments passed their recorded hashes.
Historical missing attachment/native-tail/startup exceptions remain unchanged;
these counts do not claim all historical gaps are repaired.

Both desktop1440 and mobile390 browser checks passed against live vibe.local:
tested asset hashes, WebSocket updates,12saved messages in settings and the chat
picker, with no page errors in those screens. HTTPS3443 entrypoint API also
returned the same messages. These are browser-emulated mobile checks, not a
physical phone test. Attachment upload and retrieval passed through live HTTPS;
test attachment48b0a1b2-6cfe-4a31-a3b3-b4a7ba24220b is retained and labeled.

Reused existing test session4eefa404-cac8-446a-8bf6-2ff35e65a4a7, not a new or
replacement maintenance thread. Turn Steer redirected execution4ccc061e-ea93-
407f-904e-aff93370d4e7 without creating another execution; a native goal completed.
Separate Stop canceled72038b82-c982-4566-8286-5f8f87ea96fe and left it killed,
not completed. No project files were edited by the test agent.

Logs show the preexisting missing July screenshot cache and unknown native-item
warnings, independently found in Blue's pre-cutover journal. Existing duplicate
draft-deletion/flyout limitations and disabled CU capacity integration are not
claimed repaired. No new database/permission failure was observed in acceptance.

## Backups And Recovery

Evidence root: `/mnt/vk-storage/vk-green-refresh-20260914/`.
Attempt: `cutover-20260914T152557Z/` contains status, approval context, final
boundary, standby and original-continuation receipts, and live acceptance results.

Desktop directory: `B:/vk-backups/vk-green-refresh-20260914/`.
- Final frozen archive: `final-boundary-20260914T152604Z.tar.zst`, SHA256
  `cce9b355460b087a620a371125d4c6e4f2ffced91e3b6b8a48c8b6de3c4b7e8b`.
- Pre-cutover catch-up: `final-delta-rehearsal-20260914T152405Z.tar.zst`, SHA256
  `ab548a6a33435666c957ee5eefc7ee556f1ed67251e9674f9eda1b875c4d191c`.
  Despite the helper's historical filename, this is the live online catch-up.
- Refreshed software/tools: `release-tools-refresh-20260914T150558Z.tar.zst`,
  SHA256 `9e16ea8f83408d0efb02f01a10680c8c3e91d042b3dd8495adf2bb34686469dc`.

The final backup has12integrity-checked SQLite snapshots, extracted/hash verified
and Desktop hash verified. The protected VK/native generations stayed stable;
the separately copied monitor-local telemetry DB kept writing and is explicitly
not represented as part of the VK frozen generation. The backup chain still
requires the12:24online delta plus September11 preservation AND recovery-metadata
archives. Never replace current production data with any of these older snapshots.

Do not rerun the handover. Retain Blue frozen for operator-approved cutback.
Before any cutback, drain new Green executions and preserve latest writes; use
the rehearsed same-data recovery path, never an old DB restore. Green is enabled
for boot; a power loss cannot preserve Blue's in-memory frozen process, so do
not describe that scenario as an instantaneous thaw rollback.
