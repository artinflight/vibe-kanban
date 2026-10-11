# Fixed original-worker continuation

This branch implements a default-off, process-scoped backend capability. It is
not live and not staging-ready until compiled integration checks and independent
review pass. The older prepared commits remain on the MCP Approval Bridge branch;
this narrow branch starts at current verified staging, retaining its newer
consent-size and capacity fixes.

## Independent-review corrections and adoption boundary

The review of03b95d857 invalidated the earlier readiness claim. PR243 remains
draft until the corrected exact head passes compiled checks and independent
review. Historical green runs below did not cover the identified launch paths.

The actual cached CodingAgent clone, with saved overrides, is checked before
prompt/command construction or launch. Its rendered continuation is pinned in
memory. Every worker native start, including asynchronous approval feedback,
passes a final one-shot fence held until the native RPC responds. Terminal
revocation/readiness shares that fence. Active or unknown worker goals are
rejected before thread/resume, since loading can itself activate native work.

Raw saved routing may be absent. A separate release-adopted Shadow/Recommend
policy feeds a temporary resolver copy; the persisted and launched configuration
remains identical to the originals. Collision checks cover every session in the
worker workspace and canonical shared worktree. Queue take/start/requeue remains
inside admission. When this capability is default-off, unrelated starts do not
acquire its global mutex.

The corrected backend journals ordinary input before steering/queueing, even
while the capability is disabled. The private contract pins the producer coverage
receipt, journal watermark, native rollout path and complete input-prefix digest.
Native input, dropped/reset execution history, rollback/compaction and partial or
unknown history cannot silently amend the grant. Only exact receipt-bound worker
input survives suffix validation; images in the adopted prefix remain hashed.
No transcript or profile contents enter diagnostics.

A legacy contract captured before journaling cannot prove that old ingress has
no pending steering. Current executable adoption still rejects it. The previous
two-restart install/capture/adopt plan does not meet next-restart usability and is
superseded by the following proposal; adoption mechanics are not changed here.

### Proposed one-restart bootstrap, for release-owner review

Use the existing trusted private startup artifact and its SHA256 release pin,
never an agent/API grant payload. The artifact retains the exact fixed approved
scope, original identities, profiles, goal identity/objective, assets and native
input-prefix digests; bootstrap may supply producer coverage, not new authority.
The release coordinator must first prove the old ingress producer is gone and
that neither original native thread has a writer or pending steering delivery.
This requires the existing restart inventory plus a pinned old-producer/process
identity receipt, checked against kernel process identity at startup. A killed
execution row alone is insufficient. Unrelated processes are not stopped.

Before any HTTP/relay/queue/scheduled request ingress, startup verifies that
quiescence evidence against the selected dataset/native home, verifies both exact
captured input prefixes and existing execution histories, starts durable coverage,
and seals its watermark into a derived durable contract. No changed history can
be recaptured into authority. Adoption must be atomic and idempotent: preserve a
previous derived contract and all terminal/uncertain states across restart. The
normal caller/profile/goal/assets/access/resource/capacity/ownership guards remain
required on every dispatch. The coordinator must inventory all ingress tasks so
no task can run between quiescence verification and admission registration.

Required isolated acceptance: old producer/native writer still alive or unknown
rejects bootstrap; changed/truncated/dropped/steered input rejects it; wrong
release pin/dataset rejects it; startup ingress waits for successful adoption;
identical bootstrap survives restart without rebaselining; revoked/ready grants
and uncertain attempts remain closed. Validate these before changing adoption
mechanics or calling this a one-restart-ready feature. This turn creates no
quiescence receipt or live grant and authorizes no actual restart.

Authority is the existing verified owner approval, held by the already trusted
release owner and backend/state. The receipt proves quiescence/freshness, not
consent. Same-UID/backend-host compromise can alter this trusted base; the design
provides no external custody or independent host-compromise protection. No short
TTL, routine renewal, agent-facing creation/amendment endpoint or new access is
introduced.

### Remaining guard corrections

Collision candidates come from running non-development executions and queued
sessions regardless of workspace archival/deletion or execution drop flags.
Resolve each active candidate's canonical ownership; unknown active ownership
fails closed. Unrelated missing idle history contributes no candidate.

Goal/get, thread/resume and turn/start receipt delivery/waiting is bounded to ten
seconds per RPC, including pipe writes. Timeout removes the pending response
entry. Under the launch fence, unavailable receipts persist an uncertain attempt
and suspend future starts. They neither replay nor send an exit signal to stop
already-dispatched work. A late response cannot unlock authority. Explicit owner
revocation can acknowledge after the bounded wait and persists across restart.

The old private source delivery receipt and contract are superseded and must not
be used for activation. Root coordinates independent review and the currently
clarified idle Staging acceptance after corrected head/test evidence. Scheduled
artifact loopback isolation remains FAILED until its authorized route succeeds.

## Authority and lifetime

The verified dot conversation supplies initial authority. The release owner must
adopt a private contract containing the exact original manager/worker session,
workspace, native thread, saved full executor configurations, native goal identity
and objective, revision instructions, original execution anchors, repository/task
ownership, effective profile digests and immutable required-asset pins. The
profile digests cover the resolved cached profile with saved overrides, including
launch and permission settings; invocation rechecks them without logging their
contents. Actual IDs, consent evidence and
asset locations must never enter public Git, fixtures or PRs.

`VK_BOUNDED_WORKER_CONTRACT` selects that private release artifact;
`VK_BOUNDED_WORKER_CONTRACT_SHA256` pins its exact bytes. The pin is integrity
evidence, not proof of consent. Authority comes from the verified owner approval
and trusted release-owner adoption. Neither setting is accepted from an MCP
argument or VK follow-up. The startup loader rejects a worktree-local artifact,
incomplete contracts, changed existing grants and altered saved profiles.
No agent-facing operation creates, broadens, renews or reactivates authority.

There is no short clock TTL or renewal loop. Lifetime is the fixed current
revision goal, ending at review readiness or revocation. A changed/unknown goal
or new ambiguous input suspends the grant permanently; it cannot silently amend
the contract. A subsequent scope requires new independently verified owner
authorization and release adoption, outside this capability.

The backend and its database remain the already trusted computing base. The
scope is fixed in the adopted in-memory contract; durable state records only
its digest, terminal lifecycle and attempts. This does not provide external
custody or independent protection against compromise of the backend host,
service settings, executable or same-UID state. Same-UID filesystem access is a
real limitation, explicitly retained. Existing platform app-wide consent and
notification subscriptions cannot represent this scoped grant and are unchanged.

## Invocation and admission

Only the saved original manager receives an execution-bound Unix-socket/stdio
transport, with a backend-created process nonce. The backend chooses the caller
from its own execution context, not request metadata. The nonce stays in process
environment; request diagnostics never echo it, parameters or contract contents.
Actual registered native thread/turn, model and effort are checked. Both normal
chat and existing `/goal resume` launch paths verify resolved profile values.

`continue_original_worker` accepts no target, prompt or metadata. The backend
selects the original worker and renders instructions from the adopted contract.
The fixed marketing clarification is grey date placeholders across headers,
chart axes and task dates, with literal dates only in unchanged QA sources.
No old field counts or task-date edits define scope. Terminal no-argument tools
can revoke the grant or end it at owner review readiness; neither approves work.

The existing follow-up handler performs dispatch. Continuation, ordinary input,
queue steering and process admission share serialization. Before dispatch the
backend checks caller/current execution, native goal and original thread,
workspace/task/repository ownership, latest worker input, idle/queue collision,
original full profile, Recommend mode, required asset/access pins, global capacity
and fresh three-sample RAM/swap/PSI/SSD evidence. The native worker verifies thread,
model/effort, goal, assets and resources again before inference. Capacity denial
cannot put a bounded request into the ordinary queue. Existing Figma/AE and every
unrelated action keep their approval paths; the one-shot bridge is unchanged.
Bounded launches use a read-only capacity-controller admission instead of the
interactive takeover path: existing scheduled authority blocks the continuation,
without lease revocation or stopping another execution. Manager history after the
adopted anchor is checked at binding and invocation; only unchanged native goal
resumes are allowed. Inputs accepted before loading this feature cannot silently
amend its authority.

## Durable attempts

A unique pending reservation is persisted under admission before dispatch, and
the execution receipt is bound before spawning the process. Concurrent and
repeated invocation IDs cannot cause another dispatch. Lost responses, process
failure and backend restart leave an uncertain attempt. There is no blind retry.
Only a matching durable successful original-worker execution can reconcile an
attempt; running, missing, failed and killed receipts remain closed. Revocation
and readiness survive restart and cannot be reactivated by reloading the artifact.

## Validation and release boundary

Fixtures are synthetic. The tests exercise the actual stdio parser, integrated
admission engine, SQLite ledger, caller checks, simultaneous/repeated requests,
terminal lifecycle and uncertain receipt/restart reconciliation. Native transport
uses the already verified installed0.159.2 same-thread/paused-goal resume route.
The previous two interrupted full-crate tests remain unverified; the policy
kernel's20 tests are not acceptance for this implementation.

Hosted Test run38138968513 compiled commit975856c1: all six initial continuation
integration fixtures passed, with518 workspace tests passed and11 skipped.
Frontend checks/approval UI fixtures and schema checks passed. Clippy and Tauri
stopped on one unused mutable binding, corrected in the follow-up. The expanded
fixtures now exercise the production Unix proxy/backend nonce path and exact
ContainerService pre-spawn gate; their compiled result is pending the next run.
Scheduled-artifact run38138968480 failed the existing bubblewrap loopback
prerequisite (`Failed RTM_NEWADDR: Operation not permitted`), before artifact
compilation. This is retained as a validation/release boundary, not bypassed.
Follow-up Test run38140071765 at4f2c3368b passed all nine continuation fixtures,
521 workspace tests (11 skipped), schema, Clippy, frontend and Tauri checks.
Final Test run38140591079 at03b95d857 passed all10 continuation fixtures,
522 workspace tests (11 skipped), Clippy, schema, frontend/approval UI and Tauri.
Scheduled artifacts remain blocked by the same runner namespace prerequisite.
The private source delivery receipt is retained outside public source; it is
proposed for review, not an accepted next-restart entry.

No Cargo build is permitted on the constrained MCP host. The established Desktop
WSL ordinary-user context remains unavailable; no root or permission workaround
is allowed. The inspected PR Test workflow supplies check-only hosted compilation,
schema checks, Clippy and workspace tests; draft publication is for validation,
not readiness. Deployment workflows do not trigger on this feature branch or
staging. No deployment workflow may be dispatched for this task.

After compiled checks and review, the staging owner must accept the exact narrow
source SHA and a next-restart entry, including the private adopted artifact. A
separately authorized restart activates matched backend/stdio code. Actual
approval-free behavior remains unverified until the original manager makes a
legitimate continuation and its receipt is observed. No real test/competing
manager or worker prompt belongs in validation.
