# STREAM.md

## Current Scope

Branch fix/recovery-completion-boundary fixes repeated recovery injection after
completed summaries and records the running-standby requirements. No production
stop, cutover, database rewrite or standby-readiness claim is in this change.

## Current Maintenance Scope: September 11

Branch `docs/blue-readiness-20260911` records tested handover evidence and lessons
from online preparation. It contains documentation only. Green must remain usable;
production interruption or routing changes need a later explicit cutover approval.
The old stream identifier and deployment history below are historical context.

### Prior Integration Scope


## Current Stream: Attachment Preservation During Cutover

- Branch: `vk/4e18-cutover-attachment-safety`, based on `fork/staging` at
  `9dfd19c34`.
- Worktree: `/mnt/vk-storage/vk-blue-test-20260911/source`.
- Scope: add opt-in `DISABLE_ATTACHMENT_CLEANUP` so restart preparation can
  preserve attachment files and records while still allowing upload/retrieval.
- Reason: startup unconditionally deletes records without workspace links.
  Task-only references and unlinked uploads must not be deleted during cutover.
- Default behavior is unchanged. Orphan classification itself is not repaired
  by this flag. No production activation is implied by this source change.
- Prior autonomous-goal feature notes below describe the inherited baseline.

## Stream Identifier

- Branch: `vk/80a0-vk-continuation`
- Base: current `fork/staging` (`8c82e47ea` at investigation).
- Worktree: `/home/mcp/code/worktrees/80a0-vk-continuation/_vibe_kanban_repo`

## Objective

Enable outcome-directed autonomous continuation across this instance's projects,
using native Codex goals and durable progress evidence, with bounded refinement
and explicit return of control for completion or substantive user involvement.

## Scope and decisions

- Reuse installed Codex 0.153.4 native goals and scheduling; do not create a second
  scheduler or automate user messages saying continue.
- Preserve ordinary tasks and other executor behavior. Codex goal support is
  available globally through `/goal`; no repository configuration is required.
- Add a fixed supporting checklist, evidence, automatic recovery and a failed-recovery fallback
  under the instance's Codex home. Native goal objective/status remain authority.
- Root-only goal lifecycle handling, old-thread checkpoint compatibility, live
  steering registration, Stop persistence and focused/runtime regression coverage.
- No live backend restart or frontend switch in feature preparation. Follow
  `VK_AGENT_DEPLOYMENT_RUNBOOK.md` for the separate deployment gate.

## Validation and handoff

See `VK_AUTONOMOUS_GOALS.md` for behavior, tradeoffs and reproducible tests, and the
latest `HANDOFF.md` entry for exact validation and remaining deployment work.
