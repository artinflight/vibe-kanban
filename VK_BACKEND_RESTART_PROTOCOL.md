# Backend Restart Protocol

Established by the operator on 2026-09-11. This is the authority for future
backend restart windows; older stop-and-switch examples are historical.
An established protocol is not evidence that a particular candidate is ready.

## Frozen Capture Writer Coverage

The September30 attempt failed before activation because Git metadata changed
outside the paused VK/native-process inventory. Inventory writers against the
entire protected backup scope, including repository common Git directories and
background fetch/maintenance, not just running agent rows. Identify and coordinate
unrelated consumers rather than killing them or assuming the incumbent freeze
stops their writes. Keep the final stability assertion; a checksum-verified
archive alone is not a verified frozen boundary. A failed attempt is consumed,
not authorization to retry. See `VK_GREEN_ROLLBACK_20260930.md`.

September30 diagnosis identified fitrdy-manager.service background Git polling.
For the renewed authorized window, pause its verified polling parent and drain
any existing Git children before capture; preserve/resume the same parent after
healthy routing/recovery. Bind its process identity into approval and recovery
receipts. Do not stop the unrelated application or weaken backup exclusions.

After recovery, verify the actual incumbent runtime/configuration separately
from candidate readiness. Report preexisting exceptions and lifecycle changes
explicitly: a cleared maintenance draft is acceptable only with evidence that
its exact text was already submitted in the original thread. Do not silently
omit all scratch rows from preservation checks.

## September 30 Runtime And Telemetry Requirements

For the AutoSwitch V1 deployment, pin production to the verified Codex CLI/runtime
0.159.2 through the qualified launcher. Check the exact launcher, signed-in account
fingerprint and Codex home against the seven-model availability proof, including
GPT-6 Luna, GPT-6 Sol and GPT-6.1 Sol. If that identity changes or proof age reaches
24 hours at deployment, rerun only the bounded availability verification against
the actual production identity. Do not rerun the broader V1 acceptance suite for
a proof refresh. Do not alter proof timestamps or expose account credentials.

VK_ROUTING_EVENTS_FILE and CU_ROUTING_EVENTS_FILE must resolve to the same private
file. Verify candidate settings before handover and actual process environments
after activation; a prepared CU drop-in alone is not proof that live CU uses it.
For September30 the feed is
`/mnt/vk-storage/codexusage-android/monitor/vk-routing-events-v1.jsonl`.
The controller verifies these requirements before interruption and after routing,
with latest-data rollback if live verification fails. Preserve manual model
choices, existing configuration and the normal staging-to-main promotion path.

## Generation Roles

September30 authority: Green2506054 is live/enabled on5261/5262; original
Blue764264 remains frozen/disabled for same-latest-data ownership cutback.
CU2506120 runs the reconciled406f19b companion. Read VK_GREEN_LIVE_20260930.md.
Both original and v2 September30 attempts are consumed; never repeat them.

September23 current authority: ownership-capable Blue764264 is live on5121/5122.
Legacy Green is stopped/disabled, not frozen, with original release retained for
latest-data restart recovery. Read VK_OWNERSHIP_CUTOVER_20260923.md. The initial
legacy transition was separately authorized because that binary could not
release its lifetime lock. For subsequent ownership-capable builds use the
staging VK_CAPACITY_OWNERSHIP.md protocol; do not blindly reuse either consumed
September23 attempt or infer permission for a later cutover.

September15 role authority is `VK_GREEN_LIVE_20260915.md`: Green1674994 is live,
Blue2150526 is frozen for latest-data cutback. Older dated examples are historical.

### Required Capacity Integration

September23 production demonstrated that pausing an incumbent retains its
lifetime exclusive capacity-controller file lock. A candidate sharing that
controller root cannot open it, even though API health and SQLite checks pass.
Inspect actual incumbent lock ownership before declaring readiness. Rehearse
with a capacity-enabled incumbent holding the real type of controller lock;
a private companion process and separate controller roots do not prove transfer.
The handover must transfer capacity ownership while preserving goals, grants,
running/paused child state, and latest-data cutback to the retained incumbent.
Do not unlink or replace the locked inode to manufacture success, start two
owners, stop the incumbent contrary to the paused-standby requirement, or skip
live reconciliation. If no tested ownership transfer exists, remain not ready.
The consumed September23 attempt is not permission to try again.

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

September15 added a second model-selection regression: a correct GPT-6/Xhigh
label and a successful submission masked the absent reasoning dropdown and old
catalog entries. On MCP, open the actual Codex model menu at desktop/mobile
sizes and verify GPT versions below5.6 are hidden and GPT-6 has the supported
Low/Medium/High/Xhigh/Max menu choices. Do not merely check the selected label.
Do not offer native-only efforts the deployed VK enum cannot accept. Carry
PR117 into the candidate and the retained cutback frontend; preserving the old
frontend verbatim can reintroduce a known UI regression. Do not reset chats.

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
