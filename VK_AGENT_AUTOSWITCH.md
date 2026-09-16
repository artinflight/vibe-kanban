# Automatic agent switching

Status: integrated design, 2026-09-16; CU contract revision 2 reconciled. Nothing in this document is
implemented by this pass. The next session should begin development; the
**docs-only restriction applies only to this design pass**.

The normative integration is [VK_AGENT_AUTOSWITCH_INTEGRATION.md](VK_AGENT_AUTOSWITCH_INTEGRATION.md),
`cu.allocation.v1` draft revision 2, reconciled with CU's producer design.
This revision incorporates the source design at `29f99ad75`; it replaces its
pending contract questions without changing the initial/advanced capability split.

## 1. Product decisions

Settings → Agents gains **Automatic agent switching**, off by default. Users add,
remove and enable individual agent/model configurations, including several models
of the same agent. Auto assigns coherent work among that list using CodexUsage
(CU) allocation information. Participation means the user considers that
configuration suitable; VK does not infer model intelligence from names or prices.

- CU owns usage, account/pool identity, limits, reset calendars, allocation targets,
  future reserves, safety margins, pacing/reset urgency, allocation preferences
  and any quota-balancing switch thresholds.
- VK owns eligibility for this work, configuration selection, execution, continuity
  and explanations. It does not scan provider logs, estimate tokens, convert tokens
  into quota, or maintain a second allocation ledger.
- Parallel jobs remain supported even when they share a subscription quota pool.
  Coordinate admission decisions briefly; do not lock a pool for a job lifetime.
- Initial delivery covers new work and safe finite-turn continuation. Active
  autonomous-goal transfer across engines is a separate advanced capability.
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

Historical inspection on 2026-09-15: CU was inspected read-only at `/home/mcp/code/codexusage`, branch
`fix/adaptive-daily-target`, HEAD `400fa63f029adf64ebeb610ddc195cf15309dbdd`.
At that inspection its working tree was dirty; the following existing working files include untracked
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
flag, display label, **complete ExecutorConfig**, and one opaque CU `poolId`.
Array order is a deterministic final tie-break, not an allocation weight.
Deduplicate identical effective config/pool pairs. Different models/reasoning
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

CU owns each pool's stable account/entitlement identity and all simultaneous quota
windows. VK maps a resolved execution configuration to exactly one CU pool in v1,
verifies the snapshot's non-secret `bindingKey` against its actual launch account
and entitlement, and invalidates the mapping when execution-relevant settings
change. Multiple configurations can share that pool. A provider/model label alone
is not billing identity. CU account rebinding creates a new pool ID requiring
explicit remapping; cycle/policy changes use generation fencing. Unverifiable
identity, paid fallback, or overlapping entitlements that cannot be faithfully
represented by one pool make the configuration unavailable for Auto. No invented
multi-pool mapping or raw credentials reach the browser. See the contract's exact
identity encoding and provider-fixture requirement.

Permissions and required tools are eligibility constraints, not ranking inputs.
Check the destination's effective permission/tool behavior against the task's
current authorization. The same PermissionPolicy enum does not prove equivalent
sandbox enforcement across executors. Unsupported equivalence blocks that transfer;
never broaden access to make a cheaper or better-funded configuration eligible.

## 4. Shared CU ↔ VK contract

Implement [the normative shared contract](VK_AGENT_AUTOSWITCH_INTEGRATION.md#shared-contract-v1),
`cu.allocation.v1` draft revision 2. CU's producer copy is
`docs/allocation-contract-v1.md`. Read both repository handoffs in the integration
file; exact wire fields, endpoints, errors, deadlines and lifecycle assertions
are settled there. `/api/capacity` is not this API and existing grants are separate.

VK reads ranked pools, then requests atomic admission for one chosen pool and a
durable execution identity. CU does not need candidates, models, incumbent identity,
work context, token estimates or goals. VK sends only selected authority identifiers
and lifecycle assertions. CU alone computes pressure, reserves, quota windows,
reservation sizes and renewal eligibility. Rank is preference, never permission.

Snapshot expiry is distinct from an active permit's deadline. New-admission denial
or ranking changes do not revoke a confirmed permit. Unavailable/stale CU cannot
extend it. Renew or stop by the last confirmed deadline with an independent runtime
guard. An observed epoch/generation change or real provider limit initiates stop;
never infer a refill from wall-clock reset. Unsupported expiry enforcement makes
an executor unavailable for Auto, not serialized behind a one-runner semaphore.

Keep origins and dedicated allocation credentials in administrator configuration;
no browser URL/token or reset/launch authority. Use the contract's bounded requests,
monotonic conservative timing, scoped authentication and version handling.

## 5. Configuration selection and parallel admission

1. Apply Auto/manual intent, participant enablement, actual model/account validation,
   authorization/tool suitability, safe-boundary and deadline-enforcement capability.
2. Group eligible configurations by poolId. Among those with a fresh eligible CU
   pool view, choose the lowest CU rank. Within that pool prefer a compatible
   incumbent, otherwise saved participant order. Several models add no pool weight.
3. Persist a planned execution identity and obtain CU atomic admission. A current
   rank change alone need not deny the chosen pool. On denial refresh and consider
   another locally eligible pool; never choose a denied fallback from row order.
4. Persist admission/launch identity, revalidate settings and bindingKey, arm expiry
   enforcement and spawn at most once before startBy. Report started. A storage
   failure or ambiguous launch is reconciled before retry; no guessed refund.
5. Renew capacity while running without changing configuration. Reconsider provider
   choice at a safe finite-turn boundary, not on every renewal/rank fluctuation.
   Safe continuation creates its own execution/admission; permits are not transferable.

The CU ledger serializes its short read/check/write transitions, so concurrent
accepted demand is visible to the next admission. Several permits on one pool can
run simultaneously. VK needs only per-execution/continuation duplicate-start fences,
not a pool-lifetime lock or global workspace-exclusive owner. Independent jobs do
not wait for a previous execution to end or for its post-completion observation.
CU may conservatively hold unobserved reservations; that is capacity accounting,
not an execution-count cap. Existing host resource limits remain in force.

CU settles reservations from VK's durable stop/never-started assertions and fresh
covering observations. VK has no consumption estimator or quota ledger. Reconcile
pending operations by idempotency key, especially after timeout/crash. A local
mutex is neither required for CU atomicity nor a multi-host quota guarantee.

Manual/external usage is observed by CU, not retroactively managed. Existing
foreground preemption remains. Co-enabling overnight work requires shared CU
accounting/reset interlocks; until implemented, CU's policy_conflict affects that
pool. Only competing owners of the same continuation are mutually excluded.

## 6. Boundaries and handoff

| Situation                           | Required behavior                                                                                                                                                                                                                                                 |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| New task/execution                  | Resolve auto once before session creation; carry the full selected config into the action and show the decision. Setup/cleanup scripts themselves are not agent candidates.                                                                                       |
| Ordinary follow-up                  | Prefer coherent ownership; use CU rank and prefer the incumbent within the chosen pool when the previous finite turn is fully settled. Explicit selection pins it. Switching must not create unsolicited continuation turns.                                      |
| Multi-turn autonomous work          | Initial delivery switches only when existing task state and a settled finite turn are sufficient. Engine-owned objective/progress reconstruction is advanced scope; otherwise keep the owner or pause.                                                            |
| Long-running native goal            | Initial delivery retains the engine owner or pauses it. Advanced transfer needs acknowledged native pause and progress continuity; a turn-completed log event is not a transferable boundary.                                                                     |
| Allocation approaching margin       | New-admission denial does not revoke a permit. Renew confirmed authority or stop by its deadline; rank changes do not interrupt work. VK computes no quota threshold.                                                                                             |
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

Use existing graceful stop facilities with grace bounded by remaining permit time
minus the tested escalation margin; the earlier unconditional 30-second grace is
withdrawn. Arm a crash-independent deadline guard before launch. If startup/renewal
and stopping cannot fit the issued interval, do not launch this configuration.
The 20-second initial CU maximum does not imply existing executor support. A timeout does not make the
boundary safe. Do not launch the successor until process/descendant death is
confirmed. Partial edits after forced termination require a recovery pass before
normal work, and unresolved external effects require user input. Do not spend a
last quota call solely to obtain a polished handoff.

### Durable handoff content

Use existing repository/task state, persisted prompts, summaries and validation
records first. If those suffice, pass references plus the next action; do not create
a duplicate objective/checklist store. Persist only missing handoff context and
source/successor links with existing execution records. The following is a content
checklist, not a requirement to duplicate every fact into a new database entity.
Use the outgoing agent's summary for rationale. No extra summarizer
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
compare-and-swap updates ensure only one owner advances that continuation.
This fence does not exclude unrelated parallel jobs or other users of its pool. Persist source,
destination, handoff revision and launch idempotency key before spawn; reconcile
an ambiguous spawn with its execution record/process identity before any retry.
Crash recovery may rebuild a handoff but never replay a completed launch. Old
sessions remain readable; sends to a superseded owner return the current owner
link. Transfer queued user messages once in sequence, keeping attachment access
and explicit model selections; new user input invalidates an unlaunched handoff.

## 7. Staged capability: basic routing first, goal transfer later

### Initial implementation — independently useful and releasable

Deliver CU-informed selection for new tasks/executions and safe finite-turn
continuations where existing repository/task state plus a small handoff is enough.
Support different engines at these boundaries without assuming their native
session formats are interchangeable. Reuse existing authorized follow-up behavior;
add no goal creation, new autonomous scheduler or universal checkpoint engine.

An active native goal remains with its owning engine. Its internal turn-completed
event does not make it an ordinary completed execution. If it cannot safely
continue, pause/wait or use existing same-engine recovery; show “Cross-engine goal
transfer not supported yet”. Do not reconstruct the goal in another engine as an
initial-release fallback. Independent new jobs still benefit from CU balancing
while that goal is pinned or paused. An ordinary task can change agents at a
settled boundary without needing a portable goal framework.

Initial acceptance does not require active cross-engine goal transfer. Describe
that limitation explicitly in settings/status and release notes; it is an advanced
capability, not a blocker for shipping basic parallel autoswitching.

### Advanced capability — separate implementation and acceptance

The inspected Codex checklist is thread-local and its native engine owns scheduling.
A later goal-transfer implementation must preserve the authorized objective,
corrections, completed evidence, remaining work, pauses, budgets and recovery state;
acknowledge/fence the old engine before starting another; and maintain one owner
for that objective. Never mark the old goal complete merely to transfer ownership.

Prefer existing native goal/task/checkpoint state and references. Add only missing
transfer metadata after proving what the destination needs; a new portable goal
store or a non-native continuation loop is not prescribed by this basic design.
No agent-to-agent debate, replanning layer or additional quota engine is needed.
Existing sound architecture remains authoritative unless new evidence warrants a
change. The main risk is lost context/intent, not code-format incompatibility.

Before enabling advanced transfer, prove native pause/next-turn race handling,
objective/evidence continuity, single ownership, and preservation of needs-input,
user-stop, permission and recovery constraints. Native token budgets must not reset
or be converted through invented exchange rates. If their semantics cannot be
preserved, that destination is ineligible unless the user explicitly revises the
budget. These requirements apply to advanced transfer and do not gate initial
new-task or ordinary safe-boundary switching.

### Interaction with unused-capacity scheduling

Auto switching and selected overnight capacity are separate opt-ins. Existing
scheduled grants are bound to Codex/account/session and do not authorize Factory or
arbitrary foreground execution. The initial implementation keeps a scheduled run
on its authorized configuration; it can stop/wait under the existing controller.
It must never transfer that grant or evade its local-only permissions. Ordinary
auto work follows existing foreground preemption and requires old grant revocation
and confirmed stop when preempting that scheduled execution or taking over its
continuation. Sharing a quota pool alone is not a reason to serialize jobs. Extending background routing
requires an explicit later CU grant/adapter capability; do not silently broaden
this already deployed subsystem.

## 8. Settings and execution UX

Add one section below the existing agent profile editor:

- Toggle, explanatory sentence (“Balance selected configurations using CodexUsage
  allocations; switch ongoing work at safe boundaries”), and CU health/last update.
- Add configuration opens existing agent/variant/model/reasoning controls, then
  an available CU pool with verified account/entitlement binding. Show exact effective model and permission mode.
  Model choices come from the executor; budget choices come from CU.
- Rows show enabled state, label, agent + model + variant/reasoning, account/pool
  labels, CU recommendation/admission status, reason and retry/deadline context,
  and remove action. Shared-pool rows say “Shares allocation with …”.
- Link to CU for allocation editing. VK displays CU-supplied explanations; it does not
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
Already admitted work retains renewal/expiry obligations until stopped; toggling
the setting cannot convert a running permit into unlimited manual authority.

Show “Auto · Agent / Model” and a short reason, then an activity entry for every
switch with previous/next config, CU reason and continuity links. Show advanced
goal-transfer limitations without disabling basic auto routing. On a
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
3. Extend existing session/execution persistence with routing intent, selected
   participant/config revision, CU decision/admission identity, launch key and
   source/successor linkage. Store only missing handoff context and a transfer
   generation/state sufficient to prevent duplicate continuation owners. No
   workspace-wide unique auto owner or new portable goal/checklist table is required
   for the initial implementation. Use migrations only where existing records
   cannot represent these facts; those are future development changes.
4. Record CU contract version, decision identity, selected config, opaque pool
   bindings and reason with the action. No VK scores or copy of quota history.
   Cached recommendations are disposable; launch/transfer identities and pending
   messages are durable. Advanced objective transfer metadata is separate scope.
5. Put one selector/admission service alongside existing services. Call it from
   new-work resolution and eligible direct/queued finite follow-up resolution.
   Engine-owned autonomous goal callbacks remain unchanged in initial delivery. Final `start_execution` admission verifies the already-resolved
   assignment under locks; it must not secretly change a session's executor.
   Update MCP entry points to carry intent; do not route subagents, reviews or
   setup/cleanup actions implicitly. Explicit specialized work must pass capability
   checks before it can opt in.
6. Add narrowly scoped executor adapter methods/capability data for resolved model
   and account context, safe finite-turn continuation and error classification.
   Advanced native goal transfer adapters are not an initial prerequisite. Use existing
   CodingAgent dispatch; no separate provider registry in each UI/selector path.
   CU billing providers need not equal VK executor types.

A storage write failure before launch means no auto launch. If a record cannot be
updated during execution, request stop and hold ownership for reconciliation.
Config writes use atomic persistence/revision checking so stale UI saves cannot
resurrect removed participants. Re-check profile fingerprints at spawn. Do not
persist secrets inside a resolved profile audit payload.

## 10. Failures and recovery defaults

| Failure                                                          | Default                                                                                                                                                                                                  |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CU unavailable/stale/invalid                                     | No new admission. Existing runs keep only their confirmed permit deadline, renew if possible, otherwise stop by it. Snapshot loss alone does not revoke a permit. Manual mode retains existing behavior. |
| One provider auth/model unavailable                              | Exclude only that binding/config; explain setup issue. Another eligible config may receive work after safety checks.                                                                                     |
| Confirmed hard account/pool limit                                | Block every configuration sharing the affected pool until fresh CU recovery/cycle evidence. A different model on that pool is not a fallback.                                                            |
| Transient provider fault                                         | Try at most one alternate config per failed assignment boundary, then pause. Cool down affected binding for 60 seconds (or longer provider Retry-After); revalidate before reuse.                        |
| Generic runtime/test failure                                     | Do not assume quota failure or rotate models. Keep task evidence and existing error handling; automatic retries could repeat bad code or side effects.                                                   |
| Ambiguous network/spawn failure                                  | Reconcile execution and external effects before choosing again. Idempotency key prevents duplicate work.                                                                                                 |
| All allocations protected/exhausted                              | Durable capacity wait; retry using CU refresh/retry guidance with bounded transport backoff. No busy loop, reset-credit redemption or paid spillover.                                                    |
| Missing handoff / dirty state changed / native pause unconfirmed | Rebuild from durable evidence if possible; otherwise needs-input. Do not fabricate validation or assume a dead process.                                                                                  |
| User input/approval/manual pin/goal budget pause                 | User state wins over capacity recovery and auto retry.                                                                                                                                                   |

Distinguish operational capacity waiting from a substantive needs-input pause so a
fresh observation can resume only the former. After restart, reconcile all pending
assignments and native goals before admitting new auto work. Persist cooldowns
when needed to prevent a restart from replaying a provider-failure loop.

## 11. Factory and requested model examples

Per the review correction, **Factory's router model ID is `auto`**. Represent
Droid + `auto` and Droid + explicit Claude Opus as separate ExecutorConfig entries.
For the router use `executor: DROID`, `model_id: "auto"`; use the verified explicit
Opus model ID for the other entry. They may map to the **same Factory subscription
quota pool**. An execution configuration is not a quota pool, and adding the
router entry does not add a subscription or independent capacity.

The inspected [Droid executor](crates/executors/src/executors/droid.rs) passes the
model string through `--model` and uses `--session-id` for follow-up. Its September
15 discovered list lacked the router entry; expose/validate `auto` through that
existing adapter during development. `--model auto` selects Factory routing;
`--auto low/medium/high` controls permissions. Do not conflate either with VK's
master autoswitch toggle or assume omitting the model selects the router.

Internal routing stays Factory's responsibility. CU evaluates the actual Factory
quota binding; VK neither recommends the router unconditionally nor counts its
possible underlying models as independent pools. Router-ID discovery is no longer
an unresolved design question. Installed CLI/account compatibility and telemetry
remain implementation acceptance checks. The exact requested Astra/Opus model IDs
and account access still need normal executor validation; never silently substitute
another model or bake their names into allocation policy.

## 12. Implementation sequence and acceptance

The next development session begins implementation of the initial capability.
Reconcile current staging and implement the shared revision-2 contract; do not
re-open resolved product decisions or wait for goal portability.

1. Build VK-side revision-2 contract fixtures and CU client against the shared
   agreement, not CU internal ledgers or locally invented quota formulas. Implement
   independent deadline enforcement and durable lifecycle reconciliation.
2. Implement config/settings, complete ExecutorConfig round-tripping, manual
   precedence and CU-backed new-work selection. Include Droid `auto` distinctly.
3. Add safe finite-turn continuation, minimal missing handoff context, linked
   sessions, queue ownership and launch reconciliation using existing execution
   machinery. Preserve parallelism within shared pools.
4. Validate and release this **initial capability independently**, with active
   cross-engine goal transfer explicitly unsupported. Enabling a provider requires
   a trustworthy CU binding and actual model/account compatibility for that provider.
5. Later, implement advanced active-goal transfer with its own acceptance gates
   from section 7. It is not part of initial feature readiness.

| Area                      | Initial acceptance evidence                                                                                                                                                                                                                                           |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared contract           | Version/expiry rejection; local eligible-pool intersection and within-pool incumbent preference; CU rank honored; all-denied wait; unknown binding rejected; current-work safety semantics; no VK budget formulas or raw-ledger dependency.                           |
| Parallel admission        | Two accepted jobs on one shared pool overlap in execution; racing requests use agreed admission/revision semantics; another admission need not wait for completion or a post-completion observation; failed/ambiguous starts and restart do not duplicate admissions. |
| CU recommendation mapping | Fixtures in which CU ranks a near-reset or underused pool first select a compatible configuration from that pool. CU owns the numerical policy tests; VK checks the result without recomputing it.                                                                    |
| Config/UI                 | Off migration; add/remove/re-enable; multiple models per agent; explicit Opus and `auto` can share a pool; manual override; stale profile/settings invalidation; refresh persistence; mobile/keyboard support and visible goal-transfer limitation.                   |
| Launch/continuity         | Complete model/reasoning survives initial/direct/queued finite resumes; legacy requests stay manual; task corrections, architecture decisions, dirty files, all repos and attachments survive safe linked-session handoff; queued messages delivered once.            |
| Safety/faults             | Provider failure, uncertain external effects, detached writers, pending approvals, user stop and storage/transport failures cannot trigger unsafe transfer. An untransferable active goal stays with its engine or pauses while independent jobs continue.            |
| Existing behavior         | Current manual parallelism, native scheduling and background-grant restrictions remain intact; no extra autonomous loop, workspace-wide auto exclusion or pool-lifetime lock.                                                                                         |

Advanced acceptance separately proves acknowledged native quiescence, objective/
progress/budget preservation, owner fencing and restart recovery across supported
engines. Do not present initial tests as evidence of that later capability.

During development run focused Rust/UI and shared-contract checks, regenerate
Rust-derived types/SQLx metadata when affected, then the repo's staging baseline:
`pnpm run format`, `pnpm run ops:check`, `pnpm run check`, `pnpm run lint`,
`cargo test --workspace`, plus affected generation checks. CU allocation/collector
validation belongs to its design and repository. Use isolated backend fixtures for
execution transfers and the documented light preview for ordinary UI checks.
Deployment follows the existing separate runbook, not this design pass.

## 13. Integration status and activation gates

Both available design streams now use the terminology and protocol in
[the integration agreement](VK_AGENT_AUTOSWITCH_INTEGRATION.md). CU's producer
copy carries the identical shared contract block. Candidate submission, raw quota
snapshots, VK scores, pool-lifetime locks and mandatory active-goal transfer are
not part of the initial implementation.

No known contract mismatch remains. Activation still requires trustworthy provider
telemetry (especially Factory), verified matching account/entitlement identity,
CU consumption/reporting-lag/in-flight-tail bounds, and VK independent deadline
and descendant-stop enforcement for each enabled executor. Overnight co-accounting
is an explicit implementation gate. Unknown combinations remain unavailable;
fixtures do not certify real provider safety. Factory `auto` is the settled router
ID in this stream; normal installed CLI/account compatibility checks still apply.

The initial capability is independently releasable after its integration acceptance.
Overlapping entitlements requiring multi-pool atomic admission and active native
goal transfer are explicitly later capabilities, not hidden completion requirements.
The temporary docs-only boundary applies to this pass only. No implementation,
goal creation, production service change or deployment occurred here.
