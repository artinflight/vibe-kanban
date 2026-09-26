# VK Chat Orchestration Layer

Branch `vk/d498-vk-chat-orchestr` records the persistent conversational layer design
based on source `2fd585ac30bfa75975f6319585e4a66bb684fdcf`.

Design entry: [VK_CHAT_ARCHITECTURE.md](VK_CHAT_ARCHITECTURE.md), with
[contracts](VK_CHAT_CONTRACTS.md), [voice](VK_CHAT_VOICE.md),
[implementation sequence](VK_CHAT_IMPLEMENTATION.md) and
[future implementation prompt](VK_CHAT_HANDOFF.md).

This completed task produced architecture and implementation handoff documentation.
It made no feature-code, runtime, deployment or external-provider changes. Future
implementation begins when the user sends the handoff instruction; the current
phase boundary does not constrain that implementation.

## September 26: Android calls, car MMI and spoken-language acceptance

All five VK_CHAT design documents now specify Android-first mobile voice through
Core-Telecom, screen-off operation and real phone/car MMI call-control acceptance.
The native provider transport must be proven early; Retell remains conditional on
that gate. Desktop web retains text/history and browser voice is secondary.
Supervisor speech is natural plain English, with technical material available
visually. An early real-model text-output evaluation gate precedes voice
integration. Raw workspace history/behaviour stays unchanged; optional direct
playback selects prose without a summarising model. The handoff includes both
requirements. No implementation, provider setup or runtime changes were made.

Validation: `pnpm run ops:check`, design links/anchors and `git diff --check`
passed. `pnpm run format` completed Rust formatting then failed because `prettier`
is unavailable; no feature source changed. Device/car behaviour and model output
are documented acceptance gates, not tested functionality. This revision is
uncommitted and unpushed; future implementation begins on explicit instruction.
