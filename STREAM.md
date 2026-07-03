# STREAM.md

## Stream Identifier

- Branch: `vk/1ed3-vk-branch-chats`
- Repo:
  `/home/mcp/code/worktrees/1ed3-vk-branch-chats/_vibe_kanban_repo`
- Working mode: branch existing workspace chats into new workspaces.

## Objective

- Add a local workflow to start a new workspace from an existing agent chat
  context.

## In Scope

- Backend session endpoint that creates a new workspace, copies source repos,
  branches from the source workspace branch, and starts a forked agent turn from
  the source session's durable resume anchor.
- Workspace chat toolbar affordance for starting the branch with the current
  editor message as the branch instruction.
- Generated TypeScript API types.
- Focused Rust and web-core validation.

## Out of Scope

- Creating brand-new issues from the branch action.
- Remote/cloud workspace linking beyond preserving the source local task link
  when present.
- Live VK service restart or deployment.
- Browser UI smoke against a running local instance.

## Current Status

- Implemented `POST /api/sessions/{session_id}/branch-workspace`.
- The route requires a completed source agent turn with durable
  `agent_session_id` and rejects sessions that cannot preserve chat context.
- The new workspace copies source repositories and uses the source workspace
  branch as each repo target branch, so the new workspace starts from current
  source code state.
- Existing local issue/task linkage is preserved via `workspaces.task_id`.
- Workspace chat now shows a branch icon in existing-session mode. The user
  types a branch instruction, clicks the icon, and is navigated to the new
  workspace after spawn.

## Relevant Files / Modules

- `crates/server/src/routes/sessions/mod.rs`
- `crates/db/src/models/requests.rs`
- `crates/server/src/bin/generate_types.rs`
- `packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx`
- `packages/web-core/src/shared/lib/api.ts`
- `shared/types.ts`

## Validation So Far

- `pnpm install --offline --frozen-lockfile`
- `pnpm run generate-types`
- `pnpm run format`
- `cargo check -p server`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
- `pnpm --filter @vibe/web-core run lint`
- `git diff --check`

## Validation Gaps

- Browser UI smoke has not been run.
- Full repo `pnpm run check`, `pnpm run lint`, and `cargo test --workspace`
  have not been run.
- The new endpoint has not been exercised against a live VK instance.

## Next Safe Steps

1. Run a local UI smoke: open an existing completed workspace chat, type a
   branch instruction, click Branch chat, and verify the new workspace starts
   with preserved context.
2. Decide whether a later follow-up should create a new issue/sub-issue as part
   of branching instead of only preserving the source local task link.
3. Run full PR baseline before opening a PR into `staging`.
