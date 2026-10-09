## Execution-scoped warning follow-up — candidate, validation pending

WHAT: Preserve execution A's terminal capture warning when older execution B
successfully completes or closes after pending retries. WHY: available older
history is not evidence that a newer unavailable capture has recovered. CONTEXT:
same isolated c3-relative candidate; reviewer configuration remains unchanged
pending owner confirmation. SUCCESS: both interleavings retain A's warning until
an authoritative A retry succeeds, with existing pending and scope tests intact.

The hook stores errors by execution ID within the existing scope. Successful
pages clear only their own execution's error; batch start retains errors.
Removing an execution or switching scope retires only the associated errors.
No writer, backend, API, connector, routing, permission or live state changes.
Hosted UI/type/compiled acceptance is pending at the next exact source commit.

## Exact-source review follow-up — candidate, validation pending

WHAT: Repair both P2 findings against334a2a2. WHY: a healthy drain must not leave
a sticky warning, and a short exit/Stop must not win writer ownership before its
first poll. CONTEXT: same isolated branch, c3-relative patch, no live changes.
SUCCESS: compiled ownership/map-removal and running/completed/pending/closed
regressions plus healthy UI recovery and terminal failure boundaries.

The caller passes the existing MsgStore Arc. Receiver ownership and metadata
subscription are established synchronously before tokio::spawn; an RAII owner
tracks active capture through task completion, failure or cancellation, independent
of the container map. This is presentation liveness, never review closure proof.
The history API returns capture_pending only for a live owner. A persisted pending
sidecar without a live owner is still terminal capture_error, including restart.

The UI has one retry timer per explicitly pending completed execution, at1000ms.
It re-reads authoritative finite history, never infers closure from process status
or websocket EOF. HTTP reads pause while disconnected/loading. Timers stop on
closed/error response, process removal/running, workspace change or unmount.
Healthy closure loads the current report without manual retry. Terminal damaged
captures keep warnings and do not automatically retry. Connector reads propagate
pending separately from incomplete; they do not poll or emit delivery evidence.

New hosted regressions cover map removal before writer first poll, cancelling an
unpolled writer without a stranded producer, actual HTTP running/completed/pending/
closed, owner interruption, automatic UI closure, initial pending, terminal failure
and scope-change cancellation. Connector100 Python tests pass. Exact revised Rust/
UI hosted acceptance remains pending until its new commit receipt is attached.
All prior raw/native/CI evidence remains preserved. No local Cargo builds,
deployment/restart, approval changes, wider PR merge or badge changes.

# e3e1 — Lossless reply capture and visible incomplete status

WHAT: Repair the October 9 post-cutover completed-but-empty Staging reports.
WHY: coordination must not substitute a pre-cutover report when a newer capture
failed. CONTEXT: source starts at the deployed backend c3c48e6324f778ccd03a5761c2314b440e9ceac3;
main/staging were fetched, but production remains an unmerged combined release.
This independent feature worktree leaves all original/staging worktrees and native
transcripts intact. SUCCESS: bounded capture preserves raw finals under burst/lag,
incomplete captures survive restart as visible unavailable state, strict review
proofs stay fail closed, and compiled isolated regressions pass.

## Verified incident

Staging session 7d6734c1-c8d0-4d55-ac27-b1f763d15a6e executions 3bd4815a,
95d4f979, 3c466517 completed at 20:35:52.856, 20:53:31.933, 20:56:37.479 UTC.
Their native finals remain at 20:35:48.662, 20:53:27.754, 20:56:33.127 UTC.
The old writer stopped after broadcast lag of 20/9/1 messages, mid-large resume
response. All three log-history pages returned zero entries; connector discovery
fell back to a historical final. No native transcript, raw file or badge was
modified for diagnosis or recovery. Private user histories are not checked in.

## Source behavior

- Live raw stores use one bounded 128-chunk capture queue, independent of UI
  broadcast capacity/history eviction. The producer awaits storage capacity.
- The single writer is claimed and registered before the exit monitor. Raw EOF
  and metadata Finished must both drain; an early UI Finished cannot certify a
  raw prefix. Source/disconnect/write failures do not publish a review fence.
- Split UTF-8 stdout is preserved; invalid/partial UTF-8 fails closed.
- The same writer owns a small `<execution>.capture.json` pending/closed state.
  Pending survives interruption even if captured JSON happens to end on a valid
  line. It is presentation state, never a review proof. Existing files without a
  sidecar are framing-checked; no retrospective fence/backfill is fabricated.
- Completed Codex log-history returns capture_error for incomplete/damaged or
  unverified durable capture, before history cache/replay. Failed startup logs
  retain their existing diagnostic read path. Native transcript evidence stays
  untouched. Integrity review retains its independent closure, byte/hash, exact
  final, revision, all-session, manual-intent and deduplication guards.
- UI visibly reports unavailable recent replies. Connector candidate stops on
  that newer unavailable execution instead of substituting an older final.
  No tools, permissions, routing, auth or administration surface is added.

## Validation and limits

Before capacity coordination, compiled utils queue tests passed 7/7, including
20 MB / 5,000 chunks, tiny UI capacity, UI eviction, a slow consumer, source
failure, duplicate consumer and disconnect. Connector tests passed 96/96.
Later UTF-8, real storage-writer/restart/native replay, isolated HTTP and UI
regressions require hosted CI. Do not claim them passed until exact-commit CI
receipts are attached. pnpm run format and ops:check passed. No production
service/server binary or inference was started.

Local compilation stopped after Seamus's Disk Space coordination. Target:
/mnt/vk-storage/vk-connector-repair-20261007/cargo-target-compat. No active Cargo
writer remains. Only inactive test executable debug/deps/utils-e95cc44e49995141
(115658752 allocated bytes) is cleared for verified reversible Desktop B offload;
no cache, source, fallback, incident evidence or shared output was cleaned.

Root/Dev/Staging must review the c3-only patch and hosted acceptance, including
Stop/short-exit drain and full-message hash proof. This turn does not deploy,
restart or merge; activation uses the existing owner-controlled release flow.
No fabricated backfill of the three old captures is part of this patch.

## Routine dispatch proposal — no setting change

Read-only Plugin Management inspection on October 9 found Vibe MCP for dot
asdk_app_6ac2687e6e808191a04f4a21f4b6cfd7 set to Use my default, effective
Allow low-risk actions (review_important_actions). Structured permission tooling
exposes app-wide inherit/always_ask/ask_before_writes/review_important_actions/
full_access, not an exact-action or single-session exemption. The server declares
run_session_prompt as an agent write; commands' AUTO is intentionally independent
of MCP consent. The T18 human_approved action is resolved; never replay it.

Proposed narrow behavior: client-owned authorization for an explicitly reviewed
batch binds existing session IDs, exact task/prompt versions and owner source
acknowledgement; Root dispatches once, rechecks idle status, records the execution
receipt, and expires the authorization on scope change/rejection or completion.
This requires a supported client tool/action-scoped confirmation mechanism; the
currently exposed app-wide settings do not implement it. Do not replace it with
server-side automatic acceptance or reclassify agent writes as read-only.

The available app-wide alternative is a Vibe-only full_access override, which
would stop ordinary confirmation for ALL exposed connector tools, including
agent creation and badge/receipt writes. It is broader than routine dispatch and
is NOT recommended as a narrow fix or authorized here. A distinct owner decision
would be needed before any such change. No global change, manual shell command,
credential action or consent bypass is proposed. Root can present this exact
tradeoff and supported dependency to the owner without asking them to run commands.

Official confirmation-control reference:
https://developers.openai.com/plugins/changelog#june-2026
