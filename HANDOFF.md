# HANDOFF.md

## Pickup Note

- Branch: `vk/1b5d-vk-chat-models`
- Worktree:
  `/home/mcp/code/worktrees/1b5d-vk-chat-models/_vibe_kanban_repo`
- Current focus: Codex 5.6 Sol upgrade for local VK.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Updated global `@openai/codex` from `0.142.5` to `0.144.1`; this is the
  package backing `/home/mcp/.local/bin/codex`.
- Verified official Codex model docs list:
  - `gpt-5.6-sol`
  - `gpt-5.6-terra`
  - `gpt-5.6-luna`
  - Max reasoning as a higher-depth option when enabled.
- Updated `/home/mcp/.local/share/vibe-kanban/codex-home/config.toml` to use:
  - `model = "gpt-5.6-sol"`
  - `model_reasoning_effort = "xhigh"`
- Added the GPT-5.6 family to VK's Codex model selector:
  - `gpt-5.6-sol`
  - `gpt-5.6-terra`
  - `gpt-5.6-luna`
- Added Codex `max` reasoning support to the source enum/schema surface.
- Regenerated `shared/types.ts` and `shared/schemas/codex.json`.

## Validation

- `npm view @openai/codex version dist.tarball bin --json`
- `npm install -g @openai/codex@0.144.1`
- `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home /home/mcp/.local/bin/codex --version`
- `npm list -g @openai/codex --depth=0`
- `pnpm run generate-types`
- `pnpm run format`
- `cargo test -p executors codex --lib`

## Validation Gaps / Failures

- No live VK service rebuild, restart, or UI smoke was performed.
- Broader PR baseline checks such as `pnpm run check`, `pnpm run lint`, and
  `cargo test --workspace` were not run.

## Next Safe Steps

1. Commit the source-controlled changes.
2. Deploy/restart only through the normal VK deployment workflow if the selector
   update should appear in the live UI.
