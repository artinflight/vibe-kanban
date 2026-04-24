# HANDOFF.md

## What Changed This Session
- Wired workspace turn-completion notifications to reuse the final assistant summary metadata block.
- Added optional ntfy mirroring for completed/failed workspace turns via `ssh homelab docker exec ntfy ...` when `VK_NTFY_TOPIC` is set.
- Confirmed the live `vibe-kanban` user service environment now includes `VK_NTFY_TOPIC=vk-workspace-turns`.
- Confirmed the live systemd unit launches `/home/mcp/.local/bin/vibe-kanban-serve`, which shells into `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`.
- Confirmed the currently installed `vibe-kanban-server-cleanfix` binary does not yet contain the ntfy strings from this branch, so live notifications are not using the new code path yet.
- Completed a local `cargo build --release -p server` from this worktree, but the first direct binary swap attempt failed with `Text file busy` because the live service still had the installed binary open.
- The follow-up stop/copy/start deploy step was started but interrupted before completion, so the branch code is committed but not yet landed into the installed live server binary.

## What Is True Right Now

- The live local install is the source of truth.
- `/api/info` reports `shared_api_base: null`.
- The board/issue data now lives locally in `~/.local/share/vibe-kanban/db.v2.sqlite`.
- `staging` is the branch to use as the current repo base.
- Turn-completion notifications now extract `Label:: value` metadata lines from the stored coding-agent summary before notifying.
- The ntfy bridge defaults to SSH host `homelab` and container `ntfy`; set `VK_NTFY_TOPIC` to enable it, and optionally override with `VK_NTFY_SSH_HOST` / `VK_NTFY_CONTAINER`.
- The live topic currently configured for the local service is `vk-workspace-turns`.
- The local service is still running the installed binary at `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`, not a direct process from this worktree.
- End-to-end ntfy delivery is still blocked until that installed binary is replaced with the build from this branch and the service is restarted cleanly.

## Known Good Backups

- Lean restore latest:
  - `/home/mcp/backups/vk-lean-restore-latest`
  - `/home/mcp/backups/vk-lean-restore-latest.tar.gz`
- Matching Desktop mirror:
  - `Desktop/vk-backups/vk-lean-restore-latest.tar.gz`
- Larger full-state snapshot:
  - `/home/mcp/backups/vk-complete-state-20260418T205324Z`

## What The Next Agent Should Do

- Start new VK repo work from `staging`.
- Take the lean backup before risky schema/runtime changes if the hourly backup is not fresh enough for the task.
- Keep the local-only behavior intact unless there is an explicit reason to reintroduce remote/cloud functionality.
- Prefer verifying issue/workspace/project behavior through the live local API before assuming the UI is right.
- To finish the ntfy rollout, stop `vibe-kanban.service`, replace `/home/mcp/.local/bin/vibe-kanban-server-cleanfix` with the fresh `target/release/server` build from this branch, and start the service again.
- After the binary swap, run one real workspace turn and verify the subscriber receives the `vk-workspace-turns` notification with the workspace name plus compact summary metadata.
- Open or update the branch PR if more ntfy follow-up work is resumed later.

## What The Next Agent Must Not Do

- Do not re-enable `VK_SHARED_API_BASE` or `VK_SHARED_RELAY_API_BASE` for the local install.
- Do not claim a DB-only copy is a full backup.
- Do not wipe or replace the local DB without first taking a new lean restore backup.
- Do not assume missing PR badges mean the PR is unmerged; check the local `pull_requests` rows first.

## Verification Required Before Further Changes

- `curl -s http://127.0.0.1:4311/api/info` and confirm `shared_api_base` is `null`
- `git status --short --branch`
- Task-specific validation for any runtime or UI change

## Verification Status From This Session
- `cargo test -p services notification -- --nocapture` passed, including new metadata parsing tests.
- `ssh homelab docker exec ntfy ntfy publish --quiet --title 'VK ntfy smoke' --message 'workspace notification smoke test' <throwaway-topic>` exited `0`.
- `systemctl --user show vibe-kanban.service --property=Environment,ExecStart,ActiveState,SubState --no-pager` confirmed `VK_NTFY_TOPIC=vk-workspace-turns` and the installed launcher path.
- `strings /home/mcp/.local/bin/vibe-kanban-server-cleanfix | rg "VK_NTFY_TOPIC|failed to publish workspace completion to ntfy|notify_workspace_turn_completion|Workspace::"` returned no matches, confirming the live installed binary does not yet include the branch ntfy code.
- `cargo build --release -p server` completed successfully from this worktree.
- Direct binary replacement into `/home/mcp/.local/bin/vibe-kanban-server-cleanfix` initially failed with `Text file busy` while the service was still running.
- `pnpm run format` did not complete because `packages/web-core` could not find `prettier` in this worktree.

## Session Metadata

- Branch: `vk/7617-vk-wire-ntfy`
- Repo: `/home/mcp/code/worktrees/7617-vk-wire-ntfy/_vibe_kanban_repo`
- Focus: ntfy turn-completion notifications, live service topic wiring, and pending installed-binary rollout
