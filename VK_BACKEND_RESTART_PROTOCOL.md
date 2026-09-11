# Backend Restart Protocol

Established by the operator on 2026-09-11. This is the authority for future
backend restart windows; older stop-and-switch examples are historical.
An established protocol is not evidence that a particular candidate is ready.

## Operator Contract

Green stays usable throughout preparation. Build, test, inventory, rehearse,
prepare recovery tools and transfer the bulk backup while the operator works.
Do not ask the operator to stop all work while those operations run.

Prepare Blue against isolated disposable state. At readiness, explain in plain
English what is ready, the measured interruption window, what cannot continue
through that window, and the rollback limitations. Then wait for an explicit
**cut over now** instruction. Permission to prepare, proceed with preparation,
or update these docs is not permission to interrupt production.

The intended handover is brief. Five seconds is a target, not a guarantee.
If measured results exceed the proposed window, improve preparation or agree a
different window before interrupting work. Never quietly substitute a long
stopped-backend backup for an approved short switch.

## Preparation While Green Stays Live

- Reconcile every In Staging issue and live-only fix with the exact candidate
  source and frontend. Record exclusions and validation gaps explicitly.
- Run Blue with separate writable DB, Codex home, cache and worktrees. Contain
  migrations, cleanup, background jobs, credentials and external side effects.
  A copied DB does not redirect absolute history paths or make them isolated.
- Finish builds, functional checks, compatibility tests and bulk backup work
  before announcing readiness. Preserve all referenced native histories,
  `thread_history_*.sqlite`, indexes, goals, settings, saved messages, attachments,
  dirty/untracked files and Git metadata. Verify actual archive restoration.
- Keep backup staging on mounted `/mnt/vk-storage`; verify permanent copies on
  Desktop `B:/vk-backups/`. Do not prune originals or previous backups.
- Rehearse the complete proposed critical path with disposable state: writer
  fencing, final consistent capture/refresh, activation, routing, acceptance and
  rollback. Record these durations separately. A fast API startup or route
  change alone is not a measured cutover time.
- Check process identities, consumers, permissions, mounts, credentials and
  recovery actions before production is touched. Repeat volatile checks at the
  switch. A controller must survive its own VK execution being interrupted.

## Final Window After Explicit Approval

Account for active turns, queued work, approvals, subagents, previews and external
callers. Drain work or obtain acceptance for specifically identified interrupted
runs. Do not mark an interrupted run completed or replace its original thread.

Enforce one authoritative writer. Capture the changes made since preparation at
a consistent boundary and ensure Blue uses that latest state, not its earlier
test copy. The chosen recovery mechanism must protect this boundary; slow
verification cannot simply be omitted to achieve a shorter interruption.

Switch frontend, API, WebSockets and relevant direct callers coherently. Preserve
old hashed assets for open tabs. Verify data and user workflows before declaring
success: original-thread continuation, saved messages on desktop/mobile,
navigation, attachment upload/retrieval, execution, steering and Stop, plus the
features in the release. Process health alone is insufficient.

## Keeping Both Instances Available

Two running processes are acceptable only with proven isolation or a genuinely
passive standby. Moving the frontend does not disable a backend's direct APIs,
background jobs, cleanup, cached state or native-history writes.

Current VK does not have a verified hot database-switch/passive-standby mechanism.
A Blue process opened against a test database does not become production merely
because traffic moves to it. If activation requires restarting Blue against
current data, or stopping Green to fence its writers, include that action in the
measured proposal and obtain the operator's explicit agreement. Do not imply
that keeping Green running automatically provides lossless instant rollback.

## Rollback And Failure

Before Blue accepts authoritative writes, rollback can return to the untouched
authoritative state. After Blue accepts work, preserve its latest data. Use old
software against that state only when compatibility is rehearsed; otherwise
reconcile safely or repair forward. Never restore a stale Green snapshot over
new work. Do not interrupt new executions as an automatic rollback shortcut.

Retain old artifacts and all recovery evidence. Rehearse startup side effects
on the rollback artifact too: the old Green binary deletes unlinked attachments
unless the preservation guard is backported and enabled.

On an aborted switch, restore service safely, explain the actual state, preserve
failure evidence and re-establish readiness. Do not automatically retry the
production handover. A resumed maintenance message is not renewed operator
approval. Keep progress conversational and issue one final report after work ends.

## September 11 Failure To Avoid

The first attempt stopped Green before checking two preview-owned Codex process
images. Linux reported their replaced executable paths with ` (deleted)`; a
basename assertion rejected them. This was a missing preflight check, not lost
conversation files. The controller returned to guarded Green with the same data
before taking the final snapshot or starting production Blue. The original
maintenance thread resumed. No successful cutover or final backup is claimed.

Process checks must handle replaced executable images and verify process start
identity plus executable inode/device, not trust a PID or pathname alone. Test
the actual preflight observations as well as mocked failure paths. Do not repeat
the previous controller: prepare a new attempt only after renewed readiness and
explicit operator approval.
