# HANDOFF.md

## What Changed This Session

- Finished the repo-side Ops Playbook adoption for this VK fork.
- Added repo-specific standards for operating model, validation, continuity, and agent behavior.
- Added a VK-specific adoption doc and a repeatable local-instance QA checklist.
- Updated the root continuity and identity docs to reflect the adopted model and the active task branch.
- Tightened the ops-governance check so the new playbook artifacts are required.
- Tightened the agent rules again so completion summaries happen once per task, continuity docs are updated during the task, and PR work is expected when a branch is review-ready.
- Identified that canonical local `staging` has diverged from `fork/staging` and tightened the branch rules around exact sync.

## What Is True Right Now

- The live local install is the source of truth.
- `/api/info` reports `shared_api_base: null`.
- The board/issue data now lives locally in `~/.local/share/vibe-kanban/db.v2.sqlite`.
- `staging` is still the branch to use as the current repo base for new feature work.
- The canonical local `staging` checkout is currently ahead 5 and behind 3 relative to `fork/staging`.
- This stream's implementation branch is `vk/df84-vk-ops`.
- The repo now documents the full fork-specific Ops Playbook model, including local-instance QA expectations before `staging`.
- The repo also now documents that agents should not emit multiple final summaries for the same task and should treat doc updates plus PR handling as part of finishing the work.

## Known Good Backups

- Lean restore latest:
  - `/home/mcp/backups/vk-lean-restore-latest`
  - `/home/mcp/backups/vk-lean-restore-latest.tar.gz`
- Matching Desktop mirror:
  - `Desktop/vk-backups/vk-lean-restore-latest.tar.gz`
- Larger full-state snapshot:
  - `/home/mcp/backups/vk-complete-state-20260418T205324Z`

## What The Next Agent Should Do

- Start new normal VK repo work from `staging`.
- Repair the canonical local `staging` checkout before treating the branch model as healthy again.
- Use `docs/operations/local-instance-qa-checklist.md` before calling a branch ready for `staging`.
- Take the lean backup before risky schema/runtime changes if the hourly backup is not fresh enough for the task.
- Keep the local-only behavior intact unless there is an explicit reason to reintroduce remote/cloud functionality.
- Finish the GitHub-side setup if the remote fork still lacks a protected `staging` branch.
- Follow the one-summary-per-task rule even when the user asks for commit, push, or PR follow-up steps inside the same task.
- Use `git fetch fork origin --prune` plus `pnpm run ops:branch-sync` as the standing canonical-branch health check.

## What The Next Agent Must Not Do

- Do not re-enable `VK_SHARED_API_BASE` or `VK_SHARED_RELAY_API_BASE` for the local install.
- Do not claim a DB-only copy is a full backup.
- Do not wipe or replace the local DB without first taking a new lean restore backup.
- Do not assume missing PR badges mean the PR is unmerged; check the local `pull_requests` rows first.
- Do not treat the documented `staging` flow as fully enforced if GitHub branch protection has not been aligned yet.
- Do not put task-branch scope back into `STATE.md`.
- Do not leave doc updates or PR work undone once the branch is otherwise review-ready unless the blocker is stated clearly.
- Do not branch new work from a locally diverged canonical `staging` checkout.

## Verification Required Before Further Changes

- `curl -s http://127.0.0.1:4311/api/info` and confirm `shared_api_base` is `null`
- `git status --short --branch`
- `git fetch fork origin --prune`
- `pnpm run ops:branch-sync`
- `pnpm run ops:check`
- Task-specific validation for any runtime or UI change

## Verification Status From This Session

- Ops docs and governance changes were reviewed locally.
- The required ops-governance check should pass once the updated files are in place.
- No new runtime/UI behavior was changed in this session, so no fresh local app smoke test was required beyond preserving the existing local-only truth.
- The strengthened reporting and PR-execution rules still need a fresh `pnpm run ops:check` after these latest doc edits.
- Canonical branch sync currently fails because local `staging` is diverged from `fork/staging`.

## Session Metadata

- Branch: `vk/df84-vk-ops`
- Repo: `/home/mcp/code/worktrees/df84-vk-ops/_vibe_kanban_repo`
- Focus: finish Ops Playbook adoption for this fork without breaking local-only safety
