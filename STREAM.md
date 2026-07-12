# STREAM.md

## Stream Identifier

- Branch: `vk/419a-vk-allow-follow`
- Repo:
  `/home/mcp/code/worktrees/419a-vk-allow-follow/_vibe_kanban_repo`
- Base: local `staging`
- Working mode: VK active Codex follow-ups

## Objective

- Allow users to send follow-up messages while a Codex coding-agent turn is
  still running by injecting them into the active Codex session at the next
  safe opportunity.

## In Scope

- Local Codex app-server follow-up injection.
- Local session follow-up queue fallback behavior.
- Chat UI queue status for pending follow-ups.
- Generated local shared TypeScript types.

## Out of Scope

- Live `vibe-kanban.service` restart or deployment.
- Remote/cloud queue persistence.
- Remote/cloud follow-up injection.

## Current Status

- Queueing a follow-up for a running session now appends to the session queue
  instead of replacing the previous queued message.
- When the current agent turn is ready to hand off, queued messages are collapsed
  into one ordered follow-up prompt and started as the next coding-agent turn.
- For active Codex app-server executions, the queue endpoint now first attempts
  to inject the follow-up into the live process. The Codex client stores pending
  follow-ups, interrupts the active turn with `turn/interrupt`, and submits the
  text as the next turn after `turn/completed`.
- The post-run queue path remains as a fallback when there is no active Codex
  client or when the active executor is not Codex.
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
- `cargo check -p executors -p services -p local-deployment -p server`

## Validation Gaps / Failures

- Plain `pnpm run check` without `NODE_OPTIONS` failed in `local-web:check`
  because Node hit its default heap limit.
- Full backend workspace check failed because this environment is missing the
  system `glib-2.0.pc` dependency required by `glib-sys`.
- No live service restart, deploy, or browser smoke was performed.

## Next Safe Steps

1. Run a local UI smoke after preview/dev server startup if desired.
2. Deploy/restart only through the normal VK deployment workflow.
