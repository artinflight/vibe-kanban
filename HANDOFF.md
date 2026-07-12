# HANDOFF.md

## Pickup Note

- Branch: `vk/a8c5-vk-something-wro`
- Worktree:
  `/home/mcp/code/worktrees/a8c5-vk-something-wro/_vibe_kanban_repo`
- Current focus: workspace chat replay stability during live execution-log
  websocket reconnects.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Checked live `vibe-kanban.service` logs.
  - Found repeated `MsgStore broadcast lagged` messages and
    `server::routes::execution_processes: stream error` entries.
  - Live service memory was roughly `9.1G` RSS while three VK Codex executions
    were attached.
- Updated `packages/web-core/src/shared/lib/streamJsonPatchEntries.ts`.
  - Websocket reconnects now preserve the last good `{ entries }` snapshot.
  - Reconnect scheduling still clears pending, unapplied patch operations and
    cancels any queued animation frame.
  - Replayed patches from `/entries/0` replace entries in place instead of
    temporarily shrinking the visible chat transcript.
- Added `packages/web-core/src/shared/lib/streamJsonPatchEntries.test.ts`.
  - The test simulates a websocket reconnect where replay starts with entry `0`
    and verifies that newer visible entries remain present while replay catches
    up.
- Rebased the branch onto `fork/staging` before PR creation so the PR contains
  only this chat replay fix.
- Updated `STREAM.md` for the current branch.

## Validation

- `pnpm install --offline --frozen-lockfile`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
- `pnpm run format`

## Validation Gaps / Failures

- `pnpm --filter @vibe/web-core exec vitest run src/shared/lib/streamJsonPatchEntries.test.ts`
  failed because `vitest` is not installed as a project dependency.
- `pnpm --filter @vibe/web-core run check` without increased `NODE_OPTIONS`
  failed with Node heap OOM; rerunning with `--max-old-space-size=4096` passed.
- No live deploy, restart, or UI smoke was performed.

## Next Safe Steps

1. Push/open a PR into `staging`.
2. Merge to `staging` for inclusion in the next restart candidate.
3. Investigate backend stream pressure separately if the `MsgStore broadcast
   lagged` volume remains high after the frontend replay fix.
