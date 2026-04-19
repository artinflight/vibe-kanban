# STREAM.md

## Stream Identifier

- Branch: `vk/df84-vk-ops`
- Repo: `/home/mcp/code/worktrees/df84-vk-ops/_vibe_kanban_repo`
- Working mode: adopt the Ops Playbook baseline fully into this VK fork without breaking the local-only runtime

## Objective

- Finish the Ops Playbook adoption for this VK fork so task branches are validated locally before `staging`, then promoted safely toward upstream PRs.

## In Scope

- Repo-specific standards and adoption docs for the fork
- A repeatable local-instance QA checklist
- Root continuity updates needed to reflect the current branch and adopted model
- Governance-check updates needed to enforce the new doc baseline

## Out of Scope

- Reviving the old cloud-backed board model
- Depending on `api.vibekanban.com` for local board state
- Reworking unrelated product code or release workflows

## Stream-Specific Decisions

- `staging` remains the working base branch for normal development, but this implementation work is landing on `vk/df84-vk-ops`.
- The local install must keep `shared_api_base` disabled.
- The lean backup system is the default backup path; the full-state backup is the heavy fallback.
- The playbook adoption should specialize the baseline for VK rather than copying the standards repo verbatim.

## Relevant Files / Modules

- `AGENTS.md`
- `README.md`
- `REPO_IDENTITY.md`
- `STATE.md`
- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`
- `docs/audits/vibe-kanban-ops-audit.md`
- `docs/standards/*.md`
- `docs/adoption/*.md`
- `docs/operations/release-safety.md`
- `docs/operations/local-instance-qa-checklist.md`
- `docs/self-hosting/local-backup-recovery.mdx`
- `scripts/vk_lean_backup.py`
- `scripts/run_vk_lean_backup.sh`
- `scripts/vk_restore_lean_backup.py`
- `scripts/run_vk_restore_latest.sh`
- `scripts/check-ops-playbook.mjs`

## Current Status

- Confirmed:
  - hourly lean backup cron is installed
  - Desktop mirror copy is active
  - local issue creation works
  - local workspace creation/linking works
  - existing branch policy, freshness, and ops-governance checks already exist in the repo
- Pending:
  - add the missing repo-specific standards/adoption docs and QA checklist
  - align the continuity docs with the current task branch and adoption status
  - keep GitHub-side `staging` protection aligned with the documented model

## Risks / Regression Traps

- Confusing a docs-only adoption with actual enforcement if the governance check is not updated too
- Repointing the service back to cloud/shared API config while touching ops docs
- Leaving `STREAM.md` or `HANDOFF.md` pointing at `staging` after work now happens on task branches

## Next Safe Steps

1. Add the missing repo-specific standards and adoption docs.
2. Update the root continuity docs and ops-governance check.
3. Validate the docs/gov changes and record the remaining GitHub-side follow-up.
