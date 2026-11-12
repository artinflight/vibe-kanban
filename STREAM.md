# Recommend launch correction — 2026-11-12

Current isolated branch: `fix/autoswitch-recommend-advisory`; draft [PR #296](https://github.com/artinflight/vibe-kanban/pull/296) targets staging. Review
[the focused correction](VK_AUTOSWITCH_ADVISORY_FIX.md) for cause, exact scope,
16 delegation regressions, preserved guards and pending native validation.
The owner requires all workers, including writable ones. The source fix covers
both; the earlier read-only profile is an insufficient workaround, not adoption.
Ten additional Python checks pass. The installed embedded-child veto remains;
no universal no-restart override has been established. No backend restart,
live mutation or pilot execution in this correction. Provider work is separate.

## Inherited stream notes

# Active-goal specialist delegation

Branch: `fix/active-goal-specialist-delegation`, based on current `fork/staging`.

Resolve the NODEs rejection of an explicitly authorized specialist assignment
while keeping native goal ownership with the orchestrator. The source had a
blanket active-goal delegation ban, and the resumed native thread only exposed
`vk_goal_checkpoint`, not the required `vk_delegate` tool.

Bounded routed children may serve an active unbudgeted goal. Existing Vibe
specialist sessions may receive authorized bounded continuations through the
supported session tool when dynamic delegation is absent. Parent ownership,
review, result collection, capacity, routing and approval controls remain.
Explicit token budgets and scheduled capacity remain ineligible because native
root accounting excludes child usage. No live restart, production reassignment,
goal mutation, or NODEs rendering/device work is part of this fix.

Prior stream history: [STREAM history](STREAM_HISTORY_20261017.md) and
[previous record](deployment-history/20261030-before-reconciliation/STREAM.md).
