# HANDOFF.md

## Pickup Note

- Branch: `staging`
- Worktree:
  `/home/mcp/code/worktrees/a6c2-vk-multi-line-in/_vibe_kanban_repo`
- Current focus: staging integration of completed VK feature/fix branches.
- Live deploy/restart status: none performed from this worktree.

## What Is True Right Now

- Local `staging` was clean before merging `fork/staging`.
- `fork/staging` contributed the workspace chat replay stability fix:
  - `packages/web-core/src/shared/lib/streamJsonPatchEntries.ts`
  - `packages/web-core/src/shared/lib/streamJsonPatchEntries.test.ts`
- Local `staging` already contained:
  - multiline paste preservation in workspace creation
  - archive-to-Done linked workspace cleanup
  - ntfy agent turn-completion notification work
- The current operator request is to rebase and merge
  `vk/a5ed-vk-saved-message` into `staging`.

## Validation Known From Landed Streams

- Ntfy turn-completion stream:
  - `cargo fmt --all --check`
  - `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
  - `pnpm install --offline --frozen-lockfile`
  - `cargo test -p services notification::tests`
  - `pnpm run format`
- Chat replay stream:
  - `pnpm install --offline --frozen-lockfile`
  - `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
  - `pnpm run format`
- Saved messages stream:
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run format`
  - `pnpm --filter @vibe/ui run format:check`
  - `pnpm --filter @vibe/ui run check`
  - `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
  - `scripts/preview.sh verify`

## Validation Gaps / Failures

- No live production deploy or restart has been performed from this staging
  worktree.
- The chat replay Vitest command could not run because `vitest` is not a
  project dependency.

## Next Safe Steps

1. Finish the `fork/staging` merge.
2. Rebase `vk/a5ed-vk-saved-message` onto local `staging`.
3. Merge `vk/a5ed-vk-saved-message` into local `staging`.
4. Run final formatting and focused checks for the staging result.
