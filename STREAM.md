# STREAM.md

## Stream Identifier

- Branch: `vk/cc70-vk-errors`
- Repo:
  `/home/mcp/code/worktrees/cc70-vk-errors/_vibe_kanban_repo`
- Working mode: local VK runtime error repair

## Objective

- Make VK tolerate newer Codex app-server thread item variants when resuming,
  forking, or reading old threads.

## In Scope

- Codex JSON-RPC response decoding in the VK executor.
- Focused compatibility handling for known thread-history response shapes.
- Runtime-state cleanup needed to unblock local VK workspace operations.

## Out of Scope

- Broad Codex protocol dependency upgrades.
- Live deploy or `vibe-kanban.service` restart without explicit operator
  confirmation.
- Unrelated cleanup of old worktrees, archived projects, or frontend chat UI.

## Current Status

- Restored missing Codex rollout/session files from backup for old VK threads.
- Cleared a broken `hyroxready-app` symlink that blocked a VK worktree create.
- Added a JSON-RPC response sanitizer for `thread/resume`, `thread/fork`, and
  `thread/read` responses.
- The sanitizer drops unknown `thread.turns[].items[]` variants such as
  `subAgentActivity` before typed deserialization, preserving known entries.
- Added focused unit tests for dropping unknown thread items only on thread
  history responses.

## Validation

- `cargo fmt --all --check`
- `cargo test -p executors jsonrpc::tests` attempted twice but could not
  complete because the filesystem ran out of space while building
  `codex-app-server-protocol`.
- `pnpm run format` attempted, but failed because `prettier` is missing from
  this worktree.

## Next Safe Steps

1. Free enough disk space for a Rust build.
2. Rerun `cargo test -p executors jsonrpc::tests`.
3. If validation passes, build and deploy through the normal VK deployment
   workflow only after operator confirmation.
