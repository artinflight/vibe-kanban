# CodexUsage ↔ VK autoswitch integration

Status: agreed documentation target, 2026-09-16; **not implemented or deployed**.
Canonical integration design beside [VK autoswitch](VK_AGENT_AUTOSWITCH.md).
CU retains its provider/allocation design in `docs/agent-autoswitch.md` and an
identical producer copy of the contract block in `docs/allocation-contract-v1.md`.
Both future agents implement `cu.allocation.v1`, draft revision 2. No executable
schema, production code, test, service or UI is created by this pass.

## Inspected streams and reconciliation

VK source baseline is `2fd585ac3`; autoswitch design is `29f99ad75` from
`vk/4e1b-vk-agent-autoswi`, including its parallel-admission review correction.
CU was inspected at `/home/mcp/code/codexusage`, branch
`docs/agent-autoswitch-integration`, HEAD `400fa63`. Its allocation implementation
and new design documents are working-tree content, not all part of that commit.
The CU proposal appeared during this pass and was read before integration; earlier
notes saying it could not be found are superseded. Unrelated dirty files remain.

| Mismatch                                                 | Agreed resolution / owner                                                                                                                                                                                                                           |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VK `binding_id` and sets of pools versus CU one `poolId` | VK stores one opaque CU pool ID per complete configuration in v1. A pool contains all simultaneous windows on one entitlement. Shared/overlapping entitlements that cannot be represented faithfully as one pool are unsupported, not approximated. |
| Account labels do not prove the launch uses CU's account | CU exposes a non-secret `bindingKey`; VK's adapter compares the actual launch context. Changed account/entitlement gets a new pool ID.                                                                                                              |
| VK submits candidates/incumbent; CU ranks pools          | CU ranks eligible pools globally. VK intersects them with locally suitable configurations and picks the lowest rank. No candidate/model/goal payload or incumbent field is needed.                                                                  |
| Quota eligibility versus execution suitability           | CU owns budget/provider eligibility. VK owns model access, permissions, tools, user intent, safe resume and runtime enforcement capability. Both must pass.                                                                                         |
| CU exports pressure and constraint percentages           | Remove them from v1. Rank, reasons, retry hints and permission deadlines are sufficient. Targets, reserves, reset calendars and formulas remain CU-side.                                                                                            |
| Snapshot versus admission                                | Snapshot is advisory. CU atomically reserves on admission and renewal; accepted pending demand is visible to the next transaction. VK never debits quota.                                                                                           |
| Shared pools versus parallel work                        | Several permits can coexist on one pool. Serialize only CU ledger transitions. No execution-lifetime pool lock or wait for another job to finish.                                                                                                   |
| Current-work disposition                                 | A confirmed permit authorizes only its interval. Denied admission is not revocation; denied renewal/outage cannot extend the last confirmed deadline. Rank changes do not interrupt runs.                                                           |
| VK 30-second graceful stop versus CU 20-second permits   | Stop grace must fit inside remaining authority, including escalation. A crash-independent guard and validated stop/tail bounds are activation gates. Do not assume the existing Codex background guard supports arbitrary executors.                |
| Native goals and overnight grants                        | Initial routing supports new work and safe finite-turn handoffs. Active native goals keep their owner or pause. Background grants retain their semantics and must share CU accounting before co-enablement.                                         |

The need for bounded admission is concrete: CU's proposed ledger accounts for
unobserved concurrent usage with conservative reservations. A read-only ranked
list cannot provide that behavior. Keep the ledger in the existing CU process;
VK contributes lifecycle assertions, not capacity estimates or a second ledger.

<!-- BEGIN SHARED CONTRACT cu.allocation.v1 revision 2 -->

## Shared contract v1

`cu.allocation.v1`, draft revision **2**. Revision 1 was an unimplemented proposal;
this draft replaces it before either implementation ships. Pin revision 2 in both
initial conformance suites; reject superseded draft revision 1. After release, additive optional fields may increment
revision; changing required fields, states or semantics requires a new major.
Unknown major/required state fails closed; unknown optional fields are ignored.
Unknown reason codes render generically and make the affected result unavailable.

### Transport and common types

Private server-to-server JSON HTTP in CU at `/api/allocation/v1`. All requests
require `Authorization: Bearer <dedicated allocation consumer token>` and
`X-CU-Contract: cu.allocation.v1`. POSTs require `Content-Type: application/json`.
The token is bound to one stable consumer ID and permits only this interface's
reads and lifecycle/admission writes. It cannot edit allocations, redeem resets
or launch VK work. It is separate from CU→VK overnight credentials. Configure
origin/token outside browser settings; loopback initially, or explicitly configured
private authenticated TLS. Reject redirects and browser Origin requests; no CORS.

Every JSON response has CU-owned `contract`, `revision`, `serverTime` (UTC RFC3339)
and `epoch` (opaque authority ID); use `Cache-Control: no-store`. Authentication
errors may omit authority details. CU changes epoch on restart/replacement and
reconciles old admissions before granting new work. IDs are nonempty opaque,
case-sensitive strings; clients never parse labels, pool IDs, epochs, generations
or permit versions. All listed fields are required unless explicitly optional.
Nullable values are explicit JSON null. Times have millisecond precision or better;
validity intervals are half-open (equality is expired). No NaN/infinite numbers.

VK uses a 2-second HTTP timeout and 1 MiB response bound. For a deadline D in a
response sent with serverTime S, record request-send and response-receive monotonic
times. Conservatively use `receive + (D-S) - full_RTT - 250ms` as the local
deadline. Nonpositive remaining time means expired. Arm a suspend-aware independent
guard before spawn; after clock discontinuity/suspend or unverifiable guard state,
reconcile instead of reusing cached permission. Neither browser nor host wall-clock
skew may extend authority. Runtime expiry must work if the VK process dies.

### Pool identity, mapping and snapshot — GET /pools

Response adds `pools`, an array including configured unavailable pools. Each view:

| CU-owned field | Type and meaning                                                                                                                                                                                                                                        |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `poolId`       | String, stable identity for one provider/account/entitlement. Several configurations or homes can reference it. IDs such as `factory-standard` are examples, not global constants. Never reuse or silently rebind an ID to another entitlement/account. |
| `bindingKey`   | Non-secret comparable fingerprint of provider/account/entitlement, defined below. A label or matching model vendor is not binding evidence.                                                                                                             |
| `label`        | Human-readable account/pool label for Settings; not an identifier or executable input.                                                                                                                                                                  |
| `generation`   | Opaque revision of applicable quota cycles and permission-relevant policy. Reset/replenishment or policy invalidation fences prior permits.                                                                                                             |
| `state`        | `eligible`, `paused`, `unknown`, `disabled`. Only eligible permits an admission attempt, never a launch by itself.                                                                                                                                      |
| `reasons`      | Array of stable reason codes; empty iff eligible.                                                                                                                                                                                                       |
| `validUntil`   | UTC timestamp or null; earliest expiry of the observations/policy behind this view. Must be future for eligible state. Fresh HTTP does not refresh old evidence.                                                                                        |
| `rank`         | Positive integer, unique among eligible pools; 1 is preferred. Null otherwise. CU alone computes it, including all targets/reserves/reset urgency.                                                                                                      |
| `retryAt`      | UTC timestamp or null, earliest useful reevaluation hint. Not proof of reset, capacity or permission.                                                                                                                                                   |

`bindingKey` is `sha256:` plus lowercase SHA-256 of three length-prefixed UTF-8
strings: provider namespace, canonical account subject, entitlement ID, in order.
Each prefix is the ASCII decimal UTF-8 byte length followed by `:`; no delimiters,
case conversion or Unicode normalization are added. CU's provider adapter defines
the three exact canonical values and supplies matching sanitized fixtures for VK's
executor adapter. Multiple homes for one entitlement produce the same key. The
raw account subject/credentials are never sent over this interface. This hash is
identity evidence, not authentication. No shared inference from marketing names.

For the inspected regular Codex adapter, pin namespace `openai.codex`, use the
nonempty exact `accountId` string from its quota RPC, and entitlement `codex`
(the regular limit-ID bucket). An explicitly verified legacy regular bucket with
an absent/empty limitId maps to `codex`; never map another bucket to it. CU's
existing hash of accountId alone is not the new bindingKey. Synthetic input
`openai.codex`, `test-account`, `codex` encodes as
`12:openai.codex12:test-account5:codex` and yields
`sha256:9e4727ad35f7f4b566570940bc26b31531a477a656c9293a02753c90d62fa9cc`.
Factory's canonical account/entitlement source is not yet verified; its matching
identity fixtures are part of that provider's activation gate, not guessed IDs.

VK owns complete config→pool mapping in Settings, validated against the adapter's
actual launch account/entitlement key before spawn. Account/profile changes
invalidate validation; unknown identity is ineligible. Account rebinding requires
a new pool ID and explicit VK remapping. Changes of cycle/policy on the same pool
can refresh generation without remapping. A route that might debit unrepresented
entitlements (including paid fallback) is ineligible. The v1 consumption bound is
pool-wide across all allowed configurations, including router choices and workers;
CU does not need model IDs or model cost classes.

VK filters configured, locally suitable pools and chooses the lowest CU rank.
Within that pool choose the compatible incumbent, otherwise saved participant
order. Two Factory models sharing one pool add no weight or capacity. No numeric
pressure, quota constraints, reset calendar or estimates cross this contract.
CU remains responsible for freshness, reserves, absent-versus-unknown limits and
all simultaneous windows. Rank changes never command interruption or revoke a
permit. Read at decision time; background selection polling is at most once per
5 seconds, coalesced, with transport backoff. Admission/renewal recheck internally.

### Atomic admission — POST /admissions

VK-owned request fields: `requestId` (UUID idempotency key), `executionId` (stable
opaque planned execution identity), and selected `poolId`, `generation`, `epoch`
copied from CU. One execution per request. No model, prompt, goal, worktree,
candidate list, estimated consumption or requested budget/interval is sent.

CU atomically rereads current eligibility and charges a conservative reservation
for every constraint before replying HTTP 201 with `admission`. Rank change alone
does not deny a still-eligible selected pool. CU serializes only the durable ledger
transaction; provider IO, spawn and execution occur outside it. Several admissions
on the same pool may succeed and run simultaneously. A second nonterminal admission
for the same consumer/execution is 409 `execution_conflict`.

Every admission response/status object has the following CU-owned fields:

| Field                                                | Type and meaning                                                                                                                                               |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `admissionId`, `executionId`, `poolId`, `generation` | Strings binding one admission to the requested execution and capacity.                                                                                         |
| `epoch`                                              | Issuing authority, retained even when a status response has a newer envelope epoch.                                                                            |
| `status`                                             | `reserved`, `active`, `settling`, `uncertain`, `closed`. Only reserved/active with matching current authority and unexpired confirmed permission permits work. |
| `permitVersion`                                      | Opaque identity of the latest issued interval; never a client counter.                                                                                         |
| `startBy`                                            | Exclusive deadline for first spawn; a renewal does not allow another launch.                                                                                   |
| `validUntil`                                         | Exclusive deadline by which VK must stop the execution and its consuming descendants unless a valid renewal is confirmed.                                      |
| `renewAfter`                                         | Earliest next renewal attempt; CU prevents interval stacking.                                                                                                  |
| `startedAt`, `endedAt`                               | UTC timestamps or null, CU receipt times of accepted lifecycle assertions.                                                                                     |
| `reasons`, `retryAt`                                 | Array of reason codes and nullable UTC retry hint for current state.                                                                                           |

CU initially caps intervals at 20 seconds and launch windows at 5 seconds, clipped
by evidence/reset safety. These are maxima, not a promise of a usable interval.
CU/VK deployment enrollment must validate common worst-case consumption, reporting
lag, shutdown and remote in-flight tail bounds for every enabled executor on a
pool. VK rejects an interval that cannot accommodate startup, renewal round trip
and its tested stop/escalation budget. It reports not_started after fencing spawn.
CU keeps unverified combinations unavailable; no execution serialization workaround.
Longer intervals are CU configuration requiring matching validation, never a VK
request override. CU can tune them without exposing allocation mathematics.

VK durably records admission plus launch identity, revalidates config/account and
deadline, arms its independent guard, launches at most once, then reports started.
A snapshot, an unconfirmed response, or a successful old idempotency replay is
not sufficient authority to launch. Persisting/spawning uncertainty is reconciled
before any alternate launch for that work. Never reuse a permit for a successor.

### Idempotency and status

Every POST includes `requestId`. Scope is consumer + key across operations,
including method/path and parsed body. Same operation/key/body returns its original
business result (HTTP 200 replay for an original success, original error status for
a denial), without extending deadlines. The outer response envelope always carries
current serverTime/epoch, including replays; the admission retains its issuing epoch.
Never age a replayed deadline relative to the original operation's serverTime. Different operation/body is 409 `idempotency_conflict`.
Retain durable keys/outcomes or tombstones for the consumer's lifetime in v1; do not
turn an old retry into fresh permission. A committed operation with a lost reply
is resolved through lookup or identical retry, never a guessed new key.

| GET path                    | Required response additions to envelope                                                                                                                                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/admissions?requestId=KEY` | `operation: {httpStatus, result}` with the original complete JSON response (including its original epoch/deadlines), and `admission` with current state or null for a denial. Unknown key is 404 and does not authorize launch. |
| `/admissions/ID`            | `admission` in current state. No unrelated last-operation payload.                                                                                                                                                              |
| `/admissions`               | `admissions`, all this consumer's non-closed admissions. Closed records remain addressable by ID/key.                                                                                                                           |

On operation lookup, use the current outer envelope's serverTime for deadline
conversion, never the historical serverTime nested in operation.result. The current
admission state controls reconciliation; an old success does not revive it.

All lists must fit the response bound. An oversized response fails closed; CU must
not silently truncate recovery records. First delivery supports one authoritative
CU writer, with distinct authenticated consumer identities; cloned/restarted VK
instances must not concurrently own the same execution namespace.

### Lifecycle — POST /admissions/ID/events

VK supplies requestId, executionId, permitVersion, and `event`. It supplies no
client timestamp: receipt time is conservative evidence for settlement. Response
is HTTP 200 plus the current `admission`. Authentication binds consumer, admission
and execution. Invalid transitions return 409 `state_conflict`.

| Event            | Exact VK assertion and CU effect                                                                                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `started`        | Launch occurred before startBy under confirmed permission; reserved→active. Late delivery records history but cannot restore expired/revoked permission.                                                         |
| `not_started`    | VK durably fenced every launch attempt and knows it never launched. reserved/uncertain→closed and refund R. An ambiguous spawn is insufficient.                                                                  |
| `ended`          | Execution and all consuming descendants are confirmed stopped. active/reserved/uncertain→settling; retain R until a covering observation. Accept reserved→settling for a crash before started was delivered.     |
| `limit_observed` | Provider explicitly reported a real capacity limit. CU pauses the whole pool for new admissions/renewals. Optional `retryAt` is a CU-validated provider hint, not permission to reopen. Does not assert stopped. |

Delayed started cannot undo settling/closed. Old-epoch/version events may settle
historical state or record a hard limit but cannot grant permission. An ended
assertion for the same execution also fences a renewal whose response was lost:
all its intervals settle, not just the client's last known permitVersion.

CU keeps each full reservation until both the execution ended (or passed into a
confirmed next interval) and an authoritative provider observation covers that
interval plus verified reporting lag and in-flight consumption tail. Client time,
permit expiry and arbitrary account deltas never refund capacity. CU owns these
bounds and settlement; VK reports process lifecycle only. R is reserved capacity,
not reported actual usage. Conservative overlap may temporarily double-count.

Expiry without stop confirmation becomes uncertain and quarantines that pool for
new admission/renewal. CU restart fences old authority with a new epoch and retains
unsettled reservations. VK stops by its last confirmed deadline even if CU is down,
then retries durable ended delivery. Recovery needs confirmed stops and covering
fresh evidence. Wall-clock reset alone never reopens a pool or settles old usage.
A hard-limit latch clears only after post-failure, lag-covering provider evidence
explicitly verifies recovery of all required limits; unknown/unchanged cached
evidence or a retry timestamp is insufficient. If recovery cannot be verified,
stay paused and expose the reason. Unaffected pools remain usable.

### Renewal — POST /admissions/ID/renew

Required VK body: requestId, executionId, permitVersion, generation, epoch.
Only an active current unexpired permit after renewAfter can renew. CU atomically
checks current data and charges the next interval before HTTP 200 plus admission.
The next interval extends from old validUntil to new validUntil; retain old charges
until covered. PermitVersion advances; one future interval at a time. CU computes
renewAfter so further renewal cannot stack unbounded intervals. No process restart
or new-model selection occurs at renewal.

Denied renewal returns 409. Ordinary budget denial leaves only the previously
confirmed deadline; it never extends it. If renewal is uncertain, keep the old
deadline until lookup confirms a current valid permit. If it passes, stop/report
ended even if CU granted more time. A late success must not resurrect a stopped
execution. On learning an epoch/generation change or actual provider limit, VK
begins stopping immediately; the previous deadline remains the absolute bound.

Snapshot unavailability/rank changes alone do not revoke confirmed authority.
On stale usage or CU outage, no new launches; running work can use its confirmed
interval while trying renewal, then must stop. A graceful checkpoint must fit
inside the stop budget; never spend extra quota to polish handoff text. VK owns
stop, reconciliation, same-engine resume and safe finite-turn transfer. CU never
launches, kills, copies a goal or supplies continuation prompts via this interface.

### Errors

Envelope plus `error: {code, reasons, retryAt}`; reasons array, retryAt nullable.

| HTTP / code                                                        | Meaning                                                                                          |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| 400 `invalid_request`                                              | Malformed fields/operation.                                                                      |
| 401/403 `unauthorized`                                             | Missing credential or wrong consumer scope.                                                      |
| 404 `not_found`                                                    | Unknown pool, admission or operation.                                                            |
| 409 `not_eligible`                                                 | Fresh atomic decision denied; VK may consider another freshly eligible mapped pool.              |
| 409 `stale_authority`                                              | Epoch/generation/version mismatch or expired authority; reconcile/refetch.                       |
| 409 `execution_conflict`, `idempotency_conflict`, `state_conflict` | Reconcile; no blind new-key retry.                                                               |
| 426 `contract_mismatch`                                            | Unsupported contract; disable automatic integration, preserve manual behavior.                   |
| 503 `unavailable`                                                  | Storage/authority unavailable; no new permission. A lost post-commit outcome still needs lookup. |

Reason vocabulary: `pacing`, `safety_reserve`, `reserved_capacity`, `hard_limit`,
`provider_unavailable`, `stale_data`, `missing_data`, `auth_required`,
`adapter_unverified`, `unbounded_usage`, `reset_pending`, `account_changed`,
`uncertain_execution`, `policy_conflict`, `disabled`, `storage_unavailable`.
Known temporary constraints are paused, missing verification is unknown, operator
choice is disabled. A denial always has at least one reason. Provider details
stay CU-side. Neither errors nor the interface can authorize paid spillover,
earned-reset redemption or a change to the user's goal/permissions.

<!-- END SHARED CONTRACT -->

## VK behavior and implementation handoff

Build off-by-default Settings → Agents participants with complete ExecutorConfig,
pool mapping/binding validation and explicit Auto/Manual intent. Reuse existing
executor discovery and preserve actual model/reasoning on initial/direct/queued
launches. Droid `auto` and explicit Opus are distinct configs on the same verified
Factory pool. User examples are not proof of account access.

Implement the private CU client, ranked pool intersection and durable launch/event
reconciliation. Reuse execution records and continuation fences, not a quota ledger
or global workspace-exclusive scheduler. CU's atomic admission makes host-wide
selection locks unnecessary; local compare-and-swap prevents duplicate starts of
the same work. Pending unrelated launches and running jobs remain parallel.

Implement independent expiry enforcement for each admitted execution, including
owned descendants, renewal and replay-safe end reporting. Existing selected-Codex
guards establish a useful precedent, not generic adapter support. An executor
without demonstrated bounded consumption/stop behavior is ineligible for Auto.
Turning Auto off/manual selection stops future routing changes but does not remove
an active run's permit obligations: finish with renewal on its incumbent or stop
at expiry. Explicit manual takeover is a separate launch after safe reconciliation.

Use existing safe-boundary handoff for finite continuations: preserve dirty files,
latest user messages, evidence and attachments; link successor sessions instead of
passing native IDs across agents. A forced stop is not a safe handoff until owned
workers and uncertain external effects are reconciled. Active autonomous goals
stay pinned or paused; no portable goal store/second continuation loop is required.

| Failure                                                    | Runtime default                                                                                                                                                                                              |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CU unreachable, stale/missing evidence or invalid response | No new admission; retain the last confirmed permit only, renew if possible, stop by deadline. Cache is never fallback authority.                                                                             |
| Preferred model cannot start, definitely no execution      | Fence launch, report not_started, exclude that config and allow at most one alternate attempt at this boundary with a new admission. Model-specific faults do not exclude another valid model automatically. |
| Provider auth/service failure                              | Exclude affected configs/account; use 60-second cooldown or longer provider retry hint. Another freshly eligible pool may receive one safe retry. No indefinite rotate/retry loop.                           |
| Unexpected real limit                                      | Report limit_observed; block every configuration on that pool locally until CU verifies recovery. Stop/reconcile and report ended separately. Other models on that pool are not fallbacks.                   |
| Ambiguous start, stop or external effect                   | Retain identity and reservation; reconcile before retry/transfer. Do not assert not_started or ended without evidence.                                                                                       |
| Every configured provider unavailable                      | Durable capacity-wait with reasons; bounded retry, no silent manual/default/paid fallback. User can explicitly choose manual, pause or repair setup.                                                         |
| Generic code/test failure, approval/input/budget pause     | Existing task semantics win. Neither more capacity nor another model automatically retries or bypasses the pause.                                                                                            |

Capacity waits refresh no faster than every 5 seconds and no earlier than CU's
future retry hint. Transport failures back off 5, 10, 20, 40, then 60 seconds with
jitter; active permit renewal/stop deadlines take precedence over background
polling. One unsuccessful alternate launch leaves this work paused for user retry;
an unrelated task or later recovered capacity wait is not permanently disabled.

## CU implementation handoff

Retain provider adapters, normalized windows and allocation math from the CU
design. Add the minimal snapshot and atomic multi-permit journal/routes above,
pool/binding identity and common provider identity fixtures. Reuse existing private
durable storage and HTTP process; no external lock service or execution scheduler.
Enforce one authoritative journal writer. Recover uncertain records conservatively.
Do not make VK send models or calculate reservation sizes to compensate for missing
provider bounds. Validate each pool's worst-case bound for all enrolled executors.

Unify the existing overnight scheduler's consumption with the same pool accounting
and earned-reset interlocks before enabling both modes for that pool. Until that
integration is proven, return policy_conflict only for the affected pool while
overnight authority can exist. Preserve existing overnight permissions/preemption;
this is not a permanent single-runner rule. Other manual/external clients remain
observed account-wide with uncertainty margin; no instant visibility guarantee.

## Future integration and testing handoff

Implement fixtures independently against the identical revision-2 block, then
connect isolated CU/VK processes and disposable executions. These are future
checks, not tests added or claimed run by this documentation pass.

| Scenario                                                  | Required observable result                                                                                                                                                                                                   |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Two Factory configs, one pool; parallel launch burst      | One entitlement/binding, no duplicate allocation weight. With capacity for two intervals, two admissions and two overlapping executions succeed; an additional unfunded admission waits. Also run another pool concurrently. |
| Same account in two homes; account/profile/scope change   | Equal verified binding keys share a pool. Mismatch prevents spawn; account rebind cannot silently reuse old mapping.                                                                                                         |
| CU rank disagrees with local model suitability            | VK filters unsuitable rows, uses next ranked usable pool, and performs no allocation arithmetic. Model choice inside a pool does not alter its rank.                                                                         |
| Short/weekly/monthly constraint, reset, stale/absent data | CU enforces all windows and oldest authoritative freshness. No admission from historical analytics or the reset clock alone. VK sees only state/reasons/deadlines.                                                           |
| Admission/renew/event commits with reply lost             | Same key resolves original outcome; one launch, original deadline until confirmed renewal, no premature refund, late renew cannot resurrect ended execution.                                                                 |
| CU/VK crash, restart, suspend; detached consuming child   | Independent stop meets deadline, old epoch cannot renew, unsettled records recover with real process evidence. No launch replay and no affected-pool reopening before covering observation.                                  |
| Stale provider, real hard limit, all pools unavailable    | Whole shared pool blocks; unaffected pool may work. Safe stop/wait, bounded retries, no paid spillover/reset call, no fabricated recovery.                                                                                   |
| Finite switch and active native goal                      | Finite handoff preserves edits/messages/evidence and stops old workers. Native goal remains owner-pinned or paused, with no accidental cross-engine transfer.                                                                |
| Overnight/manual coexistence; Auto turned off mid-run     | Shared CU accounting/reset interlock, normal foreground precedence, manual defaults preserved, outstanding permit obligations still enforced.                                                                                |
| Protocol parsing and identity fixtures                    | Required fields, unknown version/reasons, half-open expiry, hashing/non-ASCII length prefixes, malformed responses, request conflicts and conservative RTT calculation conform in both implementations.                      |

## Blockers, activation gates and scope closure

No known wire or ownership mismatch remains between the inspected designs after
these edits. Development against fixtures can start independently. Real activation
still requires evidence that documentation cannot supply: Factory authoritative
live quota/access/rolling-reset behavior; trustworthy consumption/lag/tail bounds
for each pool (including router choices); matching launch-account identity; and
VK crash-independent stop/deadline enforcement for each enabled executor. Affected
combinations stay unavailable until proven. Existing overnight co-accounting is
also an explicit implementation gate. These are not claims of current support.

Deliberately later: multi-pool atomic charging where one entitlement cannot express
overlap, model-specific CU cost classes if needed, and active cross-agent goal
transfer. Do not quietly activate unsupported configurations or claim those later
capabilities are part of initial readiness. No unresolved user preference blocks
the initial design. This pass ends with docs; a later session implements and tests.
