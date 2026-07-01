# HANDOFF.md

## Pickup Note

- Branch: `vk/c096-vk-agent-turn-no`
- Worktree:
  `/home/mcp/code/worktrees/c096-vk-agent-turn-no/_vibe_kanban_repo`
- Current focus: ntfy notifications for completed VK coding-agent turns.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Added ntfy turn-completion publishing in
  `crates/services/src/services/notification.rs`.
  - Reads `VK_TURN_COMPLETION_NTFY_URL`,
    `VK_TURN_COMPLETION_NTFY_TOPIC`,
    `VK_TURN_COMPLETION_NTFY_TOKEN`, and
    `VK_TURN_COMPLETION_NTFY_TIMEOUT_SECS`.
  - Falls back to `VK_NTFY_URL`, `VK_NTFY_TOPIC`, and `VK_NTFY_TOKEN`.
  - Publishes by HTTP POST to the configured ntfy topic.
  - Logs failures without failing execution finalization.
- Added focused tests for ntfy URL construction and env fallback selection.
- Added `notify_agent_turn_completion` to the shared container service logic.
- Called the ntfy turn notification from the local execution monitor after a
  coding-agent execution reaches `completed` or `failed` and after summary
  extraction.
- Rebased this branch onto local `staging` for merge.
- Separately granted anonymous read-only access for the live ntfy topic
  `vk-workspace-turns`, allowing mobile subscriptions through
  `https://opntfy-mobile.fly.dev`; anonymous publishing remains denied.

## Validation

- `cargo fmt --all --check`
- `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
- `pnpm install --offline --frozen-lockfile`
- `cargo test -p services notification::tests`
- `pnpm run format`

## Validation Gaps / Failures

- No live service restart or live turn smoke was performed.
- Broader PR baseline checks such as `pnpm run check`, `pnpm run lint`, and
  `cargo test --workspace` were not run.

## Next Safe Steps

1. Merge into `staging`.
2. Deploy/restart only through the normal VK deployment workflow.
