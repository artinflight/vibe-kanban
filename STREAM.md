# STREAM.md

## Stream Identifier

- Branch: `vk/1b5d-vk-chat-models`
- Repo:
  `/home/mcp/code/worktrees/1b5d-vk-chat-models/_vibe_kanban_repo`
- Base: local `staging`
- Working mode: VK Codex model availability and default-model repair

## Objective

- Bring VK's Codex model selector and isolated Codex default in line with the
  current Codex model guidance.

## In Scope

- Local VK Codex executor model list.
- VK isolated Codex home default model and reasoning effort.
- Focused validation for selector/config changes.

## Out of Scope

- Restarting or deploying the live `vibe-kanban.service`.
- Changing Codex account entitlements or ChatGPT plan state.
- Reworking dynamic model discovery from Codex itself.

## Current Status

- Verified current official Codex guidance:
  - `gpt-5.5` is the recommended Codex model for most tasks.
  - `gpt-5.4-mini` is recommended for lighter/faster coding tasks and
    subagents.
  - `gpt-5.3-codex-spark` is a research-preview model available to ChatGPT Pro
    subscribers for near-instant text-only coding iteration.
- Confirmed VK's isolated Codex config had been pinned to:
  - `model = "gpt-5.4"`
  - `model_reasoning_effort = "high"`
- Updated the isolated VK Codex config to:
  - `model = "gpt-5.5"`
  - `model_reasoning_effort = "xhigh"`
- Added `gpt-5.4-mini` and `gpt-5.3-codex-spark` to VK's Codex model selector.

## Validation

- `cargo fmt --all --check`
- `cargo test -p executors codex --lib`
- `pnpm install --frozen-lockfile`
- `pnpm run format`
- `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home /home/mcp/.local/bin/codex --version`
- Confirmed `/home/mcp/.local/share/vibe-kanban/codex-home/config.toml`
  now starts with `gpt-5.5` / `xhigh`.

## Next Safe Steps

1. Rebuild/restart VK through the normal deployment workflow before expecting
   the new selector entries in the UI.
