# Dot steering and follow-up investigation — 2026-10-15

Dot's exact `Session is running; no follow-up sent` refusal originates in the
external connector, before any prompt POST reaches VK. Supporting active steering
requires changing that connector. Supporting an explicitly deferred Codex prompt
also requires a backend API change: the existing queue route deliberately steers
Codex and refuses its queue fallback.

This is an investigation and implementation plan. No connector, backend, routing
policy, service or running agent was changed.

## Confirmed request path

The active `vibe-dot-connector.service` uses the separate connector project at
`/home/mcp/code/vibe-dot-connector`. Its `adapter.py` intercepts
`tools/call: run_session_prompt` in `Adapter.handle`; it does not forward this
tool to the bundled Rust MCP executable.

1. `local_followup` accepts only `session_id` and `prompt` (maximum 60,000
   characters), then calls `resolve_followup_config`.
2. That resolver requires CODEX and calls `session_configs`, which invokes the
   read-only `session-config.mjs` WebSocket snapshot helper.
3. `session_configs` rejects **any** row with `status == "running"` using the exact
   reported error. This includes script/dev-server rows, not just a coding turn.
4. Only after this gate does resolution inspect the saved draft and preserve
   model, effort, permission and routing restrictions. Recommend is enforced by
   setting routing mode to `shadow`.
5. `local_followup` POSTs to `/api/sessions/{id}/follow-up` and assumes a newly
   created execution ID. It cannot return a steering or queued receipt.

Relevant external source: `adapter.py` functions `session_configs`,
`resolve_followup_config`, `local_followup`, `post_fixed` and `Adapter.handle`;
`session-config.mjs`; `test_recommend.py`; and `README.md`'s Recommend-only policy.
The connector's tool schema has no delivery-mode parameter or queue tools.

The repository's own [Rust MCP tool](crates/mcp/src/task_server/tools/sessions.rs)
also only calls `/follow-up`, has no steering/queue tools, and returns an
execution-only response. Fixing that Rust tool alone does not fix Dot's local
override. Its config builder also leaves model/effort/permission unspecified,
so replacing the override must preserve the connector's stronger selection policy.

## Existing backend behavior

| Intent | Existing route | Behavior |
| --- | --- | --- |
| Start/resume an idle session | `POST /api/sessions/{id}/follow-up` | Starts an execution; capacity exhaustion may instead return queued error data. |
| Correct an active Codex turn | `POST /api/sessions/{id}/queue` | Calls native `turn/steer` on the current thread and expected turn; returns `QueueStatus::Empty` on acceptance. |
| Queue behind a running non-Codex agent | Same `/queue` route | Falls back to an ordered message batch when steering is unavailable. |
| Explicitly defer a Codex prompt until the next turn | No dedicated delivery mode | `/queue` attempts steering and explicitly rejects the Codex queue fallback. |
| Inspect/cancel pending work | `GET` / `DELETE /api/sessions/{id}/queue` | Available in HTTP/UI, absent from Dot's tool surface. |

Sources: [queue handler](crates/server/src/routes/sessions/queue.rs),
[follow-up handler](crates/server/src/routes/sessions/mod.rs),
[container steering and consumption](crates/local-deployment/src/container.rs),
[native Codex client](crates/executors/src/executors/codex/client.rs),
[queue service](crates/services/src/services/queued_message.rs), and
[UI API client](packages/web-core/src/shared/lib/api.ts).

The native client waits up to 40 readiness attempts, 50 ms apart, for the active
execution/client/thread/turn binding. Unavailable steering yields a conflict,
not a deferred Codex message. Existing tests explicitly enforce that policy.
The route accepts `message` and `executor_config`, whereas `/follow-up` accepts
`prompt` and `executor_config`; simply changing the URL is insufficient.

The queue service can already accumulate ordered Codex-configured messages and
the container can resume them. The limitation is public API admission/delivery
policy, not an absent queue engine. Queued messages are combined into one next
turn. Persistence/recovery is conditional on `VK_AUTOMATIC_GITHUB_SYNC`; without
it, the queue is in memory, and failed/killed-turn finalization discards its batch.
Do not promise restart-safe or failure-safe follow-ups without addressing this.

## Required implementation

1. Separate configuration lookup from running-state rejection in the external
   connector. For steering, bind to the actual active coding execution; a dev
   server is not an active coding turn. Preserve current executor/model/effort,
   permissions and Recommend-only restrictions. A steering message does not
   reconfigure the already running model; draft selection applies to a later turn.
2. Expose explicit steering and deferred delivery, either with separate tools or
   an optional delivery parameter. Keep existing idle `run_session_prompt` calls
   compatible. Steering should use the existing fixed `/queue` endpoint, with
   its correct request shape and current owner-input/admission checks.
3. Add an explicit backend queue-only mode for Codex. It should bypass steering
   only when deferral is requested, preserve ordered messages, and use existing
   admission, input journaling, scheduled-owner amendment/takeover rules and
   capacity/finalization paths. Keep the current steering-only default; do not
   silently convert an unaccepted correction into a later turn.
4. Make state selection and acceptance authoritative in the backend. A connector
   snapshot can race turn completion/start. Use an expected execution/turn where
   appropriate and a clear conflict when it changed; do not blindly resend a
   possibly accepted prompt against another endpoint.
5. Return distinct `started`, `steered`, `queued`, `not_ready` and uncertain
   outcomes. Steering retains the current execution ID; queued input has no new
   execution yet. Preserve HTTP conflict reasons and typed capacity-queue data:
   `post_fixed` currently discards `success: false` queue information, while the
   Rust MCP helper also expects only an execution success envelope. Add receipt
   or request-ID reconciliation before any retry after an uncertain send.
6. Expose bounded queue inspection/cancellation if Dot is to manage follow-ups,
   updating its fixed allowlist, dispatch and discovery schemas. Preserve its
   prompt bounds, CODEX-only policy and absence of generic HTTP/shell/stop tools.
   Add matching Rust MCP capabilities if other MCP clients need parity; regenerate
   shared TS/schema output through the normal generators if API types change.
7. Validate connector mocks and backend integration for idle/running/not-ready,
   turn-boundary races, script/dev-server-only activity, ordered multiple prompts,
   capacity queues, cancellation, restart/failure recovery, preserved settings,
   scheduled-owner boundaries, and uncertain writes. Then perform an authorized
   disposable-session end-to-end check. Connector-only steering adoption requires
   only its own process reload and cached-tool refresh if schemas change; backend
   queue-mode changes require the normal reviewed VK release/restart process.

## Evidence and limits

- Existing connector `test_recommend` suite: **9 tests passed**, run with
  `PYTHONDONTWRITEBYTECODE=1` and the connector directory on Python's module path.
- A mocked running execution snapshot through the actual `local_followup` path
  reproduced the exact error and asserted **zero `post_fixed` calls**. No live
  prompt or paid turn was sent.
- Read-only service/process inspection found the connector active. The gateway
  script forwards `/api/` requests without an endpoint-specific queue allowlist;
  it is not the source of this refusal.
- The active VK service was `vibe-kanban-combined-20261014.service`, not the
  historical `vibe-kanban-green.service`. Its executable contained both the
  Codex queue-readiness refusal and `turn/steer` RPC strings. This is capability
  evidence, not successful live steering. A synthetic unknown-session queue GET
  returned HTTP 404; it does not establish real-session delivery.
- `pnpm run ops:check` and `git diff --check` passed. `pnpm run format` completed
  Rust formatting, then stopped because web-core's `prettier` is not installed
  in this checkout. Only Markdown documentation changed.
  No Rust compilation, live steering/queue mutation, connector restart, backend
  restart, deployment, permission change, commit or push was performed.
