# VK → CodexUsage routing contract, version 1

Owner: VK persists selection and execution identity; CodexUsage owns token/allowance
accounting. This contract adds no CU dependency and no new scheduler. It is a
source contract for the AutoSwitch branch, not a claim of live deployment.

## Read surfaces

Use the existing VK execution-process API, including
`GET /api/execution-processes/{execution_id}` and the session execution stream.
An execution carries `id`, `session_id`, `executor_action`, lifecycle timestamps,
status and exit code. Resolve workspace/task links through the existing session
and workspace records; a standalone chat may have no task ID.

`executor_action.typ.executor_config` contains the concrete settings requested
for that execution, including its opt-in `routing` policy. For automatic routing,
VK resolves this object **before** the execution row is created.
`executor_action.routing_decision` is optional for backward compatibility. Its
version-1 fields are generated in `shared/types.ts` from Rust:

| Field | Meaning |
| --- | --- |
| `version`, `id` | Contract version and unique routing decision UUID |
| `mode` | `auto` or `shadow`; absent decision/absent policy keeps manual behavior |
| `floor` | Effective capability floor, including retained prior floor and risk escalation |
| `reason` | `capability_floor`, `previous_execution_failed`, `native_resume_pinned`, or `recommendation_unavailable: …` |
| `requested_model` | Caller model before routing |
| `selected_model`, `selected_effort`, `service_tier` | Router selection; in shadow mode these are recommendations, not executed settings |
| `previous_model`, `previous_execution_id` | Predecessor in this VK session, when present |
| `escalated` | Decision was triggered by a failed predecessor at a new requested boundary |
| `catalog_observed_at` | Unix seconds for the availability snapshot, nullable |
| `account_fingerprint` | SHA-256 of native account type + `:` + email; internal correlation value, never an authentication credential |

The persisted policy carries mode, declared floor, denied models and escalation
consent. Cost rank is an operator preference from the model policy registry, not
a measured allowance weight. Schema version 1 describes field semantics, not a
version of model capability or a model snapshot.

## Native execution observation

After native thread start/resume succeeds, VK appends this JSON event to the
execution's raw log. Automatic mode verifies account, model, effort, provider and
standard service tier before emitting it and before starting inference:

```json
{
  "method": "vk/routing",
  "params": {
    "decision": {"version": 1, "id": "decision-uuid", "mode": "auto"},
    "native_thread_id": "native-thread-id",
    "resolved_model": "gpt-6.1-sol",
    "resolved_effort": "medium",
    "resolved_service_tier": null
  }
}
```

The example abbreviates the decision; the actual event contains every field in
the table. `resolved_service_tier: null` means standard in VK's pinned protocol;
native 0.159's `default` is normalized to null. Other values are **not** mapped to
standard. A provider reroute stops an automatic execution for review.

VK also renders the event as a system message containing actual model/effort,
mode, recommendation and reason. Native thread IDs remain recorded by the
existing turn/session machinery. Use native `turn/started`, `turn/completed` and
token events for turn identity: one VK execution may contain several native goal
turns. A successful settings observation is not a completed task or a quality
pass; consult execution outcome and independent validation separately.

## Correlation and accounting rules

- Join `execution_id → session_id → workspace_id` through VK records; associate
  native thread and turn IDs with that execution's logs. The same native thread
  can span multiple VK executions/models. Do not charge an entire thread to its
  first or last model.
- Segment usage by observed model/effort/tier changes. The event establishes the
  VK boundary configuration; native context/events are needed for subsequent
  changes and delegated work. Preserve unknown values rather than inferring them.
- Deduplicate by source + native thread/turn + event identity/cumulative baseline.
  Do not sum repeated cumulative totals or hydrated/forked history. Reasoning
  tokens may already be included in output totals.
- Include failed attempts, reviewed/rejected changes and escalation recovery in
  accepted-task cost. A routing decision without native observation consumed no
  proven inference; mark usage unknown/zero only when the source supports it.
- Shadow recommendations must never be attributed as the executed model. Use
  `resolved_*` plus the underlying native token events.
- No-candidate admission failures currently return actionable API errors without
  creating an execution row. Durable rejected-decision analytics is deferred.
- Treat the account fingerprint as internal pseudonymous account data. Do not
  expose email, account tokens or prompt contents in aggregate reports.

## Optional future CU → VK allowance snapshot

A separate read-only service contract can provide `version`, account fingerprint,
observed time/freshness, limit-pool ID, used/remaining percentage and reset time for
each reported window. Missing data means unknown. Account-level deltas during
concurrent work are not per-model billing. V1 does not consume this snapshot or
change reset/lease policy. Future usage pressure may reorder qualified candidates
or defer work, never reduce the established floor or override human selection.

The CU agent can implement this consumer independently; no CU repository files
were changed by the VK implementation.
