# STREAM.md

## Stream Identifier

- Branch: `vk/93f4-vk-stop-defaulti`
- Repo: `/home/mcp/code/worktrees/93f4-vk-stop-defaulti/_vibe_kanban_repo`
- Base: `fork/staging`
- Working mode: focused local-web behavior fix

## Objective

- Stop Plan Mode from being inherited by later agents just because a previous
  agent was started in Plan Mode.

## In Scope

- Shared executor-config resolution used by create-mode and workspace chat.
- Branch-local continuity notes for this task.

## Out of Scope

- Executor backend behavior after a request explicitly includes Plan Mode.
- Broader agent profile, model, reasoning, or variant persistence changes.
- Live production deployment.

## Stream-Specific Decisions

- Past process history may still seed executor, variant, model, and reasoning
  defaults.
- `permission_policy` is different: it should come from an explicit current
  selection or draft scratch state, not from the previous completed process.
- Existing scratch data may still preserve an in-progress explicit Plan Mode
  selection for that same unsent draft.

## Relevant Files / Modules

- `packages/web-core/src/shared/hooks/useExecutorConfig.ts`
- `packages/web-core/src/shared/components/CreateChatBoxContainer.tsx`
- `packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx`
- `packages/web-core/src/shared/hooks/useWorkspaceCreateDefaults.ts`

## Current Status

- Implemented the frontend defaulting fix in `useExecutorConfig`.
- `pnpm run format` passed after installing workspace dependencies.
- `pnpm --filter @vibe/web-core run check` hit Node's default heap limit once,
  then passed with `NODE_OPTIONS=--max-old-space-size=4096`.

## Risks / Regression Traps

- Re-adding `permission_policy` to last-used fallback will recreate the reported
  bug.
- Removing scratch fallback would be too broad because it would discard an
  explicit unsent draft selection.
- Changing executor or variant fallback would alter unrelated user convenience
  behavior.

## Next Safe Steps

1. Smoke-test in the UI by starting one agent with Plan Mode, then opening a new
   agent composer and verifying the permission button resolves to Auto.
2. Run broader checks if this branch is promoted into `staging`.
