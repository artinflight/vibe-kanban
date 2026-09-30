# VK Model AutoSwitch: feasibility and investigation plan

Investigated 2026-09-30 against VK `1b31e18748ea347c7303688deb9eb1704a764550`
on `vk/5a81-vk-model-autoswi`. Status: planning, not an implemented router.

## Recommendation

**Routing is technically feasible at new-execution and follow-up boundaries.**
VK already carries model and reasoning overrides into Codex thread start/resume.
There is no demonstrated safe hot-swap inside an active turn, and no evidence yet
that a particular cheaper model preserves Astra-quality results on our workload.
Build an opt-in recommendation/shadow phase before automatic selection; qualify
narrow task classes through measured outcomes before enabling execution changes.

The minimum safe tier should be an empirical eligibility rule for a task, repo,
validation environment and model/settings combination—not a universal ranking.
First filter for quality, capability, availability and user constraints; then
minimize expected **total accepted-task cost**, including review and rework.
If the safe set is empty or unaffordable, pause/defer rather than lower the floor.

## Evidence and scope

Read the selection, action persistence, Codex RPC, queue, native-goal, log and
capacity paths listed below; inspected recent Git history and continuity reports.
Ran a read-only `initialize` → `initialized` → `model/list` probe using installed
`codex-cli 0.153.4` and Green's Codex home. The response had no next page, including
hidden models. No inference turn, task replay, production restart, profile change
or deployment was performed. Discovery establishes an advertised catalog, not
successful execution or account entitlement for each model.

Local cache corroboration: Green `models_cache.json`, fetched
`2026-09-30T11:29:09.547475896Z`, client `0.153.4`. Only model metadata and selected
nonsecret config fields were read; credentials were not inspected. The probe
used the installed CLI and Green home; this does not establish the executable or
configuration of every already-running VK agent. Recheck the actual launcher,
provider and account identity before a pilot.

CodexUsage source was inspected read-only at `/home/mcp/code/codexusage`, HEAD
`400fa63f029adf64ebeb610ddc195cf15309dbdd` **with existing local changes**. Findings
refer to those files as observed, not a clean commit or verified live service.
No statistical workload audit or cross-model quality benchmark was run.

## Models and settings actually discovered

All four models below were returned by native `model/list`, are represented in
this session's model options, and can be represented by VK's executor config.
Their task suitability remains a hypothesis requiring local evaluation.

| Exact ID        | Native description/role                                   | Native default effort | Native efforts                       | VK usable efforts |
| --------------- | --------------------------------------------------------- | --------------------- | ------------------------------------ | ----------------- |
| `gpt-5.6-luna`  | Fast, efficient older model                               | medium                | low, medium, high, xhigh, max        | same              |
| `gpt-5.6-terra` | Balanced older model for straightforward work             | medium                | low, medium, high, xhigh, max, ultra | low through max   |
| `gpt-5.6-sol`   | Older workhorse                                           | low                   | low, medium, high, xhigh, max, ultra | low through max   |
| `gpt-6-astra`   | Frontier model for demanding work; native catalog default | medium                | low, medium, high, xhigh, max, ultra | low through max   |

Native metadata reports text/image input for all four, multi-agent version `v2`
for Astra/Sol/Terra and `v1` for Luna. This is a compatibility distinction, not a
quality score. The cache reports a 272,000-token context window for each; public
API pages advertise 1,050,000. Use the effective Codex runtime limit, not the API
maximum, when estimating whether a handoff fits.

The native catalog describes `ultra` as reasoning with automatic delegation.
VK's `ReasoningEffort` enum cannot represent it. Public API `none` is likewise
absent from VK and this native catalog. Neither belongs in the initial router.
Delegation must remain subject to the task's permission and agent policies.

Native Fast/priority is advertised for all four, with increased usage and speed
claims of 2x for Astra and 1.5x for the others. Those are **speed descriptions,
not measured allowance multipliers**. VK maps a `-fast` model suffix into a base
model plus `ServiceTier::Fast`; `/fast` is another control. Treat service tier as
a separate setting and explicitly preserve/reset it on transitions. Default
routing experiments should use standard service, subject to an explicit lock.

The public catalog also mentions GPT-6 Sol/Luna and a GPT-6.1 Sol ID. None was
returned by this native probe, even with hidden models included. Do not invent
aliases or add these to the routable set until discovery and execution validation
agree. Public model lists are not account entitlement lists; the official
[app-server integration guide](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
also cautions that discovery may return a bundled catalog.

### Cost: API prices are not Codex allowance weights

Published standard API USD per million tokens, fetched on the investigation date:

| Model         |  Input | Cached input | Output | Official source                                                         |
| ------------- | -----: | -----------: | -----: | ----------------------------------------------------------------------- |
| GPT-5.6 Luna  |  $0.20 |        $0.02 |  $1.20 | [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna.md)   |
| GPT-5.6 Terra |  $2.00 |        $0.20 | $12.00 | [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra.md) |
| GPT-5.6 Sol   |  $4.00 |        $0.40 | $20.00 | [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol.md)     |
| GPT-6 Astra   | $10.00 |        $1.00 | $50.00 | [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra.md)   |

These pages also specify long-input/cache pricing qualifications; Sol's current
pricing is promotional through at least November 21, 2026. Store dated prices,
not permanent constants. API estimates require the actual token categories,
service tier and applicable pricing rules. They do not establish what percentage
of this account's weekly Codex allowance a task consumes. The relative allowance
costs remain unknown; do not label API-dollar estimates as measured plan savings.

Reasoning effort is a useful second dimension: compare Sol xhigh with Sol medium
before assuming a model downgrade is necessary. Lower effort may reduce usage
or may cause more retries. Measure the outcome. Native default, VK fallback and
account config differ: VK's fallback and the inspected Green config use Sol
xhigh, while native Sol discovery defaults to low.

## How VK currently selects and launches models

| Layer / source                                                                                                                                                                                 | Observed behavior and routing implication                                                                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [useExecutorConfig.ts](packages/web-core/src/shared/hooks/useExecutorConfig.ts)                                                                                                                | Resolves explicit selection, matching draft/last-used config and preset/defaults; create-mode preset preference has separate precedence. Reasoning reuse is guarded by matching model. The fallback is Sol/xhigh. Preserve this provenance rather than treating every populated model field as a human lock. |
| [codexModelSelector.ts](packages/web-core/src/shared/lib/codexModelSelector.ts), [codex.rs](crates/executors/src/executors/codex.rs) `discover_options`                                        | Backend catalog is static; frontend filters pre-5.6 GPT entries and adds Astra/five effort options. A menu entry is not live capability discovery.                                                                                                                                                           |
| [profile.rs](crates/executors/src/profile.rs), [initial](crates/executors/src/actions/coding_agent_initial.rs) and [follow-up actions](crates/executors/src/actions/coding_agent_follow_up.rs) | `ExecutorConfig` carries executor/variant, model, reasoning and permission overrides. Actions resolve cached profiles then apply overrides. Do not mutate global profiles to route one task.                                                                                                                 |
| [sessions/mod.rs](crates/server/src/routes/sessions/mod.rs), [queue.rs](crates/server/src/routes/sessions/queue.rs), [review.rs](crates/server/src/routes/sessions/review.rs)                  | Follow-ups/reviews/queued requests carry config. Session validation locks executor family, not a particular Codex model. Retry may reset Git by default: escalation must not blindly use retry/reset.                                                                                                        |
| [services/container.rs](crates/services/src/services/container.rs) `start_execution`                                                                                                           | Persists the executor action and pre-execution repository HEADs before spawn. Resolve and record routing before this point so persisted config describes the launched action. Revalidate queued work when admitted.                                                                                          |
| [local container](crates/local-deployment/src/container.rs)                                                                                                                                    | Consumes queues, enforces capacity admission and injects workspace/session/execution IDs. Use existing lifecycle and execution identity, not a second worker/scheduler.                                                                                                                                      |
| [codex.rs](crates/executors/src/executors/codex.rs) `build_thread_start_params`, `resume_params_from`, `launch_codex_agent`                                                                    | Model, reasoning config and service tier reach thread start/resume. Later VK follow-ups can select another model while preserving the native thread. Native behavior still needs cross-model continuity acceptance.                                                                                          |
| [client.rs](crates/executors/src/executors/codex/client.rs)                                                                                                                                    | Ordinary `turn/start` inherits settings; collaboration mode uses a resolved model stored in `OnceLock`. Steering sends text and expected turn ID, no model override. Native autonomous continuation is not the same as a new VK execution.                                                                   |
| [capacity.rs](crates/server/src/routes/capacity.rs)                                                                                                                                            | Scheduled resume uses the latest execution config or a newer saved draft. Preserve this explicit intent and existing grant/lease checks. CU start payload does not supply a routing choice.                                                                                                                  |

The locally pinned Codex protocol (`38771c9`, `app-server-protocol/src/protocol/v2.rs`,
`TurnStartParams`) accepts `model`, `effort` and `service_tier` overrides for later
turns. Its collaboration mode takes precedence over model/effort. Merely adding
`model` to VK's next `turn/start` could therefore be ineffective unless that mode
is updated too. `TurnSteerParams` has no model field. This agrees with the
[official turn configuration contract](https://learn.chatgpt.com/docs/app-server#turns).

**Feasibility by boundary:** task creation and later user follow-ups fit existing
APIs; queue admission needs consistent resolution; same-process next-turn routing
requires client changes and tests; changing a running turn requires orderly
interrupt/drain and a new turn, not steering. Native goal loops may start turns
without passing through VK's execution admission. Initially pin the model for a
native goal run and route only at an explicit pause/resume boundary. Do not add a
competing continuation loop or automatically restart a completed/paused goal.

## Estimating the minimum safe capability

Available before launch: prompt, attachments, linked task metadata where present,
workspace/repo identities, branch/base revision, existing conversation and diffs,
selected profile, permissions and goal state. Task metadata is incomplete for
workspace-first chats. Repo inspection can add affected paths, ownership,
dependency breadth, existing patterns and test commands; that is extra work, not
information already reliably structured in a task title.

Use a small structured assessment: requirement clarity, change scope/coupling,
novelty, failure impact/reversibility, validation strength, expected horizon,
context/tool needs and explicit constraints. A bounded read-only scout may clarify
unknown scope; include its cost. Repository/prompt text is untrusted evidence and
cannot override server policy. Missing evidence raises uncertainty, not confidence.

Candidate starting points below are **pilot hypotheses, not approved safe tiers**:

| Work envelope                                                                           | Candidate to compare                                             | Required protection / higher-tier trigger                                                                                       |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Exact mechanical edits, factual docs with supplied sources                              | Luna low/medium; Terra medium                                    | Deterministic diff/source checks; operational/security guidance is not automatically low-risk docs.                             |
| Isolated UI, boilerplate, tests matching an established pattern                         | Terra medium vs Sol medium                                       | Typecheck, independent behavior checks and browser/accessibility review where relevant; auth/data-flow changes raise the floor. |
| Reproduced isolated bug or local refactor with strong coverage                          | Sol medium/high; Terra only after qualification                  | Preserve APIs/invariants; regression test must fail on the starting commit.                                                     |
| Cross-repo changes, unfamiliar systems, difficult debugging, architecture               | Sol high/xhigh vs Astra                                          | Strong baseline until representative evidence supports a reduction; scope and ambiguity dominate line count.                    |
| Migrations, auth/security, concurrency, production control, destructive/data-loss paths | Astra baseline plus specialist/human review                      | High-tier reasoning does not replace permissions, rehearsal, rollback or independent review.                                    |
| Ambiguous or long-horizon autonomous work                                               | Strong model for clarification/planning; pin execution initially | Require finite outcomes and independently checked milestones; cheap bounded subtasks only after explicit scope separation.      |

Recent VK history contains compact UI work (chat scroll/model selector), protocol
compatibility fixes, completion evidence reconciliation, and capacity ownership /
production recovery. These support the distinction between bounded presentation
changes and distributed state/lifecycle work. Even the UI examples exposed subtle
regressions, so “frontend” alone is not a sufficient classifier. This is a
qualitative sample from Git/continuity, not a measured distribution of all VK tasks.

## Escalation and failure handling

Combine independent observations with an agent's request for help. A low-tier
model need not correctly diagnose its own limitations for the system to escalate.

| Signal                                                                                            | Proposed response                                                                                                      |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Scope crosses protected paths or reveals migration/security/concurrency risk                      | Stop before further mutation; reassess floor and route to qualified tier/reviewer.                                     |
| Same relevant failure persists after two materially different fixes                               | Escalation candidate after checking baseline/environment; “two” is a pilot threshold to calibrate.                     |
| Tests weakened/deleted, unexplained dependencies, unrelated churn, invariant violation            | Block acceptance and request independent review; escalation alone does not clear the defect.                           |
| Repeated command/error loop, repeated rejected patch, no verified milestone within attempt budget | Trigger diagnostic checkpoint; use tool/test/diff evidence rather than confident prose.                                |
| Contradictory assumptions, review corrections, missing acceptance evidence                        | Reassess task and validation; clarify requirements if a stronger model cannot resolve the unknown.                     |
| Context near effective limit, repeated compaction, token/time budget exhaustion                   | Preserve state and consider stronger model/structured handoff; not proof of low capability by itself.                  |
| Rate limit, provider outage, missing SDK/system package, permission denial                        | Classify as infrastructure/policy; wait, repair or ask. Do not spend higher-tier attempts on unchanged infrastructure. |

Proposed escalation sequence: record a request with reason/evidence → check latest
user policy and budget → reach a safe turn boundary (or interrupt and confirm tool
processes have drained) → preserve working tree plus verified checkpoint → resolve
new config → resume once with a durable transition ID. Reconcile after crashes or
ambiguous RPC responses before retrying. Never reset dirty files just to switch.
The receiving model must inspect actual diffs/tests and original requirements,
not trust a predecessor's summary. Track rejected work and recovery cost.

Initially permit at most one automatic model escalation per attempt, with a
bounded retry/token/time budget and no automatic downgrade within the task.
If still unsuccessful, pause for diagnosis/human input. These are proposed pilot
limits, not existing VK behavior. Respect newer user messages, cancel/stop,
approval requirements and capacity expiry throughout the transition.

## Human control and proposed design

Add explicit routing intent alongside the concrete executor config:
`manual` (locked model/settings), `recommend` (no execution change), and `auto`.
Policy includes allowed/denied model IDs, minimum qualified capability, escalation
`allowed | approval-required | disabled`, and attempt budget. Keep the selected
model control; show resolved model/effort and a short reason before launch and in
history. “Use Astra” locks it; “never Astra” excludes it. If the exclusion leaves
no safe candidate, pause rather than quietly violating either constraint.
Existing sessions should remain manual by default. Persist policy separately
from draft text and preserve it through queues, reviews, retries and scheduling.
Resolve races using a policy revision; user choices always supersede stale router
recommendations. A model's tool request cannot grant itself escalation authority.

Implement a backend policy service shared by initial/follow-up/review admission,
with a pure, testable decision core. Inputs are task evidence, user policy,
qualified model/settings registry, capability snapshot and optional fresh usage
snapshot. Output is `select`, `recommend`, `pause` or `defer`, with reason codes,
evidence references and policy version. Persist the decision and concrete action
together before launch; final admission checks availability and policy revision.
Do not bury routing solely in React or rewrite the global default profile.

Use native discovery with account/provider/CLI identity, timestamp, freshness,
and successful-execution evidence. Intersect it with VK-supported settings and
our qualification registry. Unknown models remain manual/experimental. Validate
effort combinations explicitly: current override parsing can ignore an invalid
reasoning string and leave a profile's effort in effect. Record requested versus
resolved model/effort/service tier to detect silent fallback and catalog drift.
Generated TypeScript must continue to come from Rust when these types change.

## Usage tracker integration and measurement

Observed CU components:

- `src/usage-monitor.js` normalizes account windows, allowance usage, reset times,
  account identity, limit status and freshness; correctly distinguishes a weekly-
  only account from an unknown short window. `src/daily-allocation.js` owns the
  quota allocation ledger.
- `src/usage-scanner.js` aggregates rollout token events, accounts for replayed
  history, reports cached/input/output/reasoning tokens and groups by session
  model. Its parser does not attribute `turn_context` model transitions to token
  segments. Existing session-model rankings would misattribute mixed-model work.
- `src/vk-capacity.js` and VK `/api/capacity/*` coordinate goal grants and leases.
  CU owns allowance policy; VK owns permission to execute. This source contract
  is not a claim that every feature is deployed in the live backend.

Introduce a small authenticated, read-only usage snapshot contract instead of
scraping CU's UI or taking over reset controls. Include account fingerprint,
observation time, freshness/error, limit-pool IDs, remaining weekly/short-window
capacity and reset times. Existing `/api/usage` and monitor views are candidate
inputs, but their service-to-service contract and deployment need validation.
Do not copy credentials into task prompts or telemetry.

Usage pressure may choose a cheaper **qualified** candidate, disable optional
Fast mode, or defer nonurgent work until reset. It cannot relax the quality floor,
manual lock, approval gate or capacity lease. Stale/absent usage means unknown,
not unlimited headroom; preserve manual behavior and defer budget-sensitive
background automation. Model switching is not permission to reset allowance or
bypass an account-wide limit. No known per-model plan multiplier was established.

VK already persists actions, execution status/exit codes, turn summaries, repo
HEADs and logs. Its normalized `TokenUsageInfo` retains last total tokens/context
window, losing the richer categories needed for cost attribution. Add structured
telemetry rather than inferring success from a final “done” summary:

| Record             | Minimum fields                                                                                                                                                                      |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Decision           | Task/session/execution IDs, native thread/turn IDs, policy/catalog version, task features, constraints, proposed and resolved model/effort/tier, reason, usage snapshot reference   |
| Attempt/transition | Parent attempt, before/after revision and diff identity, start/end time, stop reason, escalation trigger, retries, infrastructure failures, human intervention                      |
| Usage segment      | Model/effort/tier valid for that interval, input/cached/output/reasoning tokens with provider semantics, cumulative baseline, dedup key, missing-data flag, account/window identity |
| Quality outcome    | Required tests and baseline results, acceptance/review result, correction size/severity, regression/revert linkage, reviewer identity, observation window                           |

Avoid double counting cumulative events, resumed/forked history and reasoning
already included in output totals. Join across native goals containing several
turns per VK execution. Include delegated-agent usage when enabled. Keep prompt
content out of aggregate metrics and apply retention/access controls to evidence.

Report accepted-without-rework rate, failure/retry/escalation rates, regression
severity, review corrections, total tokens, API estimate (if applicable), observed
allowance movement and completion latency, by task stratum and settings. Include
failed/abandoned attempts and review/handoff costs. Whole-account allowance changes
are delayed/coarse and contaminated by concurrent agents: serialize calibration
windows or label them non-attributable. Never infer exact per-task quota cost by
subtracting two busy-account readings.

## Practical validation and rollout gates

1. **Catalog/continuity acceptance, before routing code.** In isolated worktrees
   and test sessions, verify one bounded tool/edit/test task for each of the four
   model IDs; then a Terra→Sol and Sol→Astra handoff on one unfinished task. Check
   effective model/effort, prior instructions, dirty files, goal state, tool
   capability and token attribution. Exercise unsupported model/effort, manual
   lock, approval-required escalation, stale quota, unavailable stronger model,
   queue/user races, stop and restart recovery. Never use production operations
   as the test. A billed pilot budget and task set must be agreed before runs.
2. **Historical cohort.** Select roughly 24–40 real completed VK tasks across the
   envelopes above, including failures and difficult examples, using original
   starting revisions and requirements. Include scroll/selector, protocol-resume
   and capacity work. Curate hidden acceptance checks and exclude later fixes,
   summaries and solution commits from model-visible inputs. Deduplicate related
   tasks and hold out projects/time periods to reduce leakage.
3. **Paired pilot.** Compare the established Astra settings against Sol at lower
   effort, then Terra and Luna only in low-risk strata. Hold tool/permission/test
   environments constant, randomize run order, repeat variable cases, and use
   blinded independent review. Record both baseline infrastructure failures and
   model-induced failures. Historical Astra success alone is selection-biased
   and cannot establish what another model would have done.
4. **Quality gate.** Agree a non-inferiority margin for accepted-without-rework
   rate and a regression observation window before scoring. Require all task
   acceptance checks and no unresolved critical defect; report uncertainty and
   sample sizes. A 24–40 task pilot can reject poor candidates but cannot establish
   rare-event safety (even zero failures in 30 trials has an approximate 95%
   upper failure bound of 10%). High-risk categories remain strong/manual.
5. **Shadow then opt-in canary.** Record recommendations without changing models;
   compare to operator decisions. Enable automatic selection only for qualified
   low-risk classes, initially a small fraction of opted-in tasks, with a kill
   switch back to manual. Stop a cohort on a critical regression, override breach
   or attribution failure. Expand only when quality and total cost both improve;
   requalify after model/CLI/tool/prompt changes. Validate in this fork's local VK
   instance before staging promotion under the existing release workflow.

A useful cost comparison is:
`initial attempt + validation/review + escalation probability × recovery cost`.
A cheaper first attempt can lose when it creates expensive rework or consumes
context. A stronger model may have no advantage on deterministic edits, but that
must be demonstrated rather than inferred from token prices.

## Decisions and remaining unknowns

Before implementation, decide the primary optimization target (Codex allowance,
API dollars, latency, or a defined combination), acceptable quality margin,
pilot budget/task owner, default opt-in mode and escalation approval policy.
Agree protected task/path categories, the fallback when the safe set is empty,
telemetry retention, and which VK/CU versions will form the tested integration.

Remaining experiments must establish actual execution access to all four models,
relative plan consumption, cross-model handoff fidelity, effective service-tier
reset behavior, native goal switching boundaries, independent quality signals,
and lower-tier performance on our workload. Public capability descriptions,
self-confidence and green tests alone cannot establish a safe tier.

First implementation direction after those decisions: capability/decision
telemetry and shadow recommendations; then opt-in routing at execution boundaries;
then evidence-triggered escalation. Defer active-turn/native-loop switching until
its lifecycle and continuity tests pass. This investigation changes documentation
only and supplies no production-routing readiness claim.

## Investigation validation

Native catalog RPC completed successfully; local source links were checked.
`pnpm run format` passed using the existing SSD-hosted Prettier on PATH after
the checkout-local command initially failed with missing Prettier.
`pnpm run ops:check` and `git diff --check` passed. Only this plan and continuity
documents changed. No application test suite, browser smoke, inference benchmark
or production integration test was run for this documentation-only task.
Formatting logs: `/mnt/vk-storage/vk-model-autoswitch-20260930/`.
