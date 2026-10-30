# Antigravity ACP source preparation

Status: isolated preparation, disabled in source, not deployable or usable yet.
Baseline: fork staging `5b43524ea35b2eb5dd80d0881dc8445489f4442f`, verified
2026-10-21. Branch: `feature/antigravity-acp-preparation`. Existing integration
design docs remain on `vk/148a-vk-as-integratio` at `9bc32e097`.

## Interface and account evidence

The official [ACP registry](https://raw.githubusercontent.com/agentclientprotocol/registry/main/antigravity-acp/agent.json)
identifies Google LLC's separate `antigravity-acp` 1.4.1 runtime, distributed
from `dl.google.com`; Linux launches `agy_acp_server.par --uid=`.
Google's [Zed integration documentation](https://www.antigravity.google/docs/ide/extensions/zed/)
explicitly supports Free/Pro/Ultra Google accounts, plus Enterprise in Preview,
and documents separate API authentication options. This establishes support
for Google's Zed integration, not blanket permission for a custom VK client.
The [FAQ](https://www.antigravity.google/docs/faq) and
[terms](https://www.antigravity.google/terms) still require review for this client;
do not reuse the consumer headless CLI as a workaround.

Read-only host discovery found `/home/mcp/.local/bin/agy` resolving to
`/mnt/vk-storage/tools/antigravity-cli/bin/agy`, version **1.4.4**.
Its help lists JSON/stream-json print mode and resumable CLI conversations,
but no ACP or non-sensitive account-status command. The inspected bin directory
contains only `agy`. No separate ACP runtime was found in the inspected paths;
this is not a whole-host inventory. The operator reports being logged into the
native Antigravity application. That report does not establish authentication
for a service-user ACP session or permission for this custom VK client.
Runtime account/license/auth status remains **unverified**.
No credential file, keyring or account data was inspected. No inference,
authentication, download, installation or account modification was attempted.

## Implemented source boundary

- `ANTIGRAVITY` executor, default profile, generated-type/schema producer
  registrations, existing Antigravity icon and unavailable agent label.
  Settings can store an absolute executable path and optional exact model ID.
  There are no arbitrary shell flags, installation helper, key or billing settings.
- `ACTIVATION_VERIFIED = false` is a code gate, intentionally unavailable to
  profiles or environment variables. All launch paths reject before executing
  anything. Discovery returns unavailable and no speculative model catalog.
  Saving a profile cannot activate it. The gate is stronger than a default toggle
  while supported account/client permission and runtime behavior are unverified.
- Opt-in `AcpAgentHarness::spawn_supervised_with_command` uses the existing ACP
  client and log normalization. Gemini/Qwen's previous lifecycle is unchanged.
  Interactive approval service is mandatory; absent/no-op services are rejected.
  The container registers Antigravity with its existing approval bridge.
  Only supervised permissions are exposed. Unsupported permission/mode/reasoning
  overrides reject execution. The strict harness also rejects `with_mode(...)`
  rather than silently ignoring an unsupported configuration. No MCP configuration
  or server injection is enabled.
- Initialization and session setup have a 30-second deadline. Version mismatch,
  EOF/malformed messages, auth-required/error responses, failed model selection
  and non-end-turn stops fail terminally. No automatic authentication, replay,
  retry, model downgrade, provider switch or API fallback occurs.
- Optional models are accepted only when `session/new` or `session/load`
  advertises them via the ACP library's existing session-model extension;
  selection must succeed before the prompt. No guessed model/config IDs.
  Newer `configOptions` discovery is not claimed. If the official runtime only
  supports that interface, adapt and fixture-test it before activation.
- Resume uses `session/load` only when advertised. Versioned
  `antigravity-acp:v1:` identities bind the opaque remote session to the canonical
  executable and worktree. Foreign namespaces/paths are rejected before launch.
  No local transcript is silently replayed; reset/fork is rejected.
  Account/runtime replacement invalidates saved identities operationally; a future
  supported non-secret account binding must be verified before enabling resume.
- Cancellation keeps ACP I/O alive for up to two seconds to deliver cancel and
  receive the pending response, then signals failure. VK's container owns process
  group termination/reaping and user-cancel status. No execution-wide provider lock
  is added; simultaneous executions and manual provider choice remain intact.

## Quota ownership

Antigravity entitlement is not Codex, Factory, generic Gemini API, or direct
Claude subscription capacity. An Antigravity-hosted Claude model must not be
charged to the direct Claude pool. CodexUsage owns future verified account/pool
mapping and quota availability; this adapter invents no pool IDs or usage totals.
Manual selection and existing recommend-only routing are unchanged. Do not put
this unavailable preparation profile into automatic allocation candidates.

## Status and handoff boundary for the existing AutoSwitch owner

This preparation does not change routing, its production guard, existing model
preferences or the live hot module. Native `ANTIGRAVITY` registration is compiled
into the backend; a later reviewed backend replacement and matching frontend/types
are necessary. A hot-module reload cannot register the enum. Never use a Gemini
command override to bypass that boundary.

Before routing eligibility, the adapter and existing allocation/orchestration
owners must wire structured evidence using the existing CU/VK contract. The
following is the required semantic mapping, **not a new deployed API or a claim
that the current adapter emits these fields**. Current protocol errors remain
sanitized error messages; status wiring is explicitly unfinished.

| Evidence | Required meaning and authority |
| --- | --- |
| `contractVersion`, `executionId`, observation time | Versioned adapter observation tied to one VK execution; no launch authority implied. Map to the existing integration version rather than inventing another competing protocol. |
| `providerAvailability` | Available/unavailable/unknown for the Antigravity service or transport. A transport error is not proof of quota exhaustion or account failure. |
| `authState`, `bindingKey` | Required/verified/unknown; a verified non-secret provider/account/entitlement binding is separate from native login. No raw credentials or account subjects. An auth-required ACP error may mark required; a generic session error remains unknown. |
| `providerAllowance`, `accountAllowance` | Distinct available/blocked/unknown observations with their own scope and freshness. Neither is inferred from the other, a model vendor, login, or a successful initialization. Both start unknown without supported evidence. CU remains the authority for effective pool eligibility and allocation. |
| `poolId`, `reasons`, `retryAt` | Use CU-owned opaque pool identity and reason codes, including `auth_required`, `provider_unavailable`, `missing_data`, `stale_data`, `adapter_unverified` and `reset_pending`. No guessed Antigravity pool ID or binding. Explicit real-limit evidence can map to the existing `limit_observed` event; a generic protocol error cannot. |
| Reset evidence | Reset/retry timestamps are nullable, scoped to the affected provider/account constraint and validated by CU. Unknown stays null; a retry hint or wall-clock reset does not prove capacity. No universal five-hour window, counter synthesis or reset redemption. Internal reset calendars/allocation math stay in CU. |
| Execution disposition | Distinguish not sent, sent with unknown outcome, terminal response, and confirmed stopped. Terminal ACP errors/cancel signals are not evidence that tools made no changes or all descendants stopped. VK's container supplies stop confirmation. |

New work or a finite-turn handoff must obey the existing admission/permit rules;
provider parallelism remains intact. This draft adds no provider execution lock,
no billing fallback and no automatic provider/model choice. Unknown/stale signals
cannot grant capacity. Preserve the explicitly selected model and reasoning;
Astra requires a separate scoped supervisor approval.

At a safe handoff VK preserves execution/turn identity, worktree and dirty/untracked
files, the last confirmed response/checkpoint, outstanding side effects and stop
confirmation. A successor starts only after the predecessor is fenced and stopped.
A prompt that was sent with a lost/error response remains an uncertain-effect
operation: reconcile it, never replay automatically. Native ACP `session/load`
continues only the same engine/account context; it is not a deduplication guarantee.
Do not pass an ACP resume token to another agent or transfer an active autonomous
goal implicitly. A cancellation message or generic outage alone is not a safe
checkpoint. Persistence and reconciliation belong to the existing orchestrator,
not a new retry service in this adapter.

## Validation receipt

Passed on 2026-10-21:

- `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target CARGO_INCREMENTAL=0 cargo test
  --offline --locked -j 1 -p executors --lib antigravity -- --test-threads=1`:
  **6 passed, 0 failed**, 208 unrelated tests filtered out. Synthetic local Python
  peer only. Coverage includes initialization/version, prompt/result, explicit
  model selection/rejection, denial without follow-up inference, namespaced native
  resume and unsupported load, cancellation, auth/error/malformed responses,
  missing executable and missing/no-op approvals, and the activation gate.
  The first run found a cancellation-flush race; the corrected run passed all six.
- `pnpm run format`: passed using the existing shared Prettier installation via
  PATH. No dependency installation. No unrelated formatter diff.
- `pnpm run ops:check`, `git diff --check`, and fixture Python syntax: passed.
  Continuity indexes total 10,458 bytes after this follow-up, within the 16 KiB limit.

**Incomplete source integration:** `pnpm run generate-types` was attempted
with offline Cargo, one job, the existing shared target, incremental disabled,
a 180-second bound and a 3 GiB SSD reserve. It expanded into backend dependency
recompilation (including WebRTC/SQLx dependencies), so only its isolated process
group was stopped before output, honoring the no-broad-build constraint.
`shared/types.ts` and `shared/schemas/antigravity.json` are **not generated**.
The producer registrations are written; generated frontend consumers are not yet
coherent/compilation-ready. Do not manually patch them. Rerun the normal generator
and its `--check` path when the release/resource owner provides a safe build window.

Frontend type checking/lint, local-deployment/server compilation, full workspace
tests, real ACP runtime compatibility and end-to-end checks were **not run**.
No frontend dependency tree was installed. The executor test build passes;
this does not validate the whole application or prove Antigravity usability.

No cleanup, duplicate build target or dependency tree was created. Original
documentation worktree remains clean and unchanged. No deployment, restart,
activation, signup, billing change or live project inference occurred.

Follow-up review (source-only, 2026-10-21):

- The existing executor test executable reran **6/6 successfully** without Cargo
  or compilation. This validates the inherited compiled snapshot only.
- Added a strict rejection for unsupported harness mode selection and a seventh
  regression test. The new guard/test have **not been compiled or executed**;
  the prebuilt executable cannot validate later source changes.
- The only executable generator found in the shared target is dated October 8,
  predating this adapter; its dependency receipt belongs to another worktree.
  It cannot generate the current enum/profile/schema. It was not run, and no
  Cargo generation/build was attempted in this follow-up.
- Follow-up `pnpm run format`, `pnpm run ops:check`, branch-policy check,
  `git diff --check`, fixture syntax and default-profile JSON checks passed.
  No formatter changes outside the intended 15 paths.
- No heavy-build window is available. Type/schema generation, current-source
  Rust tests, full frontend/backend checks, routing status wiring and real-runtime
  end-to-end validation remain explicit draft/readiness gates.
- The source-publication commit uses `[skip ci]` to honor the bounded no-build
  instruction. CI is deferred, not passed; required checks remain unfulfilled and
  the PR must stay draft. A later authorized validation commit must remove that
  instruction and obtain the normal checks before merge. Do not disable workflows
  or weaken branch protection.

## Next guarded generation slot

The resource/release owner must grant an exclusive shared-Cargo slot first;
PODs, the protective archive and other disk/memory owners take precedence.
The following conservative task floors are prerequisites, not a claim of current
capacity or authorization: mounted SSD; at least 20 GiB free root, 12 GiB free
SSD and 8 GiB available RAM at start; no overlapping Cargo/rustc/linker writer;
existing dependency cache sufficient for offline operation. The owner must
monitor and stop the command before crossing 15 GiB root / 4 GiB SSD / 2 GiB
available-RAM reserves, or apply a stricter current host policy. Do not reclaim
caches to reach these floors. If unavailable, keep generation pending.

From this branch worktree, the exact bounded normal generation command is:

```sh
timeout --signal=TERM --kill-after=5s 180s env \
  CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target \
  CARGO_INCREMENTAL=0 CARGO_BUILD_JOBS=1 CARGO_NET_OFFLINE=true \
  cargo run --locked --offline -j 1 --bin generate_types
```

This command compiles dependencies if needed; **do not run outside that slot**.
Stop on timeout/resource pressure; do not automatically retry. On successful
completion, the matching already-built binary can check output without compiling:

```sh
timeout 20s /mnt/vk-storage/cargo-target/debug/generate_types --check
```

Review generated `shared/types.ts` and `shared/schemas/antigravity.json` through
the normal producer. Reject unrelated output drift. In the same granted slot,
compile/run all seven narrow tests with offline, locked Cargo, one job and
incremental disabled, then run frontend/application checks with authorized existing
dependencies. Do not hand-edit generated files or install a duplicate dependency
tree. No successful source check authorizes a backend replacement or activation.

## Release and rollback inventory

This draft changes executor/profile registration, one opt-in ACP harness path,
approval-bridge registration, type/schema producers, the agent label/icon mapping,
synthetic fixtures/tests and branch documentation. No migrations, production
service/env files, live routing guard, hot module, package lockfiles, downloaded
runtime, auth material or account configuration are included.

Before any future release, Staging owns a matched backend executable, generated
types/schema, frontend assets, source identity and all normal production guards;
this draft provides none of those deployable artifacts. PODs completion is a
necessary gate, not cutover authorization. The source activation constant remains
false until supported runtime/client/account evidence and end-to-end QA exist.

Current rollback requires only declining/reverting this isolated source change;
there are no live effects to undo. Preserve its worktree/history and the original
design branch. A future runtime rollout must inventory newly persisted
`ANTIGRAVITY` profiles/session records, namespace/resume identities and any active
processes before downgrade. An older backend may not understand the new enum:
never delete records, restore stale data, or call an old binary alone a safe
rollback. Staging must preserve later writes and prove the compatible rollback.
The existing prior ZIP describes the previous snapshot; the draft branch/commit
is the authority for this follow-up.

## Activation handoff

1. Confirm the operator's existing account/license using supported visible
   evidence and obtain a documented basis for this custom ACP client. The user's
   choice is existing entitled ACP access if permitted, or an explicitly approved
   Enterprise/API path with separate billing authority. No signup or purchase is
   authorized by this preparation. Do not request credentials in chat.
2. Separately authorize official runtime installation and verify version,
   protocol, supported non-sensitive status/auth access for the service user,
   model/config capabilities and native resume/account identity. Do not silently
   fall back to `agy`, personal CLI quotas, API keys or credit overages.
3. Verify the actual runtime requests approval for relevant tools. The client
   can deny ACP permission requests; mock tests cannot prove all real runtime
   tools obey those requests. Exercise approval denial, cancellation, auth errors,
   model selection and resume against a synthetic empty project only, under an
   explicitly authorized license and bounded inference budget.
4. Complete generated-file/frontend/backend checks and review, then a separately
   approved source change can remove the activation gate. Source validation is
   not production acceptance. **No backend restart until PODs is complete.**
   The release owner must authorize any later merge/deployment/cutover. Green
   remains the sole live instance; Blue remains disabled.
