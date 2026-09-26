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
Production message acceptance stays disabled until a real model worker is connected.

The ordinary session queue now uses durable `agent_deliveries`, preserving existing
prompt projection and Codex steering behavior. Batch claims correlate process
creation in one transaction; recovery retries only unadmitted work, retains uncertain
outcomes, and reconciles capacity denial without losing newer messages. Actual
supervisor action dispatch/confirmations and executor integration acceptance remain.

Database validation now includes 31 passing tests covering additive legacy-history
migration, concurrent writers, restart/replay, evidence retention, scoped retrieval,
forgetting, deletion and rollback. API/delivery check status and commands are in
HANDOFF.md. No UI, configured supervisor model, provider or Android client is delivered.

## Next implementation

Finish current API/type generation checks, then move to the global UI and the
configured supervisor worker/context/policy. Complete shared dispatch integration
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
