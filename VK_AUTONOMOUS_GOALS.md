# Autonomous goals in this VK instance

## Status and use

This feature extends the installed Codex native goal engine. It is available to
Codex sessions in every project after deploying the matching VK backend. It does
not require repository instructions or project configuration. Other executors
retain their existing behavior; they do not yet implement this native protocol.
Existing ordinary sessions remain ordinary until a user explicitly starts a goal.

- `/goal <objective>` starts or explicitly replaces the native goal and begins work.
- `/goal status` (or `/goal`) reports persisted native status and usage.
- `/goal pause` pauses an idle session's goal without launching work.
- `/goal resume` explicitly renews a paused run's circuit breakers while retaining
  the checklist and evidence. Do not use it to bypass a still-unresolved blocker.
- The existing Stop button pauses an active native goal before stopping execution.
  Normal live user steering and approval/question interfaces remain available.

An objective may contain up to 4,000 characters (the native API limit). Keep the
full detailed requirements in the conversation when they are longer. A concise
objective should explicitly refer to those requirements, not replace them with a
smaller target. Use a new goal objective to revise an invalidated checklist.
Plan mode requires review before autonomous implementation and cannot start goals.

## Why the old workflow stopped

`AppServerClient::on_notification` treated `turn/completed` as executor completion.
The JSON-RPC reader then signaled exit and the container killed the app-server
process. VK only resumed work if a user follow-up was queued. Stronger repository
prompts could influence the model but could not change this lifecycle boundary.

Manual follow-ups use the stored `coding_agent_turns.agent_session_id` and native
`thread/resume`, retaining the agent's rollout and compacted conversation. They
do not recreate the conversation from the short VK summary. However, neither
that summary nor an information-free follow-up expresses a durable parent goal,
remaining requirements, or progress criteria. Recency and compaction can make the
most recent subtask disproportionately prominent. That is a plausible cause of
local refinement; it cannot be diagnosed conclusively from lifecycle code alone.

The installation has Codex CLI 0.153.4 with `goals` enabled. VK's protocol bindings
are pinned to 0.116.0 and do not expose goal messages. Codex already has persisted
objectives, automatic continuation, usage accounting, completion/blocking tools,
and paused/budget-limited/usage-limited states. VK now preserves that engine's
lifetime rather than duplicating its scheduler or sending synthetic continues.

Native protocol reference:
[Codex App Server goals](https://learn.chatgpt.com/docs/app-server#manage-a-thread-goal).
The installed CLI-generated schema is the version-specific compatibility evidence;
upstream main is useful explanatory context but is not treated as proof of what
this installed binary implements.

## Objective, progress and stop conditions

Codex's native goal is authoritative for objective and status. VK stores supporting
checklist evidence under `CODEX_HOME/vk-goal-progress/<thread-id>.json`, independent
of the workspace repository. Snapshots are written atomically. Missing snapshots
start empty; unreadable or corrupt state fails closed instead of silently losing
progress history. Goal identity includes objective and creation time.

The agent defines a finite checklist covering the whole outcome and validation.
The checklist cannot subsequently shrink, rotate IDs, or rename requirements.
Each completed requirement needs evidence. Rewriting evidence for an already
completed requirement does not count as new progress. The model judges semantic
sufficiency; VK validates the structural contract and bounds repeated activity.

New threads use `vk_goal_checkpoint`. Existing threads cannot retrofit dynamic
tools in the installed protocol, so they may use the identical JSON contract in a
terminal `<vk_goal_checkpoint>...</vk_goal_checkpoint>` assistant-message footer.
Only the current root thread and turn can update progress; tool output and child
thread notifications cannot change the root checklist.

On native turns VK supplies the durable checklist through turn-specific steering,
including a reassessment instruction after three turns with no newly completed
requirement. The native continuation prompt also repeats the objective. A stale
steer is never queued into another turn. This helps after compaction or restart;
the native history and current artifacts remain necessary for contextual detail.

VK pauses the native goal after six turns without closing a requirement, or fifty
goal turns in a run even if the agent keeps claiming progress. A missing checkpoint
also consumes this allowance. A resume preserves completed work and resets only
these run counters. Native token budgets and usage limits remain native; VK does
not silently add a token budget. No secondary scheduling loop is involved.

A checkpoint can request `needs_input` with a substantive reason: required input,
authorization, a design decision, only discretionary refinement remaining, or no
productive next action. VK pauses without labeling this as successful completion.
Normal approval/question tools retain their permission semantics. Failed or
interrupted turns never trigger VK continuation. A native engine that stays idle
for 30 seconds instead of starting its next goal turn is paused and surfaced.

When Codex reports completion, execution ends. If the supporting checklist is
incomplete VK explicitly flags completion as needing review. It does not claim
independent verification of arbitrary code or external outcomes. The model is
instructed to finish only after both the full objective and its checklist are met.

## Tradeoffs and rollout

- This implementation supports Codex goals across all repositories, not autonomous
  execution for Claude, Gemini, or every other VK executor. Native APIs are used
  because this installation already supports them; other adapters can be added
  when they offer equivalent lifecycle and goal-state contracts.
- The progress circuit breaker is deliberately conservative. Deep investigation
  can be productive without closing a requirement in six turns. Choose meaningful
  verifiable intermediate outcomes at initial planning; a pause is a review point,
  not a claim that the work failed or was complete.
- Evidence is agent-reported. Stable IDs and finite counters bound refinement but
  cannot prove semantic correctness or prevent all false completion claims.
- Limits apply at turn boundaries, not within an arbitrarily long single turn.
- Stop tries to persist pause before process termination. If the app-server is
  unresponsive, VK still stops the process and logs the persistence failure; check
  native goal status before resuming after an abnormal interruption.
- Backend deployment/restart is required. Source changes and passing tests do not
  change the running green service. Follow the deployment runbook; do not restart
  active agents as a side effect of testing this feature.

## Reproducible validation

Run all executor tests in the shared Cargo target. The state-machine suite covers
an eight-stage objective across 24 turns, repeated polishing and evidence rewrites,
scope shrinking, missing checkpoints, hard limits, explicit input and serialization.

The ignored `native_goal_runtime` integration test launches the actual installed
Codex app-server against an offline Responses fixture. It uses no credentials or
external model requests. Supply an isolated CODEX_HOME under the task SSD path:

```bash
mountpoint /mnt/vk-storage
mkdir -p /mnt/vk-storage/vk-continuation/native-progress
CODEX_HOME=/mnt/vk-storage/vk-continuation/native-progress \
  CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target CARGO_INCREMENTAL=0 \
  cargo test -p executors --lib native_goal_runtime -- --ignored --nocapture
```

Repeat with fresh isolated directories and `VK_GOAL_TEST_SCENARIO=loop` or
`VK_GOAL_TEST_SCENARIO=needs_input`. These tests exercise native scheduling and VK
lifecycle together. Deterministic model responses prove orchestration, not an
unattended real model's ability to finish an arbitrary substantial software task.

## Validation recorded on 2026-09-11

- 53 executor unit tests passed; the native integration test is opt-in.
- Four installed-Codex offline scenarios passed: eight-stage progress via old-thread
  footers, the same via dynamic tools, repeated refinement, and required input.
- A real GPT-6 Astra evaluation completed a Python NDJSON reporting CLI in seven
  work turns without user follow-ups. All seven checklist requirements closed, all
  21 generated tests passed, independent CLI assertions passed, and native status
  became complete. The run took 378 seconds and native accounting recorded 81,194
  tokens. This is evidence of useful continuation, not a guarantee for every task.
- The real evaluation is explicitly selected with `VK_GOAL_TEST_SCENARIO=real`.
  It uses a real model and account usage; keep authentication private in an isolated
  CODEX_HOME and remove the temporary credential afterward. Work happens in its
  `work` subdirectory, separately from credentials and protocol logs.
- Targeted backend compile/Clippy, frontend type checks (6 GiB Node heap), formatting
  and ops governance passed. Full desktop/workspace checks require the host's
  missing GTK development package; no claim of a fully green baseline is made.
- No live green restart or frontend publication occurred.

The final Stop and fresh-app-server resume scenarios also passed. To repeat a
resume fixture, set `VK_GOAL_TEST_RESUME_THREAD` to a paused fixture's thread ID and
reuse its isolated CODEX_HOME. Set `VK_GOAL_TEST_SCENARIO=stop` for Stop persistence
or `tool` for dynamic checkpoint calls.

The backup helper now snapshots `goals_*.sqlite` through SQLite's online backup
API and preserves `vk-goal-progress`. This is required in addition to native
rollouts and the existing VK state. A restore test verified database integrity,
exact native goal rows and checklist equality. Use the current green backup
workflow and correct green paths when preparing an actual release.

A matching frontend/release binary candidate is staged at
`/mnt/vk-storage/vk-continuation/candidate-b986fed9f/manifest.json`. It has not been
deployed. The runtime source commit is `b986fed9f`; the follow-up commit only adds
backup preservation and final continuity records. Release review, a fresh Desktop
backup, final live inventory and explicit green restart approval remain.

The built backend also passed an isolated HTTP API smoke: repository/workspace
creation, eight native goal turns in one VK coding-agent execution, all eight
requirements recorded, and final VK `completed` status. The offline fixture used
separate data, Codex home, worktrees and localhost ports; it was shut down after
the check. Evidence is in `/mnt/vk-storage/vk-continuation/api-smoke-2/result.json`.
