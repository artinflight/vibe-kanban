# STREAM.md

## Stream Identifier

- Branch: `vk/419a-vk-allow-follow`
- Repo:
  `/home/mcp/code/worktrees/419a-vk-allow-follow/_vibe_kanban_repo`
- Base: local `staging`
- Working mode: VK queued agent follow-ups

## Objective

- Allow users to send follow-up messages while a coding-agent turn is still
  running, without stopping or interrupting that running process.

## In Scope

- Local session follow-up queue behavior.
- Local execution monitor handoff from completed agent turn to queued follow-up.
- Chat UI queue status for pending follow-ups.
- Generated local shared TypeScript types.

## Out of Scope

- Live `vibe-kanban.service` restart or deployment.
- Remote/cloud queue persistence.
- Changing executor protocols to inject into an active process mid-turn.

## Current Status

- Queueing a follow-up for a running session now appends to the session queue
  instead of replacing the previous queued message.
- When the current agent turn is ready to hand off, queued messages are collapsed
  into one ordered follow-up prompt and started as the next coding-agent turn.
- Existing `data` remains in the queue API response as the most recent queued
  message for compatibility and edit restore.
- The queue API response now also includes `messages` with all pending
  follow-ups in order.
- The chat UI displays a queued message count when more than one follow-up is
  waiting.
- The local type generator now trims line-end whitespace before writing
  `shared/types.ts`, so generated type changes pass whitespace checks.

## Validation

- `pnpm install --offline --frozen-lockfile`
- `pnpm run generate-types`
- `pnpm run generate-types:check`
- `cargo test -p services queued_message`
- `pnpm run format`
- `git diff --check`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run check`:
  - frontend checks passed
  - backend workspace check failed on missing system `glib-2.0` pkg-config
    dependency before reaching changed crates
- `cargo check -p services -p local-deployment`

## Validation Gaps / Failures

- Plain `pnpm run check` without `NODE_OPTIONS` failed in `local-web:check`
  because Node hit its default heap limit.
- Full backend workspace check failed because this environment is missing the
  system `glib-2.0.pc` dependency required by `glib-sys`.
- No live service restart, deploy, or browser smoke was performed.

## Next Safe Steps

1. Review the queued follow-up prompt wording.
2. Run a local UI smoke after preview/dev server startup if desired.
3. Deploy/restart only through the normal VK deployment workflow.
