# STREAM.md

## Stream Identifier

- Branch: `vk/land-live-fixes-20260422`
- Repo: `/home/mcp/_vibe_kanban_repo`
- Working mode: local-only VK maintenance / live-fix audit branch

## Objective

- Audit and repair new VK UI/runtime features that appeared merged or deployed but failed in live use.
- Current focus: needs-attention sidebar marker clearing, attachment upload/paste, codeblock copy, workspace rename actions, issue PR details, and merged PR state.

## In Scope

- Local-only runtime stability
- Dysfunctional VK feature investigation
- Focused fixes that can be promoted through `staging` and then production
- Documentation of root cause and prevention rules
- Space cleanup planning required before executing/deploying the repair set

## Out of Scope

- Reviving the old cloud-backed board model
- Depending on `api.vibekanban.com` for local board state
- Bulk-merging stale feature branches with unrelated changes
- Restarting live VK without explicit user approval

## Stream-Specific Decisions

- `staging` is the base branch; this stream lands through a PR back into `staging`.
- The local install must keep `shared_api_base` disabled.
- Live production is copy-deployed and may not match this checkout until a build/deploy happens.
- UI-only fixes can use refreshable frontend assets only after the running backend already supports the needed API behavior.
- Frontend asset swaps must still be followed by clean branch/PR promotion; a live symlink swap is an operational hotfix, not a permanent landing path.
- Every repaired feature needs a live verification step, not only a merge confirmation.

## Relevant Files / Modules

- `packages/web-core/src/shared/providers/WorkspaceProvider.tsx`
- `packages/web-core/src/shared/hooks/useWorkspaces.ts`
- `crates/server/src/routes/workspaces/core.rs`
- `crates/server/src/routes/workspaces/workspace_summary.rs`
- `packages/ui/src/components/WorkspacesSidebar.tsx`
- `packages/ui/src/components/WorkspaceSummary.tsx`
- Issue/workspace PR display paths under `packages/web-core/src/features/kanban/` and fallback PR routes

## Current Status

- Confirmed:
  - needs-attention markers are driven by `has_unseen_turns` and `has_pending_approval`
  - successful coding-agent completion must re-mark a previously seen/running turn as unseen; otherwise no needs-review icon appears after the agent finishes
  - `execution_process_id` in `coding_agent_turns` is a SQLite UUID blob, so completion marker updates must bind a `Uuid` value, not a string
  - a mounted workspace must not auto-clear unseen activity when a summary poll flips to `has_unseen_turns`; only explicit workspace selection/navigation should clear it
  - selected workspaces did not re-run `markSeen` when their already-mounted summary became unseen
  - `mark_seen` did not invalidate the server-side workspace-summary cache
  - attachment upload can silently no-op when the chat is in existing-workspace new-session mode with no `sessionId`
  - attachment upload failures are only logged to console, not surfaced to the user
  - the live attachment cache directory `/home/mcp/.cache/utils/attachments` is missing, causing current upload/read failures
  - disk space is tight enough to address first: `opSpace` reported root at `87%` full with `31G` free
  - latest codeblock-copy reliability fixes are not safely landed in current production/integration
  - workspace rename is blocked for local fallback rows by the remote-owner gate
  - PR details/merged-state rendering lacks durable rows for some affected issues
- Prepared but not deployed:
  - sidebar sub-agent indicators now read Codex `thread_spawn_edges` through `coding_agent_turns.agent_session_id`, expose summary counts, and render a stack/count marker on workspace cards
  - stale Codex open edges from completed VK parent executions are filtered out so old Android Parity children do not show as currently active forever
- Prepared but not deployed:
  - sub-agent preservation now records raw Codex `collabAgentToolCall` / `spawnAgent` completion events even when normalized `spawn_agent` entries are absent
  - `not_found` is no longer treated as terminal for sub-agent jobs; it remains recoverable and still blocks accidental follow-up prompts as unresolved work
  - chat-derived sub-agent activity preserves a known running/unresolved spawned child when a later `wait_agent` result reports `not_found`
- Prepared but not deployed:
  - `mark_seen` clears the workspace-summary cache
- Published without restart on 2026-05-06, then rolled back after regression:
  - codeblock copy overlay for read-only chat code blocks
  - local fallback workspace rename/delete action visibility when `owner_user_id = ""`
  - attachment upload errors/no-session no-op feedback in the workspace chat composer
  - mobile attachment picker activation now uses a native label/input path instead of programmatically clicking a hidden file input
  - create-mode attachment selection now uses the same native label/input path and surfaces upload failures instead of only logging them
  - frontend rejects files over the backend `20 MB` upload limit before sending, with a visible message
  - live attachment cache directory `/home/mcp/.cache/utils/attachments`
  - frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1625Z-attachment-visible-errors`
  - rollback target `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260505T1648Z`
  - current workspace auto-clears unseen turns when its summary flips to unseen, but server summary-cache invalidation still needs backend restart

## Risks / Regression Traps

- Repointing the service back to cloud/shared API config
- Deploying or validating from dirty canonical checkout instead of a clean worktree
- Merging stale feature branches wholesale
- Assuming a feature is live because it exists somewhere in git history
- Losing PR/issue display state when relying on branch/worktree presence instead of durable DB rows
- Attachment cache files can be missing even when DB rows exist; restore/backfill must verify actual files, not only records.
- Space cleanup can damage VK continuity if it prunes `codex-home`, sessions, or backups without a retention rule.
- Needs-review must not regress to either failure mode already seen:
  - false positive: non-empty `In Review` columns are not review signals by themselves
  - false negative: completed coding-agent turns that were seen while running must become unseen again on successful completion
  - keep the DB UUID-binding regression test in `crates/db/src/models/coding_agent_turn.rs` and run `cargo test -p db completed_coding_agent_turns_are_marked_unseen_by_uuid_blob` for this path
- Sub-agent preservation must not regress:
  - do not require normalized chat tool entries as the only source of spawned child IDs
  - do not mark `not_found` as completed/final in the DB or UI interruption guard
  - do not count stale Codex `open` edges as active when the VK parent execution is already completed and the child has not updated after parent completion
  - verify with `cargo test -p db not_found_subagent_status_remains_recoverable` and `cargo test -p services raw_codex_spawn_agent`

## Next Safe Steps

1. Rebuild the attachment/frontend fixes from a clean worktree so unrelated project-list UI changes cannot ship again.
2. Raise local VK attachment limit to `100 MB` in both backend and frontend, then deploy only after backup/restart approval.
3. Promote the clean attachment fixes through a clean branch/PR into `staging`.
4. Land the needs-attention server summary-cache invalidation and deploy it with the next approved backend restart.
5. Deploy the sub-agent sidebar indicator fix with the next approved backend restart, then verify against a workspace with open Codex `thread_spawn_edges`.
6. Backfill broader current live `subagent_jobs` rows from Codex `thread_spawn_edges` only after confirming the desired scope; Halley alone was backfilled as a minimal no-restart mitigation.
7. Implement PR snapshot/reconcile/backfill as a separate concern.
8. Verify every feature against live UI/API before production promotion.
