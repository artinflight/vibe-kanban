# STREAM.md

## Stream Identifier

- Branch: `vk/092b-vk-dev-self-deve`
- Repo:
  `/home/mcp/code/worktrees/092b-vk-dev-self-deve/_vibe_kanban_repo`
- Base: `fork/staging` at `91e2f9d1a`
- Working mode: VK self-development workflow hardening

## Objective

- Make Vibe Kanban development from inside Vibe Kanban safer and less
  ambiguous by documenting the clean feature/preview/release model, adding a
  generated-workspace guard, and adding a read-only live smoke script for
  deployment checks.

## In Scope

- Root-level operational docs for VK agent deployment and self-development.
- Required preview, backup, restart-ready staging, and post-restart verification
  workflows for VK agents.
- Source-controlled setup guard for generated VK development workspaces.
- Source-controlled read-only smoke checks for live local deployment invariants.
- Continuity notes for this branch.

## Out of Scope

- Restarting `vibe-kanban.service`.
- Switching the live frontend symlink.
- Deploying binaries or assets.
- Mutating live DB/project records from this source task.
- Reworking broader workspace creation, project settings UI, or lab runtime
  implementation beyond documenting the intended boundary.

## Stream-Specific Decisions

- The active development project is `VK Dev`; the old `vibe-kanban` project
  remains archived history.
- New VK development workspaces should use `/home/mcp/_vibe_kanban_repo` and
  target `staging`.
- Feature workspaces may prepare code, checks, preview, docs, and PRs.
- Feature workspaces must not restart or deploy the live VK service.
- Backend/runtime preview belongs in an isolated lab state, not live VK state.

## Relevant Files / Modules

- `VK_AGENT_DEPLOYMENT_RUNBOOK.md`
- `VK_SELF_DEVELOPMENT_WORKFLOW.md`
- `scripts/vk_selfdev_guard.sh`
- `scripts/vk_live_regression_smoke.py`
- `STATE.md`
- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`

## Current Status

- Added the deployment runbook and self-development workflow plan as new
  source-controlled docs.
- Added `scripts/vk_selfdev_guard.sh`, which verifies generated VK workspaces
  contain a real `_vibe_kanban_repo` git worktree on a branch based on
  `staging` and appends the feature/preview/release safety boundary to
  workspace-level `AGENTS.md` and `CLAUDE.md`.
- Added `scripts/vk_live_regression_smoke.py`, a read-only HTTPS smoke for
  local-only login state, project visibility, and built frontend assets.
- Expanded `VK_AGENT_DEPLOYMENT_RUNBOOK.md` so future agents have the full
  feature-prep, preview, lean Desktop-mirrored backup, restart-ready staging,
  and restart verification workflow in source control.
- Expanded `VK_SELF_DEVELOPMENT_WORKFLOW.md` so the VK Dev project model points
  agents to those required workflows instead of relying on chat history.
- Pinned CI `sqlx-cli` to `0.8.6` so schema checks match the repo's SQLx crate
  version and do not float to a Rust-1.94-only CLI release.
- No live deploy, frontend symlink swap, service restart, or live DB mutation
  has been performed in this branch session.

## Risks / Regression Traps

- The canonical checkout `/home/mcp/_vibe_kanban_repo` may be intentionally
  dirty; do not build or deploy from it just because it is canonical.
- Branch names in historical handoffs can be stale; trust the checked-out branch
  and code first.
- A workspace name that looks like VK work is not proof that the workspace
  contains the VK repo.
- `VK_AGENT_DEPLOYMENT_RUNBOOK.md` contains deploy instructions, but this branch
  does not grant permission to restart or deploy production VK.
- The smoke script is intentionally narrow and read-only. It does not replace
  UI/browser validation for a release candidate.

## Next Safe Steps

1. Run formatting and focused script validation.
2. Optionally run the live smoke script if `https://vibe.local` is reachable.
3. Create or inspect a throwaway `VK Dev` workspace to verify the guard runs in
   the generated workspace context.
4. Open a PR into `staging` after validation.
