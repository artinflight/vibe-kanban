# STREAM.md

## Stream Identifier

- Branch: `vk/18a4-vk-issue-priorit`
- Repo: `/home/mcp/code/worktrees/18a4-vk-issue-priorit/_vibe_kanban_repo`
- Base: `fork/staging`
- Working mode: local VK bug fix

## Objective

- Restore issue priority updates in local-mode VK so changing priority from the issue panel and command bar persists.

## In Scope

- Local compatibility issue create/update handlers
- Local metadata round-tripping for priority values
- Branch-local continuity docs for this stream

## Out of Scope

- Remote/cloud issue priority APIs
- Broader issue field refactors
- UI redesign work

## Stream-Specific Decisions

- Keep the local fallback storage model intact by continuing to store priority inside local metadata embedded in task descriptions.
- Support both setting and clearing priority in local issue PATCH requests.

## Relevant Files / Modules

- `crates/server/src/routes/local_compat.rs`
- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`

## Current Status

- Completed:
  - identified that local fallback issue reads exposed priority but local fallback issue PATCH ignored `priority`
  - added local create/update/bulk-update handling for priority metadata
  - added unit coverage for setting and clearing priority metadata
- Pending:
  - rerun backend validation on top of current `fork/staging`
  - verify the issue panel flow in the local VK UI
  - finish the rebase and merge into local `staging`

## Risks / Regression Traps

- Local issue priority is synthetic metadata, not a dedicated DB column, so status and priority updates must continue to share the same description-rewrite path.
- Current `staging` already has unrelated local divergence from `fork/staging`; landing this branch locally does not remove that separate divergence.

## Next Safe Steps

1. Resolve the rebase conflicts by keeping this branch’s continuity notes and merged backend behavior.
2. Continue the rebase onto `fork/staging`.
3. Merge the rebased branch into the local `staging` checkout.
