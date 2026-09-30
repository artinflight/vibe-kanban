# September 30 Failed Green Activation

## Subsequent Authorization And Diagnosis

The operator subsequently said "Get it done", authorizing a new v2 attempt.
Read HANDOFF.md and cutover-attempt-v2.json for that attempt; the original result
below remains historical evidence. Read-only process observation repeatedly
captured Git children of fitrdy-manager.service PID1147 in hyroxready-app.
Its discovery.mjs calls fetchRepoBranches, implemented in git.mjs as git fetch.
The observer polls independently of VK, explaining the missed writer boundary.

The corrected controller pauses the known observer parent, allows existing Git
children to finish, and records/thaws the same process after healthy routing or
recovery. A private actual polling-parent/child test proves child completion,
no writes while paused and resumed writes on the same PID. Eight controller
failure/policy tests pass. No whole Git directory or metadata stability exclusion
was added. Original markers, software and receipts remain preserved; v2 uses
distinct attempt and approval marker names.

## Current Authority

Attempt `cutover-20260930T200841Z` is consumed. The continuation explicitly
prohibits retrying it. Blue is recovered and usable, not newly deployed Green.
No older database was restored. This supersedes pre-handover readiness claims
in `VK_GREEN_PREPARATION_20260930.md` and the dated continuity entries.

Blue remains the original PID764264, running on5121/5122 behind gateway4720
and `https://vibe.local`. Its binary hash matches the retained release at
staging1b31e1874, version0.1.42. Green's production unit is inactive, PID0.
CU restarted as PID2205788 using its incumbent cu-20260923 package and is
connected/reconciled. Both selected capacity goals and grant history passed
preservation checks. All inventoried external native writers were released.

The resumed VK native process and CU native process actually run Codex0.153.4.
Neither live service has the new routing-feed environment variable. Therefore
CLI0.159.2 and common VK/CU telemetry remain UNDEPLOYED. Their successful
candidate verification is not live production acceptance.

## Why Activation Stopped

The final frozen capture detected writes to:

- `/home/mcp/code/hyroxready-app/.git/FETCH_HEAD`
- `/home/mcp/code/hyroxready-app/.git/objects/maintenance.lock`

`incremental_capture.py` rejected that unstable boundary. The archive had reached
Desktop verification before the stability assertion, but there is no successful
final-capture receipt: it must not be called a valid frozen backup. Green had not
started. The controller reacquired ownership on the same Blue PID, restored the
incumbent CU configuration, routed Blue and resumed this original conversation.
Logs show CU stopped20:08:45 and recovered20:09:25 UTC; this is not a precise
measurement of browser downtime.

The writer's process identity is not established. Git activity is evidenced by
the changed paths, not proof of a particular editor, timer or agent. Freezing VK
and inventoried Codex processes did not quiesce every protected repository writer.
Do not weaken stability checks, exclude whole Git directories, kill unrelated
services or repeat the handover to work around this failure.

## Recovery Acceptance

Evidence directory:
`/mnt/vk-storage/vk-green-refresh-20260930/cutover-20260930T200841Z/`.

- `rollback-acceptance.json`: SQLite quick_check passes; all pre-boundary IDs
  remain. Counts before the new attachment probe:40 projects,971 tasks,
  993 workspaces,1034 sessions,39889 executions and877 attachment records.
- All12 saved messages, navigation order, card colors and attachment/repository
  relationships are unchanged.333 previously present attachment files still
  match their hashes. A new upload/download byte round-trip passed; test file
  `e28b3511-e6df-45ae-89ad-4a267399cb15` is retained and identified as test data.
- All6036 native index paths are preserved; no previously available rollout is
  missing or smaller. The2282 preexisting missing paths remain historical
  exceptions, not repaired history. This checks availability/size, not a complete
  byte-for-byte audit of every conversation.
- Original native thread `01a03e74-2c1a-72f0-9e00-8e4293fe910d` resumed with the
  same gpt-6-astra/xhigh/AUTO configuration. No replacement thread was created.
- Scratch comparison has two explicit exceptions: the maintenance follow-up
  cleared its already-submitted draft; the exact text exists in the pre-boundary
  native user message at19:42:59.990Z. A workspace scratch timestamp refreshed
  with identical payload/creation time. No other draft loss is accepted.
- `rollback-runtime-capacity.json`: original Blue owns capacity, two selected
  goals/grant history are preserved, and CU is connected/reconciled.
- `rollback-ui-result.json`:1440px and390px browser layouts pass through both
  loopback gateway and vibe.local, with all12 saved-message titles present,
  live WebSocket frames and no page errors. These are host browser tests, not
  physical-phone/cellular testing or certificate-trust validation.
- Reconnection logs contain known MsgStore subscriber lag, unknown native-item
  sanitation and an old missing-cache attachment warning. No warning-priority
  journal entries appeared from20:10 through the recovery inspection. Existing
  log warnings are not claimed fixed. Turn Steer/Stop/goal execution was not
  re-run on the unchanged incumbent; candidate isolated evidence is retained,
  not mislabeled as new-release live acceptance. No broad V1 suite was repeated.

Maintenance `pnpm run ops:check`, `git diff --check`, Python AST parsing and
Node syntax validation pass. Required `pnpm run format` completed Rust formatting
but failed at the existing missing Prettier dependency; full formatting did not
pass. No application source or installed handover controller was changed by
this recovery acceptance task.

## Repository And Backup State

PR128 is merged into main `dcd51cc129f81d82e87dee32886091f5a507cd10` after
CI36767754212. The entire main tree matches candidate staging620bd7eb9.
Canonical main is current. A merged release is not a deployed release.
The isolated CU406f19b commit remains local, preserved in its Git bundle.

Retain the verified Desktop online baseline181003Z and software200000Z packages,
their required September11 base chain, all attempt receipts and historical
exceptions. Never restore them over current production data. The failed frozen
capture is evidence only, not deployment readiness.

## Next Safe Work

Identify and account for the repository writer missed by the pause inventory;
validate the correction without interrupting Blue. Rehearse the corrected
capture/recovery boundary, refresh package/backup evidence and only then request
authorization for a new attempt. Refresh bounded model availability only if the
24-hour proof or exact launcher/account/home binding requires it. Do not repeat
the broader V1 suite or reuse the consumed approval/controller attempt.
