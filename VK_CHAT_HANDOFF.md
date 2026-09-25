# Future implementation prompt

Copy the following prompt to start development:

> Implement VK's persistent conversational orchestration layer. Read AGENTS.md,
> STATE.md, STREAM.md and HANDOFF.md, then VK_CHAT_ARCHITECTURE.md,
> VK_CHAT_CONTRACTS.md, VK_CHAT_VOICE.md and VK_CHAT_IMPLEMENTATION.md. Treat those
> design documents as the design source of truth unless repository reality has
> materially changed since baseline commit
> `2fd585ac30bfa75975f6319585e4a66bb684fdcf`. Reconcile relevant changes, then begin
> implementation; do not produce another architecture pass. Follow the documented
> milestones, starting with durable supervisor conversation storage and shared
> delivery to existing sessions, unless concrete repository evidence justifies
> adjusting the sequence.
> Deliver the global supervisor with persistent text/voice history, scoped memory,
> natural-language routing, cross-project coordination, attention reporting, clean
> summaries and raw-evidence drill-down. Preserve existing workspace/session text
> chat exactly as the raw direct coding-agent interface, including detailed reports,
> validation, controls and history. Workspace voice transcribes into that existing
> session message path; its raw response stays unchanged. Optional direct playback
> uses no second reasoning/summarisation model. Keep voice metadata separate, with
> no parallel direct conversation or supervisor memory applied to workspace chat.
> Reuse low-level dispatch and voice transport where sensible; supervisor behaviour
> belongs only to the global supervisor.
> Update the design when implementation decisions materially change it. Use fixtures
> while provider credentials are unavailable and identify the precise live-integration
> gates. Follow VK's validation, storage, preview and deployment rules. If I explicitly
> activate autonomous development, use VK's existing native goal/checkpoint mechanism
> for the full implementation objective; do not create another continuation loop.

Sending this prompt authorises feature development. Deployment and external
account/spend decisions follow the normal repository and user-authorisation rules.
