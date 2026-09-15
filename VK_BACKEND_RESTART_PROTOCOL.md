# Backend Restart Protocol

Established by the operator on 2026-09-11. This is the authority for future
backend restart windows; older stop-and-switch examples are historical.
An established protocol is not evidence that a particular candidate is ready.

## Generation Roles

September15 role authority is `VK_GREEN_READY_20260915.md`: Blue2150526 is live,
new Green5091 is only prepared. Older dated examples below are historical.

### Required Capacity Integration

Use the candidate staging source's `scripts/vk-capacity-deployment.py` and
`scripts/deployment/mcp-capacity.json` for every MCP deployment. Package both
server and release-matched guard. Render and inspect candidate/CodexUsage
drop-ins, preserve previous settings, install without starting services and
require read-only `check` success before readiness. Include configuration and
tool hashes in the approved recovery package. Never rotate the private token.

The CU companion may need a restart to load its stable gateway/database
settings. Inventory CU-owned native processes separately from preserved external
processes, and include that restart in the approved window. Rehearse companion
stop/start and backup-abort recovery with private units, never production CU.
After routing, require `live-check` to verify running settings, connection and
reconciliation; do not equate installed configuration with live readiness.
Preserve enabled/disabled state and selected goals without enrolling or enabling
anything. Include CU persistent data in backup/journal coverage and quiesce its
writes before the final capture. An old incumbent without loaded capacity
configuration can restore ordinary operation, not prove the new integration.

Any readiness refresh invalidates previous approval. Bind the fresh approval to
the exact readiness SHA256 and staging commit; verify the current incumbent
frontend path/content before entering maintenance. A frontend-only hotfix can
change the required rollback assets without changing backend binaries. Preserve
old receipts and publish refreshed readiness only after the new software package
has been restored, verified and mirrored to Desktop.

Color names are relative roles, not permanent ownership. As of September14,
Blue is the accepted incumbent, original frozen Green is retired, and a fresh
Green is prepared from staging after PR112 merged. Apply the protocol to the
verified incumbent and candidate, not to hard-coded historical unit names.
Retiring a standby is not permission to interrupt the incumbent or activate its
replacement. A test replica is never copied over authoritative production data.

Allow accepted buffered UI-preference writes to flush after closing routed
connections and before freezing the incumbent. Current source delays those
writes by750ms; the prepared handover includes a1.5s drain interval and then
verifies frozen database generations. Inventory direct callers separately.
Use the reciprocal production start interlocks before activating a replacement;
the historical Blue start guard knows only the retired Green service.

## September 12 Failure Corrections

The operator permits a loaded but paused Green, retaining its original PID for
thaw/cutback. Do not substitute a Green stop/restart. Green remains usable during
preparation; production Blue uses separate ports and is forbidden from starting
while Green can write. Rollback always uses latest data, never an older DB copy.

Test the actual production recovery function against isolated real services and
APIs, including backup failure BEFORE Blue starts. Mock success paths and a
similar rehearsal implementation missed the September12 profile-format defect.
`profiles.json` contains overrides, while the profiles PUT API requires complete
profiles. Expand overrides using the exact incumbent defaults and runtime merge
semantics; account for serde defaults. Do not PUT unchanged cached settings on
an aborted switch. After Blue writes, refresh Green from latest settings before
routing back. Verify the production entrypoint, not just the thawed process.

Downloaded model catalogues and debug telemetry are not native conversations.
Document narrow regenerable/diagnostic exclusions and retained baseline copies;
never apply them to histories, goals, settings, execution output or worktrees.
Refresh the journal and online baseline after a lost/moved-directory watch.
Pin an online SQLite read snapshot where continuous writes would otherwise keep
restarting backup. Frozen-boundary committed-generation checks still apply.

Budget peak disk use for snapshots, archive, extraction and rehearsal together.
Do not run overlapping bulky verification jobs near capacity. Keep failed
evidence; relocate scratch copies only after destination checksum verification.
Never assume permission to delete a retained restore-test copy or user data.

## Existing-Chat Model Preservation Gate

The September 12 cutover checks missed existing-chat model selection. A correct
global default, preserved history and a successful execution do not prove that
the next turn uses the user's chosen model. This gate applies to backend
restarts, frontend swaps and cutbacks.

- Before preparation, record session IDs and effective model, reasoning effort,
  executor and preset for existing chats, including explicit choices different
  from the global default. Preserve saved draft/executor settings and last-used
  execution configuration; do not overwrite drafts to collect evidence. Refresh
  this comparison at the final boundary so work during preparation is included.
- Rehearse existing-chat reopen, refresh and follow-up submission using isolated
  copies of representative state. Include empty drafts, saved drafts, delayed
  history/settings loading and a model differing from the native CLI default.
  Check the selector AND the submitted executor configuration and native model
  evidence, not merely the profile API or a newly created test chat.
- At live acceptance, compare preserved per-chat settings with the boundary
  inventory and inspect existing-chat selectors on desktop and mobile. Use
  explicitly authorized test turns for submission checks; do not send messages
  into user chats merely to test them. Record untested coverage as incomplete.
- A missing choice, unexpected fallback or disagreement between display and
  submitted model blocks readiness or successful acceptance. Do not silently
  normalize every chat to the global default, replace a user's model choice,
  or treat a new-chat test as existing-chat coverage. Explicit per-chat choices
  must survive independently of default changes.
- Test the same preservation on latest-data cutback, including choices made
  while Blue was live. Never restore older settings or a database to recover a
  model selection. Diagnose and repair only the affected state with evidence.

These are required validation outcomes, not an implemented automated guard.
See the September 12 model-selection incident in
[the restart lessons](VK_RESTART_LESSONS_LEARNED.md).

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
