# VK → CodexUsage routing telemetry v1

This is passive observability, independent of the proposed allocation/admission
contract. CU cannot start/stop agents or alter router settings through this feed.
Native JSONL token events and turn context remain authoritative for token counts
and observed model/settings. No prompts, tool arguments, credentials or UI text.

VK appends UTF-8 JSONL to a private local file; configure CU with
`CU_ROUTING_EVENTS_FILE=/absolute/path/router-events.jsonl`. CU durably imports
complete lines by immutable `eventId`; retry the identical record freely.
Conflicting reuse of an ID is rejected and surfaced. Rotate files only after CU
has imported them. File identity is local deployment configuration, not a network
API. CU stores an independent receipt; losing the feed does not delete receipts.

Every record requires `schema: "vk.routing.v1"`, globally unique `eventId`, UTC
`timestamp`, `kind`, and globally unique `executionId` (the VK execution-process
UUID, not workspace/session shorthand). `routingId` is required on every kind.
Null means unknown, never default/zero.

## Records

`decision`: required `routingId`, `workspaceId`, `sessionId`, `mode`
(`auto`, `shadow`, `manual`), `action` (`initial`, `escalate`, `switch`),
`policyVersion`, exactly one decision per execution, optional `transitionId`, `parentExecutionId`, `reasonCode`, and
`selected: {model, reasoningEffort, serviceTier}`. These settings are requested,
not authoritative observations. Escalations require `transitionId` and
`parentExecutionId`. Shadow proposals never count as routed executions.
`taskId` is optional and nullable: standalone chats need no linked task. CU
normalizes omitted/null task IDs to null, never a synthetic task ID. If present
and non-null, it must be a nonempty string. Execution attribution uses
`executionId` + `routingId`, joined by exact native thread/turn; `sessionId` and
`workspaceId` supply VK identity independently of any task link.

`turn_bound`: `routingId`, `nativeThreadId`, `nativeTurnId`; emitted after native
turn/start returns its actual ID, including each continuation in a native goal.
Optional `effective: {model, reasoningEffort, serviceTier}` may fill absent native
fields ONLY with `settingsSource: "runtime_confirmed"`, meaning an authoritative
native response/event confirmed the value. Omitted or null native effort/tier is
unknown; sending the requested configuration does not confirm it. A native settings
conflict prevents the fallback settings from being used. Native settings win.
No time-nearest or workspace-name matching. One native thread+turn belongs to at
most one execution; conflicting bindings are quarantined from execution totals.
Bind delegated child turns explicitly to include their usage in an execution.

`execution_end`: `routingId`, `outcome` (e.g. accepted, failed, interrupted),
optional `measurement: {exclusiveAccount: true, accountKey, settledAt}` for a
controlled allowance window. accountKey is CU's hashed account identity from
private observation storage. settledAt is AFTER provider-lag quiescence, not
merely process exit. It must be supplied only when the operator/VK actually
controlled the entire account (including external clients). CU still labels the
result an observed, conditional whole-account movement, not a model multiplier.

```json
{"schema":"vk.routing.v1","eventId":"decision-1","timestamp":"2026-10-01T12:00:00Z","kind":"decision","executionId":"execution-1","routingId":"route-1","workspaceId":"workspace-1","taskId":"task-1","sessionId":"session-1","mode":"auto","action":"initial","policyVersion":"pilot-1","selected":{"model":"gpt-5.6-sol","reasoningEffort":"medium","serviceTier":"standard"}}
{"schema":"vk.routing.v1","eventId":"bound-1","timestamp":"2026-10-01T12:00:01Z","kind":"turn_bound","executionId":"execution-1","routingId":"route-1","nativeThreadId":"native-thread-1","nativeTurnId":"native-turn-1"}
{"schema":"vk.routing.v1","eventId":"end-1","timestamp":"2026-10-01T12:05:00Z","kind":"execution_end","executionId":"execution-1","routingId":"route-1","outcome":"failed"}
{"schema":"vk.routing.v1","eventId":"decision-2","timestamp":"2026-10-01T12:05:02Z","kind":"decision","executionId":"execution-2","routingId":"route-2","workspaceId":"workspace-1","taskId":"task-1","sessionId":"session-1","mode":"auto","action":"escalate","policyVersion":"pilot-1","transitionId":"escalation-1","parentExecutionId":"execution-1","reasonCode":"validation_failed","selected":{"model":"gpt-6-astra","reasoningEffort":"high","serviceTier":"standard"}}
```

All joins use full IDs. Settings-only escalations are valid. Native runtime
reroutes and router escalations are separate observations. Before/after usage is
usage of parent/new execution within the requested reporting window; truncated
or unobserved attempts are explicitly incomplete, never priced as zero. A
transition timestamp alone does not prove a request changed model. Router emitters
must publish decisions and bindings before allowing another execution to reuse a
native thread. CU does not infer actual settings from the latest thread config.

## Canonical ownership and VK producer mapping (2026-09-30)

This document is the single **wire contract** for `vk.routing.v1`. The canonical
source is `codexusage/docs/routing-telemetry-v1.md`; VK's
`VK_ROUTING_TELEMETRY_V1.md` is a byte-identical distribution copy, not a second
schema. `VK_CODEX_ROUTING_CONTRACT.md` describes internal VK implementation
surfaces and points here. Change the canonical source first and synchronize the
copy. Executable wire fixtures at `codexusage/test/fixtures/vk-routing-v1.jsonl` cover
an unlinked standalone execution and an escalation; CU's routing tests consume
them. VK distributes the same bytes at
`scripts/testing/fixtures/vk-routing-v1.jsonl`.

VK currently persists `executor_action.routing_decision` and emits a native
`{"method":"vk/routing","params":...}` log event. Neither is a `vk.routing.v1`
wire record. The producer must serialize the following explicit mapping; CU must
not guess whether a snake_case internal structure is a camelCase feed record.

| Wire field                                                           | Authoritative producer source                                                                                                                    |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `schema`                                                             | Literal `vk.routing.v1`                                                                                                                          |
| `executionId`                                                        | Full persisted execution-process UUID                                                                                                            |
| `routingId`                                                          | `routing_decision.id` (unchanged on all records for this execution)                                                                              |
| `sessionId`, `workspaceId`                                           | Persisted execution session and its workspace UUID                                                                                               |
| `taskId`                                                             | Linked workspace task UUID, otherwise null or omitted                                                                                            |
| `mode`                                                               | `routing_decision.mode`; preserve shadow as shadow                                                                                               |
| `action`                                                             | `escalate` if `escalated`; otherwise `switch` when a recorded predecessor's model differs from selection; otherwise `initial` for this execution |
| `parentExecutionId`                                                  | `previous_execution_id` for a transition; required for escalation                                                                                |
| `transitionId`                                                       | `transition:${routingId}` for a transition; required for escalation                                                                              |
| `policyVersion`                                                      | `vk-autoswitch-v1` for the current v1 selection algorithm, not an invented model/pricing version                                               |
| `reasonCode`                                                         | `routing_decision.reason`                                                                                                                        |
| `selected.model`, `selected.reasoningEffort`, `selected.serviceTier` | `selected_model`, `selected_effort`, `service_tier`; these remain requests/recommendations                                                       |
| `nativeThreadId`, `nativeTurnId`                                     | Actual native thread and each started turn, scoped to this execution                                                                             |
| `effective.model`, `effective.reasoningEffort`                       | Runtime `resolved_model` / `resolved_effort`, only while confirmed valid for that turn                                                           |
| `effective.serviceTier`                                              | Runtime-confirmed tier; see pinned-protocol rule below                                                                                           |
| `outcome`                                                            | Persisted terminal execution outcome; never infer success from a settings observation                                                            |

Event IDs are opaque immutable strings. The VK producer uses `vk:` plus SHA-256
of the JSON tuple `[kind, executionId, nativeThreadId-or-null, nativeTurnId-or-null]`.
CU does not parse or reconstruct this ID; it deduplicates the supplied value.
`transitionId` is likewise opaque. Persist each event once and replay it identically.
`timestamp` is the original event time in UTC, **not** the later export/import time:
execution admission for `decision`, native turn start/binding for `turn_bound`,
terminal execution time for `execution_end`. Do not regenerate timestamps on retry.
Late task linking must not mutate an already published decision; its task ID stays
null. Missing historical event time/turn identity is not permission to invent one.

For VK's pinned native 0.159 decoder, an explicit native `default` service tier is
narrowly normalized to internal null and represents standard. The producer may
emit `effective.serviceTier: "standard"` with `settingsSource: "runtime_confirmed"`
only at that verified runtime response boundary (or when it has equivalent native
evidence). A missing field, unknown decoder provenance, requested default, or
unverified later turn remains null. CU never globally interprets null as standard.
Do not copy a thread-start observation across a later settings change without
confirmation. Publish a binding for every native goal continuation and child turn
that is to be charged to the execution. Native context still takes precedence.

VK's `account_fingerprint` hashes a different identity representation from CU's
account key. Do not use it as `measurement.accountKey` or imply account equality
without an explicit verified mapping. Controlled token/escalation acceptance does
not require a per-execution allowance assertion.

### Minimum live acceptance gate

After the producer emits the feed, run only one normal routed execution and one
controlled escalation (the initial attempt plus its escalated follow-up). Reuse
an existing verified trial if it supplies all required records. Keep trial work
isolated and bounded; respect existing capacity admission. Import those records
through CU and scan only their native log/time window. Verify full execution /
thread / turn IDs, observed models, input = cached + uncached, total = input +
output, and separate parent/follow-up totals against the original native usage
records. Missing evidence or a rejected admission is not a pass. This gate does
not authorize production restart/cutover or a historical audit.
