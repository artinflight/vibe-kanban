# Recommend-mode delegated launch correction

Source-only correction on `fix/autoswitch-recommend-advisory`, based on staging
`bc3b89deef1203dcf8851c0e294a58c8fbeca1de`. No deployment, restart, model selection
change, provider call or Art in Flight pilot run is part of this work.

## Cause

Commit `c4bd82c9c2e012dcbbad9fa3d8041536246577de` (October 1, 2026),
“Extend AutoSwitch V2 policy to bounded delegated Codex work”, deliberately required
an inherited Shadow child to qualify for the assessed task envelope. Its helper
changed the policy to Auto, filtered the qualification registry to the inherited
pair, and enforced the global minimum-required task allowlist. The original guide
explicitly documented refusing the child if that check failed. This extended an
Auto selection safeguard into the advisory mode and contradicted Recommend's
purpose. A follow-up assessment increasing the floor also required escalation
consent even though Shadow would not change the worker.

## Corrected boundary

Recommend is serialized as `shadow`. The child keeps the inherited model and
reasoning effort. Its recommendation, assessed envelope/floor, classification
source, semantic reasoning and usage telemetry remain in the existing decision
and status records, separate from actual execution settings.

The advisory task-envelope qualification is no longer a launch veto. A distinct
selected-worker check still enforces explicit owner exclusions and capability
floors, released-model status, current availability and supported/verified effort.
It takes no recommendation input. Auto still uses the existing full task
qualification and protected-work policy. No model catalog or qualification rows
were changed. A newly assessed advisory floor does not require execution-escalation
consent; existing observed-failure consent and frontier-failure protection remain.
The Shadow child brief states the explicit owner floor rather than presenting the
advisory parent assessment as an execution requirement.

The actual launch code for permissions, read-only sandbox, repo scope, job leases,
spending/capacity, cancellation, duplicate admission, parent-turn ownership, native
provider/model/effort/tier confirmation and uncertain outcomes is preserved. No
alternate launch route or classification bypass was introduced.

## Context hygiene

The existing dynamic delegation instructions now ask for compact handoffs, precise
file reads, relevant log excerpts and changed findings rather than repeated
unchanged investigation history. Required approvals, decisions and unresolved
risks must survive compaction. This closes an instruction gap on the real prompt
path; it does not truncate stored conversation history or omit repository rules.

The reported 164.9M-token/96% cached-input observation was supplied with the task.
Its underlying window, cost weighting and per-agent duplicate-context attribution
were not independently measured here. Cached input alone does not prove avoidable
waste. No currency, percentage saving or accepted-task cost improvement is claimed.
The new instruction text itself adds some context; total-task benefit needs later
observation of ordinary work, without generating a paid benchmark.

## Validation and review

- `python3 -B scripts/testing/check-recommend-delegation.py --output <mounted-SSD-check-directory>`:
  13 tests passed, including the exact production launch-selection branch with
  fixture catalog/clock inputs. The original immutable veto returns false for
  the same stronger-Astra/inherited-Sol case, and the corrected branch retains
  Sol/xhigh and the stronger advice. Ten tests also belong to the normal Rust
  executor suite. No dependency installation or Cargo compilation was required.
- The harness separately compares three unchanged launch/fence code regions and
  verifies the production call site. Those are static preservation checks, not
  native security or end-to-end acceptance.
- `pnpm run format`: Rust formatting passed; frontend stage could not run because
  Prettier is absent. No frontend source changed or dependency installed.
- `pnpm run ops:check`, Python AST parsing and `git diff --check`: passed.
- Full executor/backend compilation, native app-server interaction and live
  acceptance were not run. The shared dependency cache is empty; no heavy rebuild
  or provider inference was started.

Next: review this focused diff separately from the retained provider-failover
branch. In the normal approved build lane run
`cargo test --locked --offline -p executors --lib routing_delegation`
and the existing `delegation_cancel_dispatch_keeps_reader_and_parent_alive` and
`active_goal_delegates_bounded_specialist_without_transferring_ownership` fixtures,
then the usual backend check. These protocol fixtures use synthetic peers, not
real providers. Staging owns integration and a separately authorized release.
The corrected veto is compiled executor code; publishing just the routing hot
module cannot replace it. Nothing here authorizes restarting Vibe or the pilot.

## No-restart deployment investigation — 2026-11-12

The owner subsequently authorized deployment without restarting Vibe. Read-only
verification matched the live executable hash to the recorded October 30 backend
and found the original refusal text in the running binary. Its exact source still
calls `actual_pair_qualified` from `Delegation::launch_choice`. The active module
remains `astra-hold-a71fb2b2b-20261021`; all three payload hashes match its manifest.
Backend health returned HTTP 200 and the service identity/start time was unchanged.

The supported protocol-2 worker returns only assessment and semantic-classification
need. Its reloadable catalog and classifier instructions do not replace the
compiled delegation admission check. The profile reload endpoint reloads saved
executor settings only. The delegation instructions are also compiled with
`include_str!`; classifier instructions are a different prompt. No supported
no-restart admission override was found in the deployed source.

Publishing a module cannot install this correction. Altering assessment/catalog
qualifications to make the old veto pass would change routing policy, including
Auto behavior, instead of preserving advisory recommendations and hard guards.
No such workaround, module publication, profile change, service action or pilot
execution was performed. The source fix remains prepared for the next separately
authorized backend release; no-restart deployment is blocked by that installed
code boundary, not by a missing publication approval.
