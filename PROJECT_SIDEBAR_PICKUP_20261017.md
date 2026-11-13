# Project Sidebar pickup additions retained during efficiency integration

These are verbatim dated notes from the Staging snapshot before PR266 adoption.
Current status is in VK_RELEASE_COORDINATION_20261017.md; dated draft/CI statements
below are historical.

## STATE.md additions

# Project collaboration sidebar — October 17 preparation

The local Projects sidebar is prepared on its feature branch, not deployed.
Private per-project Dot threads reuse existing sidechat delivery/unread/attention;
shared plan entries link canonical Vibe tasks and assignees without copying their
state. Adoption needs the separate Python sidechat/connector and combined frontend,
not a Rust Vibe backend release. Preserve live CU1.6 modules and current
Mobile/Steering/Dot/artifact behavior. See VK_PROJECT_COLLABORATION.md.


## STREAM.md additions

# Project collaboration sidebar — October 17

Branch `vk/7db7-vk-project-dot-c` starts at fork/staging `7110930b6`.
Scope: private project Dot Chat and shared checklist/milestone/decision/question
entries in Projects, canonical task/owner/workspace links, desktop/mobile and
current/future projects. Existing event/tool schemas and issue/agent notification
semantics remain. No CU module changes or production activation belong here.
VK Dev issue `1900eb48-bf48-4500-97fd-56eb5ae01a3e` is linked to this workspace.
Preserve Dot and Staging received contract/release handoffs. The separate Dot
service/connector release is required; no Rust backend source changed. Read
VK_PROJECT_COLLABORATION.md for validation, preview and integration limits.
[Draft PR267](https://github.com/artinflight/vibe-kanban/pull/267) is pushed, with implementation `f60c8d1d6b2c`.
Both real sidechat/branch UI browser cases pass; the published screenshot/status
report is linked in VK_PROJECT_COLLABORATION.md. Full CI remains running.
Older entries below describe other streams and do not define this branch.


## HANDOFF.md additions

# Project sidebar pickup — October 17

[Draft PR267](https://github.com/artinflight/vibe-kanban/pull/267) is pushed; implementation `f60c8d1d6b2c`.
[Open sidebar preview](https://vibe.local/vk-artifact-viewer.html?id=15bb5759-3ce8-4234-9081-7c524f4ac8e5&name=project-sidebar-review.html&v=1). Both viewport cases and the
published report pass; CI is running (policy/freshness/ops/66 sidechat tests green).

Feature branch `vk/7db7-vk-project-dot-c`, staging base `7110930b6`, issue
`1900eb48-bf48-4500-97fd-56eb5ae01a3e`. Read VK_PROJECT_COLLABORATION.md.
Source includes private project chat, shared plans with conflict/idempotency
handling, live canonical task/owner/workspace links and separate project Dot
badges. Tests use disposable sidechat state and block Vibe writes. No production
service/assets/private data were changed; normal issue/workspace tracking was
created. Preserve Dot confirmed compatibility; Staging owns coordinated adoption.
Keep complete project_collaboration.py bundle and live CU1.6 pins. Do not treat
this feature as included in frozen PR264 without explicit integration.
Rust workspace checks and post-adoption/physical-phone acceptance remain limits.

End of retained upstream additions.
