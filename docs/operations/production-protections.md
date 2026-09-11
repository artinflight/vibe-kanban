# Local Production Protections

Use the [release-safety guide](release-safety.md) and the repository's
`VK_AGENT_DEPLOYMENT_RUNBOOK.md` before changing a live instance. This document
integrates the earlier Production Protections concern with the current runtime;
historical commands naming retired blue are not deployment instructions.

## Protect The Authoritative Instance

- Discover the running service, executable, frontend, database and Codex home.
  Do not assume the canonical checkout or port 4311 is production.
- Keep feature tests isolated from live data, repositories, credentials, cleanup
  jobs and execution processes. Use the lightweight preview only when the running
  backend already supports the feature being tested.
- Do not restart services, replace binaries, switch frontend assets or mutate
  production state without operator authorisation for that operation.
- Keep releases immutable and validated. Do not deploy debug binaries or build
  a production frontend from a dirty maintenance checkout.
- Do not revive the retired `vibe-kanban.service`. A new blue candidate is a
  separately named service, not permission to reuse retired state.

## Preserve Work Across A Changeover

- Drain executions and queued work. Account honestly for interrupted executions;
  never mark them completed to make a readiness check pass.
- Allow only one backend to write authoritative state. Retaining old software
  does not make an old database a safe rollback target after new work is accepted.
- Preserve attachments, dirty/untracked files, Git metadata, native rollouts,
  indexes and all continuity databases, including `thread_history_*.sqlite`.
  Use SQLite-aware copies, not a raw live database/WAL copy as the restore source.
- Stage bulky backups on the mounted SSD and verify copies on Desktop
  `B:/vk-backups/`. Do not prune previous backups during deployment.
- Prevent automatic cleanup during a protected handover. The attachment guard
  `DISABLE_ATTACHMENT_CLEANUP=1` suppresses startup orphan deletion in supporting
  builds while leaving uploads and downloads available. Older builds do not
  recognise this flag. Worktree cleanup has separate guards in the runbook.
- Validate saved messages on desktop/mobile, original conversation reopening,
  attachments, workspace creation and actual served asset identity. A healthy
  process alone is not proof of recovery.

Keep unresolved historical recovery gaps visible. Do not fabricate replacement
threads, silently restore stale state, or describe a partial backup as complete.
