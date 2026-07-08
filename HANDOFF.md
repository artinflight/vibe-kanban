# HANDOFF.md

## Pickup Note

- Branch: `vk/1b5d-vk-chat-models`
- Worktree:
  `/home/mcp/code/worktrees/1b5d-vk-chat-models/_vibe_kanban_repo`
- Current focus: Codex model availability and default-model repair for local VK.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Verified current Codex model guidance from official OpenAI docs.
- Found VK's isolated Codex home was pinned to `gpt-5.4` with `high`
  reasoning, so VK's default Codex runs were not following the current Codex
  recommended default.
- Updated `/home/mcp/.local/share/vibe-kanban/codex-home/config.toml` to use:
  - `model = "gpt-5.5"`
  - `model_reasoning_effort = "xhigh"`
- Added the currently documented Codex choices missing from VK's Codex model
  selector:
  - `gpt-5.4-mini`
  - `gpt-5.3-codex-spark`

## Validation

- `cargo fmt --all --check`
- `cargo test -p executors codex --lib`
- `pnpm install --frozen-lockfile`
- `pnpm run format`
- `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home /home/mcp/.local/bin/codex --version`
- Confirmed the isolated Codex config begins with `gpt-5.5` / `xhigh`.

## Validation Gaps / Failures

- No live VK service rebuild, restart, or UI smoke was performed.
- Broader PR baseline checks such as `pnpm run check`, `pnpm run lint`, and
  `cargo test --workspace` were not run.

## Next Safe Steps

1. Deploy/restart only through the normal VK deployment workflow if the selector
   update should appear in the live UI.
