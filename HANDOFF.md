# HANDOFF.md

## Pickup Note

- Branch: `vk/1ed3-vk-branch-chats`
- Worktree:
  `/home/mcp/code/worktrees/1ed3-vk-branch-chats/_vibe_kanban_repo`
- Current focus: branch existing workspace chats into new workspaces or
  sub-issues while preserving the source agent context.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Added `BranchChatWorkspaceRequest` and `BranchChatWorkspaceResponse`.
- Added `POST /api/sessions/{session_id}/branch-workspace`.
- The branch workspace route:
  - loads the source session/workspace
  - requires a completed source coding-agent turn with a durable resume anchor
  - creates a new workspace
  - links to an explicit current issue when provided, otherwise preserves the
    source local `task_id` link when present
  - attaches the same repos with the source workspace branch as target branch
  - creates a new session and starts it as a `CodingAgentFollowUpRequest`
    against the source agent session id
  - emits immediate execution/workspace patches and analytics
- Regenerated `shared/types.ts`.
- Added `sessionsApi.branchWorkspace`.
- Added a `Branch chat` toolbar dropdown to existing workspace chat sessions.
  The current editor text becomes the branch instruction.
- The dropdown can create a new workspace from the source chat context and link
  it under the current issue when the chat is viewed inside an issue route.
- The dropdown can also open a new sub-issue draft inside the current issue,
  seeded from the branch instruction and review comment context.

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
- The new endpoint has not been exercised against a live VK instance.
- Full repo `pnpm run check`, `pnpm run lint`, and `cargo test --workspace`
  have not been run.

## Must Not Do

- Do not restart `vibe-kanban.service` from this feature workspace without
  explicit operator approval.
- Do not deploy binaries or switch frontend assets from this feature workspace
  without explicit operator approval.
