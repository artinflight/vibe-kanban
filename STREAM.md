# STREAM.md

## Current scope

- Branch: `feature/unused-capacity`, from fork staging `9a2591916`.
- Worktree: `/mnt/vk-storage/codexusage-capacity/vk`.
- Objective: VK enforcement and integration for the approved CodexUsage unused
  daily capacity system. Configurable 21:00–04:00 scheduling, native same-goal
  suspension/resume, interactive priority, no earned resets or fresh-week spill.
- Current implementation: expiring execution permissions, independent systemd
  deadlines, native pause/interruption and offline failure tests.
- Remaining: authenticated controller, durable managed-goal/restart/queue gating,
  CU scheduling and owner controls, full cross-system acceptance and delivery.

See `VK_UNUSED_CAPACITY.md` and the latest `HANDOFF.md`. This branch is not live.
Production restart/cutover remains a separate final approval after preparation.
