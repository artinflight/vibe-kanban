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

## October 1: Pre-Cutover Preparation Performance

Branch `fix/vk-precutover-preparation`, based on fork/staging620bd7eb9.
Scope: versioned preparation-only tools, verified static evidence/artifact reuse,
rolling online backup checkpoints, bounded concurrent queue inspection, and
whole-preparation timing. The fenced capture callback now has real private
handover/recovery acceptance and is approved for staging integration. See
VK_PREPARATION_PERFORMANCE.md. No production pause/restart/reroute, application
feature change, or replacement of an existing production controller.
Inherited stream notes below describe other work, not this branch's authority.

## AutoSwitch V1 staging-only release

Branch `release/autoswitch-v1` rebases validated V1 onto staging56792a72c.
See [VK_AUTOSWITCH_V1_STAGING.md](VK_AUTOSWITCH_V1_STAGING.md) for exact commit
mapping, preservation of newer staging behavior and operator deployment notes.
V2 remains untouched on `vk/5a81-autoswitch-cu-recovery` at64e9cb5bd and is
excluded. Only continuity documents conflicted; no source conflicts. The operator
owns all post-merge actions. Do not contact or trigger a deployment/staging agent.

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

## September 28 — two concurrent selected capacity goals

Added bounded two-agent admission and per-session stop, retaining shared allocation,
independent native/OS deadlines, same-workspace exclusion and interactive priority.
See [VK_CAPACITY_CONCURRENCY.md](VK_CAPACITY_CONCURRENCY.md) for API semantics,
real two-native-goal acceptance and deployment requirements. Companion CU changes
are required; old clients keep one slot. Production deployment remains operator-owned.

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

## September 30: scheduled resume history

Scope: scheduled capacity resumes preserve native-goal supporting progress,
turn/stagnation counters, recovery plans and substantive input holds. Explicit
manual resumes retain their current fresh-attempt behavior. No scheduling,
quota, containment or selected-agent admission limits are relaxed. This is the
manager-side fix; the active Chat Orchestration implementation is separate.
