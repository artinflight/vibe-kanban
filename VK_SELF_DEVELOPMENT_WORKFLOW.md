# VK Self-Development Workflow Plan

## Status

- Created on 2026-06-26 after investigating why Vibe Kanban work inside Vibe
  Kanban has been unreliable.
- Phase 1 implementation started on 2026-06-26. Live DB project/repo settings
  were updated without a VK restart after row-level backups.
- No deploy, frontend symlink swap, or service restart was performed.
- Active project created: `VK Dev`
  (`1cf19067-4055-4432-bbc1-581919f9185d`).
- Tracking issue created: `VK Dev::Self-development workflow hardening`
  (`81312321-b5f5-4c13-ad1e-629b296d7bab`).
- Backup root:
  `/home/mcp/backups/vk-selfdev-config-20260626T131845Z`.

## Problem

Working on Vibe Kanban from inside the live Vibe Kanban instance is currently
too easy to confuse with operating the live instance itself. Feature work,
preview work, release preparation, and production deploy work have been mixed in
the same project/workspaces and sometimes in dirty or stale worktrees.

That creates four failure modes:

1. Agents make changes in an old task worktree and assume the canonical repo or
   live service changed.
2. Agents build or deploy from a dirty maintenance checkout and accidentally
   omit or roll back unrelated fixes.
3. Workspace creation can start from a stale or wrong repo/branch default.
4. Backend/restart work can interrupt the same live VK instance that is managing
   the agent.

## Current Findings

- The live `vibe-kanban` project exists but is archived.
- That project is linked to repo id `10d5e738-f1bd-4370-b6af-42835f988fe1`,
  path `/home/mcp/_vibe_kanban_repo`.
- The linked repo has no repo-level `default_target_branch`, no setup script, no
  dev-server script, and no default working-dir override.
- The project scratch defaults for `vibe-kanban` do target `staging`, but this
  lives in UI scratch state rather than the repo record, so it is weaker than a
  durable repo/project setup.
- Many VK-named workspaces are attached to the archived project and old task
  worktrees under `/home/mcp/code/worktrees/...`.
- At least one workspace named like VK work was not linked to the VK project and
  contained a different repo (`life-os`) in its workspace directory. Names alone
  are not a safe source of truth.
- The canonical checkout `/home/mcp/_vibe_kanban_repo` is intentionally dirty
  with ongoing operational/source changes, so it must not be used as a build or
  deploy source.
- Local `staging` and `fork/staging` currently differ. A future setup step must
  define which integration ref VK workspaces should use and keep the local
  branch current before creating workspaces.

## Target Model

Use VK as a task manager and feature-work launcher, not as the direct production
release actor.

The clean model is:

1. Active project: create a new active project such as `VK Dev` or unarchive and
   repair the existing `vibe-kanban` project.
2. Repo link: link exactly one repo, `/home/mcp/_vibe_kanban_repo`.
3. Default base: new normal workspaces start from the integration branch
   (`staging`, kept current with the chosen fork remote).
4. Feature work: VK agents work only in their generated workspace worktrees.
5. Preview: frontend changes use `pnpm run preview:light`; backend changes use
   an isolated lab runtime, not the production service.
6. Release: a separate release-prep step creates a clean candidate worktree,
   runs validation, writes a manifest, takes/validates backup when needed, and
   stops at operator approval before restart.
7. Production: frontend symlink swaps and backend restarts follow
   `VK_AGENT_DEPLOYMENT_RUNBOOK.md`; feature workspaces must not restart live VK.

## Required Project Configuration

Implemented phase 1:

- Created active VK development project `VK Dev`.
- Linked it to exactly one repo, `/home/mcp/_vibe_kanban_repo`.
- Set project display customization to abbreviation `VK` with a pastel color.
- Set project repo defaults to the VK repo and `staging`.
- Set the repo default target branch to `staging` so the UI does not fall back
  to `main`.
- Added repo setup guard `bash scripts/vk_selfdev_guard.sh`.
- Live repo setup command now uses the canonical absolute guard path:
  `bash /home/mcp/_vibe_kanban_repo/scripts/vk_selfdev_guard.sh`.
- Added repo dev-server script `pnpm run preview:light`.
- Added the required feature-prep, preview, backup, restart-ready staging, and
  post-restart verification workflow to `VK_AGENT_DEPLOYMENT_RUNBOOK.md`.
- Left the old `vibe-kanban` project archived as history.
- The guard now injects the workspace safety boundary into generated workspace
  `AGENTS.md` and `CLAUDE.md` files when it is missing, so normal prompts do
  not need to repeat deploy/restart/live-DB restrictions.

Still to implement or validate:

- Clear stale VK draft/default scratch rows that point to old feature branches,
  but only after backing up the rows being changed.
- Create a throwaway VK Dev workspace to prove the generated workspace contains
  `_vibe_kanban_repo`, targets `staging`, and runs the guard.
- Validate `pnpm run preview:light` from an actual generated VK Dev workspace.

## Preview Requirements

Frontend-only preview:

- Use `pnpm run preview:light`.
- It should proxy to the existing green backend on `127.0.0.1:4511`.
- Its dynamically allocated Tailscale Serve URL is tailnet-only. Use the
  approved `8443` Funnel workflow from the deployment runbook for public
  operator review.
- It must not start another backend watcher.
- Stop it with `pnpm run preview:light:stop` after review.
- Use `pnpm run preview:light:run` inside the VK preview panel when the preview
  should be bound to the panel process lifecycle.
- Exact preview commands, port overrides, and Tailscale notes live in
  `VK_AGENT_DEPLOYMENT_RUNBOOK.md`.

Backend/runtime preview:

- Use a separate lab state directory, not live state:
  `/home/mcp/.local/share/vibe-kanban-lab`.
- Use a separate Codex home, not live VK Codex state:
  `/home/mcp/.local/share/vibe-kanban-lab/codex-home`.
- Use separate ports from live VK.
- Do not point `vibe.local` at the lab.
- Do not use the lab to run production workspaces or active user agents.
- If real live data or a service restart is needed, stop and switch to the
  release/deploy workflow instead of treating it as feature preview.

## Feature Prep And Release Prep

Normal VK Dev agents prepare work. They do not release production.

Feature prep means:

- start from the `VK Dev` project
- use `_vibe_kanban_repo`
- base normal work on `staging`
- run the setup guard
- keep the branch scoped
- update docs/tests with code
- validate locally or with preview
- open a PR into `staging`

Release prep means:

- create a clean candidate worktree
- prove the candidate contains every intended fix
- prove it does not drop known live fixes
- build binary/assets before the restart window
- write the deploy manifest
- take and verify the lean Desktop-mirrored backup
- check active agents
- stop at "restart-ready" until the operator approves

The exact checklist lives in `VK_AGENT_DEPLOYMENT_RUNBOOK.md`.

## Backup Requirement

Before any operation that can affect live VK state, binary deployment, frontend
assets, or service continuity, use the lean restore backup:

```bash
./scripts/run_vk_lean_backup.sh
```

The backup must be mirrored to Desktop and the resulting path must be recorded
in the task handoff or deploy manifest before restart/deploy work proceeds.
See `docs/self-hosting/local-backup-recovery.mdx` for restore details.

## Release Boundaries

Feature workspaces may:

- edit source
- run focused checks
- run frontend preview
- update docs and handoff
- prepare a PR into `staging`

Feature workspaces must not:

- overwrite `/home/mcp/.local/bin/vibe-kanban-serve*`
- switch `/home/mcp/.local/share/vibe-kanban/frontend-dist/current`
- restart `vibe-kanban.service`
- modify live DB/project records without an explicit operational task
- prune live sessions, live Codex home, or registered worktrees

Release-prep work may only proceed after:

- current state is documented in `HANDOFF.md`, `STATE.md`, and `STREAM.md`
- the candidate is built from a clean worktree
- the manifest proves all current live fixes are included
- the lean restore backup has completed and mirrored to Desktop
- `scripts/vk_live_regression_smoke.py` is current for the intended live state
- active-agent checks are clear or the operator explicitly accepts interruption

## Implementation Plan

1. Done: backed up the current VK project/repo/scratch rows relevant to
   `vibe-kanban`.
2. Done: created a new `VK Dev` project and left the old `vibe-kanban` project
   archived as history.
3. Done: updated the chosen project/repo defaults:
   - repo path `/home/mcp/_vibe_kanban_repo`
   - base branch `staging`
   - status template matching the normal operator columns
4. Done: added a VK self-development setup guard script and wired it as the repo
   script for this project/repo.
5. Pending: add or harden an isolated lab runtime helper if one is not already
   reliable enough.
6. Done in source and immediate guard path: generated-workspace config content
   includes the feature/preview/release boundary, and the guard backfills that
   boundary into generated workspace files before the next backend deploy.
7. Pending: add smoke checks for:
   - active VK project appears exactly once
   - archived VK history does not pollute active left nav
   - new VK workspace selects the VK repo and integration branch by default
   - generated workspace contains `_vibe_kanban_repo`
   - `preview:light` starts without starting a backend watcher
8. Done: created a tracking issue in `VK Dev` for release/deploy work, with
   instructions that it may prepare but not restart without operator approval.

## Acceptance Criteria

- Done by DB/API validation: the active VK development project exists once as
  `VK Dev`.
- Done by DB/API validation: `VK Dev` repo defaults return the canonical VK repo
  with target branch `staging`.
- Pending UI/manual validation: creating an issue from that project defaults to
  the VK repo.
- Pending UI/manual validation: creating a workspace from that issue defaults to the approved integration
  branch, not `main` and not an old feature branch.
- Pending generated-workspace validation: the generated workspace includes
  `_vibe_kanban_repo/AGENTS.md`.
- A wrongly named workspace with a different repo is visibly not treated as VK
  work by the setup guard.
- Frontend preview works from a workspace without restarting live VK.
- Backend preview can run against isolated lab state.
- Release/deploy steps remain gated by backup, active-agent checks, manifest,
  smoke, and explicit operator approval.

## Open Decisions

- Resolved for phase 1: use a new active `VK Dev` project and keep old
  `vibe-kanban` history archived.
- Resolved for phase 1: use `staging` as the durable default branch. Still need
  a follow-up rule to keep local `staging` synchronized with the chosen fork
  remote before creating VK Dev workspaces.
- Whether release-prep should happen inside a VK workspace with strict guards or
  only from an external Codex/tmux operator session.
