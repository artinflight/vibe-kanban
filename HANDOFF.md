# HANDOFF.md

## Pickup Note

- Branch: `fix/multiline-paste-priority`
- Worktree: `/tmp/vk-paste-pr`
- Current focus: preserve multiline chat paste by running VK's paste guard
  before Lexical's default rich paste handler.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Changed `packages/ui/src/components/PasteMarkdownPlugin.tsx` so multiline
  `text/plain` wins before the `text/html` opt-out and is inserted with
  `selection.insertRawText(plainText)`.
- Changed the paste command registration from `COMMAND_PRIORITY_LOW` to
  `COMMAND_PRIORITY_HIGH` so Lexical's default rich paste handler cannot
  consume mobile/document clipboards before VK's multiline guard runs.
- Added a source regression check to `scripts/vk_live_regression_smoke.py` for
  the high-priority multiline paste handler.
- No live frontend asset swap, backend binary deploy, DB edit, or service
  restart was performed.

## Previous Staging Context

- Added `VK_AGENT_DEPLOYMENT_RUNBOOK.md` as a source-controlled pickup guide for
  agents working on VK from inside VK.
  - It now includes the required feature-prep workflow, lightweight/staging
    preview workflow, lean Desktop-mirrored backup workflow, restart-ready
    staging workflow, and post-restart verification sequence.
- Added `VK_SELF_DEVELOPMENT_WORKFLOW.md` to document the active `VK Dev`
  project model, feature/preview/release boundaries, pending validation, and
  acceptance criteria.
- Added `scripts/vk_selfdev_guard.sh`.
  - Verifies setup is running from a real `_vibe_kanban_repo` git worktree.
  - Verifies the repo has the expected VK docs and `vibe-kanban` remotes.
  - Appends a safety boundary to workspace-level `AGENTS.md` and `CLAUDE.md`.
  - Backfills `VK_SELF_DEVELOPMENT_WORKFLOW.md` and
    `VK_AGENT_DEPLOYMENT_RUNBOOK.md` from the canonical checkout when a
    staging-based generated workspace does not have them yet.
- Added `scripts/vk_live_regression_smoke.py`.
  - Checks local-only `/api/info` invariants.
  - Checks `VK Dev` appears once among active projects.
  - Checks the old `vibe-kanban` project is not active.
  - Checks the frontend index loads and references built assets.
- Pinned CI `sqlx-cli` installation to `0.8.6` to match repo SQLx crates and
  stop schema checks from floating to `sqlx-cli 0.9.0`, which currently requires
  a newer Rust compiler than the pinned workflow toolchain.
- Replaced stale branch-local continuity notes that referred to
  `vk/ea3c-vk-auto-archive`.

## What Is True Right Now

- This branch is rebased onto `fork/staging` at `91e2f9d1a`.
- Only source/docs changes have been made in this worktree.
- No binary install, frontend symlink swap, service restart, or live DB mutation
  has been performed by this session.
- The first real VK-created workspace setup failed because an earlier guard used
  `rg`, which was not available on the setup-script `PATH`. The guard now uses
  `grep`, and the setup rerun completed successfully.
- The docs say live phase-1 DB/project settings were changed earlier on
  2026-06-26, with backups under
  `/home/mcp/backups/vk-selfdev-config-20260626T131845Z`.
- The deployment docs now explicitly say VK feature agents prepare work and PRs;
  release/deploy agents separately build from a clean candidate, take the lean
  Desktop-mirrored backup, stage everything to restart-ready, and then stop
  until the operator approves the final restart.

## Validation So Far

- `pnpm install --offline --frozen-lockfile`
- `pnpm run format`
- `pnpm --filter @vibe/ui run check`
- `python3 -m py_compile scripts/vk_live_regression_smoke.py`
- `python3 scripts/vk_live_regression_smoke.py`
- `pnpm run ops:check`
- `git diff --check`
- `pnpm run check` partially passed through `local-web`, `remote-web`,
  `web-core`, and `ui` checks, then failed during backend workspace checking
  because the clean environment is missing system package metadata for
  `glib-2.0.pc` required by `glib-sys`.

## Prior Branch Validation

- `bash -n scripts/vk_selfdev_guard.sh`
- `python3 -m py_compile scripts/vk_live_regression_smoke.py`
- Temporary generated-workspace guard smoke:
  - created a temporary git worktree on a feature branch based on `staging`
  - ran `scripts/vk_selfdev_guard.sh` from the workspace root
  - verified the safety boundary appeared in generated `AGENTS.md` and
    `CLAUDE.md`
  - removed the temporary worktree and branch
- `pnpm run ops:check`
- `python3 scripts/vk_live_regression_smoke.py`
- `pnpm install --offline --frozen-lockfile`
- `pnpm run format`
- `pnpm run ops:check`
- Real VK setup rerun:
  - workspace `092bc4b8-600d-4591-ade7-df7ca49936fe`
  - process `2cbe7371-3345-4660-8298-aa2fd4f2a5db`
  - completed with exit code `0`

## Validation Gaps / Failures

- Full backend workspace check was blocked by missing `glib-2.0.pc` in the clean
  validation environment; this branch changes only frontend paste handling,
  smoke script, and docs.
- The real VK-created workspace setup has been exercised and repaired.
- `pnpm run preview:light` from an actual generated VK Dev workspace
- A real release/restart was not performed and should not be inferred from the
  docs updates.

## Next Safe Steps

- Validate `pnpm run preview:light` from that generated VK Dev workspace.
- Push/open a PR only after the operator confirms this branch should be promoted.

## Must Not Do

- Do not restart `vibe-kanban.service` from this feature workspace.
- Do not deploy binaries or switch frontend assets from this feature workspace.
- Do not mutate the live DB/project rows unless the user explicitly changes this
  into an operational repair task.
