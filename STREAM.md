## Delegated work continuation (2026-10-01)

AutoSwitch now admits native leaf children through `vk_delegate` on the existing
app-server connection. Auto reuses V2 subtask assessment/qualification; Shadow keeps
qualified parent settings and records recommendations. Explicit/protected floors,
exclusions, bounded briefs, duplicate/overlap checks, existing capacity, native
interrupt and consented boundary escalation apply. Native child settings are checked
before inference; child logs cannot replace root identity. CU v1 remains unchanged,
with child turn bindings plus additive `vk.delegation.v1` hierarchy/usage events.

Read [VK_AUTOSWITCH_DELEGATION.md](VK_AUTOSWITCH_DELEGATION.md). New chats are needed
for dynamic tools; leaf-only delegation is disabled for native goals/scheduled runs.
The paid two-turn native harness was attempted once and blocked before inference
by the existing execution-capacity guard. Do not claim native child acceptance or
live V2 Shadow has passed. Finish that bounded check when capacity is genuinely
available, then the planned full Shadow check. No staging/deployment changes or
agent coordination occurred. Prior V1 deployment and V2 work remain preserved.
Validation: 119 executor tests pass (five opt-in runtime tests ignored),
executor/services Clippy, format/ops and CU contract byte comparison pass.

## Semantic fallback continuation (2026-10-01)

Auto/Shadow now adds one bounded gpt-5.6-luna/low/standard classification turn only
for materially uncertain deterministic assessments. Known envelopes, manual/pinned
execution and protected floors skip inference. Closed structured output feeds the
existing qualification/floor/exclusion and consented escalation logic. No tools,
implementation loop, staging/deployment changes or agent coordination.

Native sample: ordinary assignee display -> Luna6/medium; private-project access
-> Astra/high; vague/persistence/intermittent-failure requests -> Sol6.1/medium.
Two deterministic controls incur zero calls. Five final classifier calls measured
3,978–3,986 input tokens, 78–133 output and 4.344–8.664 seconds each. One initial
transport check also ran. Classification attempts/usage persist in decisions and
a separate vk.classification.v1 feed; CU vk.routing.v1 is unchanged.
Read VK_AUTOSWITCH_FULL_ROUTER.md for configuration, bounds and actual evidence.
Validation: 29 focused regressions, executor/services Clippy, generated-type and
web-core TypeScript checks, format and ops pass. Source-only; live V2 Shadow QA
and net-savings measurement remain pending.

## Natural-language triage continuation

V2 now recognizes common presentation outcomes on named UI surfaces and corroborates
them with bounded repository evidence at the existing execution boundary. Structured
triage includes uncertainty, validation availability and inspection counts; missing
context retains Workhorse. No planning model call, registry change, CU contract change
or V1 deployment work. Read VK_AUTOSWITCH_FULL_ROUTER.md for scope and limits.

## V2 resumed after V1 staging integration

Continue on `vk/5a81-autoswitch-cu-recovery`; V1 PR127/deployment is separate and
must remain untouched. Follow-up qualification persistence and lexical assessment
repairs are implemented, plus a read-only policy recommendation command. Details:
[VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md). This is not live
activation or live Shadow evidence. No V1 model acceptance campaign was repeated.

# Automatic assessed router (V2)

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Extends accepted V1 with default task assessment, explicit model/effort/envelope
qualification, configurable pair preference, operator-reported validation and
risk-expansion escalation. See [VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md).
Auto can choose older Luna/low, Luna6/medium and Sol6/medium without Routine labels.
Manual and explicit floors/exclusions remain authoritative; no scheduler or reset.
Experimental pairs remain shadow-only. Matching release deployment and a small
live Shadow sanity check remain pending; no production activation in this stream.

## Accepted V1 history

# VK Model AutoSwitch V1

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Scope: opt-in model/effort routing at existing Codex execution boundaries.
[VK_MODEL_AUTOSWITCH.md](VK_MODEL_AUTOSWITCH.md) supersedes the planning-only
catalog and describes policy, implementation and enablement gates.
[VK_CODEX_ROUTING_CONTRACT.md](VK_CODEX_ROUTING_CONTRACT.md) defines usage joins.
All seven required models execute on isolated CLI 0.159.2 using the existing
account. Default host CLI 0.153.4 and production VK remain unchanged.
Manual, shadow and automatic modes preserve per-chat control; automatic routing
requires fresh executable-pair evidence and pauses rather than violating floors.
CU-compatible lifecycle telemetry is implemented. Native executor acceptance
passes at the existing capacity limit; private candidate API acceptance and CU
correlation evidence are tracked in VK_AUTOSWITCH_ROLLOUT.md. The active worktree
was externally deleted; recovered source is outside the managed worktree tree at
`/mnt/vk-storage/vk-model-autoswitch-20260930/source`.
No production restart, deployment, global profile change or autonomous retry.

## Inherited integration context

The following notes describe inherited work, not this branch's task scope.

# Capacity Cutover Lock

Current scope: implement authenticated ownership release/acquire with fresh
state reload and paused same-PID fallback for compatible backends. Production
cutover is explicitly withheld by the operator, who is using VK. Do not stop,
pause, restart or reroute production. See VK_CAPACITY_OWNERSHIP.md. The running
legacy backend requires a separate one-time upgrade before using this protocol.

Fix read-only readiness to detect a capacity owner that survives process pause.
Branch fix/capacity-cutover-lock adds the existing-inode lock barrier and real
kernel-lock tests; it does not change production services or silently replace
the operator's same-PID standby requirement. Restart-based recovery is separately
rehearsed with copied data and requires explicit approval before production.

## Integrated Codex Model Selector Regression

Restore GPT-6 reasoning choices and hide GPT versions below5.6 in the Codex
selector. Updated onto staging fa7523c17, this frontend-only compatibility correction
does not rewrite existing chat selections, drafts, defaults or native settings.
No backend restart. See `VK_MODEL_SELECTOR_FIX.md` for evidence and deployment.
## Integrated Staging Context: VK::Weird Message

Scope: reconcile native goal completion evidence within the current turn and
report completion status in the standard summary metadata. Replace the generic
checklist warning with `Completion::` after `Human Needed::`, naming missing
evidence when unverified. VK normalizes its status into the existing report;
a response without a standard report receives a compact metadata line.

The reconciliation request is a single turn/steer pinned to the current root
turn. It never starts another turn, reopens the goal or changes its budget.
Final checkpoints remain accepted after the native completion notification.
A rejected/late steer falls back to an honest unverified status. Checklist
verification is supporting evidence, not an independent audit of the objective.

Backend and shared frontend changes are pushed for
[PR #123](https://github.com/artinflight/vibe-kanban/pull/123) into staging.
They are not deployed. See HANDOFF.md for validation and deployment boundaries.
