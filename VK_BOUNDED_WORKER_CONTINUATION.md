# Fixed original-worker continuation

This branch implements a default-off, process-scoped backend capability. It is
not live and not staging-ready until compiled integration checks and independent
review pass. The older prepared commits remain on the MCP Approval Bridge branch;
this narrow branch starts at current verified staging, retaining its newer
consent-size and capacity fixes.

## Authority and lifetime

The verified dot conversation supplies initial authority. The release owner must
adopt a private contract containing the exact original manager/worker session,
workspace, native thread, saved full executor configurations, native goal identity
and objective, revision instructions, original execution anchors, repository/task
ownership and immutable required-asset pins. Actual IDs, consent evidence and
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
