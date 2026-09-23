# Ownership-Capable Blue Deployment

## Authorization And Scope

After ownership implementation, the operator authorized the complete cutover
while stepping away. This supersedes the previous preparation-only instruction.
PR124 merges the lock barrier and explicit ownership handover into staging
1b31e18748ea347c7303688deb9eb1704a764550. Build source f9dac41e4 has the same
application tree; frontend remains the previously validated staging package.
No GitHub Actions are used.

## Initial Legacy Transition

Running Green1674994 has no release/acquire endpoints. This first transition
therefore stops that legacy process after draining work, rather than freezing
its lifetime capacity lock. Its original release and configuration are retained;
recovery starts that software against the same latest production data. This is
not a same-PID paused fallback. The limitation was disclosed before production
actions. Future handovers between ownership-capable builds can use explicit
release, pause, acquire and same-process latest-state return.

The actual one-time switch and recovery implementation is initial_transition.py
under /mnt/vk-storage/vk-blue-refresh-20260921. It rejects outstanding grants and
executions, preserves goal choices and issued grant history, and never restores
an older database or controller state. Recovery refuses to interrupt new work.
Historical frozen generations, missing histories and attachments are unchanged.

## Evidence And Continuation

The September23T154246Z attempt is consumed and preserved under its original
folder. Its marker and prior preparation records are archived in
before-ownership-transition-20260923T183659Z. This is a new separately authorized
attempt, not a retry of that controller state.

The old change journal was invalidated by a moved Python cache directory. A
fresh journal-ownership-20260923.sock and fresh online baseline replace it.
The final boundary must still be captured and verified on Desktop. Production
must not use replica data. All backup payloads stay on mounted SSD/Desktop.

Read cutover-attempt.json and its status.json before any action after an
interruption. Never repeat a consumed handover. Resume only the original
maintenance conversation. Complete live preservation, model menus, saved
messages, attachment round-trip, Turn Steer/Stop/goals, desktop/mobile and CU
reconciliation checks before one final report. This document alone is not
evidence that activation or acceptance succeeded.

## Fresh Preparation Results

The release build passed in10m55s; server SHA256 is
fadb37bf4ea6a26a0d949d05726bd4549bd0beea3e3531fe5b65a6005b9ea873.
The old/current release rehearsal at rehearsal-20260923T185047Z passed
successful switch, backup-abort recovery, unhealthy capacity recovery, companion
lifecycle and latest saved-message/config/goal-selection/issued-ID retention.
Its final measured switch was5.93s and restart recovery0.47s. These isolated
timings do not guarantee the production final capture duration.

Fresh isolated release tests pass original native-history resume without a new
turn, same-thread follow-up, same-execution steering, separate killed Stop,
native goal completion and attachment round-trip. Four desktop/mobile existing
chat tests verify drafts, delayed history, displayed and submitted models.
Model menus include GPT-6 Low/Medium/High/Xhigh/Max and hide pre-5.6 choices.
Local and Tailscale desktop/mobile saved-message tests pass without page errors.
The temporary functional service and port18471 proxy are stopped.

The first functional probe raced service startup; after readiness it passed.
The first model-preservation invocation preceded its required fixture result;
rerunning after fixture completion passed. The temporary tailnet endpoint had
been removed during earlier cleanup; it was recreated, tested and removed.
No production state was modified by these test setup corrections.

Fresh checks also passed39 CU integration tests,19 rendering tests,3 readiness
binding tests and2 external-writer tests. Earlier81 executor/5 guard/21 Python
tests and targeted Clippy remain relevant. Full workspace/Tauri suites were
not rerun; no changes to frontend application sources relative to staged build.

The online archive online-refresh-20260923T183710Z.tar.zst is verified on
Desktop B:/vk-backups/vk-blue-refresh-20260921, SHA256
615909569a1d8fb8baf8cdaa4846c2dfe3c33354ea11711f708f957a663de8f3.
All29 SQLite payloads restored and passed integrity checks. Both original
required Desktop baseline archives were freshly checksum-verified. Online
catch-up and final boundary receipts remain authoritative for subsequent work.
