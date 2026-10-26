# Compact project Dot Chat header

The project sidebar shows the destination name once, a Project/Workspace scope
hint, Chat/Shared plan tabs, and one attention toolbar. Privacy, detailed scope,
refresh and disconnect live in the keyboard/touch-accessible conversation details
disclosure. Escape closes it and returns focus without closing the mobile sheet.
The disclosure overlays history, so opening it does not shrink the conversation.

This presentation mode applies only inside Projects, including embedded workspace
chat. Standalone workspace chat keeps its existing header. Destination lifetimes,
message/read/attention APIs, drafts, reply targets and delivery remain unchanged.
Long names retain ellipsis and full-name hover titles; message/composer text stays
16 px. Attention navigation stays visible even when there are no flags.

Validation uses the actual React sidebar with production CSS and synthetic-only
transport. The existing routing browser test checks 390/1440 layouts, a 160 px
header ceiling, at least 65% conversation/composer space, details keyboard/Escape,
zero/changing flags without writes, long names, draft/reply/reload retention and
exact in-flight destinations. The hosted frontend-only workflow retains screenshots
and a self-contained preview alongside its immutable frontend package.

Status: implementation and preview only. Focused synthetic project routing,
attention navigation and project-notice regressions passed locally. Exact hosted
layout/type/state receipts and operator preview are recorded separately. Not deployed.
No production pointer, backend, Dot service or agent changes are included.
