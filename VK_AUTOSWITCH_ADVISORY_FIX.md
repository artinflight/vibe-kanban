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

This boundary applies to **all otherwise-authorized workers**, including workers
allowed to edit. It has no read-only eligibility condition. The focused harness
now exercises the actual launch selection and sandbox assignment blocks across
read-only, workspace-write, already-authorized full-access and inherited/default
sandboxes, with never/on-request/untrusted approvals. Writable assignments retain
the exact inherited sandbox, approval, working directory and extra configuration;
a read-only assignment still restricts the sandbox. Explicit owner restrictions
and unavailable models still block both worker types. These are source-extracted
fixtures, not proof of native enforcement or deployed behavior.

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
  16 tests passed, including the exact production launch-selection branch with
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

## Enabled operational workaround — 2026-11-12

The compiled `vk_delegate` correction is still not live. A bounded alternative for
independently authorized read-only work is now available without replacing Vibe:
ordinary dedicated Vibe workers started through the existing atomic
`create_issue_and_start_workspace` workflow, in Recommend mode, using the new
`RECOMMEND_READ_ONLY` profile. This is a different existing orchestration path,
not an automatic redirect of failed child requests or a replacement scheduler.

The profile was added through the supported `PUT /api/profiles` route and verified
both through API readback and its persisted file. Every previously existing
profile is unchanged. The new profile copies the existing Sol 6.1/high defaults
and inherited instructions, with native `sandbox=read-only` and
`ask_for_approval=never`: it does not grant write access or permit escalation out
of that sandbox. Existing selected model/effort, routing policies, queues, hot
module and active executions were not changed. The backend stayed healthy with
its original process/start identity. No worker, pilot, or provider probe ran.

Use the worker's exact already-authorized model and effort explicitly; the new
profile is not permission to change them. Use one stable workflow request UUID
for each distinct authorized assignment. Retain it and reconcile native receipts
on uncertainty; never substitute legacy follow-up or a fresh ID after a refusal.
The existing workflow atomically binds issue, workspace, repository, owner and
session, and claims launch once. Existing executor permission/capacity/admission
checks remain on that path. Root/dot must retain the task's explicit owner limits,
approved repository scope and read-only assignment; this route is not a blanket
fallback for tasks with incompatible restrictions, shared writes, or uncertain
prior execution. Do not switch providers, activate Auto, or select Astra.

The normal top-level routing path records its stronger recommendation/reason but
does not mutate the requested execution pair in Shadow, including when a
recommendation is unavailable. No task qualification catalog was weakened. Keep
these workers as bounded leaf assignments, with compact relevant context; native
`vk_delegate` still uses the old admission code until the compiled fix is adopted.

The original pilot's separate safe-continuation readback currently reports
`checkpoint_required` / `native_terminal_capture_unverified`, despite no running
execution, queued input or conflicting jobs. This hold was not cleared and the
new profile is not permission to evade it by recreating an existing task. The
responsible owner must reconcile its terminal/capture evidence before continuing
that original session. Independently authorized new workers use fresh native
sessions and do not copy or replace that session's history.

Validation: nine lightweight offline tests passed in
`python3 -B scripts/testing/test_advisory_worker_profile.py`. They cover additive
profile preservation, idempotent preparation, collision/default-change refusal,
readback mismatch, the existing connector's exact Recommend transformation,
unknown policy refusal and the actual launch-claim SQL's duplicate/uncertain,
owner, repository, chat, existing-execution and link-revision guards. SQL uses
small synthetic in-memory tables; it is not a full backend/native acceptance run.
The tested claim SQL, issue-workflow server and top-level routing source match
the installed backend commit. The earlier 13 delegation regressions remain the
source-fix evidence. No paid inference was used to validate this workaround.

Rollback: through the supported profiles settings route, remove only the added
`RECOMMEND_READ_ONLY` entry after checking that its settings still match this
addition and that it is not in use. Preserve all current other entries; do not
restore an old whole-profile snapshot over later changes. No backend restart is
required for that profile removal. Private deployment/readback receipts remain
outside tracked source. Full live worker acceptance remains unperformed because
the owner explicitly prohibited starting the pilot tests in this task.

## Owner correction: all workers — 2026-11-12

The owner rejected the read-only-only workaround as insufficient. That profile
is historical, unused-by-this-task configuration; it is **not** the completed fix
and is not a requirement for normal writable work. It has not been widened or
silently assigned to any existing session. The actual source fix already applies
to writable and read-only children. Current validation is 16 source-extracted
Rust tests and 10 lightweight Python tests, with no provider or pilot execution.

The installed normal Vibe worker route supports writable profiles and keeps
Shadow recommendations advisory. However, it is not an interchangeable redirect
for every embedded child: the current atomic issue-workflow connector exposes
variant/model/effort, but not the child's complete routing restrictions or explicit
permission override. Its new-workspace ownership semantics also cannot replace
an uncertain existing native child or session. A configuration transform retaining
fields does not prove its public caller accepts those fields. Do not discard those
restrictions, recreate held work, or substitute a default profile to use the route.

The running backend still owns the embedded `vk_delegate` veto. The protocol-2
module cannot change that launch branch; ordinary profile reload changes executor
settings, not executable code. No universal no-restart deployment was established.
The healthy original backend process, persisted profile configuration and atomic
workflow capability were re-read at 14:14:52 UTC; configuration exactly matches
the prior limited-profile receipt. No live mutation was made in this correction.

Acceptance remains: all worker types, unchanged selected pair and real guards,
advice visible, and actual runtime adoption. The source fix and focused tests
satisfy only the source portion. Full backend compilation/native fixture acceptance
and deployment remain unperformed. A backend restart is prohibited by the owner;
there is no permission here to substitute a restart, memory patch, new backend,
weakened model qualification, or unrelated launcher. Do not report this feature
as deployed from the existence of a read-only profile or passing source fixtures.
