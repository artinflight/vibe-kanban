# DELTA.md

## 2026-04-18T00:00:00Z | staging | local-only recovery baseline

- Intent: recover the usable VK board state, remove active cloud coupling, and make the local install restorable.
- Completed:
  - imported the VK cloud export into the local SQLite DB
  - switched the live runtime to local-only behavior (`shared_api_base: null`)
  - restored project settings, local columns, issue creation, workspace linking, and workspace history scroll
  - added lean backup + one-click restore scripts
  - installed hourly backup cron with Desktop archive mirroring
- Verified:
  - local API reports `shared_api_base: null`
  - project boards and issues load locally
  - backups are created locally and mirrored to Desktop
- Not complete / known gaps:
  - some historic metadata can only be reconstructed if present in export or DB snapshots
  - project-scoped PR fallback is still broader than it should be

## 2026-04-18T22:00:00Z | staging | hyrox issue/workspace/PR repair

- Intent: repair missing workspace links and merged PR indicators in the `hyroxready-app` kanban after local recovery.
- Completed:
  - re-linked `ART-57` to `FR::Cardio Timer Font Size`
  - restored merged PR metadata for:
    - `ART-60` -> `#799`
    - `ART-61` -> `#800`
    - `T42` -> `#801`
  - updated issue workspace cards so PR badges are visible on small/narrow layouts
- Files changed:
  - `packages/ui/src/components/IssueWorkspaceCard.tsx`
- Backups:
  - `/home/mcp/backups/vk-hyrox-pr-workspace-fix-20260418T223433Z`
  - `/home/mcp/backups/vk-hyrox-ui-rollout-20260418T224435Z`
  - `/home/mcp/backups/vk-t42-pr-fix-20260418T233203Z`
- Verified:
  - local fallback API shows the repaired issue/workspace/PR links
  - live bundle rolled to `index-tPwgyQmd.js`
  - fix committed to `staging` as `1ad3ed085`

## 2026-04-18T23:00:00Z | staging | vibe-kanban project smoke test

- Intent: prove the `vibe-kanban` project can resume normal issue/workspace work locally.
- Completed:
  - created a temporary issue in the `vibe-kanban` project
  - created a linked workspace against `_vibe_kanban_repo`
  - verified the workspace appeared under the issue immediately
  - stopped and deleted the temporary workspace
  - deleted the temporary issue
- Verified:
  - local issue creation works
  - local workspace creation works
  - workspace linking/refresh works
- Not complete / known gaps:
  - none blocking normal project work in the `vibe-kanban` board

## 2026-04-19T00:00:00Z | staging | workspace turn ntfy notifications

- Intent: mirror completed VK workspace turns to the homelab `ntfy` container and include the compact `Label:: value` metadata from the final assistant summary.
- Completed:
  - updated workspace completion notifications to load the saved coding-agent turn summary before notifying
  - extracted compact metadata lines from the final summary using the ops-playbook `::` contract
  - added optional ntfy publishing via `ssh homelab docker exec ntfy ntfy publish ...`
  - gated ntfy publishing behind `VK_NTFY_TOPIC`, with optional overrides for `VK_NTFY_SSH_HOST` and `VK_NTFY_CONTAINER`
  - added unit coverage for metadata extraction and no-metadata fallback behavior
- Files changed:
  - `crates/services/src/services/container.rs`
  - `crates/services/src/services/notification.rs`
  - `HANDOFF.md`
- Verified:
  - `cargo test -p services notification -- --nocapture`
  - `ssh homelab docker exec ntfy ntfy publish --quiet --title 'VK ntfy smoke' --message 'workspace notification smoke test' <throwaway-topic>`
- Not complete / known gaps:
  - full repo formatting is still blocked in this worktree because `packages/web-core` cannot find `prettier`
  - end-to-end subscriber verification for a real completed workspace turn still requires `VK_NTFY_TOPIC` in the runtime environment

## 2026-04-24T00:00:00Z | vk/7617-vk-wire-ntfy | ntfy rollout blocked at installed binary swap

- Intent: finish live rollout of the ntfy workspace-turn notification branch by wiring the topic into the local service and swapping the installed server binary.
- Completed:
  - confirmed the live `vibe-kanban` user service environment includes `VK_NTFY_TOPIC=vk-workspace-turns`
  - confirmed the service launcher runs `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - confirmed that installed binary does not yet contain the ntfy notification strings from this branch
  - completed `cargo build --release -p server` from this worktree
- Verified:
  - `systemctl --user show vibe-kanban.service --property=Environment,ExecStart,ActiveState,SubState --no-pager`
  - `strings /home/mcp/.local/bin/vibe-kanban-server-cleanfix | rg "VK_NTFY_TOPIC|failed to publish workspace completion to ntfy|notify_workspace_turn_completion|Workspace::"`
  - `cargo build --release -p server`
- Not complete / known gaps:
  - direct replacement of `/home/mcp/.local/bin/vibe-kanban-server-cleanfix` initially failed with `Text file busy`
  - the interrupted follow-up stop/copy/start step means the live service is still not running the ntfy-enabled branch binary
  - no branch PR existed yet at this checkpoint
