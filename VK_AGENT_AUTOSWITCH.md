# Automatic agent switching

Status: implementation-ready design, 2026-09-15. Nothing in this document is
implemented by this pass. The next session should begin development; the
**docs-only restriction applies only to this design pass**.

## 1. Product decisions

Settings → Agents gains **Automatic agent switching**, off by default. Users add,
remove and enable individual agent/model configurations, including several models
of the same agent. Auto assigns coherent work among that list using CodexUsage
(CU) allocation information. Participation means the user considers that
configuration suitable; VK does not infer model intelligence from names or prices.

- CU owns usage, account/pool identity, limits, reset calendars, allocation targets,
  future reserves, safety margins and any measured burn-rate calculation.
- VK owns eligibility for this work, configuration selection, execution, continuity
  and explanations. It does not scan provider logs, estimate tokens, convert tokens
  into quota, or maintain a second allocation ledger.
- Select at a new assignment and reconsider at a safe continuation boundary. Prefer
  the incumbent through coherent work. Quota exhaustion is a failure to avoid,
  rather than the normal switching trigger.
- Explicit manual selection pins the work. Turning auto off restores normal manual
  selection without changing the saved manual default or interrupting a running
  process. No implicit fallback to unselected, paid-overage or unknown-capacity
  configurations. Auto with no eligible candidate waits and explains why.
- Auto routing does not authorize autonomy. Ordinary messages still finish their
  turn; only an explicitly authorized autonomous objective gets continuation turns.
- First implementation targets the local execution host, including its relayed UI.
  Hosted remote execution is not implicitly supported. Executor/provider support
  remains extensible through existing executor adapters and CU collectors.

## 2. Inspected architecture and provenance

VK source: `2fd585ac30bfa75975f6319585e4a66bb684fdcf`, branch
`vk/4e1b-vk-agent-autoswi`. Source inspection establishes architecture, not what is
running in production. Historical runtime notes elsewhere conflict; no deployment
claim or runtime change follows from this design.

| Existing mechanism                         | Evidence and intended extension                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Executor identity and overrides            | [profile.rs](crates/executors/src/profile.rs): `ExecutorConfig` already carries executor, variant, model_id, agent_id, reasoning_id and permission_policy. Reuse it intact. `ExecutorProfileId` alone loses model/reasoning. Profiles are cached and saved in `profiles.json`.                                                                                |
| Executor capabilities and option discovery | [executors/mod.rs](crates/executors/src/executors/mod.rs), [model_selector.rs](crates/executors/src/model_selector.rs), [config routes](crates/server/src/routes/config.rs): availability, preset options, discovered model options and `apply_overrides` already exist. Availability is a hint, not proof of current account quota or model access.          |
| Agents settings                            | [AgentsSettingsSection.tsx](packages/web-core/src/shared/dialogs/settings/settings/AgentsSettingsSection.tsx) edits profiles/variants and the manual default. Add one section; reuse discovery and model controls. Follow [local web styling](packages/local-web/AGENTS.md).                                                                                  |
| Global settings                            | [config v8](crates/services/src/services/config/versions/v8.rs) uses versioned config migration. Add routing settings through the next version, preserving the manual executor_profile.                                                                                                                                                                       |
| Initial work                               | [workspace creation](crates/server/src/routes/workspaces/create.rs), services container `start_workspace`, and [initial action](crates/executors/src/actions/coding_agent_initial.rs) resolve a profile and apply the complete config. Resolve auto before creating the executor-bound session/action.                                                        |
| Follow-ups                                 | [session routes](crates/server/src/routes/sessions/mod.rs) and [local container](crates/local-deployment/src/container.rs) queued follow-ups reject executor mismatch. Preserve this invariant. Same-executor model overrides already flow through follow-up actions.                                                                                         |
| Execution and repository state             | [services container](crates/services/src/services/container.rs) `start_execution`, execution process/action rows and execution-process repo-state rows record launches and before/after HEADs. Extend admission here and record resolved choices in the existing action.                                                                                      |
| Continuity                                 | [sessions](crates/db/src/models/session.rs) belong to a workspace and keep their executor; [coding_agent_turn](crates/db/src/models/coding_agent_turn.rs) records native IDs, prompts and summaries. Successful turns are resume anchors; interrupted prompts are recovered. Reuse this evidence, but a last summary alone is not a full cross-agent handoff. |
| Native goals                               | [Codex client](crates/executors/src/executors/codex/client.rs) lets the native engine schedule turns. [goals.rs](crates/executors/src/executors/codex/goals.rs) persists supporting checklist/evidence/recovery counters under Codex home, keyed by thread. No provider-neutral goal ownership or atomic transfer exists.                                     |
| Existing CU bridge                         | [capacity routes](crates/server/src/routes/capacity.rs), [capacity controller](crates/executors/src/capacity/controller.rs), guard and [unused-capacity notes](VK_UNUSED_CAPACITY.md) implement selected native Codex goal grants, expiry and stop/resume. They are not a generic agent allocator.                                                            |

CU inspected read-only at `/home/mcp/code/codexusage`, branch
`fix/adaptive-daily-target`, HEAD `400fa63f029adf64ebeb610ddc195cf15309dbdd`.
Its working tree is dirty; the following existing working files include untracked
implementation and must not be assumed present in that commit or a release.
Do not overwrite or absorb that work without reconciling its owner's branch.

| CU source, relative to that repository         | Observed behavior                                                                                                                                                                                                                                                                                    |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/usage-scanner.js`                         | Codex rollout usage and advisory weekly-token-cap projections; these estimates are not live subscription quota.                                                                                                                                                                                      |
| `src/codex-account.js`, `src/usage-monitor.js` | Account RPC observations; hashed account identity; weekly and short-window limits, reset timestamps, explicit absent-vs-unknown short window, freshness, durable monitor state and reset-credit controls.                                                                                            |
| `src/daily-allocation.js`                      | Percentage-point accounting, daily assigned/consumed/unused/protected/usable values, fixed future floor, cumulative weekly pacing ceiling, timezone/DST and reset fencing. Mid-day bootstrap can be advisory only.                                                                                   |
| `src/capacity-scheduler.js`                    | Shares the CU ledger, calculates measured-burn headroom, checks short-window capacity, grants/renews selected paused Codex goals. Current constants include 20-second leases, 15-second freshness and a short-window stop at 90% used. These are background policy, not generic foreground defaults. |
| `src/server.js`, `src/vk-capacity.js`          | `/api/usage`, `/api/mobile`, `/api/capacity`, owner controls and authenticated CU→VK capacity requests. `/api/capacity` is a display view: it omits allocation identity and encodes overnight `canRun`. It cannot directly authorize general routing.                                                |

No Factory/Droid usage collector, generic multi-pool allocation API, or comparable
cross-provider pacing contract was found in CU's inspected `src/` and `test/`.
The smallest integration is to expose/extend CU's existing monitor/allocation
logic; neither copying its formulas into VK nor treating dashboard estimates as
quota is acceptable.

Working-file SHA-256 anchors for the next developer:

```text
daily-allocation.js f8c3d7594c31344aabc56b19b29d0f3a47e3274c1fc49d3ad2a580b54387d3a7
usage-monitor.js ff931960b45cfc83624b0beb25cf05256b00fe5ae2cacc0aaec9ee288e1a35da
capacity-scheduler.js 3bcc6c07131541f1684b8f8f02621e1550b5df03705038e0a55a1f30f42f36e1
server.js a14f2e5da1ff8db30fe542fbc76aee3570b40968e2c44313beba62579f226a8d
```

## 3. Participating configurations and account binding

Persist an ordered `participants` list inside `automatic_agent_switching`, with
`enabled: false` as the migration default. Each entry has a stable UUID, enabled
flag, display label, **complete ExecutorConfig**, and opaque CU `binding_id`.
Array order is a deterministic final tie-break, not an allocation weight.
Deduplicate identical effective config/binding pairs. Different models/reasoning
or variants of the same executor are valid entries, even when they share quota.

Resolve profile defaults when adding the entry and materialize model, mode and
reasoning choices. An explicit provider router is a model choice. An omitted model
must not silently become “Auto”: where an executor genuinely cannot name a model,
use a verified resolved-default identity with a profile revision and CU mapping;
otherwise show that entry as unavailable for auto. Reuse executor discovery and
validation; do not accept invented model IDs simply because they are strings.

Record a fingerprint of the resolved profile's execution-relevant settings.
Changes to model, account/home, endpoint, commands, permissions or tools invalidate
binding validation. Invalidate removed/renamed profiles rather than falling back to
DEFAULT. Harmless display-label changes do not invalidate admission. In-flight
work retains its resolved config; changed settings apply at the next boundary.

CU binding describes the actual billing account and every shared pool charged by
that config (account-wide, short-window, model-specific, router-wide, etc.). Provider
labels in ModelInfo are not billing identities: Droid using an OpenAI model may
still consume Factory allocation. VK's executor adapter supplies a non-secret
account-context descriptor for matching; CU owns its stable identity and pool map.
Unknown account binding makes automatic execution ineligible. No credentials,
auth files, reset credits or raw provider responses reach the browser.

Permissions and required tools are eligibility constraints, not ranking inputs.
Check the destination's effective permission/tool behavior against the task's
current authorization. The same PermissionPolicy enum does not prove equivalent
sandbox enforcement across executors. Unsupported equivalence blocks that transfer;
never broaden access to make a cheaper or better-funded configuration eligible.

## 4. CU ↔ VK contract (new, required implementation)

Add a versioned **read-only routing snapshot** endpoint to CU, proposed
`GET /api/routing/v1/snapshot`. Keep `/api/capacity` compatible. CU produces the
same underlying allocation facts for its dashboard, background scheduler and this
API, with an explicit `interactive_routing` policy view. Overnight eligibility is
not foreground eligibility. Existing background grants retain all their controls.

Use server-to-server HTTP. Configure the CU origin and a read-only credential file
in the VK service, separately from CU→VK launch credentials. Restrict origin to an
administrator-configured loopback/private HTTPS service; validate redirects, use
request timeouts, response-size bounds and no browser-supplied URL. Add read-token
verification to CU for this endpoint; its existing public display routes are not
that authentication mechanism. No launch, reset or allocation-edit authority is
needed. Settings exposes connection health, not the token or arbitrary endpoints.

Contract fields, all named here as a proposed wire contract:

| Level           | Required information                                                                                                                                                                                                                                                                                               |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Snapshot        | `schema_version: 1`, unique `snapshot_id`, `generated_at`, `valid_until`, `policy_revision`; UTC timestamps; no-store. Freshness is per observation, not just HTTP response age.                                                                                                                                   |
| Binding         | `binding_id`, opaque `account_id`, `account_revision`, supported config descriptor/model mapping, `pool_ids` (all applicable constraints), status/reason.                                                                                                                                                          |
| Pool            | `pool_id`, `cycle_id`, `observed_at`, `valid_until`, `resets_at` when applicable, native `unit`, limit/used/remaining, CU target and protected reserve, safety margin, `routable_remaining`, `admit_new`, `continue_current`, `retry_at`, status/reason. Unknown numeric values are null, never zero or unlimited. |
| Pacing per pool | `behind_target_fraction` and `remaining_target_fraction` in [0,1], plus `target_ends_at`. CU normalizes against that pool's target, accounting for reserves, resets and all applicable allocation policy. Zero/unconfigured targets are unavailable, not divisors.                                                 |

For each pool CU chooses the current allocation horizon and exports its end as
`target_ends_at` (no later than that allowance's reset/expiry). With target amount
`T > 0`, actual consumption `C` and target consumption by now `P` in that same
horizon, `behind_target_fraction = clamp((P - C) / T, 0, 1)` and
`remaining_target_fraction = clamp(min(routable_remaining, max(T - C, 0)) / T, 0, 1)`.
CU defines `P` from its existing pacing policy and preserves its authoritative
opening/future floor; VK does not reconstruct `T`, `P` or `C`. Multiple windows
must each have their own horizon. Missing authoritative pacing cannot be replaced
by the dashboard's token projection. CU must expose a denied/unknown pool until
it can calculate a valid view from its ledger.

`routable_remaining` is available **after** reserve and safety deductions. CU must
not subtract headroom twice, distribute a second daily allowance at each query, or
reuse a historical cycle after a reset. All required pools must permit admission.
CU explicitly distinguishes a provider-confirmed absent limit from an unreadable
limit. An account with only a reported weekly window need not invent a short one.
An unmetered provider can participate only through an explicit authoritative CU
budget/policy binding; an unknown limit is not unmetered.

CU computes safety margin from existing observed quota movement and monitoring/
stop latency where available, with a conservative provider-specific floor when
history is insufficient. This remains CU work. Its current Codex background
headroom formula and short-window protection are reusable inputs, not constants
to scatter in VK. New provider limits/units/calendars belong to CU adapters.

VK fetches at decision time and refreshes every 15 seconds while auto work
is active (earlier if CU expiry requires), coalescing concurrent requests. A decision accepts observations no older
than the smaller of CU's expiry and 60 seconds; CU may require a stricter deadline.
Use a 2-second request timeout. Expired snapshots, future-dated observations beyond
5 seconds clock tolerance, invalid ranges, unknown versions, missing pool mappings
or a changed account/cycle require fresh validation. Never predict a quota refill
at the wall-clock reset time; wait for CU's new cycle observation.

This read-only view does not reserve tokens and cannot guarantee no quota failure
from external clients. CU must include their observed usage in its existing source.
Do not claim instant visibility or add a VK usage estimator to fill that gap.

## 5. Selection policy

Selection is a deterministic function of the work, configured participants, fresh
CU snapshot, current assignment and actual VK running/admitting executions.

1. Apply master switch, explicit manual pin, participant enablement and task scope.
   Filter config availability, model/account validation, authorization/tool needs,
   continuation support and all CU pool admission conditions.
2. Group equivalent quota exposure by sorted pool IDs. Adding three models on one
   account does not create three allocations or three tickets in a lottery.
3. For each applicable pool CU supplies fractions `d = behind_target_fraction` and
   `r = remaining_target_fraction`. VK computes urgency
   `u = min(1, r / max(hours_until_target_ends_at, 1))`, and pool score `d + u`.
   The configuration score is the **minimum** score over its required pools;
   the tightest applicable pool controls. CU calculates the fractions; VK only
   ranks them. Compare these dimensionless values, never raw tokens or dollars.
4. For new work choose the highest score. Equal scores choose the less recently
   assigned quota group, then participant order. Entries sharing the same pools
   choose the incumbent if compatible, else participant order. Round only for UI;
   use full precision for selection and a fixed tie tolerance of 1e-6.
5. Keep an eligible incumbent until a coherent boundary. At that boundary a
   voluntary switch requires another candidate's score to exceed it by at least
   0.05 and at least one newly completed material checkpoint since the last
   voluntary switch. A finite user turn is a coherent boundary for ordinary work.
   Required evacuation for quota/availability ignores this score threshold.
6. Revalidate under admission locks immediately before spawn, persist the decision,
   then launch. If no candidate survives, persist a capacity wait with reason and
   retry time. Never silently use the manual default or change the user's budget.

The constants above are initial policy defaults with deterministic tests, not
claims of optimal workload forecasting. No historical task-duration estimator is
required. CU can evolve allocation targets without VK learning provider formulas.

Illustrative inputs (CU fractions, not measured account data):

| Candidate/pool               | Behind target d | Remaining target r | Hours left | Score |
| ---------------------------- | --------------: | -----------------: | ---------: | ----: |
| A, resetting soon            |            0.10 |               0.20 |          2 |  0.20 |
| B, later reset               |            0.10 |               0.60 |        120 | 0.105 |
| C, farther behind its target |            0.40 |               0.50 |         24 | 0.421 |

A wins over B when both are similarly paced; C wins new work because it is much
further behind. If A also requires a short-window pool with score 0.02, its score
is 0.02; if that pool denies admission A is excluded. If the incumbent B is still
inside a coherent unit, it finishes that unit while safe. The policy spends
available capacity without promising to exhaust every pool before reset.

### Concurrent work

For the first release allow one automatic execution/admission per shared CU pool
on a VK host. This is a routing concurrency rule, not a consumption reservation.
Different independent pools can run concurrently. Acquire pool locks in stable
order and a workspace ownership lock; recheck active manual and scheduled work
sharing the binding. Auto waits while those occupy the pool. Manual work keeps
its existing precedence and admission behavior. After a run ends require a CU
observation newer than its end before admitting another auto run on that pool.

Persist the assignment and reconcile running process identities after a VK restart;
an empty in-memory lock map is not proof of availability. CU stale readings or
uncertain process state keep automatic admission closed. Multi-host reservations
and higher concurrency per pool are later extensions of CU's allocation authority,
not prerequisites for this local-host feature. Existing manual parallelism and
outside clients mean safety margins still matter.

## 6. Boundaries and handoff

| Situation                           | Required behavior                                                                                                                                                                                                                                                 |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| New task/execution                  | Resolve auto once before session creation; carry the full selected config into the action and show the decision. Setup/cleanup scripts themselves are not agent candidates.                                                                                       |
| Ordinary follow-up                  | Keep the incumbent while eligible; reconsider when the previous finite turn is fully settled. Explicit selection pins it. Switching must not create unsolicited continuation turns.                                                                               |
| Multi-turn autonomous work          | Prefer one configuration through a material work unit. A completed turn/checkpoint is necessary but pending tools/approvals/processes can make it unsafe to transfer.                                                                                             |
| Long-running native goal            | Native turn completion is inside a still-running execution. Request and acknowledge native pause before transfer; a log event alone cannot fence the next native turn. See goal ownership below.                                                                  |
| Allocation approaching margin       | CU denies new admission first. While `continue_current` is true allow current work to reach the next boundary; then switch/wait. If CU denies continuation, request graceful pause/stop immediately.                                                              |
| Sudden limit/unavailability         | Stop/reconcile the old executor and descendants; capture actual partial state. A launch known to have failed before starting work can be retried on a different eligible configuration without a work handoff. Unknown launch outcomes cannot be treated as such. |
| User stop, input or approval needed | Suspend auto continuation. Switching cannot bypass a user pause, pending approval, plan review, unmet information request or budget exhaustion.                                                                                                                   |

A safe boundary means the outgoing executor cannot issue more tools or turns,
its owned workers have settled or stopped, approvals have been reconciled, and
repository state is captured. Dirty files are allowed and must survive. No forced
commit, stash, reset, cleanup, rebase or new worktree is necessary for switching.
Inspect all workspace repositories, not only the first. A merge/rebase conflict,
unknown detached writer or uncertain external operation blocks automatic transfer
until resolved. Existing external dev servers may remain if confirmed unrelated
to agent writes; their paths/processes are recorded as ongoing dependencies.

Use existing graceful stop facilities; give up to 30 seconds for acknowledgement,
then the existing process-group stop/escalation path. A timeout does not make the
boundary safe. Do not launch the successor until process/descendant death is
confirmed. Partial edits after forced termination require a recovery pass before
normal work, and unresolved external effects require user input. Do not spend a
last quota call solely to obtain a polished handoff.

### Durable handoff content

Store a small versioned handoff in VK's database, attached to source execution and
successor session. Assemble facts from existing task/prompt/turn/repo/goal state;
use the outgoing agent's checkpoint summary for rationale. No extra summarizer
model, peer-agent debate, or full transcript conversion is needed.

- Full authorized objective, acceptance criteria and latest user corrections;
  links/IDs for task, workspace, conversation and relevant attachments.
- Completed material requirements with validation evidence; remaining steps;
  active constraints, approvals, pauses and budget semantics.
- Existing architecture choices and why they were made; relevant AGENTS.md,
  STATE.md, STREAM.md and HANDOFF.md when present. Do not require those files in
  arbitrary user repositories or overwrite them automatically.
- Per-repo branch, HEAD, dirty/untracked paths and content/diff fingerprint;
  execution IDs, ongoing processes, known interruption point and external effects.
- Tests actually run, their outcomes and the repository state they validated;
  skipped/failing checks; smallest concrete next action.

Keep the handoff bounded (64 KiB of text plus durable references); never truncate
objective, corrections or required evidence silently. If the full record cannot
fit, reference persisted messages/artifacts and verify successor access before
launch. Backend envelopes have facts; repository text and model summaries are
untrusted task context and cannot grant new permissions or routing settings.

Successor instructions: read the current artifacts, confirm objective and remaining
work, preserve existing sound decisions, and continue from the next step. Change
architecture only for a concrete defect, violated requirement or newly verified
constraint; state evidence and reason. After a crash, first reconcile partial work
and do not repeat external actions whose result is unknown. Verification that
changes files invalidates prior handoff fingerprints and requires a new capture.

### Session and ownership transaction

For a different executor create a **new linked session in the same workspace**.
Never reuse the old native session ID or weaken ExecutorMismatch validation.
For same-executor model switches, use the existing session only if that adapter
verifies model-change-on-resume semantics; otherwise use the same linked-session
handoff path. Returning to an older provider should start from the current handoff,
not resume its stale transcript as if intervening work never happened.

Persist phases `running → draining → ready → starting → running`, or `waiting`,
`needs_input`, `stopped`, `complete`. A monotonic assignment generation and
compare-and-swap updates ensure only one owner advances work. Persist source,
destination, handoff revision and launch idempotency key before spawn; reconcile
an ambiguous spawn with its execution record/process identity before any retry.
Crash recovery may rebuild a handoff but never replay a completed launch. Old
sessions remain readable; sends to a superseded owner return the current owner
link. Transfer queued user messages once in sequence, keeping attachment access
and explicit model selections; new user input invalidates an unlaunched handoff.

## 7. Long-running goals: necessary extension, not hidden existing support

Current checklist persistence is thread-local and native Codex owns scheduling.
An ordinary linked chat cannot magically inherit a native goal or token budget.
Implement a thin **portable continuation record** for auto-enabled autonomous work
in VK's existing execution/DB layer. It contains stable objective ID/revision,
current owning session/execution, status/pause reason, immutable requirements,
completed evidence, recovery counters, constraints, handoff revision and budget
references. Extract/reuse the present `Progress` validation and checkpoint grammar;
there must be one authoritative checklist for this objective, not copied lists
that drift. Native-only manual goals keep their current behavior.

For a native-backed owner the native engine continues to schedule turns; VK never
starts a second continuation loop. Import its existing objective and progress only
at a confirmed paused boundary, preserving completed evidence and stagnation/
recovery state. Adapters publish updates into the portable record and check its
ownership generation before continuing. On transfer pause/fence the old native
goal, save its final state, then activate the successor. Never mark an old goal
complete to release ownership; it remains paused with a successor reference.

For an executor without native goals, use the existing execution-finalization/
follow-up machinery to start **one finite turn at a time**, and only for explicitly
authorized autonomous work. Its checkpoint is accepted through the existing
message marker grammar (or dynamic tool when supported), bound to the active root
execution/generation. Reuse full-objective completion checks, needs-input handling
and recovery limits. Ignore descendant or superseded-owner checkpoints. A missing
or invalid checkpoint pauses instead of sending unbounded “continue” prompts.
This small continuation adapter is necessary for cross-agent goals; no second
multi-agent coordinator, planner or quota engine is proposed.

Adapters must demonstrate quiesce, resume/start, checkpoint delivery, permissions
and status semantics before being eligible for autonomous transfers. Ordinary
new-task routing can support an executor before that adapter is ready, but the
full feature must not claim cross-agent goal completion based only on new tasks.

Native token budgets are model/provider-specific. Preserve native usage and limits
on same-native resumes. A goal with an explicit native token budget cannot transfer
to another provider unless the original budget semantics can be enforced there.
Default to paused/ineligible destination with “Budget cannot transfer”; never reset
the budget or convert it using invented token exchange rates. The user may revise
that goal to a portable constraint (for example a CU allocation budget or deadline),
which is a real authorization change. No budget change is required for ordinary
unbudgeted goals. Elapsed deadlines and explicit iteration limits remain cumulative
across sessions; switching never resets recovery or progress counters.

### Interaction with unused-capacity scheduling

Auto switching and selected overnight capacity are separate opt-ins. Existing
scheduled grants are bound to Codex/account/session and do not authorize Factory or
arbitrary foreground execution. The initial implementation keeps a scheduled run
on its authorized configuration; it can stop/wait under the existing controller.
It must never transfer that grant or evade its local-only permissions. Ordinary
auto work follows existing foreground preemption and requires old grant revocation
and confirmed stop before reusing a workspace/pool. Extending background routing
requires an explicit later CU grant/adapter capability; do not silently broaden
this already deployed subsystem.

## 8. Settings and execution UX

Add one section below the existing agent profile editor:

- Toggle, explanatory sentence (“Balance selected configurations using CodexUsage
  allocations; switch ongoing work at safe boundaries”), and CU health/last update.
- Add configuration opens existing agent/variant/model/reasoning controls, then
  an available CU account binding. Show exact effective model and permission mode.
  Model choices come from the executor; budget choices come from CU.
- Rows show enabled state, label, agent + model + variant/reasoning, account/pool
  labels, safe capacity, allocation pacing, next reset, current eligibility reason,
  and remove action. Shared-pool rows say “Shares allocation with …”.
- Link to CU for allocation editing. VK displays targets/reserves; it does not
  offer a second budget slider. Do not expose provider reset-credit controls here.
- Allow saving incomplete/disabled entries with a visible issue. Enabling requires
  at least one valid participant; one works but shows “No alternative configured”.
  All currently unavailable is a visible waiting state, not automatic disablement.
- Removing a participant changes membership only, not the underlying profile.
  Running work finishes/stops at its boundary; next admission rechecks membership.

New-task composer defaults to Auto only while the setting is on. Existing chats
retain their mode; enabling globally does not take over active/manual sessions.
Explicitly choosing a configuration changes that task to Manual until the user
chooses Auto again. Persist this intent separately from resolved ExecutorConfig;
legacy API calls without routing intent stay manual. Turning the master toggle off
pins active auto work to its last configuration and removes future automatic
switching; it does not resume paused work or silently choose a different default.

Show “Auto · Agent / Model” and a short reason, then an activity entry for every
switch with previous/next config, allocation reason and handoff link. On a
cross-session switch follow the current owner in the workspace chat and retain
source-history links. Surface waiting vs draining vs recovery vs input required.
Provide Retry, Choose manually and Pause actions. Retry refetches/revalidates; it
cannot override missing quota or a blocked handoff. Render desktop/mobile and
keyboard-accessible controls using existing styling/i18n conventions.

## 9. Persistence and backend integration plan

Future implementation changes, not changes authorized in this design pass:

1. Versioned global config stores auto enablement and participants. Extend the
   existing config route and discovery response; generate shared TS types from
   Rust. Keep profile CRUD as the source of executor configuration.
2. Add explicit routing intent (`manual` or `auto`) to create/follow-up/queue inputs,
   task/session state and scratch round-tripping, defaulting missing fields to
   manual. Keep complete concrete ExecutorConfig in execution actions for replay
   and audit. A request cannot claim an unresolved Auto executor enum variant.
3. Add durable assignment/continuation and handoff records with DB migrations:
   objective/assignment UUID, generation, workspace/current session/process,
   routing mode, participant/config revision, phase, pause reason, source/successor
   IDs, launch key, checkpoint/handoff payloads and timestamps. Unique active
   ownership per auto-managed workspace; revision checks reject concurrent edits.
   Finite work can use the assignment record without a goal/checklist payload.
4. Record a small decision payload with the action: policy/snapshot/cycle IDs,
   chosen participant/resolved config, pool IDs, scores and reason codes. Keep
   only the relevant decision facts, not an accumulating copy of quota history.
   Capacity cache is disposable; ownership, messages and handoffs are durable.
5. Put one selector/admission service alongside existing services. Call it from
   new-work resolution, direct/queued follow-up resolution, and autonomous boundary
   callbacks. Final `start_execution` admission verifies the already-resolved
   assignment under locks; it must not secretly change a session's executor.
   Update MCP entry points to carry intent; do not route subagents, reviews or
   setup/cleanup actions implicitly. Explicit specialized work must pass capability
   checks before it can opt in.
6. Add narrowly scoped executor adapter methods/capability data for resolved model
   and account context, quiesce/continuation and error classification. Use existing
   CodingAgent dispatch; no separate provider registry in each UI/selector path.
   CU billing providers need not equal VK executor types.

A storage write failure before launch means no auto launch. If a record cannot be
updated during execution, request stop and hold ownership for reconciliation.
Config writes use atomic persistence/revision checking so stale UI saves cannot
resurrect removed participants. Re-check profile fingerprints at spawn. Do not
persist secrets inside a resolved profile audit payload.

## 10. Failures and recovery defaults

| Failure                                                          | Default                                                                                                                                                                           |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CU unavailable/stale/invalid                                     | No new auto work. Ask current owner to reach a safe boundary; expired continuation authority triggers stop. Manual mode remains available with existing behavior.                 |
| One provider auth/model unavailable                              | Exclude only that binding/config; explain setup issue. Another eligible config may receive work after safety checks.                                                              |
| Confirmed hard account/pool limit                                | Block every configuration sharing the affected pool until fresh CU recovery/cycle evidence. A different model on that pool is not a fallback.                                     |
| Transient provider fault                                         | Try at most one alternate config per failed assignment boundary, then pause. Cool down affected binding for 60 seconds (or longer provider Retry-After); revalidate before reuse. |
| Generic runtime/test failure                                     | Do not assume quota failure or rotate models. Keep task evidence and existing error handling; automatic retries could repeat bad code or side effects.                            |
| Ambiguous network/spawn failure                                  | Reconcile execution and external effects before choosing again. Idempotency key prevents duplicate work.                                                                          |
| All allocations protected/exhausted                              | Durable capacity wait; retry on CU update, no faster than 15 seconds, or at supplied retry time. No busy loop, reset-credit redemption or paid spillover.                         |
| Missing handoff / dirty state changed / native pause unconfirmed | Rebuild from durable evidence if possible; otherwise needs-input. Do not fabricate validation or assume a dead process.                                                           |
| User input/approval/manual pin/goal budget pause                 | User state wins over capacity recovery and auto retry.                                                                                                                            |

Distinguish operational capacity waiting from a substantive needs-input pause so a
fresh observation can resume only the former. After restart, reconcile all pending
assignments and native goals before admitting new auto work. Persist cooldowns
when needed to prevent a restart from replaying a provider-failure loop.

## 11. Factory and requested model examples

VK's current [Droid executor](crates/executors/src/executors/droid.rs) passes a
string model through `--model` and uses `--session-id` for follow-up. Its discovered
model list is hardcoded and includes Opus 4.6; it does **not** include Opus 5 or a
Factory router entry. `--auto low/medium/high` controls permissions, not model
routing. Omitting `--model` selects a provider default; it does not establish Auto.

Factory's official [router documentation](https://docs.factory.ai/model-independence/factory-router)
confirms a selectable Factory Router, also called Auto Model in some surfaces.
Its [CLI reference](https://docs.factory.ai/droid-cli/cli-reference) distinguishes
model choice, autonomy and session continuation. Both were inspected 2026-09-15.
The inspected pages do not establish the exact router CLI model ID for this host;
`droid` was not found on this shell's PATH. No live Factory login or quota call was
made. Verify the supported CLI's actual ID and account access before enabling it.

Represent Droid + explicit Opus and Droid + Factory Router as separate entries once
verified. Both may share Factory quota; CU maps that accurately. Internal router
choices stay Factory's responsibility. VK applies no preferred-router heuristic.
User examples “GPT-6 Astra” and “Claude Opus 5” express desired configurations, not
verified IDs or availability in this checkout. Resolve exact supported IDs through
executor discovery during implementation; do not replace the requested models
silently or bake example names into allocation code.

## 12. Implementation sequence and acceptance

The next session starts development from this design, reconciling current staging
and CU's in-progress source first. Use separate scoped VK/CU changes where needed.
No further general design round is needed.

1. CU contract and adapters: expose authoritative Codex interactive allocation
   view, add generic binding/pool normalization and test fixtures; implement and
   verify Factory quota collection/allocation before enabling Factory entries.
2. VK config, selector and new-work admission: full ExecutorConfig round-trip,
   shared-pool gates, deterministic policy, manual default compatibility and
   Settings → Agents controls. Keep auto disabled until end-to-end validation.
3. Boundary transfer: assignment/handoff persistence, linked sessions, queue
   ownership, same-executor model resume checks, stop/restart/idempotency behavior.
4. Autonomous support: portable checkpoint adapter and fenced native ownership
   transfer; demonstrate an unbudgeted multi-turn objective continuing across two
   actual supported agents with no lost requirements or duplicate native loop.
5. Integrate and validate locally, then normal staging PR/release preparation.
   Deployment/restart requires the existing separate runbook procedure. A partial
   new-task milestone is not evidence that long-goal switching is complete.

Required tests and observable acceptance:

| Area               | Evidence required                                                                                                                                                                                                                                                       |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CU contract        | Shared accounts/models, all required windows, absent vs unknown, target/floor integrity, stale/advisory bootstrap, DST, reset/replenishment, policy/account changes, authentication and no reset mutations. Current background scheduler tests must still pass.         |
| Policy             | Fixtures above; near-reset preference; behind-target balancing; bottleneck pool; reserves respected; identical-pool entries add no weight; incumbent threshold/progress stickiness; deterministic ties; zero/all unavailable; large clock jump and invalid numbers.     |
| Config/UI          | Off migration, add/remove/re-enable, two models on one executor, profile change invalidation, router vs permission Auto, manual override, stale setting revision, refresh persistence, error reasons and mobile/keyboard operation.                                     |
| Launch/concurrency | Simultaneous requests cannot claim same workspace/pool; actual resolved model/reasoning survives initial/direct/queued resumes and restart. Legacy requests remain manual. Failure before/after spawn cannot duplicate execution.                                       |
| Handoff            | Same dirty worktree/HEAD preserved; all repos and attachments reachable; partial edits and latest user correction retained; old session readable; queued messages exactly once; successor uses current architecture and validation evidence. No reset or forced commit. |
| Goals              | Material checkpoint transferred; native next-turn race fenced; old owner cannot resume/write; finite non-native continuation reuses recovery counters; needs-input, stop and budget pauses survive switch/restart; no goal created by the master toggle.                |
| Faults             | Provider loss mid-tool, detached writer, hard shared quota, CU outage mid-turn, stop timeout, database failure at each phase, unknown external side effect, stale quota after reset. Demonstrate stop/wait instead of optimistic transfer.                              |
| Existing capacity  | Selected scheduled goals retain grants, native model/reasoning and permission restrictions; automatic foreground routing cannot broaden/replay a scheduled grant.                                                                                                       |

Run focused Rust/UI/Node contract tests during development, regenerate Rust-derived
shared types and SQLx metadata when affected, then the repo's staging PR baseline:
`pnpm run format`, `pnpm run ops:check`, `pnpm run check`, `pnpm run lint`,
`cargo test --workspace`, plus affected generation checks and CU's documented tests.
Use isolated backend fixtures for process/goal transfers and the documented light
preview for routine UI checks. Live acceptance needs confirmed model/account access;
mock success alone cannot prove native stop, Factory routing or quota safety.

## 13. Actual dependencies and unresolved evidence

Product decisions above are resolved; no user preference is needed to start coding.
These are concrete activation gates, not reasons to postpone implementation:

- CU lacks the proposed generic routing snapshot and Factory collector in inspected
  source. Integrate its dirty/untracked allocation work through the appropriate
  branch. Verify an authoritative Factory usage/limit/reset source and account/pool
  mapping; if unavailable, show Factory as unsupported for auto rather than infer
  quota from model tokens. Operator credentials/access may be needed at that gate.
- The host's supported Droid CLI/router ID and the requested model IDs/access must
  be verified. The generic selector and Codex path can be developed using fixtures
  while that evidence is gathered; unverified entries cannot be activated.
- Cross-agent native goals require the continuation/ownership extension and real
  quiescence tests. Native-token-budgeted goals need an explicit user budget revision
  if their semantics cannot transfer. That decision is per goal, not a new global
  budget policy and not a blocker for unbudgeted goal development.

This design pass ends with documentation. Future handoff: **begin implementation**,
starting with the CU snapshot contract and VK configuration/selection tests, then
complete safe transfer and goal integration. Do not carry the temporary docs-only
boundary into that explicitly authorized development session.
