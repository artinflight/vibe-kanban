# VK Chat Orchestration Layer — implementation

Active native goal: **get this built.** The user authorised implementation on
2026-09-26. The earlier documentation-only task is complete and its temporary
execution boundary has expired. No production deployment is authorised by this
feature implementation.

Branch `vk/d498-vk-chat-orchestr`; approved design at `04071ef42`, inspected source
baseline `2fd585ac30bfa75975f6319585e4a66bb684fdcf`. Work follows
[architecture](VK_CHAT_ARCHITECTURE.md), [contracts](VK_CHAT_CONTRACTS.md),
[voice](VK_CHAT_VOICE.md), [milestones](VK_CHAT_IMPLEMENTATION.md) and
[handoff](VK_CHAT_HANDOFF.md).

## Current implementation

Milestone 1 now has supervisor-only SQLite conversation/message/event/run storage,
action proposals, retained source evidence and scoped/versioned memory. Atomic
acceptance, replay, leases, fenced completion, export and revision-checked deletion
preserve existing raw workspace reports. A stable local installation principal
owns these records; relay requests are denied until explicit ownership mapping.
The opt-in API exposes history/replay, records, export/deletion and memory forgetting.
Message acceptance now follows a deployment-owned worker's readiness. Explicit
supervisor model/credential configuration is required; no live configuration has
been enabled for this branch.

The ordinary session queue now uses durable `agent_deliveries`, preserving existing
prompt projection and Codex steering behavior. Batch claims correlate process
creation in one transaction; recovery retries only unadmitted work, retains uncertain
outcomes, and reconciles capacity denial without losing newer messages. Runtime
supervisor dispatch/confirmations and executor integration acceptance remain.
Supervisor action storage now freezes the exact text, recipients and executor
configuration, binds consequential instructions to expiring owner confirmations,
and atomically transfers approved recipients into the shared ledger. Cancellation
fences undispatched proposals. Direct/queued process admission now shares a
transaction for process, repository snapshots and raw prompt, preventing concurrent
coding launches and orphan processes after prompt-write failure. Post-commit
publication preserves workspace events. Validation is recorded in HANDOFF.md.
The action dispatcher now joins those records to existing queue and exact-process
steering, with approval/capacity/native-goal gates and immutable target checks at
consumption. Supervisor rows remain isolated from ordinary direct batches. The
existing recovery scan publishes changed action outcomes. Inactive Codex goals are
checked in the configured executor before native resume; raw direct behavior stays
unchanged. The worker now proposes actions through a distinct user-intent assessment,
and the API/global panel provide bound confirmation and receipt recovery. Model
sending is available only when deployment supplies this action service and the
consumer is ready. Outcome evidence ingestion and live model/executor acceptance
remain.

The direct session steering route now records exact-process attempts and durable
acknowledgements; eight new DB-backed tests prove retry/crash boundaries. Current
regression passes 53 DB, 58 service, three Codex protocol, seven conversation API
and two queue-route tests. Unknown
acknowledgements never enter the queue. The dispatcher now consumes only the owned attempts returned by action admission;
model authorization and user confirmation interfaces now connect through the same
service. Deterministic API-to-dispatch coverage does not certify live executors.

Database validation now includes 53 passing tests covering additive legacy-history
migration, concurrent writers, restart/replay, evidence retention, scoped retrieval,
forgetting, deletion and rollback. API/delivery check status and commands are in
HANDOFF.md. The first global UI and configured supervisor adapter are implemented; live model/
provider validation, Android client and full integration acceptance remain open.

The global launcher/panel now lives above host-scoped navigation, with local-authority
history/replay, retry identity, raw-source drill-down, activity, memory forgetting,
export and deletion. Workspace text rendering stays unchanged. Seven API tests, seven
replay reducer tests, web-core/local-web typechecks and focused lint pass. Browser
fixture assets build, but Chromium cannot launch under the scheduled sandbox
(`shutdown: Operation not permitted`); no visual/accessibility acceptance is claimed.

The supervisor run engine and local read tools are now implemented against a
provider-neutral model contract. They enforce renewable leases, bounded tool
context, safe failures, source-linked atomic replies and cancellation. Initial ten
fake-model integration tests pass; the worker regression passed all 31 database
and 29 service tests. A configured OpenAI Responses adapter and startup consumer
are now connected. Stateless tool turns retain temporary provider items only in
memory; VK persists the final grounded reply, sources and token usage. The worker
recovers pending work, stops acceptance on rejected credentials, and never retries
failed/interrupted turns automatically. A receipt retry still works after worker
shutdown. Bounded reply-status APIs/UI make failures visible after reload; model
capabilities refresh while the panel is open. Live model acceptance, complete
project/attention projection and mutating action policy are still required.

## Next implementation

Connect trusted semantic policy, confirmation API/UI and supervisor dispatch to
the validated delivery primitives, including current goal/approval gates and
queued-target revalidation. The configured read-only model path is ready for live
evaluation once the funded model/account and credential file are supplied; keep
that gate distinct from deterministic tests.
The initial global UI and its generated API contracts are ready for integration. Complete shared dispatch integration
and its real execution-boundary acceptance alongside that work. Prepare the early
spoken-text corpus before live voice integration. Do not rework the tested storage
foundation without a concrete integration failure or missing acceptance outcome.
Android Telecom/car MMI, natural English speech, raw direct workspace chat and
provider-neutral voice remain requirements of the full native goal.

## Validation environment

Scheduled execution has restricted network and no provider calls. Rust dependencies
are available offline. Use `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target`,
`CARGO_INCREMENTAL=0`, `SQLX_OFFLINE=true`; TMPDIR points to the mounted SSD's
`/mnt/vk-storage/capacity-build-tmp`. `pnpm run format` completes Rust formatting
and frontend formatting now passes after an offline dependency install using an
SSD copy of the cached pnpm store. No live DB, service,
provider account or deployment was changed.
