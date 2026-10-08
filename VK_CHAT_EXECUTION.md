# Execution and resume procedures for VK Chat

These procedures govern this implementation stream. Read them on pickup after
AGENTS.md, STATE.md, STREAM.md and the current HANDOFF.md entry. They supplement
native goal controls and repository safety rules; they do not start, resume or
complete a goal, authorize spending, or authorize deployment.

## Work toward a usable result

The next product milestone is a demonstrable global text supervisor: open its UI,
ask about a workspace, inspect a source-linked reply, send an ordinary authorized
instruction to the existing agent, and see the delivery/result with raw-evidence
access. Existing workspace chat must stay raw and work without the supervisor.
Mocks prove component behavior; this milestone also needs an authorized real-model
and agent demonstration. Do not call a fixture-only demonstration usable acceptance.

First close the specific failing/unvalidated work recorded in HANDOFF.md. Then
move to the above milestone. Add backend work only for a concrete requirement,
observed defect, or dependency of that outcome. Defer discretionary refinements;
do not defer necessary security, correctness or required acceptance checks.

Following milestones remain: natural spoken-text evaluation with a real model;
provider/native transport proof; Android native voice call; physical phone/car
controls and recovery; remaining integration, privacy, restore and release gates.
Use VK_CHAT_IMPLEMENTATION.md for dependencies and full acceptance. A useful first
slice is not a reduction of the full objective or its fixed native checklist.

## Start each authorized work window

1. Read current artifacts and the native goal/checkpoint when one exists. Check
   branch, HEAD and dirty state; preserve edits. Documents saying "active" do not
   prove that runtime goal ownership or permission is still active. Do not recreate
   a missing goal or run an independent continuation loop.
2. Recover the last job before issuing another equivalent command. Poll its exact
   tool/job handle. When unavailable, inspect recorded host process identity/start
   time, exit record and outputs where accessible. A timeout or quiet log is not
   termination; a missing handle with an independently live process is not a reason
   to duplicate it. Reuse completed results when they cover the current code.
3. Check mounted build storage, available headroom and relevant permissions. Use
   the dedicated SSD Cargo target with incremental compilation off. Investigate
   insufficient space under the host cleanup policy, never broad-delete caches,
   active work, attachments or databases. Recheck old blockers rather than inheriting
   yesterday's network, browser, credential or storage state.
4. State one observable outcome, the acceptance evidence, dependencies and an
   estimated time allocation within the actual authorized window. This is an
   execution plan, not a newly invented token budget or permission expiry. Surface
   missing model/provider access, bounded spend approval, hardware or deployment
   authority before starting work that depends on it; continue independent work.

## Keep work bounded and close it

- Reassess halfway through the planned allocation and when evidence changes the
  approach. If the outcome is slipping, diagnose the reason and choose a productive
  next action; do not silently extend a backend subproblem through the whole window.
- Reserve time before the known window ends to record results and exact pickup
  state. Do not start a predictably long build just before expiry without an
  authorized surviving job and observable recovery path. Do not kill healthy work
  merely to manufacture a neat checkpoint; record a live job as pending.
- Run the narrowest checks covering the actual change, plus mandatory repository
  checks. Broaden only for new changes, failures, integration concerns or required
  release/PR validation. Do not rerun passing checks solely because a turn resumed.
- Close a slice with its tests, limits and pickup state before adding optional
  edge cases. An auto-save commit preserves work; it does not certify that work
  compiles, passes tests or is ready for use.
- Move on once a requirement is sufficiently met. Preserve the fixed full-goal
  checklist; do not inflate progress by splitting it into easier completed items.
  Follow native no-progress/recovery rules in addition to this outcome review.
- Stop immediately on a user stop or revoked authorization. Leave genuine required
  decisions as needs_input when supported; do not ask again for permission already
  granted, or treat elapsed time as approval.

## Leave a recoverable checkpoint

Keep the current HANDOFF.md entry concise and authoritative over its dated history:

- HEAD/working tree state and the outcome this window attempted.
- What changed, what was demonstrated, and what is still unverified.
- Exact validation command, source revision plus dirty-state identity, exit status,
  and unique log/artifact path. Record filtered suites; do not sum reruns as extra
  coverage. Retain failed-run evidence rather than overwriting it with a rerun.
- For a live job: tool session/job ID, host PID/start time if available, working
  directory, output path and last authoritative observation. Mark missing evidence
  explicitly; never invent handles, success or elapsed token usage.
- Exact remaining defect or blocker and the first next action. Record who must act
  only when a real external decision/action is required.

Update the native checkpoint when available; mark broad requirements complete only
with evidence matching their full scope. Keep proof in durable files as well as
chat. Do not let progress bookkeeping trigger a duplicate goal or worker.

## Report honestly

Lead with what the user can now do, what was actually demonstrated, what remains
untested/blocked, and the next outcome. Distinguish implemented, fixture-tested,
live-tested and deployed. Do not use uncalibrated percentages, line counts, commits
or test counts as overall completion measures. "One of nine requirements verified"
is a checklist fact, not an effort percentage.

Report token/cost usage only from an actual usage ledger, identifying scope and
cached/billed distinctions where available. Build wall time is not token usage.
Call a wait verified only after observing a specific live job. Disclose incomplete
work without presenting a polished status update as implementation progress.

## Audit for the managing orchestration agent

The separate MCP-host report is:
`/mnt/vk-storage/reports/vk-chat-orchestration/2026-09-30-resumable-goal-audit.md`.
It contains evidence, limitations and proposed manager-level safeguards. Those
safeguards are recommendations, not claims that the manager already implements them.
