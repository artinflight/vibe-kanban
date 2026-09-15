# Conversation, delivery and memory contracts

Companion to [architecture](VK_CHAT_ARCHITECTURE.md). All routes, tables and
interfaces in this document are proposed unless explicitly labelled existing.
Names establish the implementation contract; generate public types from Rust.

## Storage model

Use the existing local SQLx database and migration machinery. UUID primary keys,
UTC timestamps, foreign keys and bounded JSON payloads follow existing VK patterns.
Create tables additively; do not rewrite execution logs or legacy chat history.

| Table | Essential columns and constraints |
| --- | --- |
| `conversations` | `id`, `authority_id`, `principal_id`, `kind` (global/direct), nullable `workspace_id`, `session_id`, `next_seq`, `revision`, `created_at`, `archived_at`. Unique default global per authority/principal; unique direct per authority/principal/session. Check global has no workspace/session; direct has both and session belongs to workspace |
| `conversation_messages` | `id`, `conversation_id`, `created_seq`, `role`, `origin` (typed/voice/agent/derived/system), `body`, `revision`, `status`, nullable `reply_to_id`, `source_ref_id`, `voice_session_id`, `client_message_id`, `created_at`. Unique `(conversation_id, client_message_id)` when provided |
| `conversation_events` | `(conversation_id, seq)` primary key, `event_id` unique, `type`, `schema_version`, `entity_id`, `entity_revision`, `payload`, `occurred_at`. Durable user-visible changes and action transitions; transient token/ASR deltas are not durable events |
| `conversation_runs` | `id`, `conversation_id`, `input_message_id`, `input_revision`, `status`, `generation`, `lease_owner`, `lease_until`, `context_manifest`, `model_config`, `usage`, `error`. One active leased generation per conversation; status covers pending/running/completed/interrupted/failed |
| `conversation_actions` | `id`, `run_id` nullable for direct sends, `conversation_id`, `origin_message_id`, `intent_kind`, `payload`, `payload_digest`, `state`, `route_evidence`, `authorisation_source`, `created_at`. Immutable authorised payload; corrections create new actions |
| `agent_deliveries` | `id`, `action_id`, fully qualified target, `executor_config`, `target_revision`, `message`, `state`, `attempt_count`, `not_before`, `lease_generation`, nullable `execution_process_id`, `provider_receipt`, `error`. Unique `(action_id, target_session_key)`; shared session queue consumes these rows |
| `conversation_confirmations` | `id`, `action_id`, `principal_id`, `payload_digest`, `target_revision`, `expires_at`, `state`, `answered_message_id`. Durable, one-use, compare-and-swap acceptance |
| `conversation_evidence` | `id`, typed source key (authority/session/process/turn/log entry or repo state), `source_revision`, `content_hash`, `availability`, `captured_at`, optional retained raw report. Unique source/revision; stable references, no arbitrary filesystem paths from callers |
| `conversation_message_evidence` | `(message_id, evidence_id)`, optional excerpt locator, `relationship` (summarised/quoted/supporting). Supports many reports per answer |
| `conversation_memory` | `id`, `principal_id`, scope kind/key, `claim_key`, `body`, `entity_refs`, `state` (proposed/active/superseded/retracted), `revision`, `supersedes_id`, `source_message_id`, `author_kind`, `confidence`, `valid_from`, `valid_until`. Partial uniqueness for one active revision per principal/scope/claim key |
| `conversation_context` | `conversation_id`, `revision`, `focus`, `topic_segment`, `summary`, `covered_through_seq`, `source_versions`, `invalidated_at`. Derived and rebuildable; never used as sole evidence |
| `conversation_read_cursors` | `(principal_id, conversation_id)`, `last_read_seq`, `last_reviewed_sources`, `updated_at`. Monotonic explicit acknowledgement; separate from existing `CodingAgentTurn.seen` |
| `voice_sessions` | `id`, `conversation_id`, `provider`, `provider_call_id`, `voice_key`, `generation`, `state`, `transcript_cursor`, `started_at`, `ended_at`, `usage`, `retention_config`. Unique provider/call ID; never stores browser access token |
| `voice_utterances` | `id`, `voice_session_id`, `provider_segment_key`, `revision`, `speaker`, `text`, `status`, audio offsets, nullable `message_id`, `response_generation`, `delivery_state`. Unique segment key/revision; explicit link to canonical text |

A direct conversation wraps one session rather than one execution. Existing
multi-user deployments must not treat the local operator principal as a cloud
user. Initially provision one stable installation operator ID under the existing
trusted boundary; authenticated relay principals need an explicit ownership map.
Do not map all relay users onto this principal. Authorisation applies equally to
history, evidence, memory, search, streaming and actions.

Index messages/events by conversation/sequence; deliveries by target/state/order
and lease expiry; memories by principal/scope/state; evidence by source identity;
runs by pending/lease expiry. Scope references are validated typed keys because a
single foreign key cannot span local and cloud entities. Keep tombstone names for
deleted targets, not dangling executable routing capabilities.

Raw process logs already live under the asset directory at
`sessions/{session}/processes/{process}.jsonl`, with legacy SQLite fallback in the
execution log service. Reference these through that service. Retain the exact
final report used in a summary when source cleanup could otherwise remove it;
retain referenced diagnostic artefacts under the approved retention policy, or
record their loss explicitly. Archiving a workspace does not erase conversation
history. History deletion and source artefact deletion are separate operations.

## Transaction and event contract

A durable mutation increments conversation sequence, updates its query row and
inserts its event in the same database transaction. Increment `next_seq` under the
write transaction, not from wall-clock time or a frontend counter. Emit notifications
only after commit. SQLite hooks/MsgStore can wake subscribers but are not a durable
outbox or proof that a transaction committed. Workers scan durable pending rows at
startup and after missed notifications.

Durable event types include `message.created`, `message.revised`, `message.final`,
`run.status`, `action.status`, `delivery.status`, `memory.changed`,
`confirmation.requested`, `confirmation.resolved`, `voice.status` and
`evidence.updated`. Envelope: `event_id`, `conversation_id`, `seq`, `schema_version`,
`type`, `entity_id`, `revision`, `occurred_at`, `payload`. Clients ignore an event
already applied by sequence and apply entity revisions monotonically. Unknown
optional types trigger snapshot refresh rather than crashing the whole chat.

Prefer the existing WebSocket transport/auth patterns for conversation streams.
`GET .../events/ws?after_seq=N` first replays committed rows, then tails them. Avoid
a replay/live subscription gap by using the DB sequence as authority throughout;
a wakeup requests rows after the last cursor rather than forwarding opaque hook
payloads. Periodic catch-up also recovers lost notifications. A lagging subscriber
gets `resync_required` and a snapshot cursor instead of unbounded server buffering.
Paginated history is independent of the live stream.

Transient `response.delta` and `transcript.partial` frames include run/voice
generation and stable entity ID. They can be lost; final durable events replace
them. On reconnect fetch the snapshot and resume after its sequence. Never infer
that the user saw/spoke/heard a message simply because the server emitted it.

## Proposed HTTP surface

Mount local routes under the existing `/api` request boundary. Use existing
`ApiResponse<T>` conventions and generated Rust/TypeScript DTOs. IDs in URLs are
local to the selected authoritative backend; external references in payloads are
fully qualified. No browser-to-model credentials or arbitrary tool execution API.

| Route | Behaviour |
| --- | --- |
| `POST /conversations/resolve` | Resolve/create the principal's global conversation or an explicitly selected direct session; idempotent by unique keys |
| `GET /conversations` | Principal-owned history list; cursor pagination and text search |
| `GET /conversations/{id}` | Snapshot with last sequence, active run/action summaries and capability flags |
| `GET /conversations/{id}/messages?before_seq=&limit=` | Older messages and evidence/activity links; default 50, cap 200 |
| `POST /conversations/{id}/messages` | `{client_message_id, body, origin, reply_to_id?, expected_focus_revision?, target?}`; 202 only after message plus pending run/direct action commit; returns stable IDs/sequence |
| `POST /conversations/{id}/messages/{mid}/corrections` | Creates a linked correction, preserving original authorisation evidence; never silently edits dispatched instructions |
| `GET /conversations/{id}/events/ws?after_seq=` | Replay/live contract above, using existing signed WebSocket mechanisms where applicable |
| `POST /conversation-runs/{id}/cancel` | Fences model generation; cancels only undispatched proposals, returns any already delivered actions |
| `GET /conversation-actions/{id}` | Exact payload/targets/receipts and evidence visible to its principal |
| `POST /conversation-actions/{id}/cancel` | Cancels pending deliveries via compare-and-swap; cannot unsend a successful steering message |
| `POST /conversation-confirmations/{id}/answer` | Decision with expected digest/revision; changed/expired grant returns conflict |
| `GET /conversation-evidence/{id}` | Raw report or authorised paged artefact lookup; unavailable source is explicit |
| `GET/POST /conversation-memories` | Scoped list/search or explicit addition |
| `PATCH/DELETE /conversation-memories/{id}` | Revision-checked supersession/retraction, scope validation and cache invalidation |
| `POST /conversations/{id}/read` | Acknowledge displayed sequence and actually reviewed source coverage |
| `GET /voice/capabilities` and `GET /voice/voices` | Provider availability and selectable voice previews, no credentials |
| `POST /conversations/{id}/voice-sessions` | Bind call to conversation, selected direct session if applicable, and voice preference; short-lived browser connection material |
| `POST /voice-sessions/{id}/resume` and `/end` | Reconcile/reconnect or start a new media segment on the same conversation; idempotent end |

Initial limits: 64 KiB text per conversational message (attachments by existing
reference), 20 routing candidates per page, default maximum 5 inferred recipients
before scope review, and one active model run per conversation. Explicit larger
sets are supported through reviewed target manifests. These are configurable
resource defaults, not prompt instructions. 401/403 denote access failure, 404
missing entity, 409 stale state/idempotency payload mismatch, 413 limits and 429
capacity. Retryable errors include a backoff hint. Disabled provider returns a
specific configuration-required capability error while text/direct work continues.

The supervisor's model tools call domain services, not an HTTP loop back into its
own server. Initial tools: `find_context`, `read_workspace_state`,
`read_agent_history`, `read_evidence`, `list_attention`, `propose_agent_message`,
`read_action`, `search_memory`, `propose_memory_change`. Typed results carry source
IDs/revisions, availability and access scope. The model cannot execute arbitrary
SQL, shell commands, filesystem paths or provider callbacks.

## Dispatch and reconciliation

Refactor existing session follow-up/queue handlers and their frontend callers onto
one dispatch service. Keep their public compatibility during migration. Replace
the authoritative `DashMap` queue with persisted `agent_deliveries` (optionally an
in-memory cache), including legacy callers by giving them source/action IDs. Do
not copy messages into both an independent supervisor queue and the old consumer.

Message acceptance is not execution success. Per-recipient states:

```text
pending -> awaiting_confirmation -> ready -> dispatching
                                      |          |
                                      v          v
                               waiting_capacity  steered / queued / started
                                                     |
                                                     v
                                            completed / failed / interrupted
uncertain acknowledgement -> unknown_delivery -> reconciled or explicit retry
pending/ready/queued -> cancelled (only before consumption)
```

`steered` means the executor acknowledged input into a running turn. `queued`
means VK durably holds it. `started` means a correlated coding process was admitted.
`completed` means a correlated result arrived, not independent verification of the
agent's claims. Multiple messages steered into one running process may share its
final result; mark that grouping rather than fabricate one answer per instruction.
“Ask why” can remain awaiting an answer even after a generic completion report.
Action aggregate state derives from recipient states, preserving partial success.

For a running session use `try_steer_active_turn` only if supported. Current Codex
queue route returns conflict when steering is unavailable, deliberately without
queue fallback. Preserve this behaviour: surface retryable not-ready; do not
silently save a Codex correction for a later turn. For other agents, use the
existing queue-at-turn-boundary semantics with durable rows. An idle session uses
existing follow-up/resume and safe interrupted-context logic. Capacity waits are
represented explicitly. Persist full effective executor/model/reasoning selection;
never substitute a global default. Exclude dev servers as message consumers.

Serialise admission by session and use a workspace admission guard where existing
setup/Git operations require it. Revalidate session membership, archive/worktree
state, native-goal pause, permissions and active process under the guard. A process
finishing between resolution and dispatch causes a re-read; it does not change the
target session. A renamed/archived/deleted target may require re-resolution.
Queue cancel and consumer claim must be one atomic state transition. Preserve
message ordering by committed sequence; keep individual provenance when legacy
behaviour combines several messages into one follow-up prompt.

Create an execution correlation (delivery ID to process ID) in the same transaction
as process admission, before spawning. Extend the internal admission API to accept
this key. Recovery checks the correlated process and runtime status before trying
anything again. A durable lease with generation prevents two workers from
consuming one row; a process-local mutex alone is insufficient after restart.

Steering crosses an external executor boundary that does not currently promise
idempotent delivery. Write an attempt before the RPC, persist its acknowledgement
afterwards, and use provider message/turn IDs if exposed. A crash between receipt
and persistence yields `unknown_delivery`; reconcile against actual logs/thread
state. Without conclusive evidence, do not automatically resend. Explain the
uncertainty and allow an explicit retry. Never claim exactly-once agent effects.
Use the same rule for provider call creation timeouts: reconcile, then retry.

A durable result-ingestion scan uses coding-turn ID plus source revision/hash as
its key. Live events give low latency; restart scan repairs missed finalisations.
Initial direct history is a lazy projection of existing turns/logs with stable
source keys. New direct sends and their projected agent echoes share those keys
so the transcript does not double-render. Keep original input separate from any
expanded executor prompt. Native retry/reset makes an old process `dropped`;
record that supersession in evidence and exclude it from current-state summaries,
while retaining historical action records. Existing process normalisation and
attachment handling remain the raw view.

## Concurrency and failure semantics

- Text and finalised speech enter one sequence. Two clients may append concurrently;
  unique client IDs deduplicate retries. A reused ID with changed content is 409.
- Conversation model work uses one renewable lease/generation. A new utterance can
  interrupt generation; ignore late model tool proposals from the fenced generation.
  Already accepted actions remain visible and independently reconciled.
- Direct and global sends to the same agent use the same admission/queue boundary.
  Opposing instructions are not merged by a summary. Show their order and ask for
  clarification when the new intent is ambiguous.
- One active microphone owner per conversation. A second device requests takeover;
  the old generation is fenced before new media starts. Typed messages remain usable.
- Model failure leaves committed input and delivery records intact; retry a run
  with its existing action IDs. A new model response cannot duplicate those effects.
- Disk/DB write failure means no accepted message and no action/speech asserting
  success. Keep an unsent draft and explain the failure. Do not acknowledge first.
- Offline hosts retain explicit last-observed state. No silent cross-host reroute.
  Throttle retries and expose retry/cancel; ordinary unrelated sessions stay usable.
- Approval expiry or lost native approval waiter is reported; re-fetch the agent's
  current request. Persistent orchestration confirmation does not resurrect an
  expired executor approval.

## Observability, privacy and retention

Use existing tracing and error conventions. Correlate conversation/message/run/
action/delivery/process/voice-session IDs. Record routing candidates and selection
reason, source coverage, exact sent message, receipt, summary model/version,
transformation kind and error stage. Do not log chain-of-thought, API keys, tokens,
raw audio or full prompts to general telemetry. The authorised activity view is
where content and evidence belong.

Measure acceptance-to-delivery latency, queue age, unknown deliveries, duplicate
suppression, routing clarifications, source freshness, summary corrections,
voice reconnects, first-audio latency, billable minutes and model usage. Alerts
focus on stuck delivery, failed ingestion, persistence failure and spend limits.
“Summarised from 2 reports” and expandable sources explain abstraction without
making the conversation a debugging console.

Keep conversation text/memory until user deletion by default; raw audio off.
Provide export and deletion covering rows, retained report copies, summaries,
search indexes and provider records where supported. Redact deleted event payloads
rather than retaining supposedly deleted content in an append-only log; retain
minimal sequence/tombstone metadata. Backups obey separately disclosed retention.
Cross-project report forwarding to another agent is an action with minimum needed
context; reading both projects does not automatically justify copying all their
logs or secrets. Scope-aware retrieval excludes inaccessible content before model
calls. Provider/model data egress must be declared in settings.

Local origin checks are CSRF protection, not user authentication: current middleware
allows requests without Origin and bypasses signature verification for non-relay
requests. Preserve trusted local access; never expose new chat/tools routes publicly
on the assumption that CORS authenticates them. Voice ingress is separately
restricted as described in [voice security](VK_CHAT_VOICE.md#security-and-third-party-processing).
