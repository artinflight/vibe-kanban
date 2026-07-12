# STREAM.md

## Stream Identifier

- Branch: `vk/a8c5-vk-something-wro`
- Repo:
  `/home/mcp/code/worktrees/a8c5-vk-something-wro/_vibe_kanban_repo`
- Base: `fork/staging`
- Working mode: VK local workspace chat stability

## Objective

- Stop workspace chats from appearing to load older and older messages on their
  own during live execution-log websocket reconnects.

## In Scope

- Local frontend websocket replay behavior for chat/log JSON patch streams.
- Focused validation for the stream replay fix.
- Checking live service logs to identify the trigger.

## Out of Scope

- Restarting or deploying the live `vibe-kanban.service`.
- Broad backend stream capacity or memory hardening.
- Changing chat UI layout or message rendering semantics.

## Current Status

- Live logs showed repeated `MsgStore broadcast lagged` errors and
  `execution_processes` stream closures while the service was at roughly
  `9.1G` RSS.
- The frontend stream helper used to reset its local snapshot before every
  reconnect, causing replay from `/entries/0` to temporarily shrink the visible
  transcript.
- `streamJsonPatchEntries` now preserves the last good snapshot across
  reconnects and only clears unapplied pending patch ops.
- Added a regression test for reconnect replay preserving already-visible
  newer entries.
- Rebased the branch onto `fork/staging` before opening the PR so the PR only
  contains this chat replay fix.
- No live restart or deployment was performed.

## Validation

- `pnpm install --offline --frozen-lockfile`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
- `pnpm run format`

## Validation Gaps / Failures

- `pnpm --filter @vibe/web-core exec vitest run src/shared/lib/streamJsonPatchEntries.test.ts`
  could not run because `vitest` is not installed as a project dependency.
- `pnpm --filter @vibe/web-core run check` without increased `NODE_OPTIONS`
  hit Node heap OOM; the same check passed with `--max-old-space-size=4096`.
- No live UI smoke was performed because this branch was not deployed into the
  running local VK instance.

## Next Safe Steps

1. Push/open a PR into `staging`.
2. Merge to `staging` for inclusion in the next restart candidate.
3. Consider a separate backend hardening stream for reducing `MsgStore`
   broadcast lag under very high output volume.
