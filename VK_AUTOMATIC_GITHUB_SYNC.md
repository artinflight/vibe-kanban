# Automatic GitHub sync after owner turns

This extends the corrected PR223 preservation helper and its embedded backend
hook. Scheduling is opt-in through `VK_AUTOMATIC_GITHUB_SYNC=1`; publication
still requires the separately reviewed external
`VK_TURN_GIT_PRESERVATION_CONFIG` policy described in
[VK_TURN_GIT_PRESERVATION.md](VK_TURN_GIT_PRESERVATION.md). No live setting,
repository permission, credential, deployment or cleanup change is made here.

## Owner and idle boundary

Each admitted coding-agent execution creates one immutable durable checkpoint
row before launch. This conservatively includes read-only turns; those produce
no empty commit or new PR. Successful, failed and interrupted owner outcomes
remain separate from remote Git coverage. The worker uses persisted terminal
execution status; a pending observation is created before launch, so loss of a
completion callback does not discard its obligation.
Unbound/missing owner, group, source or policy evidence remains unverified.

The worker starts once after normal startup identity validation and original
worker adoption. Every five seconds it considers a bounded fair page, then
attempts at most one checkpoint. It waits for the owner's child tracker and
Linux process group, overlapping workspace roots and externally observed
workspace processes to be idle. It never stops an active turn. Normal input,
launch, manual session resets and workspace Git mutations share admission serialization through the
attempt and receipt persistence. Helper subprocesses have an overall 90-second
checkpoint command budget, a 110-second backend helper-group deadline and
per-command timeouts; incoming requests can wait
for this bounded operation, with their exact payload already persisted privately.
This is a trusted-backend boundary, not an external all-host-writer custody fence.
Existing helper repository/index locks, snapshot checks, scanning and branch CAS
remain mandatory. Cutover/retirement still needs its own continuously held fence.

The worker calls the existing helper directly; it creates no coding-agent turn,
sync prompt, routing decision or goal. Therefore its own completion cannot feed
the owner-turn queue. The execution UUID is the deduplication key. Blocked jobs
back off up to an hour, and verified rows cannot be overwritten by stale retries.
There is no automatic merge, reset, force push, worktree deletion or new access.

## Earlier turns, retries and user work

The normal completion callback records original heads under admission before a
later turn starts. It accepts only a successful, owner-bound helper acknowledgement
that all original obligations have been persisted. The durable observation state
starts `pending`. The tracked completion callback persists an `observing` claim
before invoking the helper, and makes one observation attempt. Helper failure
becomes sticky `failed`; a failed claim write leaves `pending`, while a failed final
write leaves `observing`. Neither unknown state permits a retroactive observation
of rewritten source. Restoring policy, a later callback, a restart or a new
owner cannot infer the missing completed history. Missing owner context and lost
callbacks also retain the pending gate. New turn ledgers inherit observed originals.

Any unresolved observation in the workspace blocks normal session reset and
worker publication for every queued owner in that workspace. The SQL verification
transition enforces the same condition, independent of pagination, retry timing,
owner metadata deletion and scheduling flags. A failed observation does not stop
admitted automatic owner work; its checkpoint remains blocked. Legacy owner
admission is held for the affected workspace while an observation is unresolved,
even if scheduling or publication policy has been disabled. Incoming work must
remain queued/private rather than being discarded. Reconciliation must prove and retain the actual completed
history; this feature provides no automatic clear/dismiss API for observations.
The new migration treats old rows, including previously verified rows, as unproven
observations. A historical green at `598fe060` is not evidence for this correction.
The helper's new `checkpoint` operation can preserve an older queued turn at a
later idle boundary without moving the latest-turn pointer. Its receipt describes
accumulated eligible work at that boundary, not a retroactive snapshot of every
earlier uncommitted byte. The existing controller `check` still requires the exact
latest turn and freshly verifies its current source and remote witness. An earlier
checkpoint cannot certify a newer pending turn. Original history cannot be replaced
by a source-only receipt, including after a later rewrite or failed observation.
Refreshing coverage retains prior receipts and all observed original commits.

Existing queued follow-ups retain every message and selected executor settings.
Publication failure does not discard them or use the legacy broad auto-commit.
The existing queue now persists accepted batches privately before acknowledgement.
Dispatch is durably marked before launch. A restart restores queued batches;
uncertain dispatch remains visible in the queue and is held for reconciliation,
never automatically replayed. A known launch failure restores its complete batch.
Scratch is deleted only after a successful start. Actual owner-turn completion
notifications remain separate from queued Git coverage; the checkpoint worker
does not emit another coding-turn completion event. No queue is replaced with a
sync prompt. Ordinary user input and native continuation retain their existing
authorization and Recommend routing boundaries.

Inbound follow-up/steering payloads are retained in a separate private database
outbox before they wait on admission. Handler cancellation/failure leaves them
pending; normal acknowledgement marks them handled. The worker defers checkpoints
for the affected workspace while a pending input is unresolved. It does not
invent a delivery/handling claim from silence, idle state or executor success.

## Legacy operation and rollback cannot bypass uncertainty

### Failed publication admission and scoped observation repair

Publication admission and original-head capture have separate inventories. Begin
durably registers the exact requested repository IDs/canonical paths before policy
or snapshot admission. The real completion callback captures all registered heads
even if no repository was admitted for publication. Publication policy changes
cannot suppress that capture; end/check still require their original review and
snapshot evidence. The first admission failure is retained separately from later
worker reports. A missing-policy observation ACK is pending, never verified.

After durable completion capture, a repository without a reviewed publication
policy waits for that policy. Its status is pending/informational, with a durable
`waiting` job; identical pending worker reports are deduplicated. No permission,
baseline, source publication or green remote receipt is inferred. Other admission
failures and unknown observations remain blocked. The status endpoint exposes the
separate admission reason when available.

`scripts/preservation/reconcile_observation.py` provides a narrowly scoped repair
for legacy completed owners whose observation failed specifically because an empty
publication admission was compared with a nonempty requested inventory. Default
operation is plan-only. Apply requires the exact plan SHA-256 and a genuine idle
boundary with no queued/incoming user work and sufficient *natural* worker backoff.
It never creates an idle gap or retimes a checkpoint.

The tool requires exact immutable requests, unchanged policy and helper-ledger
bindings, and matching native `execution_process_repo_states` for every affected
repository. Before/after commit IDs must exist, and terminal capture timestamps
must lie within five seconds after persisted completion, with no overlapping owner
through that capture. Missing, later recaptured, changed, dropped or running owners
are refused. Today's HEAD is never substituted.
It unions all retained originals and native terminal heads into private ledgers,
then compare-and-swaps only the proven observation fault. Original evidence and the
exact repair plan remain in a private write-ahead audit. Interruption retains the
DB uncertainty gate; the identical plan can resume without discarding originals.

This operation cannot mark Git coverage verified, publish, alter source/index/refs,
change permissions, deliver user input or clear unrelated failures. Native summary
and source outcome remain separate. Merged-work verification is separate remote
evidence: a merged PR alone does not prove every disconnected original's history.
Keep such originals in an explicitly private source checkpoint rather than silently
dropping them or publishing them to satisfy a status badge. Excluded files, invoices,
client payloads and runtime backups remain outside committed-source coverage.

Both normal and CI preservation test commands include the real Git/SQLite repair
fixtures. The helper remains embedded in the backend; source changes require a
reviewed matching package. A standalone scoped historical repair does not install
the prevention fix or authorize a restart.

The observation gate applies to the whole affected workspace, including new
executions without a scheduled checkpoint row. Legacy `begin` admission, `end`
completion and all backend `check`/`check-all`/`checkpoint` coverage calls check
retained SQLite observations before invoking the helper. Query failure also blocks.
Completion checks uncertainty before selecting either the legacy end hook or the
unconfigured fallback; disabling scheduling or removing/restoring the legacy
policy cannot enable broad commit/cleanup or a green preservation report.

Scheduled `begin` and completion observation still capture originals, and `block`
can retain a failure. These operations do not certify remote coverage or clear
uncertainty. Clean legacy workspaces with no unresolved observations retain their
existing behavior, including previously observed scheduled owners. Standalone
helper receipts are repository evidence; they do not reconcile VK's retained
workspace observations or authorize release. This correction withdraws the
`1bb69a4a8` candidate. Staging's existing combined PR248 remains held pending a
corrected exact-head review and its release checks.

## Automatic changed-content handoff

Automatic changed-content checkpoints require the per-repository policy to name
`handoff_file`, for example
`"handoff_file": "SYNC_HANDOFF.md"`, and must explicitly include that literal
filename in `allowed`. Missing authority blocks changed-content publication rather
than silently omitting the approved handoff. Read-only checkpoints need no new
document destination. The separate PR223 end hook retains its compatibility. This scopes documentation to already authorized public
content rather than adding a global publication destination. At a safe checkpoint,
changed eligible content produces a handoff entry listing added/modified/deleted
paths and SHA-256 digests. Source text, prompts, transcripts, media and runtime
evidence are never copied into the generated entry. Existing document content is
retained, ignored/private destinations are refused, and content markers deduplicate
retries. The document itself cannot cause another handoff entry. Read-only turns
produce neither a document nor an empty commit/PR.

The generated document passes the same file policy, scanner, snapshot/index and
remote verification as source. The helper initially creates a draft only when a
changed task branch has no matching open PR; subsequent checkpoints reuse that PR.
It never merges. Merge remains subject to explicit operator approval.

## Evidence and recovery

`GET /api/workspaces/{workspace}/github-sync` returns bounded per-turn state,
attempt count, reason, remote commit/PR witnesses and pending input IDs. It does
not return prompts, policy, source bytes or private inventories. Exact-turn summaries
also receive checkpoint status without replacing the owner's original summary.
Repeated identical blocked attempts do not create repeated attention events.

Success uses the existing helper's live `ls-remote`, independent fresh fetch,
commit/tree/object-graph verification and matching PR head. Local tracking refs,
push exit status, old reports and fixture metadata alone are insufficient.
`checkpoint_only` receipts must not be mistaken for whole-workspace or controller
acceptance. Excluded/private/ignored content remains explicitly outside Git protection.
It is neither uploaded nor declared backed up by a successful checkpoint.
Explicit private directories, transcript/rollout directories and `.private` filenames
are denied even if mistakenly allowlisted. A commit releases only its own index
lock inode; a newly acquired writer lock is retained and keeps publication pending.

After a network failure or restart, retain working files, index, original ledgers,
private receipts and queue/outbox rows. Restore the same reviewed policy and
credentials; let the existing job reconcile its remote before retrying. Never
clear a receipt or original obligation to obtain green status. Policy changes,
missing baselines, unbound groups and uncertain dispatch need scoped reconciliation.
For a retained inbound input, first verify what happened through normal VK history
and private outbox evidence. An explicit exact-ID
`DELETE /api/workspaces/{workspace}/github-sync/input?input_id={id}` marks only that
workspace's input dismissed and keeps its original private row. This is an operator
decision, not automatic handling. Uncertain queued dispatch can be reconciled and
explicitly cancelled through the existing queue API; cancellation does not replay it.
Cancellation retires its durable batch even when scheduling is disabled. A database
failure leaves the batch visible and held; acknowledgement cannot hide surviving input.

## Same-restart candidate with PR245 and PR247

The existing Staging owner prepares the combined PR245/246/247 candidate. This
feature correction supplies its exact SHA and evidence without duplicating that
integration. Prepare a clean candidate containing all exact reviewed component
heads; the older `598fe060` feature nomination is withdrawn. Run the existing Test workflow at that combined commit with
`github_sync_candidate=true`, `expected_candidate_source=<combined SHA>` and
`approval_fix_head=<PR245 SHA>`, `automatic_sync_head=<feature SHA>`. The build
refuses moved component heads or missing
ancestry, runs the normal workspace tests, builds the backend in the acceptance
profile and uploads the immutable server plus its source/hash manifest. Preserve
the external frontend release: this backend-only change authorizes no asset swap.
Do not confuse a hosted build with actual local end-hook acceptance.

Treat the checkpoint worker and its helper group as writers during any later
handover. Drain pending attempts through the normal idle/admission boundary and
the existing continuously held controller fence; never terminate an owner turn or
remove an unowned index lock to obtain readiness. A timed-out commit can leave an
owned lock for scoped reconciliation; retain its contents and original ledger.

Before nomination, review exact source and policy/scanner hashes, repository IDs,
literal allowed filenames, existing destination/audience, base/default workflow
pins and external publication automation. Per-repository exclusions and private
recovery obligations must be recorded privately. No global publication mandate
or unrelated archived-history/backup gate is added. Unresolved originals and
unknown associations still block their actual affected scopes.

The release owner alone owns the next safe-idle restart and live settings. Combine
the approval fix, this feature and PR247 in that one candidate, preserve native routing
and the selected model/effort, and keep cleanup closed. After authorized cutover,
observe a genuine substantive owner completion, queued/incoming user work, one
checkpoint job, and fresh remote equality through the status endpoint and private
ledger. Read-only, retry and interruption fixtures are bounded evidence, not
production enforcement acceptance. No forced agent stops or media operations.

Rollback uses the same schema-compatible candidate binary with
`VK_AUTOMATIC_GITHUB_SYNC` disabled and the previously verified preservation
environment restored. It retains durable rows and private helper state. Restored
user batches are held for reconciliation while scheduling is disabled. An older
binary is not a proven rollback: its migration set may reject the new schema and
it cannot reconcile these queues. Prove compatibility before nominating one; never
restore an old database over newer user work. Follow the established latest-data
release rollback protocol. Disabling publication does not permit cleanup.
