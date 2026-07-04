# HANDOFF.md

## Pickup Note

- Branch: `vk/1bd2-vk-archive-to-sa`
- Worktree:
  `/home/mcp/code/worktrees/1bd2-vk-archive-to-sa/_vibe_kanban_repo`
- Current focus: archive linked local workspaces when issues enter `Done`; the
  rebased feature has been merged into local `staging`.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Updated `crates/server/src/routes/local_compat.rs`.
- Added `is_done_status` for `Done`/`completed` status aliases.
- Generalized the linked-workspace archive helper so it applies to completed
  issue statuses, not only `In Staging`.
- Updated single and bulk local issue update flows to snapshot PR metadata and
  archive/delete linked worktrees when an issue newly enters `Done`.
- Added a unit test for completion-status alias detection.
- Replaced stale branch-local continuity notes from older streams.

## What Is True Right Now

- Workspaces linked to completed local issues keep their SQLite metadata,
  sessions, processes, turns, and PR metadata.
- The physical git worktree is removed through the existing safe archive path
  once no non-dev process is running.
- Reopening an archived workspace can recreate the worktree through the existing
  `ensure_container_exists` flow.
- The feature branch was rebased onto local `staging`, which is ahead of
  `fork/staging` with the multiline paste merge.
- Local `staging` now includes merge commit
  `a8aaa4afd Merge archive-to-Done workspace cleanup into staging`.
- No live VK service restart, binary deploy, frontend symlink swap, or live DB
  mutation was performed.

## Validation So Far

- `pnpm run format` ran Rust formatting, then failed at frontend formatting
  because `prettier` is missing.
- `git diff --check` passed before the rebase.
- `cargo test -p server local_compat::tests` failed before running tests because
  linking crashed with `ld terminated with signal 7 [Bus error]` while `/` was
  effectively full.
- `cargo clean` removed `9.0GiB`; `/` then showed about `9.3G` free.
- After the staging merge, `pnpm run format` passed from the local `staging`
  worktree.
- After the staging merge, `git diff --check HEAD^..HEAD` passed.

## Validation Gaps / Failures

- Focused Rust tests still need a successful rerun after more disk is available.
- No local VK UI/API smoke has been run for moving a linked issue into `Done`.

## Next Safe Steps

1. Re-run `cargo test -p server local_compat::tests` after freeing enough disk
   for server test linking.
2. Smoke the behavior in VK by moving a linked issue into `Done` and checking the
   workspace becomes archived with `worktree_deleted = true`.
3. Push `staging` only if the operator asks for remote publication.

## Must Not Do

- Do not restart or deploy the live VK service from this feature workspace
  without explicit operator approval.
- Do not delete DB chat/session history as part of this branch.
