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
