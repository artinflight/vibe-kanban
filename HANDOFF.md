# HANDOFF.md

## Pickup Note

- Branch: `vk/419a-vk-allow-follow`
- Worktree:
  `/home/mcp/code/worktrees/419a-vk-allow-follow/_vibe_kanban_repo`
- Current focus: active Codex follow-up injection for running VK coding-agent
  sessions, with queued follow-up fallback for unsupported executors.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Changed `QueuedMessageService` so queueing while a session already has a
  pending follow-up appends instead of replacing.
- Added `QueuedMessage.messages` to preserve every queued follow-up in order,
  while keeping `QueuedMessage.data` as the latest message for API compatibility
  and edit restore.
- Added `QueuedMessage::into_follow_up_data` to collapse multiple queued
  follow-ups into one ordered prompt for the next agent turn.
- Updated the local execution monitor to consume the collapsed queued prompt
  when starting the next follow-up.
- Regenerated `shared/types.ts`.
- Updated the local type generator to trim generated TypeScript line-end
  whitespace before writing `shared/types.ts`.
- Updated the chat hook and `SessionChatBox` so the UI can show how many
  messages are queued.
- Researched current Codex CLI behavior: Enter during a running turn injects
  instructions into the active turn, while Tab queues follow-up input for the
  next turn.
- Added a live Codex app-server client registry keyed by `execution_process.id`.
- Added active Codex follow-up injection: Vibe Kanban stores the message on the
  running client, sends Codex `turn/interrupt` for the active turn, and flushes
  the message as the next Codex turn after the interrupted or completed turn.
- Changed the queue endpoint to try active Codex injection before falling back
  to the existing queued-next-run behavior.
- Injected `VK_SESSION_ID` and `VK_EXECUTION_PROCESS_ID` into executor
  environments so running Codex clients can be addressed.
- Added focused unit tests for append and collapse behavior.
- Installed workspace dependencies offline to enable frontend formatting/checks.
- Freed disk space by deleting reproducible Rust `target/` build directories in
  old `_vibe_kanban_repo` worktrees after the first type-generation attempt hit
  `No space left on device`.

## Validation

- `pnpm install --offline --frozen-lockfile`
- `pnpm run generate-types`
- `pnpm run generate-types:check`
- `cargo test -p services queued_message`
- `pnpm run format`
- `git diff --check`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run check`
- `cargo check -p services -p local-deployment`
- `cargo check -p executors -p services -p local-deployment -p server`

## Validation Gaps / Failures

- Initial `pnpm run generate-types` failed with `No space left on device`; fixed
  by removing old reproducible build artifacts and reran successfully.
- Plain `pnpm run check` failed in `local-web:check` with Node heap OOM; reran
  with `NODE_OPTIONS=--max-old-space-size=4096`.
- The enlarged-heap `pnpm run check` passed frontend checks, then failed in
  `backend:check` because the environment lacks system `glib-2.0.pc`.
- No live service restart, deployment, or browser smoke was performed.

## Next Safe Steps

1. Optionally smoke the running-chat follow-up injection path in a local preview.
2. If a full workspace backend check is required, install/provide `glib-2.0.pc`
   or run in an environment that already has it.
3. Deploy/restart only through the normal VK deployment workflow.
