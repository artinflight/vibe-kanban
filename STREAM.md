# STREAM.md

## Stream Identifier

- Branch: `staging`
- Repo:
  `/home/mcp/code/worktrees/a6c2-vk-multi-line-in/_vibe_kanban_repo`
- Working mode: VK staging integration branch

## Objective

- Keep `staging` as the integration branch for validated VK fixes before any
  production promotion.

## Current Status

- Local `staging` contains the multiline paste fix, archive-to-Done cleanup,
  and ntfy agent turn-completion notification work.
- `fork/staging` added the workspace chat replay stability fix from
  `vk/a8c5-vk-something-wro`.
- The current integration is merging `fork/staging` into local `staging` before
  rebasing and merging `vk/a5ed-vk-saved-message`.
- No live deploy, frontend symlink swap, service restart, or live DB mutation
  has been performed from this staging worktree.

## Validation

- Prior ntfy validation included:
  - `cargo fmt --all --check`
  - `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
  - `pnpm install --offline --frozen-lockfile`
  - `cargo test -p services notification::tests`
  - `pnpm run format`
- Prior chat replay validation included:
  - `pnpm install --offline --frozen-lockfile`
  - `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
  - `pnpm run format`

## Validation Gaps / Failures

- The chat replay test file was not run under Vitest because `vitest` is not
  installed as a project dependency.
- No live deploy or production restart has been performed for these staging
  integrations.

## Next Safe Steps

1. Finish merging `fork/staging` into local `staging`.
2. Rebase `vk/a5ed-vk-saved-message` onto local `staging`.
3. Merge `vk/a5ed-vk-saved-message` into local `staging`.
4. Run formatting and the narrow checks relevant to the final staging state.
