# Conversation, delivery and memory contracts

Companion to [architecture](VK_CHAT_ARCHITECTURE.md). All routes, tables and
interfaces in this document are proposed unless explicitly labelled existing.
Names establish the implementation contract; generate public types from Rust.

## Storage model

Use the existing local SQLx database and migration machinery. UUID primary keys,
UTC timestamps, foreign keys and bounded JSON payloads follow existing VK patterns.
Create tables additively; do not rewrite execution logs or existing session history.
The `conversation_*` tables and `conversations` serve the global supervisor only.
Workspace text chat continues using existing session APIs, history and rendering.
Shared delivery and voice metadata below do not create a second workspace chat.

| Table | Essential columns and constraints |
| --- | --- |
| `conversations` | `id`, `authority_id`, `principal_id`, `next_seq`, `revision`, `created_at`, `archived_at`. Unique default global per authority/principal; no direct-conversation rows or workspace/session ownership |
| `conversation_messages` | `id`, `conversation_id`, `created_seq`, `role`, `origin` (typed/voice/agent/derived/system), `body`, `revision`, `status`, nullable `reply_to_id`, `source_ref_id`, `voice_session_id`, `client_message_id`, `created_at`. Unique `(conversation_id, client_message_id)` when provided |
| `conversation_events` | `(conversation_id, seq)` primary key, `event_id` unique, `type`, `schema_version`, `entity_id`, `entity_revision`, `payload`, `occurred_at`. Durable user-visible changes and action transitions; transient token/ASR deltas are not durable events |
| `conversation_runs` | `id`, `conversation_id`, `input_message_id`, `input_revision`, `status`, `generation`, `lease_owner`, `lease_until`, `context_manifest`, `model_config`, `usage`, `error`. One active leased generation per conversation; status covers pending/running/completed/interrupted/failed |
| `conversation_actions` | `id`, `run_id` nullable for explicitly authorised supervisor actions outside a model run, `conversation_id`, `origin_message_id`, `intent_kind`, `payload`, `payload_digest`, `state`, `route_evidence`, `authorisation_source`, `created_at`. Immutable authorised payload; corrections create new actions |
| `agent_deliveries` | `id`, nullable supervisor `action_id`, `source_kind` (supervisor/session/voice), `source_id`, `idempotency_key`, fully qualified target, `executor_config`, `target_revision`, `message`, `state`, `attempt_count`, `not_before`, `lease_generation`, nullable `execution_process_id`, `delivery_mode` (queue/steer), `steering_acknowledged_at`, `provider_receipt`, `error`. Unique `(source_kind, source_id, idempotency_key, target_session_key)`; shared session queue consumes these rows without requiring a supervisor action for direct sends |
| `conversation_confirmations` | `id`, `action_id`, `principal_id`, `payload_digest`, `action_revision`, `expires_at`, `state`, `answered_message_id`. Target revisions live in the immutable action payload; durable, one-use, compare-and-swap acceptance |
| `conversation_evidence` | `id`, typed source key (authority/session/process/turn/log entry or repo state), `source_revision`, `content_hash`, `availability`, `captured_at`, optional retained raw report. Unique source/revision; stable references, no arbitrary filesystem paths from callers |
| `conversation_message_evidence` | `(message_id, evidence_id)`, optional excerpt locator, `relationship` (summarised/quoted/supporting). Supports many reports per answer |
| `conversation_memory` | `id`, `principal_id`, scope kind/key, `claim_key`, `body`, `entity_refs`, `state` (proposed/active/superseded/retracted), `revision`, `supersedes_id`, `source_message_id`, `author_kind`, `confidence`, `valid_from`, `valid_until`. Partial uniqueness for one active revision per principal/scope/claim key |
| `conversation_context` | `conversation_id`, `revision`, `focus`, `topic_segment`, `summary`, `covered_through_seq`, `source_versions`, `invalidated_at`. Derived and rebuildable; never used as sole evidence |
| `conversation_read_cursors` | `(principal_id, conversation_id)`, `last_read_seq`, `last_reviewed_sources`, `updated_at`. Monotonic explicit acknowledgement; separate from existing `CodingAgentTurn.seen` |
| `voice_sessions` | `id`, `authority_id`, `principal_id`, `binding_kind` (supervisor/session), nullable `conversation_id`, nullable `session_id`, `provider`, `provider_call_id`, `voice_key`, `generation`, `state`, `transcript_cursor`, `started_at`, `ended_at`, `usage`, `retention_config`, `client_platform` (android/web), `client_instance_id`, `lease_expires_at`. Exactly one binding: supervisor conversation or existing session. Unique provider/call ID; never stores client access tokens |
| `voice_utterances` | `id`, `voice_session_id`, `provider_segment_key`, `revision`, `speaker`, `text`, `status`, audio offsets, nullable supervisor `message_id`, nullable `delivery_id` and existing agent response reference, `response_generation`, `delivery_state`. Unique segment key/revision; transport correlation only, not a parallel session history |

Workspace voice binds directly to the selected existing session. Finalised input
is delivered once through the session message path; its response remains in
existing agent history. Voice revisions/playback metadata live in voice tables,
not supervisor messages or an alternate workspace transcript. Supervisor memory
scopes never cause direct chat to read or write that memory. Existing
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

A durable supervisor mutation increments conversation sequence, updates its query row and
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

Workspace chat continues using existing execution/log streams. Workspace voice
status/caption events are scoped to `voice_session_id` and its generation; recovery
loads that transport state and existing session history, not supervisor replay.
Shared delivery updates feed existing session status paths; only supervisor-origin
deliveries also generate supervisor conversation activity events.

## Proposed HTTP surface

Mount local routes under the existing `/api` request boundary. Use existing
`ApiResponse<T>` conventions and generated Rust/TypeScript DTOs. IDs in URLs are
local to the selected authoritative backend; external references in payloads are
fully qualified. No client-to-model credentials or arbitrary tool execution API.

| Route | Behaviour |
| --- | --- |
| `POST /conversations/resolve` | Resolve/create the principal's global supervisor conversation; idempotent by unique keys |
| `GET /conversations` | Principal-owned history list; cursor pagination and text search |
| `GET /conversations/{id}` | Snapshot with last sequence, active run/action summaries and capability flags |
| `GET /conversations/{id}/messages?before_seq=&limit=` | Older messages and evidence/activity links; default 50, cap 200 |
| `GET /conversations/{id}/runs?before_seq=&limit=` | Implemented scoped reply-status projection, ordered by input sequence; default 50, cap 200; omits leases, context manifests and model configuration |
| `POST /conversations/{id}/messages` | `{client_message_id, body, origin, reply_to_id?, expected_focus_revision?, target?}`; 202 only after message plus pending supervisor run/action commit; returns stable IDs/sequence |
| `POST /conversations/{id}/messages/{mid}/corrections` | Creates a linked correction, preserving original authorisation evidence; never silently edits dispatched instructions |
| `GET /conversations/{id}/events/ws?after_seq=` | Replay/live contract above, using existing signed WebSocket mechanisms where applicable |
| `POST /conversation-runs/{id}/cancel` | Fences model generation; cancels only undispatched proposals, returns any already delivered actions |
| `GET /conversation-actions/{id}` | Exact payload/targets/receipts and evidence visible to its principal |
| `POST /conversation-actions/{id}/cancel` | Cancels pending deliveries via compare-and-swap; cannot unsend a successful steering message |
| `GET /conversations/{id}/confirmations` and `POST /conversations/{id}/confirmations/{confirmation_id}` | Read owned grants and submit an explicit decision with expected digest/revision; changed/expired grant returns conflict |
| `GET /conversations/{id}/actions/{action_id}` | Frozen instruction/recipients, safe delivery receipts and the latest dispatch block; no internal claim/lease fields |
| `GET /conversation-evidence/{id}` | Raw report or authorised paged artefact lookup; unavailable source is explicit |
| `GET/POST /conversation-memories` | Scoped list/search or explicit addition |
| `PATCH/DELETE /conversation-memories/{id}` | Revision-checked supersession/retraction, scope validation and cache invalidation |
| `POST /conversations/{id}/read` | Acknowledge displayed sequence and actually reviewed source coverage |
| `GET /voice/capabilities` and `GET /voice/voices` | Provider availability per client platform, native transport support and selectable voice previews, no credentials |
| `POST /conversations/{id}/voice-sessions` | Bind call to supervisor conversation and voice preference; short-lived platform-tagged client connection material |
| `POST /sessions/{id}/voice-sessions` | Bind voice to an existing authorised session; transcripts use existing follow-up/steering/queue semantics, with no supervisor run or conversation row |
| `GET /voice-sessions/{id}` and `/events/ws` | Authorised transport snapshot/events for either binding; caption revisions and playback metadata only |
| `POST /voice-sessions/{id}/heartbeat` | Renew bounded media ownership lease for authenticated client/generation; expired or fenced ownership cannot revive a call |
| `POST /voice-sessions/{id}/resume` and `/end` | Reconcile/reconnect or start a new media segment on the same supervisor conversation or existing agent session binding; idempotent end |

### Configured supervisor worker — implemented boundary

`services/conversation/openai.rs` implements the existing `ConversationModel`
interface; `runtime.rs` owns its lifecycle inside `LocalDeployment`. Workspace
messages do not call either module. The first adapter uses OpenAI Responses with
seven typed read tools and a structured final `{text, evidence_ids}` response. A
configured local deployment also supplies the action service/transport: this adds
`propose_agent_message` and `read_action`, and advertises `agent_actions` while the
consumer is ready. Deployments may omit the agent-action service; memory support
is a separate model capability.
The configured adapter also exposes `propose_memory_change` for scoped supervisor
knowledge, with its own tool-free intent assessment. Native-goal controls and
executor approvals remain unavailable as model tools. Workspace messages retain
their separate raw path.

Configuration is explicit and supervisor-specific:

| Setting | Meaning |
| --- | --- |
| `VK_SUPERVISOR_ENABLED=1` | Enable supervisor history and attempt to start its consumer |
| `VK_SUPERVISOR_MODEL_PROVIDER=openai` | Select the implemented hosted adapter |
| `VK_SUPERVISOR_MODEL` | Required API model identifier; choose a model supporting Responses, function calling and structured output; no paid model default |
| `VK_SUPERVISOR_API_KEY_FILE` | Required absolute regular file readable by the service; on Unix no group/other permissions; final-path symlinks rejected; maximum 4 KiB |
| `VK_SUPERVISOR_MAX_OUTPUT_TOKENS` | Optional per-request output ceiling, 256–8192, default 4096; this includes the provider's output accounting, not a sentence-length target |

Missing/invalid configuration leaves history readable and rejects new input.
Never borrow a coding executor's login or infer a funded provider from its model
selection. Configuration changes require the normal authorised service restart;
source implementation does not activate these settings or contact a provider.

The worker scans pending rows at startup, wakes after committed input and polls
for missed notifications every half second. SQLite leases arbitrate multiple
consumers. Readiness checks actual task/shutdown state. A rejected credential or
persistence failure stops acceptance; already pending work remains durable for
operator repair. Failed/interrupted turns are not automatically rerun. Normal
shutdown drops in-flight HTTP work and records failure; abrupt termination leaves
lease recovery to record interruption. An accepted-message retry returns the same
receipt even while the worker is unavailable; a new identity receives 503 and a
changed payload under an existing identity receives 409.

Requests use a fixed TLS endpoint, no redirects, no ambient proxy or automatic
HTTP retries, a ten-second connect timeout and sixty-second request timeout.
The existing worker bounds a turn to twelve model steps and two minutes. Input
and response bodies cap at 768 KiB and 1 MiB; retrieved tool data caps at 192 KiB
per turn, with a separate 256 KiB cap on temporary provider continuation items.
Each new instruction proposal may add one tool-free policy request within that
same time budget; exact duplicates in a turn reuse their assessment/action. Budget
for these requests as part of supervisor model cost. Token usage from decoded
responses and safe inference settings are recorded
against the run. Cancelled requests or invalid/lost responses can still incur
provider charges without known usage; reconcile those with provider accounting.
Provider error bodies, credentials and full requests do not enter logs/events.

VK reconstructs bounded history from SQLite. Requests set `store:false` and
`background:false`, without provider conversation IDs or `previous_response_id`.
Native function outputs are returned by call ID; reasoning items and incidental
assistant commentary are replayed only within that turn. They are neither visible
chat replies nor persistent/exported context. Only the final validated structured
reply and verified evidence links enter supervisor history. These wire choices
follow [function calling](https://developers.openai.com/api/docs/guides/function-calling)
and [stateless Responses guidance](https://developers.openai.com/api/docs/guides/migrate-to-responses)
(checked 2026-09-26).

`store:false` is not a promise of zero third-party retention. Declare the model
egress (selected history, scoped preferences and retrieved reports) in the settings
work; provider abuse-monitoring and caching rules still apply. Account-specific
retention and regional requirements must be checked before live use against the
[provider data controls](https://developers.openai.com/api/docs/guides/your-data).
Adapter replacement preserves VK storage, lifecycle, typed tools, safe errors and
evidence contracts; only transient provider items and HTTP serialization change.
Deterministic adapter/consumer tests do not certify live model behavior or speech
quality. The real-model corpus and funded provider configuration remain gates.

### Android call contract

The native client uses the same voice endpoints and history owners. Creation
includes `client_platform`, `client_instance_id` and a stable idempotency key;
unsupported platform/provider combinations fail before creating a billable call.
Connection material stays ephemeral in client memory. Retrying creation returns
the same binding or an explicit uncertain-creation state, not a second call.

Android owns its local Telecom handle and controls, mapped to VK voice-session
ID/generation; handles and endpoint observations are transport metadata, never
conversation messages or model tools. Voice snapshots expose connection state,
owner generation and disconnect reason. Platform call state, provider media state
and agent execution state remain distinct. Ending/hanging up is terminal for that
media generation, including across racing resume/heartbeat requests. A stopped
client cannot renew its lease; expiry reconciles/ends the provider session without
cancelling accepted agent work. Set a bounded lease (initial 60 seconds, heartbeats
every 15 seconds; measure on device), with a shorter local reconnect grace.
Device takeover fences the old generation and closes its native/media call.

Mute, audio routing and supported hold controls execute locally through Telecom
and its media adapter without a model round trip. Do not publish every endpoint
change into supervisor history. Existing authorization applies to the Android
client too; absence of a browser Origin header is not authentication. See
[native call integration](VK_CHAT_VOICE.md#android-client-and-native-call-integration).

Initial supervisor limits (existing workspace text limits remain unchanged):
64 KiB text per conversational message (attachments by existing
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

Extract reusable dispatch primitives from existing session follow-up/queue handlers.
Keep ordinary workspace callers on their existing APIs with the same behaviour;
no supervisor/model/memory dependency is introduced. Replace
the authoritative `DashMap` queue with persisted `agent_deliveries` (optionally an
in-memory cache), including existing callers through delivery source IDs, without
creating supervisor conversation/action rows for workspace messages. Do
not copy messages into both an independent supervisor queue and the old consumer.

Implemented action storage (`conversation/actions.rs`, migration
`20260926000005`) freezes message text, selected sessions, workspace identity,
repository relationships and full executor configuration. A trusted semantic
assessment of the current user request determines whether the message is
requested and consequential. This assessment is not an HTTP/tool argument supplied
by the proposing agent or an instruction taken from workspace reports. The
semantic assessment is now a distinct tool-free request to the configured model.
VK supplies the current user request, earlier user turns for explicit references,
selected entity-search/workspace-state results, and the frozen proposal. Raw agent
reports and durable preferences do not enter this assessment; names and routing
results remain data rather than policy instructions. The proposal tool accepts only
message text and session IDs, never its own approval/risk fields. Structured policy
output distinguishes ordinary, consequential, unclear and unsupported-control
requests, with an authorization judgment and retained explanation. Invalid/refused/
unavailable assessment cannot authorize delivery. Prompt version `supervisor-v4`,
assessment version `supervisor-message-assessment-v1` and known combined usage are
recorded. Real-model semantic/security evaluation remains a release gate.

The service dispatcher enforces runtime goal/approval gates before admission
and again before executing an owned steering attempt. Exact repeated proposals in
one user turn share an identity derived from the run, message and sorted recipients,
even if the model changes function-call IDs. An unfinished policy decision after a
stale-target failure is not presented as a human confirmation. Worker lease checks
fence cancelled assessment before dispatch.

Storage approves ordinary explicit messages without an additional question.
Consequential/unclear requests and inferred sets over five recipients receive a
principal-bound five-minute confirmation containing the exact payload digest and
action revision. Unsupported dedicated controls and unrequested instructions are
rejected, not converted into confirmable messages. Acceptance revalidates the
canonical targets, as does transfer into `agent_deliveries`; changing a model
configuration while retaining an old version string cannot pass validation.
Cancelled/failed/expired originating runs invalidate undispatched proposals.
Expiry also fences a previously accepted grant until delivery admission. Admission
commits all recipient rows together; a retry returns existing receipts and never
another permission to perform a steering RPC. Export/deletion include grants.

Direct and queued process creation now share transactional admission. The process,
repository snapshots and original coding prompt commit together before spawn.
Competing coding launches in one workspace cannot both observe it as idle. Direct
parallel setup and dev-server behavior is preserved; queued work requires the
workspace to finish its non-dev processes. A queued admission that loses to direct
work releases its claim without losing the message. The container explicitly
publishes the committed process/workspace state because SQLite hooks may fire
before another connection can read the new rows.

`conversation/dispatch.rs` connects approved action records to the shared queue
and exact-process steering primitive. It does not grant authorization or enable
model action tools. Preflight checks all recipients before transfer; later runtime
changes can reject individual recipients, preserving partial outcomes. Known
steering rejection is terminal; RPC/receipt uncertainty never falls back to queue.
Repeated action dispatch returns existing receipts, including after runtime changes.
The existing queue recovery scan reconciles action states and durable events when
receipt aggregates change; no additional scheduler or delivery loop is introduced.

Supervisor queue rows form isolated batches. Ordinary direct rows still collapse
into their existing ordered raw prompt, but cannot override an adjacent approved
supervisor message/configuration. Target identity, branch, repository relationships,
full executor selection and action authorization are checked before preparation,
inside atomic process admission, and immediately before external delivery. An
expired/cancelled or changed target cannot acquire a new execution through an old
proposal. This is snapshot checking, not a distributed transaction with an executor.
A transport attempt remains uncertain if VK loses its acknowledgement.

`dispatch_gate.rs` checks pending executor approvals across the workspace, capacity
ownership and workspace/session lifecycle. Active Codex sessions are read through
their exact owning app-server. For inactive sessions, the existing configured Codex
executor performs native `thread/goal/get` before `thread/resume`; no independent
probe process or progress-file guess is used. A null or complete native goal permits
ordinary follow-up. A paused, unknown, malformed or unreadable native state rejects
it; an active goal also respects its matching VK progress pause reason. Missing goal
API support therefore blocks supervisor follow-up with a recoverable diagnostic,
while existing direct workspace behavior is unchanged. No goal is created, reset
or resumed by these checks. Dedicated slash controls cannot be sent through this
message channel. Typed server-owned delivery provenance is separate from profile
and child environment overrides.

The global panel now presents consequential/unclear instructions for review with
exact text, workspace/session labels, links, expiry, and send/decline controls.
Confirmation and action events refresh the panel across clients. Acceptance binds
owner, digest and revision before dispatch; an interrupted acceptance can be retried
using the same grant. Stored delivery receipts remain readable after worker loss;
new acceptance waits for a ready action service. Known preflight blocks are durable
`action.blocked` events and appear in action details; uncertain RPCs retain their
receipts and are never blindly resent. Outcome report ingestion, real-model policy
review and real executor/capacity/approval acceptance remain release gates.
Deterministic protocol fixtures do not certify a live native session or remove
provider/device release gates.

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

For a running session use the shared durable steering wrapper only if supported.
The implemented `services::steering::steer` persists an attempt before calling
`ContainerService::try_steer_process` with the exact recorded execution ID. A
receipt with `delivery_mode = steer` and `steering_acknowledged_at` set represents
acknowledged steering; its execution may subsequently complete or fail without
erasing that acknowledgement. Replay must never select a replacement process.
Current Codex
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
existing session admission order across sources; supervisor sequence orders its
own inputs only. Keep individual provenance when existing
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
Supervisor ingestion references existing turns/logs by stable evidence keys; it
does not project a new direct history. Existing workspace rendering and prompt
history stay unchanged. Voice transport correlates accepted segments with existing
delivery/response IDs so retries cannot insert duplicate agent messages. Native
retry/reset makes an old process `dropped`;
record that supersession in evidence and exclude it from current-state summaries,
while retaining historical action records. Existing process normalisation and
attachment handling remain the raw view.

## Concurrency and failure semantics

- Supervisor text and finalised speech enter one supervisor sequence. Two
  clients may append concurrently;
  unique client IDs deduplicate retries. A reused ID with changed content is 409.
- Conversation model work uses one renewable lease/generation. A new utterance can
  interrupt generation; ignore late model tool proposals from the fenced generation.
  Already accepted actions remain visible and independently reconciled.
- Direct and global sends to the same agent use the same admission/queue boundary.
  Opposing instructions are not merged by a summary. The supervisor can clarify
  its own ambiguous intent; direct sends retain existing session behaviour.
- One active microphone owner per supervisor conversation or existing session
  binding. A second device requests takeover;
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

Direct text/voice never creates a conversation model run. A supervisor model outage
or missing model credential cannot block ordinary workspace interaction. Cancelling
workspace speech playback only stops audio; it does not cancel the coding-agent run.

### Conversational memory writes — implemented boundary

`propose_memory_change` accepts a scope, stable claim key, concise body, typed
entity references and an optional exact prior memory ID/revision. It cannot supply
its own source message, author, approval or active state. The worker binds the
proposal to the current user input. The configured adapter independently assesses
that input, earlier user references, bounded entity context, the selected prior
claim and the proposed change. Raw reports and unrelated preferences are excluded.
`remember` activates explicit standing instructions/corrections; `propose` records
an inferred claim without applying it; `clarify`/`decline` write nothing. Temporary
runtime facts, secrets and permission overrides are inappropriate memory. Actual
semantic judgments remain a real-model evaluation gate.

`put_run_memory` checks the current worker lease and source identity inside the
same SQLite writer transaction as scope validation/supersession. Cancellation
while assessment is running cannot persist a later preference. Exact repeated
proposals in a user turn recover the record without another assessment or revision.
Existing direct store edits retain their strict revision-conflict behavior.
The user source, scope, author/state and superseded revision remain durable; model
options record `supervisor-memory-assessment-v1`, and combined usage includes the
assessment. Active global/conversation preferences refresh in the current model
request and its version manifest after a change.

`search_memory` accepts an optional workspace and/or exact session; inconsistent
session/workspace pairs are rejected. It returns active `memories` and separately
labelled `proposed_memories` within bounded scoped retrieval. Pending claims never
enter active preferences; an explicit correction/acceptance can supersede their
exact revision. Project/repository/workspace/session knowledge stays in its
applicable context. Existing global settings show the records and support scoped
forgetting, which continues to fence stale in-flight context. Conversational
forgetting/rescoping and richer preference editing still need their own integrated
flows; the tool does not claim those capabilities. Raw workspace chat neither reads
nor writes any of these supervisor memories.

### Current attention retrieval — implemented boundary

`list_attention({workspace_id, offset})` scans up to twenty local sessions per
page, across active workspaces or one resolved workspace. It examines each
session, so a second agent is not hidden by the most recent workspace process.
The latest coding result excludes devservers and dropped processes. Output keeps
pending executor responses, failed/interrupted executions, unread successful
completions, capacity waiting, uncertain deliveries and paused native goals as
separate signals. None of unread completion, capacity waiting or an intentionally
paused goal proves that the user owes an answer. Read agent reports separately
for failed validation, questions expressed in prose and their rationale.

Configured deployment supplies the existing approvals/capacity/native-goal
projection through the action service; missing runtime is explicitly unknown.
Active native owners are inspected without starting/resuming a process. Runtime
calls have two-second bounds and at most four session observations run together.
A process finishing during its goal read is reported as changed, not still paused.
Inactive native goals and remote hosts are not inspected by this local tool.
Existing workspace seen flags and reports are never written. Names, repositories
and workspace links provide routing context without host paths or scripts.

The first page also reports this conversation's still-valid pending confirmations,
filtered by owner, live/completed origin run, exact action revision/digest, expiry
and optional workspace.
This is a live paged scan, not an atomic snapshot of the whole installation;
`next_offset` must be followed even when a quiet page has no attention items.
Truncation, observation start/end and coverage limits are explicit. Missing signals
cannot justify an installation-wide all-clear. The complete returned observation
is retained as `EvidenceSource::AttentionSnapshot`, hashed and linked through the
same evidence/reply/export/deletion path as reports. The global UI labels this as
an attention snapshot rather than an original agent report. Each later query
reads live state while earlier evidence remains reviewable. Source-review watermarks,
semantic report classification and completion subscriptions remain separate work.

## Spoken output contract

Supervisor response output identifies canonical message text, optional linked
speech-ready text, and visual evidence references separately. Speech text is
plain-English prose validated before TTS, not a serialised UI Markdown payload.
Store the planned speech reference/version and observed playback metadata in the
existing voice correlation model. A separate speech variant is produced by the
same supervisor run and cannot add actions or replace the canonical evidence.
Direct session playback references original response ranges plus skipped-range
metadata; it never writes a sanitised replacement agent message. See
[speech content policy](VK_CHAT_VOICE.md#speech-content-natural-plain-english).

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
restricted as described in [voice
security](VK_CHAT_VOICE.md#security-and-third-party-processing).
