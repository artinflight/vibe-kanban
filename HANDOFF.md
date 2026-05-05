# HANDOFF.md

## What Changed This Session

- Stopped `permission_policy` from falling back to the latest completed agent
  process config in `useExecutorConfig`.
- Kept current draft scratch and current user selections authoritative, so an
  explicitly selected Plan Mode still applies to that draft.
- Refreshed stale branch-local continuity notes that previously described a
  different branch.

## What Is True Right Now

- Branch: `vk/93f4-vk-stop-defaulti`
- Worktree: `/home/mcp/code/worktrees/93f4-vk-stop-defaulti/_vibe_kanban_repo`
- Changed code file:
  - `packages/web-core/src/shared/hooks/useExecutorConfig.ts`
- Changed continuity files:
  - `STREAM.md`
  - `HANDOFF.md`

## Validation

- `pnpm i`
- `pnpm run format`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`

## Notes

- A first `pnpm run format` attempt failed before dependency install because
  `prettier` was not available.
- A first `pnpm --filter @vibe/web-core run check` attempt failed with Node's
  default heap limit; the same check passed with a larger heap.

## What The Next Agent Should Do

- UI smoke-test the exact flow: start an agent in Plan Mode, then open a new
  agent composer and confirm it defaults to Auto.
- Run broader repo checks before opening or updating a PR into `staging`.

## What The Next Agent Must Not Do

- Do not reintroduce `permission_policy` as a last-used fallback.
- Do not remove scratch fallback for `permission_policy`; that would break
  explicit selections preserved in an unsent draft.
