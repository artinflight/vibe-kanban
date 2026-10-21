# Provider failover: isolated controller and adapter contract

Status: source preparation only, 2026-10-21. Dormant native-message/exit hooks,
no automatic host registration, process launcher, network client, provider signup
or new scheduler. No production provider activation. Current Codex AutoSwitch
settings and the published Astra guard are outside this provider PR.
The existing Model AutoSwitch owner retains this work; Antigravity registration
belongs to the existing integration-phase owner. Its worktree is not modified.

## Verified gap map

| Surface | Current implementation | Remaining integration |
| --- | --- | --- |
| Model routing | `routing.rs::resolve_action_inner` returns immediately for non-Codex executors. Protocol-2 worker classifies tasks and selects qualified settings. | Provider transfer changes execution ownership; it cannot be delivered by publishing a classification worker alone. |
| Claude | `executors/claude.rs` implements initial/follow-up execution and parses `RateLimitEvent`; normalization currently ignores its untyped `rate_limit_info`. | Pin real structured field semantics, account/entitlement binding, reset/Retry-After and native settings evidence. Do not scrape prose or treat process exit as quota proof. |
| Codex | `client.rs::get_account_rate_limits` exposes native account windows; slash status displays them. Existing routing has same-engine boundary escalation. | Trusted limit event and pool snapshot normalization, finite-turn checkpoint, terminal-descendant evidence and admission bridge. Native goals remain owner-pinned. |
| Antigravity | No executor registration in this AutoSwitch source. Separate owner prepares official-ACP registration/fixtures, disabled by default. | Official ACP-client category, account entitlement, authenticated identity, signals, lifecycle and compatible capabilities remain unverified. Consumer agy CLI wrapping is unsupported. |
| VK lifecycle | Existing execution records, approvals, process-group wait, completion and turn preservation exist. | Connect their verified receipts to one fenced handoff; DB status alone does not prove all descendants or external effects stopped. |
| CU telemetry | `vk.routing.v1` is passive; current producer emits decisions only for Codex. Canonical mirror is unchanged. | Provider/account-qualified native bindings and alternate execution correlation need negotiated consumer support. Never send Claude/ACP IDs as Codex IDs. |
| CU allocation | Existing `cu.allocation.v1` revision-2 proposal specifies separate bindingKey/pool/generation, ranked pools, admission permits, limit_observed, ended and reconciliation. | Its implementation/availability and cross-provider bound/stop guarantees are not established here. Observational credit-budget readback is stale/held and grants no admission. |

At the original source checkpoint, read-only verification found the then-published
`status-scope-8544d46d3-20261017` with the expected worker/manifest hashes;
Recommend and the selected model/effort were unchanged then. That historical
observation is not the current rollout state. The current operator-confirmed chat
is Auto with Sol6.1/xhigh and per-chat Astra denial; this source turn does not
change it. Current astra-hold module identity and backend PID readback are unchanged.

## Implemented source boundary

`crates/executors/src/provider_failover/mod.rs` exposes a dormant Rust controller.
It uses existing serde dependencies and follows the existing capacity controller's
private journal/lock, atomic replacement and fsync pattern. No new dependency,
Cargo target, daemon, environment switch, API or automatic provider registration is added.

The typed inputs are **trusted adapter receipts**, never model-generated JSON,
prompt text, UI assertions or credentials. Serialization is a local internal
contract, not a replacement for either CU wire protocol. Unknown fields/variants
are rejected. Bounded state is at most 2 MiB, 100 work identities; reaching the
bound holds instead of dropping deduplication history. Initialization is explicit;
missing/corrupt existing state cannot silently recreate ownership. Private paths
must be provisioned beforehand; opening them does not widen permissions.

- `Identity`: provider namespace plus CU-owned pool ID and verified binding key.
  Rebinding or aliasing one allowance under a second profile/pool is rejected.
  Codex's older routing account fingerprint is not CU's length-prefixed bindingKey.
- `Pool`: source receipt, observation/expiry, generation, authorization, adapter
  and handoff verification, authentication/health evidence, allocation rank, and
  complete applicable windows. Window IDs/kinds/reset times are sourced; there
  is no universal five-hour window. Unknown or exhausted windows block eligibility.
- `LimitEvent`: immutable event/execution/account identity, source observation,
  quota window OR rate limit OR authentication OR outage OR task failure/unknown.
  A quota observation does not assert terminal process state. Duplicate identical
  events are no-ops; conflicting reuse fails. A bare 429 is not proof of a named
  exhausted allowance; adapters must preserve that distinction.
- `Policy`/`Candidate`: existing qualification/floor/constraints represented by
  exact scope and qualification versions and approved model/effort/tier choices.
  Provider allocation rank is separate from model preference rank; neither is a
  price. Locked selections, exclusions and missing qualification hold. There is
  no cross-vendor intelligence ladder or automatically qualified Claude model.
- `Checkpoint`: objective, compact context, workspace/path/branch, HEAD plus
  dirty/index/untracked-state receipt, completed/pending steps, pending approvals,
  effects and their receipts, and complete process-tree terminal evidence.
  Native IDs are retained as provenance, never resumed under a different provider.
- `Admission` and `Boundary`: fresh scoped budget/global-lane authorization plus
  an exclusive workspace reservation, exact stopped predecessor and unchanged
  workspace receipt. These are rechecked immediately before durable dispatch.
  Production adapters must implement this fence in the existing admission path;
  the journal lock alone is not a lock over unrelated VK launchers.

Flow: structured event -> verify checkpoint and side effects -> qualify authorized
alternate pool -> Recommend or Ready -> verify independent admission and workspace
fence -> persist immutable transfer -> return a single dispatch intent. The caller
must reuse this exact execution/transition identity. One alternate attempt is
allowed per work identity, including ambiguous/failed starts; failure pauses with
a reason rather than cycling providers. No timers or retry loop run in this module.

`Recommend` can return a candidate but cannot claim a launch. Manual mode cannot
transfer. Unknown task failures, validation failures, pending approvals and active
native goals hold. A work record cannot be registered over an existing workspace
owner. A lost launch reply survives reopening as `DispatchPending`; it is never
re-emitted. `confirm_started` requires the actual native execution/model/account
receipt and persists it immutably; it does not start or resume anything.

Completed effects are skipped. Checkpoint-listed, verified-not-started effects can
be claimed once: their uncertain state is saved BEFORE the effect. A lost reply
holds until a trustworthy completion receipt reconciles it. Unlisted effects need
review. This is only effective if adapters enforce the guard: a free-running
provider tool loop is NOT proven exactly-once by these tests. Unknown effects or
uninterceptable non-idempotent work are a handoff eligibility blocker, not permission
to assume safety. No native history is deleted or rewritten.

## Reset, failure and cooldown rules

Every pool retains its own limit observations. Reopening an exhausted window
requires fresh evidence covering the cooldown/reset boundary, a changed generation
and that same window explicitly available; every other applicable window must also
be available. Missing/expired evidence and clock rollback hold. Merely reaching
resetAt or Retry-After does not authorize execution or settle usage.

Rate-limit and service/auth failures have a minimum 60-second cooldown, extended
by a later sourced Retry-After. Authentication requires newer verified auth evidence;
outages require newer verified health evidence. These failures are not labelled
quota exhaustion. Retry-After seconds and parsed server-date intervals are handled
with checked arithmetic; date parsing stays in the HTTP adapter. Bounded metadata
refresh hints are 5/10/20/40/60 seconds, never earlier than Retry-After; there is no
sixth automatic retry and no inference retry. The caller must durably account for
refresh attempts and obey earlier permit deadlines. No such loop is activated here.

All pools unavailable produces a hold/alert reason, optionally a retry hint. There
is no default-provider or paid-credit spillover and no account/plan modification.

## Minimal cross-owner handoff

The Antigravity owner need only supply a disabled adapter capability descriptor
and synthetic mapping fixtures for: official protocol/category, account/entitlement
binding, native session/turn identity, confirmed model/settings, structured quota /
rate-limit / auth / outage signals, sourced reset/Retry-After, terminal descendant
and checkpoint evidence, and supported side-effect fencing. Leave fields unknown
and the pool unavailable until verified. Do not implement another failover loop.
This document is the coordination contract; no agent was started or messaged here.

For CU, retain canonical `vk.routing.v1` unchanged. A future agreed additive feed
mapping must correlate original/new VK execution IDs, transition ID, provider,
pseudonymous binding/pool identity, and each provider's exact native IDs. Requested
settings are distinct from `LaunchReceipt.effective`. Failed/ambiguous attempts and
classifier/recovery usage remain attributable; absent tokens/costs remain unknown.
Do not put checkpoint text, effects, paths, credentials or raw account subjects in
usage telemetry. CU's allocation admission stays separate from observational data.

## Offline acceptance and remaining activation gates

Run `python3 scripts/testing/run-provider-failover-offline.py --output <private-SSD-dir>`.
It compiles this exact module with compatible already-cached serde libraries using
rustc, not Cargo, then runs fake provider/event/checkpoint tests against its real
journal and state machine. It never starts a provider or writes production state.
Logs bind source/dependency/executable hashes and `/usr/bin/time -v` RSS. This is
**synthetic controller end-to-end**, not VK backend or real-provider end-to-end.

Covered: mid-task quota, unknown running/side-effect outcome, duplicate/conflicting
limits, separate reset windows and missing-window evidence, Retry-After/backoff,
auth/outage/task failure distinctions, unavailable/exhausted alternates, one-attempt
cap, crash before/after dispatch, no replayed effects, concurrent journal owner,
corrupt/missing/write-failed journal, actual native settings mismatch, approvals,
manual/Recommend/floors/exclusions, fresh admission/workspace fences and rank conflicts.

Before any real automatic failover: connect verified provider event adapters and
finite-turn checkpoints to existing lifecycle/admission; implement persistent
workspace ownership and supported effect fencing; verify CU entitlement/permit and
crash-independent deadline/descendant-stop enforcement for each provider; seed
provider-specific qualification with explicit authorization. Antigravity additionally
needs its official ACP/account gates. A real-provider smoke test needs separate
approval. The current protocol-2 classification module cannot install these backend
hooks. No backend restart or adoption is permitted before PODs completes, and PODs
completion alone is not activation approval. No production settings change belongs
to this source preparation. No savings or real failover success is claimed.

Final offline result: 20/20 synthetic failover tests and 37/37 existing accounting/
workflow regressions pass. Standalone compilation took 1.45s with peak RSS
241,640 KiB; tests took 0.97s with peak RSS 4,224 KiB (time -v). Rust format,
ops governance and whitespace checks pass. Full format stops at the existing
missing frontend Prettier; no frontend changed. Full backend/workspace compilation
and real-provider end-to-end tests are not claimed.


## Native signal and lifecycle wiring (source only)

`native.rs` normalizes bounded structured facts. `observer.rs` connects them to the
existing journal only after an independent trusted host explicitly registers the
exact work/execution/provider/pool/native-session binding. There is deliberately
no caller of `observer::register` in production and no runtime enable switch.
The idle/default bridge does no journal I/O, extra parsing, process census or
provider calls. Hooks do not change approval, cancellation, retry or routing paths.

| Native source | Implemented facts | Limits of the evidence |
| --- | --- | --- |
| Codex `account/rateLimits/updated` | Exact limitId plus primary/secondary window, usedPercent, optional sourced duration/reset. Captured before existing raw-log suppression. | Partial windows are observations, not a complete CU inventory, authorization, generation or admission. No fixed five-hour assumption. |
| Codex `error` | Structured quota, auth, outage, HTTP rate limit, task failure/unknown; exact thread/turn and native willRetry. | No prose matching. Unnamed/unregistered quota bucket blocks the pool without inventing a window. A native retry does not establish a stopped worker. |
| Claude `rate_limit_event` | Native session, allowed/warning/rejected, provider-defined window type and optional reset. Reuses the already-parsed CLIMessage fallback. | Pinned CLI 2.1.62/account emission has not been exercised. A newer SDK schema fixture does not certify that pin. Missing/unknown schema holds. Overage status does not authorize spending. |
| Claude auth/outage/result errors | Controller accepts separately verified typed host failure receipts. | The pinned native stream has no verified structured mapping here; absent codes remain unknown, not quota. No error-text guessing or implicit API fallback. |
| Existing exit monitor | Exit result, existing process-group quiescence and verified turn preservation. | Only for registered executions. Missing group/preservation is unsafe. Detached writers, external effects, DB exclusivity and admission still need independent host receipts. |

Protocol provenance: Codex app-server v2 from the locally pinned Codex source
revision `38771c9` (RateLimitSnapshot, RateLimitWindow, ErrorNotification and
CodexErrorInfo); Claude structured statuses/types from the official
[Claude Agent SDK types](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py),
reviewed 2026-10-21. The latter is a reference schema, not a verified pinned CLI
or billing contract. Unsupported fields/statuses remain unavailable.

Native facts and resulting blocks commit atomically. Duplicate normalized limit
facts in the same execution retain the first timestamp/cooldown; they do not
renew deadlines or launch twice. Invalid bucket/session/provider evidence creates
a durable adapter hold. A failed journal write blocks dispatch/requires recovery.
Native allowed events cannot clear blocks or mint a reset generation. Fresh CU
pool evidence must cover the boundary, complete applicable windows and account
binding; quota additionally needs a new verified generation. Native resetAt alone
never grants capacity. Existing bounded Retry-After/refresh rules remain intact.

The chooser now unconditionally excludes `gpt-6-astra` from provider automation,
even if a host mistakenly supplies it as qualified. Manual task-scoped supervisor
approval remains outside Auto; generic escalation consent cannot grant it.
`preferred_return` recommends the original qualified Sol6.1 only after verified
reset and a new stopped alternate checkpoint with reconciled effects/no pending
approvals or failed validation. This is advisory, never another dispatch/retry.
The host still needs a distinct admitted/fenced continuation; no provider bounce
loop or ownership release is implemented.

### Claude authentication and billing readiness

No `claude` executable is on this session's PATH. The existing executor uses
`npx -y @anthropic-ai/claude-code@2.1.62`; this turn did not invoke it, install,
log in, inspect credential files or call quota/auth APIs. Its availability check
uses file metadata, which is insufficient proof of authentication or billing.
`disable_api_key` removes only `ANTHROPIC_API_KEY`: it does not prove the absence
of another configured billing route, proxy/router, token or provider setting.
No such values were inspected. Subscription/credit/API entitlement for this exact
launch/account is unverified. Official guidance distinguishes these routes;
never promise subscription-backed Vibe use or silently enable API fallback.

### Release inventory and explicitly unfinished checks

Provider-only source includes the controller/journal, native normalizers, opt-in
observer bridge, tiny Codex/Claude/exit-monitor hooks, offline harness and this
contract. It does not include the separate AutoSwitch classification/cost branch,
its workflow edits, the Astra hot-module branch, Antigravity registration, frontend,
profile/default settings, credentials, DB migrations or a deployment change.

Offline tests exercise the actual controller/normalizer/observer code and an exact
extracted CLIMessage enum with control-only placeholder types. That last fixture
checks serde's real tagged-fallback behavior, not full executor compilation.
Synthetic 35/35 tests pass; the pre-existing 37 accounting/workflow regressions
are checked on the preserved provider development checkpoint. No inference calls.
Full backend/workspace type checks, lint, integration builds and real-provider
end-to-end checks are NOT RUN under the current resource/budget restriction.
Required full formatting completes Rust then hits the existing missing frontend
Prettier; no dependency is installed. This is not merge-ready acceptance.

Before adoption: obtain a permitted isolated build window, compile/test the actual
executor/local-deployment crates, register a verified host binding through existing
admission, implement persistent DB workspace fencing and enforce/reconcile all
side effects, and verify CU entitlement/account generation/permit coverage. Drain
and flush native callbacks before consuming a boundary; synchronously fsynced
observer receipts must move off the async executor thread in that host integration
if write latency is material. A sole process-group check never certifies detached
workers. Sol return dispatch and cross-provider usage correlation still need that
host integration; canonical CU routing telemetry is unchanged. Antigravity remains
unavailable pending the separate official adapter/runtime/account gates. No backend
adoption/restart before PODs completion, and no production provider activation
without separate approval. This cannot be installed by the classification-only
hot module. Current Codex-model AutoSwitch remains independent.
