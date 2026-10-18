# T63 Dot activity and dispatch attribution

Continue workspace `7db73dbd-3b5d-4c21-87f1-4924be648284` on
`vk/7db7-vk-project-dot-c`, reconciled with staging `85af54d3c`.
Scope: preserve completed Mark unread; retain active agents in Running with
independent explicit action/approval visibility; attribute verified dispatch notes
only to their target workspace while retaining genuine shared conversation.
[Combined implementation/release handoff](VK_DOT_ACTIVITY_ATTRIBUTION.md).

The exact combined package was explicitly approved and activated October18;
[the live receipt](VK_T63_ACTIVITY_ROLLOUT.md) records meaningful API/UI acceptance
and latest-data cutback. No merge or unrelated service/model/effort/routing change
is authorized. Staging/Preserve retain subsequent integration ownership.

Current protections/topic map: [STATE](STATE.md). Earlier branch histories are
retained in [STREAM history](STREAM_HISTORY_20261017.md), its archive manifest,
[sidebar preparation pickup](PROJECT_SIDEBAR_PICKUP_20261017.md) and
[deployment additions](T63_DEPLOYMENT_PICKUP_20261017.md).

Owner-requested follow-up: visible per-message timestamps use stored Unix seconds
and `America/Toronto` with full date/year and EST/EDT. This is a minimal UI-only
change with desktop/mobile history/update/DST tests; retain the current frontend
baseline and all unread, attention, attribution, Running and readability behavior.
Activation is authorized via the established pointer-only release; no restarts.
Timestamp source `fe8b50194` passed desktop/mobile issue/project DST/history/update
and state regressions; two bounded builds timed out. No timestamp activation or
sealed package exists. Existing readability baseline stays live; the release
owner needs an admitted build window. Exact CI is blocked by Staging freshness.
