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

Milestone 1 started. Added SQLite supervisor conversation/message/event/run
storage and a scoped Rust repository with transactional input acceptance,
idempotent retry, paginated history, durable replay, serial worker leases,
renewal, cancellation and fenced completion. No workspace/session rows are copied
or rewritten. APIs, execution dispatch, UI and model workers are not wired yet.

Eight new conversation tests cover real additive migration, populated legacy
history preservation, concurrent acceptance, paging, rollback on injected failure,
restart and lease cancellation/expiry. The existing database suite also passes.
Exact final validation is recorded in HANDOFF.md. Full requirement completion is
not claimed: action/evidence/memory storage, delivery and remaining milestones
are still outstanding.

## Next implementation

Continue milestone 1: shared durable delivery and result correlation, installation
scope/auth mapping and API/replay integration. Add action/evidence storage and
reconciliation without changing existing Codex steering or raw workspace chat.
Prepare the early spoken-text corpus before connecting a real supervisor model.
Android Telecom/car MMI, natural English speech, raw direct workspace chat and
provider-neutral voice remain requirements. The native goal's fixed checklist
covers the complete implementation; it is not limited to this first slice.

## Validation environment

Scheduled execution has restricted network and no provider calls. Rust dependencies
are available offline. Use `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target`,
`CARGO_INCREMENTAL=0`, `SQLX_OFFLINE=true`; TMPDIR points to the mounted SSD's
`/mnt/vk-storage/capacity-build-tmp`. `pnpm run format` completes Rust formatting
but frontend formatting is blocked by missing `prettier`. No live DB, service,
provider account or deployment was changed.
