# STATE.md

## Current Objective

- Keep the local Vibe Kanban install stable, local-only, and recoverable while the repo follows a durable Ops Playbook model for branch validation and upstream promotion.

## Confirmed Current State

- Local runtime is active and serving from the rebuilt local binary.
- `/api/info` reports `shared_api_base: null`.
- The imported cloud project/issue data has been brought into the local DB.
- The `vibe-kanban` project can currently create issues and create/link workspaces successfully.
- `staging` is the correct repo base for new VK development.
- The canonical local `staging` checkout is currently diverged from `fork/staging` and must be repaired before the branch model can be treated as healthy again.
- The repo now has repo-specific Ops Playbook standards, adoption guidance, and a repeatable local-instance QA checklist in addition to the root continuity docs.
- The repo now explicitly requires one final completion summary per task, current continuity-doc updates during the task, and PR creation or update when a branch is review-ready unless blocked.

## In Progress

- Normal project work can resume. No recovery-only blocker remains for issue/workspace creation in the `vibe-kanban` project.
- The remaining activation gaps are:
  - GitHub branch protection and the remote `staging` branch need to match the documented model
  - the canonical local `staging` checkout must be brought back into exact sync with `fork/staging`

## Proposed / Not Adopted

- Reintroducing remote/shared cloud-backed board behavior.
- Treating GitHub-only state as a substitute for VK local-state backups.

## Known Gaps / Blockers / Deferred

- Some historic board metadata can only be recovered if it existed in the cloud export or local DB snapshots; completely empty lost custom columns cannot be inferred safely.
- The local fallback pull-request endpoint still returns project-wide PR data and should be narrowed by `issue_id` in a future cleanup pass.

## Relevant Files / Modules

- `HANDOFF.md`
- `STATE.md`
- `STREAM.md`
- `DELTA.md`
- `docs/standards/operating-model.md`
- `docs/standards/validation-and-automation.md`
- `docs/standards/documentation-and-continuity.md`
- `docs/standards/agent-rules.md`
- `docs/adoption/vibe-kanban-ops-adoption.md`
- `docs/operations/local-instance-qa-checklist.md`
- `docs/self-hosting/local-backup-recovery.mdx`
- `scripts/vk_lean_backup.py`
- `scripts/run_vk_lean_backup.sh`
- `scripts/vk_restore_lean_backup.py`
- `scripts/run_vk_restore_latest.sh`
- `packages/ui/src/components/IssueWorkspaceCard.tsx`

## Decisions Currently In Force

- Operate VK in local-only mode.
- Use the lean backup + Desktop mirror as the standard recovery path.
- Start new repo work from `staging`.
- Treat canonical local `staging` as a mirror of `fork/staging`, not as a place for local-only commits.
- Require local-instance validation before promoting normal task work into `staging`.
- Preserve the existing CI and release workflows while layering Ops Playbook governance on top.
- Treat doc upkeep and PR handling as part of task completion, not optional aftercare.
- Treat the local DB plus GitHub state as the combined restore source, not the old cloud.

## Risks / Regression Traps

- Reintroducing shared API env vars will put the install back into a mixed local/remote state.
- Deleting or replacing the local DB without a fresh backup will break the current restore guarantee.
- UI changes that hide PR badges or issue/workspace links can look like data loss even when the DB is correct.
- Treating the documented `staging` flow as fully enforced before GitHub branch protection is aligned would create a false sense of safety.
- Branching new work from a locally diverged `staging` checkout will fork the integration history and make promotion harder to trust.

## Next Safe Steps

1. Continue feature work from `staging`.
2. Let the hourly lean backup cron keep running, or trigger a manual backup before risky work.
3. If a future agent touches project/workspace linking, verify through the live API and the UI before merging.
4. Align the remote fork's GitHub branch protection with the documented `staging` to `main` promotion path.
5. Repair the canonical local `staging` checkout so it exactly matches `fork/staging`, then use `pnpm run ops:branch-sync` as the standing verification step.
