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

The supervisor has durable scoped history/messages/runs/replay, retained evidence,
versioned memory storage, export/deletion and a stable local operator identity.
The original workspace/session chat remains raw and independent. Relay requests
are denied until ownership mapping exists.

A configured model adapter and deployment-owned consumer perform bounded retrieval
and source-linked replies. The global launcher/panel provides history, replay,
activity, evidence and data controls. Typed message proposals now use a separate
user-intent assessment, exact-payload confirmation API/UI and the existing durable
agent delivery ledger. Ordinary authorized instructions do not require redundant
confirmation. Receipt retries do not resend, and uncertain steering does not fall
back to a queue. Live goal, capacity, approval and target checks guard delivery.
The policy/confirmation work from the previous turn is present in commit
`3b48fcc53`; it must not be reimplemented from older handoff entries.

The new supervisor attention tool reads active local sessions and current runtime
signals. Pending responses, failed/interrupted work, unread completion, capacity
waiting, uncertain delivery and paused goals stay distinct. Evidence snapshots
retain exact observed state. Queries leave raw workspace history and seen flags
unchanged. Coverage limitations and concurrent changes are explicit; inactive
native goals, report semantics and remote hosts need further integration.

## Remaining implementation

Finish memory mutation/scoping and source-review watermarks, semantic report
classification and completion subscriptions; extend project/remote context where
required by existing project navigation. Validate the configured routing/policy
and early speech corpus with a funded model. Browser/multi-client/accessibility
acceptance, real executor/capacity/approval acceptance, voice transport and provider
compatibility, native Android Telecom/car MMI, and release/restore checks remain.
No model/provider runtime is configured or deployed by this branch. Missing live
credentials does not block independent implementation work. Do not revisit the
completed storage foundation without a concrete integration gap.

## Validation environment

Use mounted SSD outputs: `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target`,
`CARGO_INCREMENTAL=0`, `SQLX_OFFLINE=true`, and SSD TMPDIR. Scheduled networking
and browser launches are restricted; do not equate fixture tests with live model,
provider or phone/car acceptance. Missing JavaScript dependencies were restored
from `/mnt/vk-storage/capacity-build-tmp/vk-chat-pnpm-store` offline.
Current commands/results and the next implementation step are in HANDOFF.md.
