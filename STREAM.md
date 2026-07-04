# STREAM.md

## Stream Identifier

- Branch: `vk/1bd2-vk-archive-to-sa`
- Repo:
  `/home/mcp/code/worktrees/1bd2-vk-archive-to-sa/_vibe_kanban_repo`
- Base during rebase: local `staging` at `ad768e583`, which includes
  `fork/staging` at `89fb5724f` plus the multiline paste merge.
- Working mode: Archive completed local kanban workspaces to save disk space.

## Objective

- Reduce disk pressure from completed local kanban work by archiving linked
  workspaces when an issue enters the `Done` status, while keeping DB/session
  context available so a workspace can be recreated if reopened.

## In Scope

- Local compatibility issue update paths.
- Existing workspace archive/delete-worktree flow.
- Focused regression coverage for completion-status detection.
- Merge the rebased feature branch into local `staging`.

## Out of Scope

- Deleting chat/session history from the database.
- Compressing executor transcript JSONL files.
- Changing remote/cloud issue archive behavior.
- Restarting or deploying the live VK service.

## Current Status

- `crates/server/src/routes/local_compat.rs` now treats transitions into
  `Done`/`completed` as completion archive triggers, matching the existing
  `In Staging` archive behavior.
- Linked workspaces are archived through the existing container service, PR
  metadata is snapshotted before cleanup, and the physical worktree is deleted
  when no non-dev process is running.
- Existing resume context is preserved in SQLite session/process/turn rows; if
  a user opens the workspace again, the existing `ensure_container_exists`
  path can recreate the worktree and clear `worktree_deleted`.
- The feature branch is being rebased onto local `staging` before merge.

## Validation

- `pnpm run format` reached Rust formatting, then failed because `prettier` is
  not installed in this worktree.
- `git diff --check` passed before the rebase.
- `cargo test -p server local_compat::tests` did not reach test execution:
  linking the server test binary crashed with `ld terminated with signal 7
  [Bus error]` while the filesystem had less than 1 GiB free.
- After the failed test attempt, `cargo clean` removed `9.0GiB` from this
  worktree's build output and `/` recovered to about `9.3G` free.

## Next Safe Steps

1. Finish the rebase and merge into local `staging`.
2. Re-run `git diff --check`.
3. Install/restore frontend dev dependencies if full formatting is required.
4. Re-run `cargo test -p server local_compat::tests` after freeing more disk
   space or building on a less constrained machine.
5. Validate in a local VK instance by moving an issue with linked workspaces into
   `Done` and verifying the workspace remains listed as archived while its
   worktree is removed.
