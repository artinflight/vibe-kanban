# Specialist assignments under an active goal

The NODEs run was explicitly authorized to delegate a bounded Task correction.
Automatic review rejected `run_session_prompt` at 2026-11-04 21:04:55 UTC because
runtime instructions prohibited delegation while a native goal was active and
required the unavailable `vk_delegate` capability. Source inspection confirmed
both the blanket instruction and admission checks. The affected native thread
was created with only `vk_goal_checkpoint`. Codex 0.166.0 cannot retrofit dynamic
tools through thread/resume. This was an instruction/capability mismatch, not a
lack of user authorization or a request to transfer ownership.

## Corrected contract

- The orchestrator alone controls the native goal, checklist, continuation,
  review, integration and completion. A specialist supplies bounded evidence.
- Routed in-process assignments use `vk_delegate` with existing scope, duplicate,
  capacity, model qualification, approval and execution-journal safeguards.
  Children have goals and further delegation disabled and cannot finish the root.
- `/goal` startup and resume now initialize the same routed delegation controller
  as ordinary chat. Existing native threads keep their actual tool inventory.
- An explicitly authorized continuation of an existing Vibe specialist session
  may use the supported `run_session_prompt` route even while the root goal is
  active. Check ownership/status first; preserve saved settings and active work,
  reconcile uncertain receipts, collect the result and keep the parent in charge.
  Missing dynamic tools do not require pausing the goal or inventing a raw launcher.
- Goal replacement while children are active remains rejected. Stop and stale-turn
  checks remain enforced. Parent turn completion with outstanding in-process
  children still interrupts the children and surfaces failed collection.
- Explicit native token budgets and scheduled capacity remain restricted: native
  root accounting is not aggregate child accounting. Alternative routes must not
  evade these restrictions. Child usage stays in the delegation journal/telemetry.

## Verification and release

Regression coverage runs the existing bounded child protocol fixture with an
active parent goal, including cancellation, read-only scope, launch, result/usage
collection, follow-up and stale-turn rejection. Separate tests verify that child
goal notifications cannot mutate the parent goal or checklist, and budget/stop
fences still reject new child work.

Local offline Rust compilation is blocked by the missing serde registry entry.
Rust formatting passed; full `pnpm run format` reaches missing Prettier because
this old worktree no longer has frontend dependencies. No frontend files change.
Hosted CI will be the Rust validation authority. No live NODEs assignment, native
goal, service, provider setting or device was changed. Activating the new runtime
instructions requires a managed backend release and a subsequent native turn;
an already-running turn retains its earlier instructions.
