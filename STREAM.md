# STREAM.md

## Stream Identifier

- Branch: `vk/1b5d-vk-chat-models`
- Repo:
  `/home/mcp/code/worktrees/1b5d-vk-chat-models/_vibe_kanban_repo`
- Base: local `staging`
- Working mode: VK Codex 5.6 Sol upgrade

## Objective

- Update VK's Codex runtime and model selector for the GPT-5.6 Codex model
  family, with Sol as the local default.

## In Scope

- Global Codex npm package used by `/home/mcp/.local/bin/codex`.
- Local VK Codex executor model list.
- VK isolated Codex home default model and reasoning effort.
- Generated shared TypeScript types and executor JSON schema.
- Focused validation for selector/config/runtime changes.

## Out of Scope

- Restarting or deploying the live `vibe-kanban.service`.
- Changing Codex account entitlements or ChatGPT plan state.
- Reworking dynamic model discovery from Codex itself.

## Current Status

- Updated global `@openai/codex` from `0.142.5` to `0.144.1`.
- Verified current official Codex guidance:
  - `gpt-5.6-sol` is the flagship GPT-5.6 model for complex coding and
    research work.
  - `gpt-5.6-terra` is the balanced everyday GPT-5.6 model.
  - `gpt-5.6-luna` is the fast, lower-cost GPT-5.6 model.
  - Max reasoning is documented as a higher-depth option when enabled.
- Updated the isolated VK Codex config to:
  - `model = "gpt-5.6-sol"`
  - `model_reasoning_effort = "xhigh"`
- Added `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` to VK's Codex
  model selector.
- Added Codex `max` reasoning support to the VK selector/config schema.
- Regenerated shared local TypeScript types and executor schemas.

## Validation

- `npm view @openai/codex version dist.tarball bin --json`
- `npm install -g @openai/codex@0.144.1`
- `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home /home/mcp/.local/bin/codex --version`
- `npm list -g @openai/codex --depth=0`
- `pnpm run generate-types`
- `pnpm run format`
- `cargo test -p executors codex --lib`

## Next Safe Steps

1. Commit the source-controlled changes.
2. Rebuild/restart VK through the normal deployment workflow before expecting
   the new selector entries in the live UI.
