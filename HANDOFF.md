# HANDOFF.md

## Pickup Note

- Branch: `vk/cc70-vk-errors`
- Worktree:
  `/home/mcp/code/worktrees/cc70-vk-errors/_vibe_kanban_repo`
- Current focus: VK local Codex resume/worktree error repair.
- Live deploy/restart status: none performed.

## What Changed This Session

- Restored missing Codex rollout/session files in VK's isolated Codex home from
  `/home/mcp/backups/vk-efficient-restore-20260603T004715Z/codex-home`.
- Removed a broken symlink at
  `/home/mcp/code/worktrees/3e23-fr-governance/hyroxready-app` that pointed to a
  deleted worktree path and blocked Git worktree creation.
- Added compatibility filtering in
  `crates/executors/src/executors/codex/jsonrpc.rs` for Codex app-server thread
  history responses.
- The filter applies to `thread/resume`, `thread/fork`, and `thread/read`
  responses and removes unknown `thread.turns[].items[]` variants such as
  `subAgentActivity` before deserializing into the pinned protocol structs.
- Added unit tests covering thread-response filtering and non-thread response
  preservation.

## Validation

- `cargo fmt --all --check` passed.
- `cargo test -p executors jsonrpc::tests` was attempted twice.
- `pnpm run format` was attempted.

## Validation Gaps / Failures

- `cargo test -p executors jsonrpc::tests` could not complete because the
  filesystem ran out of space building `codex-app-server-protocol`, even after
  cleaning this worktree's `target/`.
- `pnpm run format` fails at `packages/web-core` because `prettier` is not
  installed in this worktree.
- No live service build, deploy, restart, or VK retry smoke was performed.

## Next Safe Steps

1. Free disk space beyond the current roughly 3 GB available after `cargo clean`.
2. Rerun `cargo test -p executors jsonrpc::tests`.
3. Run the normal formatter/check baseline once dependencies are available.
4. Deploy/restart VK only through the normal VK deployment workflow and only
   after operator confirmation.
