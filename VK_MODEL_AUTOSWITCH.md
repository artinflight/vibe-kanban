# VK Model AutoSwitch: safe V1 implementation

Updated 2026-09-30 on `vk/5a81-autoswitch-cu-recovery`. This replaces the planning-only
state in commit `df3e973a5`; that commit retains the original investigation.
The full relevant family is a product requirement. One runtime's discovery
response is an observation, not the product's model definition.

## What V1 does

VK now resolves opt-in routing at its existing execution admission boundary,
before persisting `ExecutorAction` and launching Codex. It introduces no scheduler,
background retry loop, Git reset, global profile mutation or active-turn swap.
Manual remains the default. The shared model selector offers Manual, Recommend
(shadow), and Automatic, plus a capability floor, Astra exclusion and consent to
escalate after a failed execution. A backend capability flag hides these controls
when a frontend is connected to an older backend.

The initial policy is deliberately simple. Choose the lowest configured cost
rank among recently verified model/effort combinations at or above the floor.
The default floor is **workhorse**; explicitly bounded routine work can opt into
**routine**. Prompts mentioning migrations, security/authentication/authorization,
production, data deletion, credentials, concurrency or cryptography raise the
floor to **frontier**. This is a conservative heuristic, not a reliable semantic
risk classifier. Ambiguity or sensitive work should use the frontier/manual
control; a small diff or successful test is not proof of safety.

With the verified catalog from this task:

| Floor | First selection | Effort | Intended first use |
| --- | --- | --- | --- |
| Routine | `gpt-6-luna` | medium | Explicitly bounded, independently checked work; experimental |
| Workhorse | `gpt-6.1-sol` | medium | General development under existing review/test requirements |
| Frontier | `gpt-6-astra` | high | High-impact work or an escalated floor |

These capability assignments are configurable starting policies, **not measured
quality equivalence**. The implementation makes the Sol/Luna hypotheses immediately
testable on real work. It does not claim a percentage saving or Astra-equivalent
code quality. The earlier proposal for a large historical cohort is optional
future qualification, not a prerequisite to this opt-in V1.

## Current model and runtime evidence

There are four distinct facts:

1. **Representable:** `ExecutorConfig.model_id` accepts exact string IDs; adding a
   model does not require a new enum or architecture.
2. **Released/policy-known:** the administrator's model registry records release
   status, capability floor, supported VK efforts and preference rank.
3. **Discovered:** the native catalog returned the ID for this launcher/account.
4. **Executable:** a completed inference on that launcher/account verified an exact
   model/effort. Discovery alone does not authorize automatic selection. A released
   model absent from discovery can qualify through successful direct verification.

| ID | CLI 0.153.4 catalog | CLI 0.159.2 catalog | Verified on 0.159.2 |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | yes | yes | medium |
| `gpt-5.6-terra` | yes | yes | medium |
| `gpt-5.6-sol` | yes | yes | medium |
| `gpt-6-luna` | no | yes | medium |
| `gpt-6-sol` | no | yes | medium |
| `gpt-6.1-sol` | no | yes | medium |
| `gpt-6-astra` | yes | yes | high |

The old launcher is `/home/mcp/.local/bin/codex`, a wrapper that removes newer
subagent log items; inspection found no model filtering there. A fresh probe on
0.153.4 still returned only the four earlier models, and direct new-model requests
did not complete. An isolated 0.159.2 installation, using the **same account and
Codex home**, discovered all seven and completed all seven tiny inference probes.
This establishes CLI/catalog compatibility as a material cause in this environment;
A final read-only recheck of 0.153.4 after the newer CLI refreshed the same
home still returned only four IDs, so shared-cache refresh alone did not fix it.
The exact bundled-catalog versus versioned-server mechanism remains unproven. There is no remaining account-access blocker
for these IDs on the tested 0.159.2 runtime.

The newer CLI is staged at
`/mnt/vk-storage/vk-model-autoswitch-v1/codex-current/node_modules/.bin/codex`.
The host wrapper/live service was **not upgraded or restarted**. Updating the
production launcher still requires its normal compatibility and release workflow.
Model probes may refresh the native model cache; no credential was copied or
printed and no active user thread was used for the test.

Native supported efforts are low/medium/high/xhigh/max for Luna models, with
`ultra` additionally advertised for Sol/Terra/Astra. VK V1 supports only its existing
low-through-max enum. API `none` and native `ultra` are not automatically selected.
The registry, runtime-discovered effort list and successfully verified pairs are
intersected. A stronger verified effort can serve as a fallback; unsupported or
unverified combinations are not guessed.

Official references confirm the new models' positioning and effort distinctions:
[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol), and
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).
Near-Astra positioning is a reason to trial Sol 6.1, not local quality evidence.
Cost ranks are explicit initial preferences, not measured dollar or allowance
costs. API prices are not Codex weekly allowance weights. Calibrate these ranks
against accepted-task usage as the pilot produces evidence.

## Manual control, safety and escalation

- No routing policy, or `mode: manual`, preserves existing model/effort behavior.
  Selecting a model or effort explicitly locks manual mode. A saved per-chat
  policy persists; unrelated last-used settings cannot opt another chat into auto.
- Shadow keeps the requested action unchanged, logs the recommendation, and does
  not reject execution because the router cannot recommend a model.
- Auto retains the previous routing floor across follow-ups. A later short prompt
  cannot silently lower a frontier task to routine. Model exclusions are hard
  constraints. No candidate, stale evidence or incompatible launcher/profile
  returns an actionable error before an execution is launched.
- Ordinary follow-ups may change model. Native control commands and scheduled
  goal resumes retain the previous concrete model/effort, while honoring current
  floor/exclusion constraints. Native goal turns remain pinned within an execution.
  Automatic mode cannot first be enabled by a native resume; use an ordinary
  follow-up or keep manual mode. Choose manual mode to deliberately change a
  pinned goal's model. A failed pinned execution pauses for diagnosis rather than
  automatically retrying the same model.
- A failed predecessor blocks auto by default. With explicit escalation consent,
  the **next requested execution** raises the floor one step. Failure at frontier
  requires manual diagnosis. There is no autonomous retry. This detects executor
  failure, not every failed tool command or test assertion; quality-triggered
  escalation still relies on review and selecting a higher floor/manual model.
  Infrastructure errors may need repair rather than a stronger model.
- Auto retry requests that could invoke the existing Git-reset path are rejected;
  use a normal follow-up to preserve dirty work. Manual retry behavior is unchanged.
- Auto uses standard service tier and explicitly clears inherited Fast mode.
  Manual/shadow preserve existing service-tier behavior. The executor validates
  account fingerprint and returned model, effort, provider and tier before inference.
  It also pins effort in collaboration mode so mode defaults cannot undo routing.
  A native `model/rerouted` notification fails automatic execution for review.
- Reviews remain manual for V1; shadow is observational. Custom native profiles,
  providers or command/environment overrides cannot automatically reuse proof
  generated for the default launcher. These requests fail closed. Automatic
  mode currently requires a signed-in Work/Codex account with an email identity;
  API-key accounts retain manual mode pending an equally strong identity binding.

A newly queued execution is resolved when admitted. Existing capacity limits,
leases, permissions, stop behavior and goal ownership remain authoritative.
The router never grants more permission or creates/resumes a goal on its own.

## Configuration and source integration

The bundled [model policy](crates/executors/src/routing_models.json) contains all
seven IDs. `VK_CODEX_ROUTING_MODELS=/absolute/path/policy.json` replaces it with an
administrator-maintained JSON array of `{id, released, efforts, floor, cost_rank}`.
New exact IDs require configuration and verification, not Rust changes.

`VK_CODEX_ROUTING_AVAILABILITY=/absolute/path/availability.json` points to sanitized
probe evidence, bound to canonical Codex home, launcher string and account
fingerprint. Evidence expires after 24 hours and future timestamps are rejected.
Keep both files in administrator-controlled storage outside task worktrees.
Changes to the executable behind the same launcher path warrant fresh verification;
V1 binds the launcher string, not the binary's transitive dependency hashes.

The [probe](scripts/testing/codex-routing-probe.py) performs discovery without
inference by default. `--verify` explicitly enables at most seven short inference
requests, one per supplied model, with MCP/delegation disabled and no file edits.
It never retries an uncertain billed request automatically. `--models` accepts
new exact IDs. Run with the same `CODEX_HOME` and `VK_CODEX_BASE_COMMAND` as the
candidate VK process. A probe proves execution access, not coding quality.

Example candidate-only setup (do not apply to live service without deployment QA):

```bash
export CODEX_HOME=/home/mcp/.local/share/vibe-kanban-green-codex-home
export VK_CODEX_BASE_COMMAND=/mnt/vk-storage/vk-model-autoswitch-v1/integration/runtime/codex.mjs
export VK_CODEX_ROUTING_AVAILABILITY=/mnt/vk-storage/vk-model-autoswitch-v1/integration/availability.json
# Refresh only when needed; --verify consumes bounded inference:
python3 scripts/testing/codex-routing-probe.py --verify --output "$VK_CODEX_ROUTING_AVAILABILITY"
```

Main implementation locations:

- [routing.rs](crates/executors/src/routing.rs): capability policies, evidence
  admission, choice, pinning and boundary escalation.
- [container.rs](crates/services/src/services/container.rs): shared resolution
  before persisted execution creation, including predecessor identity.
- [profile.rs](crates/executors/src/profile.rs) and
  [actions](crates/executors/src/actions/mod.rs): optional policy/decision fields,
  compatible with existing stored actions and queues; no database migration.
- [Codex executor](crates/executors/src/executors/codex.rs),
  [client](crates/executors/src/executors/codex/client.rs) and
  [RPC compatibility](crates/executors/src/executors/codex/jsonrpc.rs): native
  override verification, effort pinning, reroute stop and standard-tier decoding.
- [selector](packages/web-core/src/shared/components/ModelSelectorContainer.tsx)
  and [configuration hook](packages/web-core/src/shared/hooks/useExecutorConfig.ts):
  opt-in controls and explicit selection precedence.

## Observability and CodexUsage

A decision is stored on the execution action; a `vk/routing` raw-log event joins
it to the native thread and actual resolved settings. The chat shows a system
message with mode, actual model/effort, recommendation and reason. The decision
references the previous execution so transitions can be attributed without charging
an entire native thread to its last model. Existing native events supply turn IDs.

Set `VK_ROUTING_EVENTS_FILE` to a private absolute JSONL path and point CU
`CU_ROUTING_EVENTS_FILE` at the same file. VK emits immutable/idempotent
`decision`, `turn_bound`, and `execution_end` records at persisted admission,
actual native turn binding, and terminal database update respectively. Native
thread/turn IDs are never inferred; standalone `taskId` remains null. The existing
raw log is retained. Optional delivery errors warn without changing execution.

See [the canonical wire mirror](VK_ROUTING_TELEMETRY_V1.md) and
[VK producer notes](VK_CODEX_ROUTING_CONTRACT.md) for delivery limits, identity
mapping and the proposed optional allowance snapshot. CU changes are
independent. V1 does not read weekly pressure, change resets, or estimate plan
savings. Its telemetry enables later per-attempt accounting without blocking use
on a perfect analytics system.

## Validation and rollout boundary

Evidence is under `/mnt/vk-storage/vk-model-autoswitch-v1/`.
All seven model IDs completed small native inference probes. A Luna→Sol 6.1
process-restart handoff preserved the same thread, conversation passphrase,
checkpoint and operator dirty file. Its initial harness assertion exposed native
`serviceTier: "default"`; the corrected harness completed the existing thread,
and VK now narrowly normalizes that value to standard without treating unknown
or priority tiers as standard. No production task state was reset.

Targeted automated validation covers manual authority, per-chat UI persistence,
exclusions/floors, stale/unverified model-effort pairs, native pinning, escalation
consent, parameter propagation and protocol compatibility. The ignored native
executor acceptance test is explicitly opt-in because it consumes one short turn.
The previously rejected native executor test now passes using the actual candidate
systemd execution path, with its unchanged limit of eight managed executions.
The earlier direct-process probe counted unrelated processes; no capacity limit
was raised or bypassed. A private candidate HTTP acceptance also exercises normal
Sol 6.1 routing, controlled failure, Astra escalation, dirty-state preservation
and explicit Sol 6/medium selection. Detailed evidence and remaining CU/release
gates are tracked in [VK_AUTOSWITCH_ROLLOUT.md](VK_AUTOSWITCH_ROLLOUT.md). New locale strings currently use English fallback text.
Final command results and limits are recorded in HANDOFF.md.

Before normal-task enablement: validate the built frontend/backend together in an
isolated/local VK instance, adopt the verified CLI through the existing deployment
workflow, install fresh candidate-bound evidence, and start with a few operator-
selected tasks at workhorse floor. Routine Luna should get independent diff/test
review; raise the floor when results warrant it. A critical defect, ignored manual
choice, unsafe fallback or attribution failure is a stop condition. No large
historical benchmark is required. Broader quality/usage qualification continues
on real work; automatic production deployment is not part of this implementation.
