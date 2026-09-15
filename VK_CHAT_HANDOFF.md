# Future implementation prompt

Copy the following prompt to start development:

> Implement VK's persistent conversational orchestration layer. Read AGENTS.md,
> STATE.md, STREAM.md and HANDOFF.md, then VK_CHAT_ARCHITECTURE.md,
> VK_CHAT_CONTRACTS.md, VK_CHAT_VOICE.md and VK_CHAT_IMPLEMENTATION.md. Treat those
> design documents as the design source of truth unless repository reality has
> materially changed since baseline commit
> `2fd585ac30bfa75975f6319585e4a66bb684fdcf`. Reconcile relevant changes, then begin
> implementation; do not produce another architecture pass. Follow the documented
> milestones, starting with durable conversation storage and direct-session
> delivery, unless concrete repository evidence justifies adjusting the sequence.
> Deliver the global supervisor and direct workspace conversation with shared
> persistent text/voice history, scoped memory, grounded summaries and raw evidence,
> reliable routing/delivery, safeguards and replaceable voice infrastructure.
> Update the design when implementation decisions materially change it. Use fixtures
> while provider credentials are unavailable and identify the precise live-integration
> gates. Follow VK's validation, storage, preview and deployment rules. If I explicitly
> activate autonomous development, use VK's existing native goal/checkpoint mechanism
> for the full implementation objective; do not create another continuation loop.

Sending this prompt authorises feature development. Deployment and external
account/spend decisions follow the normal repository and user-authorisation rules.
