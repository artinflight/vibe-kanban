# STREAM.md

## Stream Identifier

- Branch: `vk/c096-vk-agent-turn-no`
- Repo:
  `/home/mcp/code/worktrees/c096-vk-agent-turn-no/_vibe_kanban_repo`
- Base: local `staging`
- Working mode: VK local turn-completion notification wiring

## Objective

- Publish an ntfy notification when a VK coding agent turn reaches a terminal
  completed or failed state.

## In Scope

- Local VK server/runtime notification code.
- Existing ntfy env configuration already present in the live user systemd
  drop-ins.
- Focused Rust formatting and compile/test validation.

## Out of Scope

- Restarting or deploying the live `vibe-kanban.service`.
- Changing the Fly ntfy app, topic ACLs, or credentials.
- Frontend notification UI changes.

## Current Status

- Found existing live drop-ins under
  `/home/mcp/.config/systemd/user/vibe-kanban.service.d/`:
  - `turn-completion-ntfy.conf`
  - `ntfy-fly.conf`
  - `ntfy-topic.conf`
- Added env-backed ntfy publishing for coding-agent turn completion.
- Wired the publish call to the local execution monitor immediately after a
  coding-agent process reaches a terminal state and its summary is captured.
- Kept existing OS/browser workspace-complete notifications unchanged.
- Rebased this branch onto local `staging` for merge.
- Live ntfy ACL was separately updated so `vk-workspace-turns` can be read
  anonymously through `https://opntfy-mobile.fly.dev`; that operational change
  is not part of this repo commit.

## Validation

- `cargo fmt --all --check`
- `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
- `pnpm install --offline --frozen-lockfile`
- `cargo test -p services notification::tests`
- `pnpm run format`

## Next Safe Steps

1. Merge into `staging`.
2. Deploy/restart only through the normal VK deployment workflow.
