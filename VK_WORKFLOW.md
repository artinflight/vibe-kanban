# VK_WORKFLOW.md

## Canonical Paths

- Canonical Vibe Kanban source repo:
  - `/home/mcp/_vibe_kanban_repo`
- Live service wrapper:
  - `/home/mcp/.local/bin/vibe-kanban-serve`
- Live deployed binary:
  - `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - same current artifact is also installed at `/home/mcp/.local/bin/vibe-kanban-serve`
- Live VK state:
  - `/home/mcp/.local/share/vibe-kanban`
- VK-created workspaces/worktrees:
  - `/home/mcp/code/worktrees/...`

## What Is And Is Not Canonical

- The only canonical VK codebase is `/home/mcp/_vibe_kanban_repo`.
- `/home/mcp/code/worktrees/...` contains task-specific worktrees and agent workspaces, not the canonical product repo.
- `/home/mcp/code/vibe-kanban` does not exist and must not be treated as a real repo path.
- `/home/mcp/code/vibe-kanban-orchestrator` is a different repo.

## External Agent Rule

- If an external Codex agent is fixing Vibe Kanban itself, start it from:
  - `/home/mcp/_vibe_kanban_repo`
- Only start an agent inside `/home/mcp/code/worktrees/...` when the task is explicitly about a specific workspace or reproducing behavior inside that exact worktree.

## Deploy Model

Production does not run directly from the repo checkout.

The deploy flow is:

1. edit code in `/home/mcp/_vibe_kanban_repo`
2. build `/home/mcp/_vibe_kanban_repo/target/release/server`
3. copy that binary to both `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`
4. restart `vibe-kanban.service`

Implications:

- repo changes are not live until build + copy + restart happen
- merging to `staging` does not automatically deploy production
- merging to `main` does not automatically deploy production unless the built artifact is copied and the service is restarted
- worktrees are not production

## Branch Rules

- `staging` is the integration base for ongoing VK work
- `main` is the production branch and the only valid base for direct live hotfixes
- production changes should be deliberate, not accidental side effects of branch movement
- do not assume the currently running binary matches GitHub or even the current repo commit unless you verify it

## Hotfix Procedure

Use this path when you must change the live VK service before the normal
`staging -> main` promotion flow.

1. Start from the latest `origin/main`, not `staging`.
2. Create a dedicated `hotfix/<scope>` branch with the smallest possible scope.
3. Reproduce and validate the fix in an isolated local or detached deploy worktree.
4. Build and deploy from a clean worktree, never from a dirty canonical checkout.
5. Record the deployed commit, binary hash, and validation in `LIVE_DEPLOYMENT.json`.
6. Merge the hotfix into `main`.
7. Backfill the exact fix into `staging` immediately so future rebases do not lose it.

Rules:

- Do not bundle unrelated cleanup into a hotfix.
- Do not deploy directly from a feature branch or local-only rescue branch.
- Do not leave a live-only fix sitting outside both `main` and `staging`.
- Do not merge stale feature branches wholesale just because they contain a desired fix; port the minimal diff onto current `main` or `staging`.

## Feature Repair Guardrails

Recent failures had the same shape: a feature existed in git history or one local branch, but the live service either did not contain the latest fix or did not have durable data for the UI to render.

For every repaired VK feature:

1. Identify the exact deployed production asset or binary that should contain it.
2. Verify the fix from a clean worktree based on current `staging` or current `main` for direct hotfixes.
3. Check whether the feature depends on durable DB state, GitHub polling, route changes, or frontend-only cache invalidation.
4. Add a live verification step that proves the user-facing behavior, not just the code path.
5. Record whether rollout requires a backend restart or only a refreshable frontend asset swap.

Known current examples:

- Codeblock copy must be ported from the latest minimal reliability fix, not from stale `vk/codeblock-copy-20260429`.
- Local workspace rename must not depend on remote-owner equality when a local fallback workspace has a valid `local_workspace_id`.
- Issue PR details and merged-state badges need durable local `pull_requests` rows or a safe reconcile/backfill path while live PR monitoring remains disabled.
- Needs-attention workspace markers must clear for an already-open workspace, not only after route navigation.
- Attachment upload must never silently no-op. If a session is missing or upload fails, the composer must show the reason, and backend cache-file absence must produce a recoverable path or a clear error.

## Space Cleanup Guardrails

Freeing disk space is allowed only from an explicit cleanup list. Prefer rebuildable or low-continuity-risk data first:

1. Rust build outputs such as `/home/mcp/_vibe_kanban_repo/target`.
2. `node_modules` in archived copies or inactive worktrees after dirty-state checks.
3. Capped systemd journals.
4. Android emulator images only when Android testing is not immediately needed.

Continuity-sensitive paths require extra care and explicit approval:

- `/home/mcp/backups`
- `/home/mcp/.local/share/vibe-kanban/codex-home`
- `/home/mcp/.local/share/vibe-kanban/sessions`
- `/home/mcp/.codex/sessions`
- registered Git worktrees under `/home/mcp/code/worktrees`

Before removing any registered worktree, check for active VK agents and uncommitted changes. Before pruning backups or VK/Codex state, confirm a current valid backup exists and state the retention rule.

## Live Deploy Guardrails

The live service must keep the runtime env persisted in:

- `/home/mcp/.config/systemd/user/vibe-kanban.service.d/runtime-guardrails.conf`

Live production also uses refreshable frontend assets through:

- `/home/mcp/.config/systemd/user/vibe-kanban.service.d/frontend-dist.conf`
- `VK_FRONTEND_DIST_DIR=/home/mcp/.local/share/vibe-kanban/frontend-dist/current`

The refreshable frontend asset path has been active since the `2026-05-05`
restart. Once the running backend supports this env var, frontend-only changes
can be released by publishing a new `frontend-dist/releases/<timestamp>` folder,
repointing `frontend-dist/current`, and refreshing the browser.

Required settings:

- `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
- `DISABLE_WORKTREE_CLEANUP=1`
- `VK_DISABLE_PR_MONITOR=1`
- `VK_USE_SYSTEMD_RUN=1`
- `VK_TRANSIENT_MEMORY_HIGH=1500M`
- `VK_TRANSIENT_MEMORY_MAX=3000M`
- `VK_CODEX_BASE_COMMAND=/home/mcp/.local/bin/codex`
- `VK_ALLOWED_ORIGINS=https://vibe.local`

Run `pnpm run ops:live-runtime-guardrails` from a branch that contains the May 3 guardrail check before restart/deploy. If that script is not available on the current branch, manually verify `systemctl --user show vibe-kanban.service -p Environment` contains the settings above.

Before restarting `vibe-kanban.service`:

- check whether live coding agents are still running
- assume a restart will kill those runs
- either wait for them to finish or explicitly accept that interruption

Safe deploy rules:

- prefer deploying from a clean detached worktree rooted at the intended branch head
- do not deploy from `/home/mcp/_vibe_kanban_repo` when it is dirty
- verify `/api/info`, `/`, and the current `/assets/index-*.js` after every swap
- treat service restarts during active agent execution as destructive actions, not neutral maintenance
- if restart wedges in `deactivating`, back up the DB, wait briefly, then force-kill only the old VK main PID and let systemd respawn it
- if exact agent continuity matters, back up the VK DB, VK sessions, isolated VK Codex home, global Codex sessions/shell snapshots, systemd config, and deployed binaries before restart
- until the lean-backup archive path is hardened, use a manual directory backup fallback if Codex rollout files disappear during backup creation

## Agent Startup Checklist

Give every new VK-fixing agent these files first:

- `/home/mcp/_vibe_kanban_repo/HANDOFF.md`
- `/home/mcp/_vibe_kanban_repo/STATE.md`
- `/home/mcp/_vibe_kanban_repo/DELTA.md`
- `/home/mcp/_vibe_kanban_repo/VK_WORKFLOW.md`

Then tell the agent:

- canonical repo is `/home/mcp/_vibe_kanban_repo`
- do not treat `/home/mcp/code/worktrees/...` as canonical unless the task is workspace-specific
- production is copy-deployed from the built binary, not live-from-checkout
- do not touch tmux or unrelated Codex sessions

## Stable Working Model

- Source of truth for code: `/home/mcp/_vibe_kanban_repo`
- Source of truth for deployed runtime: `vibe-kanban.service` + `/home/mcp/.local/bin/vibe-kanban-serve-prod`
- Source of truth for live board data: `/home/mcp/.local/share/vibe-kanban/db.v2.sqlite`
- Source of truth for task-specific workspace state: `/home/mcp/code/worktrees/...`

If an agent is unclear which place to use, it should default to `/home/mcp/_vibe_kanban_repo` and only move to a worktree when the task explicitly requires it.
