# AutoSwitch V1: CU integration and rollout evidence

Version 0.1.42; source branch `vk/5a81-autoswitch-cu-recovery`. Production has
not been restarted, reconfigured or enabled for automatic routing.

## Producer and execution behavior

`VK_ROUTING_EVENTS_FILE` enables the optional private JSONL producer; CU reads
the same path through `CU_ROUTING_EVENTS_FILE`. The canonical contract is
[mirrored here](VK_ROUTING_TELEMETRY_V1.md); its fixture is distributed unchanged.
Existing persisted RoutingDecision and `vk/routing` raw logs remain intact.
Admission emits decision, native response/notification emits exact turn binding,
and persisted terminal state emits execution_end. Standalone task IDs are null.
Manual executions use their execution UUID as routing identity. Stable event IDs,
locked appends and duplicate/conflict checks prevent replay from rewriting events.
Delivery errors warn and do not alter execution; unavailable observations are not
invented. No delivery daemon, scheduler, model retry loop or schema migration.

A discovered executor defect is repaired: native failed turns and unexpected RPC
EOF report failure instead of success, making boundary escalation observable.
Manual effort is pinned into collaboration mode as well as automatic effort.
Automatic policy remains Sol 6.1/medium for workhorse, Astra/high for frontier,
with Luna confined to explicit routine opt-in. Manual remains the default; failed
attempt escalation requires existing consent and a separately requested follow-up.

## Actual bounded acceptance

Evidence root: `/mnt/vk-storage/vk-model-autoswitch-v1/integration`.
`acceptance.json` records four executions through a private VK HTTP backend:

| Role | Execution ID | Actual model/effort | Outcome |
| --- | --- | --- | --- |
| Normal automatic | 6fecd68f-302d-444b-8b1c-b3d460842e34 | gpt-6.1-sol / medium | completed |
| Controlled interruption | ef98df3b-453f-460e-be00-2e6d24175c82 | gpt-6.1-sol / medium | failed |
| Escalated follow-up | 7027019c-89e3-413e-be08-3e1f1b22fc07 | gpt-6-astra / high | completed |
| Explicit manual override | 7c51430e-bc54-45d3-ba8e-fdb7429d63d4 | gpt-6-sol / medium | completed |

All four use native thread `01a0f2b2-e52c-7160-bdee-89f8e70f8f05` with distinct
native turn IDs in `router-events.jsonl`: exactly twelve unique lifecycle records.
The escalation decision points to the failed execution. The fixture checkpoint,
conversation context and operator dirty bytes survive; resume.txt confirms the
follow-up read both files. Manual selection remains authoritative after escalation.
No task ID was invented. Native unknown tier remains null.

The first controlled signal stopped the intended unit but systemd returned an
auxiliary-process error. Before continuing, the harness reconciled its existing
receipt, verified the failed DB state and stopped unit, then performed only the
two remaining turns. No failed inference was repeated. The harness now targets
the identified unit's main process explicitly.

The previously capacity-blocked native executor test also passed (one bounded
turn, `native-executor.log`). Candidate systemd execution used the existing limit
of eight managed executions; no admission bypass or limit change occurred.
The private backend is stopped; fixture data and logs are retained.

Fresh `availability.json` proves all seven configured models on the exact
candidate compatibility launcher `integration/runtime/codex.mjs`, CLI 0.159.2,
and existing `/home/mcp/.local/share/vibe-kanban-green-codex-home` account/home.
Six pairs executed at medium; Astra at high. Model access is proven, not general
coding equivalence or an allowance saving. Evidence expires after 24 hours.

Automated checks: 94 executor tests passed (four intentionally ignored), focused
executor/server Clippy passed with warnings denied, server/guard builds passed,
formatting and ops checks passed. The native acceptance test was run explicitly.
The live HTTP harness is `scripts/testing/autoswitch-live-acceptance.py`; it
refuses silent replay and only interrupts a unit with its exact execution UUID.
No broad benchmark or full workspace suite was added/run for this integration.

## CodexUsage handoff

`/mnt/vk-storage/vk-model-autoswitch-20260930/CU_ACCEPTANCE_HANDOFF.json` contains
actual feed path, native log root, source recovery location and all execution IDs.
CU owns consumer changes. A read-only invocation of its existing RoutingStore,
scanner and report builder against only this native log imported twelve records,
deduplicated all twelve on replay and reported zero binding/settings conflicts.
`integration/VK_CU_PRODUCER_CHECK.json` compares native counters independently:

| Execution | Input | Cached | Uncached | Output | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Normal Sol 6.1 | 19,802 | 0 | 19,802 | 10 | 19,812 |
| Escalated Astra | 49,302 | 24,320 | 24,982 | 226 | 49,528 |
| Manual Sol 6 | 28,746 | 0 | 28,746 | 7 | 28,753 |

The interrupted attempt emitted no native token-count record. Its execution,
model, effort and turn binding are exact, but token usage remains unknown rather
than zero. Consequently a numerical failed-attempt-versus-escalation cost is not
certified. This is a real evidence gap; no extra trial was run to hide it.
CU owner's independent review remains pending in the shared handoff. No consumer
source was changed for this verification. No exclusive-account allowance
or causal model-cost claim is made for these concurrently active-account trials.

## Practical adoption

The existing `scripts/vk-capacity-deployment.py` workflow rendered candidate
capacity configuration. `integration/release/routing-config` adds VK's launcher,
Codex home, availability and feed paths, and CU's matching feed environment.
Nothing was installed into live service configuration. `release/manifest.json`
records exact acceptance binary/guard/launcher hashes. These are debug acceptance
artifacts, not a production release or complete frontend package.

After CU correlation passes, use the normal staging/release process to package
this source, preserve the current frontend features, and carry the verified
launcher plus its CLI dependency into the chosen immutable release location.
If launcher path/account/home changes or evidence expires, regenerate bounded
proof for that exact deployment identity before auto admission. Keep manual as
default and select Auto/workhorse for the first reviewed operator tasks. Routine
remains constrained. Feed rotation must wait for CU import; missing delivery is
visible but has no automatic durable replay/outbox in V1.

Production cutover still requires the separately authorized deployment procedure
and fresh operator approval in VK_BACKEND_RESTART_PROTOCOL.md. This integration
has not exercised a rebuilt browser UI, production handover or live rollback.
Those are release/QA gates, not a new routing benchmark prerequisite.

## Worktree recovery

The active dirty managed worktree disappeared externally at approximately 14:01
UTC. Neither this producer task nor CU requested removal. Committed V1 remained
safe; producer changes were reconstructed and validated in the registered worktree
`/mnt/vk-storage/vk-model-autoswitch-20260930/source`, outside managed workspace
cleanup. `recovered-producer.patch` supplies an additional source checkpoint.
The cause of deletion is unresolved; no production cleanup configuration was changed.
