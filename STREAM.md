# STREAM.md

## Stream Identifier

- Branch: `vk/b401-vk-reloading-old`
- Repo: `/home/mcp/code/worktrees/b401-vk-reloading-old/_vibe_kanban_repo`
- Working mode: isolated feature branch

## Objective

- Make “Reset to this point” on an older workspace-chat message land at the
  selected reset boundary instead of preserving a removed viewport anchor.

## In Scope

- Workspace-chat reset completion and scroll positioning.
- Focused frontend validation of the reset handoff.

## Out of Scope

- Changing backend reset semantics.
- Restarting or deploying the active green instance.
- Unrelated chat history, virtualizer, or preference changes.

## Stream-Specific Decisions

- `staging` is the base branch; this stream lands through a PR back into `staging`.
- The local install must keep `shared_api_base` disabled.
- Live production is copy-deployed and may not match this checkout until a build/deploy happens.
- UI-only fixes can use refreshable frontend assets only after the running backend already supports the needed API behavior.
- Frontend asset swaps must still be followed by clean branch/PR promotion; a live symlink swap is an operational hotfix, not a permanent landing path.
- Every repaired feature needs a live verification step, not only a merge confirmation.
- Frontend hotfixes must be built from a clean worktree pinned to the current live frontend release boundary plus only the intended patch. Dirty maintenance-checkout frontend builds are forbidden because they already caused project-list/nav regressions.
- Any deploy, restart, or frontend symlink swap must include a release manifest and a regression smoke result in `HANDOFF.md` before being called ready. If the manifest cannot prove the package contains every currently live hotfix, stop.
- Future VK agents must read `VK_AGENT_DEPLOYMENT_RUNBOOK.md` before touching deploy/restart/frontend asset swap work. The runbook is the current operational checklist; `LIVE_DEPLOYMENT.json` and older continuity sections can lag reality and must be verified against the live service.
- The current deployment queue is split:
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260511Tclean-frontend-regression-lock`: collapsed Kanban count, compact mobile collapsed columns, queued-status polling
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tworkspace-actions-spin-off`: command menu target-workspace visibility, spin-off workspace durable draft/error handling, mobile chat autofocus suppression
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tissue-status-selector`: direct issue-page status selector plus the previous workspace-action/mobile fixes
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tkanban-drag-persist`: Kanban card drag status/order persistence through `ProjectContext.updateIssues`
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tissue-workspace-archive-repo-defaults`: issue-view workspace Archive/Unarchive plus project-scoped repo default fallback
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tagent-chat-images`: inline rendering for agent/shared chat images from `.vibe-attachments/` markdown references
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tdefault-project-columns`: prevents repo-default saves from erasing the operator default project columns
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin`: workspace Pin/Unpin fetches fresh target state and updates the host-scoped workspace record cache before invalidating summaries
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tmobile-archive-nav`: mobile project drawer removes stale `Export data` and exposes `Archived projects`
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260604Tmultiline-paste`: multi-line plain text paste in chat composers preserves all pasted lines and carries forward the mobile archive-nav fix
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`: explicit executor/model/mode selections persist per session/workspace so switching a Plan-started session to Auto does not snap back to Plan
  - deployed no-restart asset release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260618Tbranch-search`: workspace base-branch selectors support separator/token search and carry forward the current frontend regression markers
  - deployed backend restart on 2026-05-11: orphan queued-message guard, stale sub-agent filtering, prompt JSON body limit raised to `100 MB`
- Manual workspace unread is a backend-backed feature, not a frontend-only flag: it must set the latest coding-agent turn `seen = 0` and invalidate workspace summaries so all existing needs-review markers update consistently.

## Relevant Files / Modules

- `packages/web-core/src/shared/providers/WorkspaceProvider.tsx`
- `packages/web-core/src/shared/hooks/useWorkspaces.ts`
- `crates/server/src/routes/workspaces/core.rs`
- `crates/server/src/routes/workspaces/workspace_summary.rs`
- `packages/ui/src/components/WorkspacesSidebar.tsx`
- `packages/ui/src/components/WorkspaceSummary.tsx`
- Issue/workspace PR display paths under `packages/web-core/src/features/kanban/` and fallback PR routes

## Current Status

- 2026-08-31 durable preference implementation is prepared:
  - new project-order and workspace-color tables use optimistic revisions and
    append recoverable history
  - saved-message writes/deletes reject stale revisions and record history
  - the frontend switches away from shared scratch only after detecting the
    new API, preserving compatibility with the currently running backend
  - full migration chains pass on empty and copied-live databases; the live
    copy preserved all nine saved messages
  - no runtime restart or deployment has been performed

- 2026-08-31 saved-message compatibility frontend deployed:
  - PR `#99` rebase-merged into `staging` as `a1ccb73e3`
  - older backends are treated as lacking durable saved-message support, so
    the sidecar hydrates independently and scratch remains the write fallback
  - immutable frontend release is
    `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260831Tsaved-messages-a1ccb73e31`
  - live assets are `/assets/index-Dw4SbUxk.js` and
    `/assets/index-QO1t6__J.css`
  - the sidecar still contains nine messages with SHA-256
    `b46579c2d1f41634828018825a61c3f6f8daf7718d5bc3d08c667d74ad1b468d`
  - backend PID remained `3112780`; no backend restart occurred
  - the live smoke script's release/asset constants are stale and must be
    updated separately; its failure was not a live endpoint failure

- 2026-08-31 workspace-color refresh persistence frontend deployed:
  - PR `#97` rebase-merged into `staging` as `98eb580f3`
  - browser storage preserves workspace colors immediately while the running
    backend remains on the older typed payload contract
  - immutable frontend release is
    `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260831Tworkspace-color-refresh-98eb580f3`
  - live assets are `/assets/index-DlRW8gpD.js` and
    `/assets/index-QO1t6__J.css`
  - saved-message sidecar SHA-256 remains
    `b46579c2d1f41634828018825a61c3f6f8daf7718d5bc3d08c667d74ad1b468d`
  - backend PID remained `3112780`; no backend restart occurred

- 2026-08-31 left-nav project reorder frontend deployed:
  - project icons in the left nav now remain fixed at `40px` instead of
    shrinking to fit every project into the rail
  - the project list scrolls vertically, giving drag-and-drop stable hitboxes
    when many projects exist
  - branch commit `4538b96c1`; staging commit `20e7fc065`
  - immutable frontend release is
    `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260831Tleft-nav-reorder-4538b96c`
  - live assets are `/assets/index-LxC8hBXR.js` and
    `/assets/index-QO1t6__J.css`
  - `vk-saved-chat-messages.json` was retained with SHA-256
    `b46579c2d1f41634828018825a61c3f6f8daf7718d5bc3d08c667d74ad1b468d`
  - backend PID remained `3112780`; no backend restart occurred

- 2026-08-31 issue attachment routing frontend deployed:
  - local `staging` was reconciled with `fork/staging` and advanced to
    `e621088ac`
  - issue/comment attachments in the local issue UI now route through
    `/api/attachments/upload` instead of stale issue-specific attachment paths
  - immutable frontend release is
    `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260831Tissue-attachments-b5222a01d`
  - the missed saved-message sidecar was restored into that release and now
    serves nine messages from `/vk-saved-chat-messages.json` with SHA-256
    `b46579c2d1f41634828018825a61c3f6f8daf7718d5bc3d08c667d74ad1b468d`
  - served JS asset is `/assets/index-DSZKrAbs.js`; live marker checks found
    `/api/attachments/upload` and did not find `attachments/issues`
  - direct invalid multipart POST to `/api/attachments/upload` returned `400`,
    not `405`
  - source now adds `workspace_colors` to `UiPreferencesData` and preserves an
    existing map when omitted by older clients; exact prior color choices were
    not recoverable from current or pre-swap green DB snapshots
  - backend candidate binary was built but not installed because green
    executions were active; backend PID remained `3112780`
  - green backup completed to
    `desktop:B:/vk-backups/vk-lean-restore-20260830T234448Z.tar.gz` with local
    desktop metadata at
    `/home/mcp/backups/vk-lean-restore-latest.desktop.json`

- 2026-08-30 light-theme tint follow-up deployed:
  - the colored fill now wins over the card's later `bg-panel` utility in both
    themes
  - light cards retain the existing `0.48` tint and use `0.58` on hover; dark
    cards retain `0.18` and use `0.24` on hover
  - the colored inset edge remains unchanged
  - PR `#93` rebase-merged into `staging` as `b4f57707f`
  - immutable frontend release is
    `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260830Tlight-workspace-tint-b4f57707f`
  - the recovered nine-message compatibility sidecar was retained
    byte-for-byte and verified through `vibe.local`
  - backend PID remained `3112780`; no backend restart occurred
  - public preview is `https://mcp-server.tail744c4.ts.net:8443/`

- 2026-08-29 colored Kanban workspaces deployed:
  - workspace cards expose a three-dot pastel color picker and clear action
  - selections persist in UI preferences scratch under `workspace_colors`
  - light and dark themes use distinct tint strengths, with a shared inset
    color edge and theme-aware swatch contrast
  - PR `#91` rebase-merged into `staging` as `4a314b61b`
  - immutable frontend release is
    `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260829Tcolored-workspaces-4a314b61b`
  - `vibe.local` serves the new JS/CSS through the frontend static service on
    `4313`, while API routes remain on green `4511`
  - backend PID remained `3112780`; no backend restart or migration occurred
  - public preview is `https://mcp-server.tail744c4.ts.net:8443/`

- 2026-08-29 agent preview guide prepared:
  - root-level `VK_PREVIEW_GUIDE.md` is the concise canonical entry point for
    frontend-only previews against green `4511`
  - the guide distinguishes frontend preview from backend/migration testing,
    documents the public `8443` Funnel route, and requires frontend plus
    `/api/info` probes before sharing
  - timeout, wrong-database, and disappearing-value troubleshooting explicitly
    prevents agents from starting an unnecessary second backend
  - `AGENTS.md`, `README.md`, the deployment runbook, and the detailed
    self-hosting page link to the guide for discovery

- 2026-08-29 public preview workflow repaired and documented:
  - lightweight preview defaults to the live green backend on `4511`
  - dynamic `184xx` Tailscale Serve URLs are explicitly labeled tailnet-only
  - public operator review uses Funnel port `8443` and requires successful
    frontend plus `/api/info` probes before the URL is shared

- 2026-08-29 compact tag visibility follow-up prepared:
  - Kanban headers reserve space for one truncated tag pill and a `+N` count
  - hovering the tag control exposes the complete comma-separated tag list
  - badge text truncates without hiding its color marker
  - follow-up testing found the local compatibility API still returned empty
    `tags` and `issue_tags` collections, so styling alone could not display tags
  - local Kanban tags and issue/tag associations now have SQLite persistence and
    fallback list/create/update/delete API routes
  - local issue create/update/bulk-update now persist priority metadata instead
    of accepting the UI mutation and immediately reloading the old value
  - this correction requires a backend build/restart before the green-backed
    preview can create or display persisted tags

- 2026-08-29 selectable workspace branch label prepared:
  - the centered desktop navbar branch label now permits normal text selection
    and uses a text cursor instead of acting as a Tauri drag region
  - the full branch is available as the native title when visual truncation is
    required

- 2026-08-29 compact-card and responsive-project-rail follow-up deployed:
  - PR `#85` rebase-merged into `staging` as `46014edcf`
  - release `20260829Tcompact-cards-project-rail-46014edcf` is live
  - served JS hash matched the release and `/api/info` remained healthy
  - green backend PID stayed `3112780`; no restart occurred

- 2026-08-29 compact-card and responsive-project-rail follow-up is ready for
  promotion together:
  - the branch is frontend-only and does not require a backend restart
  - the intended PR target is `staging`
  - deployment must build the merged `staging` commit in a clean worktree and
    preserve the green runtime's saved-message shim and sidecar

- 2026-08-28 responsive project-rail sizing prepared:
  - the project list consumes only the remaining vertical rail space
  - project buttons shrink evenly, stay square, and cap at the existing 40px
    square size when the project count fits
  - the rail no longer relies on vertical scrolling to fit project buttons

- 2026-08-28 compact Kanban metadata follow-up prepared:
  - tags, priority/urgency, needs-review flag, assignee, and more-actions controls
    share the issue-ID row
  - the separate priority/assignee row is removed; only PR and relationship
    badges remain below the workspace when present

- 2026-08-28 workspace-first Kanban cards rebased onto `fork/staging`:
  - active linked workspaces replace issue titles and description toggles
  - archived/hidden workspaces retain the issue-title fallback
  - linked workspaces render even without local summary enrichment
  - workspace-card clicks open the workspace; outer-card clicks open the issue
    flyout; flyout workspace clicks also open the workspace
  - frontend-only change; no backend restart is required
  - PR `#83` rebase-merged at `aa13835a9` and the clean merged-staging frontend
    release is live on green with unchanged backend PID `3112780`

- 2026-08-26 service consolidation complete:
  - green on `4511` is the sole running VK backend and is enabled for boot
  - production on `4311` and lab on `4411` are stopped and disabled
  - production is runtime-masked because a concurrent process re-enabled it once after the initial shutdown
  - `vibe.local` remains healthy and its proxy depends on green rather than production
  - production was stopped only after its final execution reached a terminal state
- 2026-06-26 multi-line rich clipboard paste hotfix live:
  - source `PasteMarkdownPlugin.tsx` now handles multiline `text/plain` before opting out for `text/html`
  - live frontend release is `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260626Tmultiline-rich-paste`, asset `/assets/index-DXMultilinePaste.js`
  - release was produced as a no-restart asset hotfix by copying live `20260618Tbranch-search` and patching only the compiled paste handler
  - validation passed: `pnpm --filter @vibe/ui run check`, targeted `git diff --check`, live curl marker checks, and live `python3 scripts/vk_live_regression_smoke.py`
  - future builds must include the source fix and must not roll back below this frontend release
- 2026-06-21 project sidebar flyout/customization prepared:
  - compact AppBar project rail now has a triangle flyout to reveal full project names
  - project edit dialog supports local project rename plus persisted abbreviation/color display overrides
  - pastel project colors are stored through UI preferences scratch as `local_project_customizations`
  - local project rename requires backend build/restart; the flyout/edit UI requires a frontend release
  - validation passed: `pnpm install --offline --frozen-lockfile`, `pnpm run generate-types`, `pnpm run format`, `pnpm --filter @vibe/ui run check`, `pnpm --filter @vibe/web-core run check`, `cargo check -p server`, `cargo test -p server routes::projects::tests`, and targeted `git diff --check`
  - no deploy/restart was performed; build the next deploy package from a clean worktree and preserve live `20260618Tbranch-search` or newer frontend behavior
- 2026-06-11 restart package prepared, backup complete, no restart performed:
  - clean candidate worktree `/home/mcp/vk-restart-candidate-20260611T112143Z` on local branch `deploy/restart-candidate-20260611T112143Z`, commit `2a32636534c6365452777f6d67f3b64583180160`
  - backend binaries installed for the next restart at `/home/mcp/.local/bin/vibe-kanban-serve*`, sha256 `fcf8832cf5a53bf67042661bd314774cfcfeaa687e458c237aeef1648004d582`; running PID `3435842` has not restarted
  - frontend release staged but not live: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260611Trestart-candidate`, asset `/assets/index-Bm8ag4JP.js`
  - live frontend pointer now points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260618Tbranch-search`; do not switch to older staged frontend assets without rebuilding them forward
  - targeted Desktop-mirrored backup complete: `desktop:B:/vk-backups/vk-targeted-restart-restore-20260611T123534Z.tar.gz`, sha256 `af5f3380ae4648a19cef910985944dc2cf8d7964d81b2947a781deb16c9d195d`
  - stock lean backup was too large for current live sessions/Codex state and was aborted before disk fill; incomplete temp data was removed
  - remaining restart-window work is active-agent recheck, frontend pointer switch, `systemctl --user restart vibe-kanban.service`, and post-restart smoke
- 2026-06-11 Codex capacity queue fix prepared:
  - source now converts global Codex cap failures into capacity-waiting queued messages for chat follow-up sends
  - live deployment still requires backend build/restart; no restart was performed
  - validation passed: `pnpm run generate-types`, `cargo test -p services takes_oldest_capacity_queue_without_consuming_normal_queue`, `cargo check -p services -p local-deployment -p server`, and `pnpm --filter @vibe/web-core run check`
- 2026-06-11 Kanban reorder fix prepared:
  - frontend no longer discards within-column drags just because the active view was sorted by something other than `sort_order`
  - local fallback boards now persist/read manual `sort_order` via task metadata `Local Sort Order`
  - live deployment still requires backend build/restart for local fallback persistence; no restart was performed
  - validation passed: `pnpm --filter @vibe/web-core run check`, `cargo test -p server local_sort_order_metadata_round_trips`, and `cargo check -p server`
- 2026-05-30 staged correction after unread regression:
  - live frontend calls `PUT /api/workspaces/:id/unread`
  - the running backend lacks that route because the previous restart deployed the ntfy-only worktree binary
  - canonical source now contains both manual unread and bounded ntfy
  - corrected binary sha256 `1ca98fdffa8d2f172ab7d94cb513e3c79e26c6a179365963d1d581ac0e45ef1a` is installed to `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - running process still uses old sha256 `be377483fccfe825fe93b10c6cba848871018e0f01d892e85c43ee072d7d19ee`
  - next restart will activate the fix, but do not restart while active agents are running
  - ntfy subscribe details: server `https://opntfy.fly.dev`, topic `vk-workspace-turns`, bearer-token auth required
- 2026-06-02 active-agent limit repair:
  - live service was missing `VK_CODEX_MAX_ACTIVE_EXECUTIONS`, so Codex executor fell back to limit `1`
  - source fallback is changed to `DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS = 8`
  - runtime docs and `ops:check` now require `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8`
  - live drop-in is updated but the running process will not see the new env until an approved restart
- 2026-06-03 resume-panic repair:
  - live `IS::UI Usability Pass` retry panicked before thread creation because `ClientRequest::ThreadResume` was missing from a hand-maintained `request_id()` match
  - source now delegates to `ClientRequest::id()` and has a regression test for `ThreadResume`
  - requires backend build/restart before live VK can resume existing agents without that panic
- 2026-06-03 restart prep:
  - user approved restart only after efficient off-MCP restore-grade backup and regression checks
  - repeated pre-restart checks show no active VK execution rows/units
  - cleanup should target rebuildable disk usage first: stale worktree `node_modules`, build outputs, and caches; preserve VK DB, sessions, Codex home, worktrees, and backups until the new Desktop backup is verified
  - queue regression must be included in the deployed package and verified after restart
  - efficient restore archive is mirrored to Desktop at `desktop:B:/vk-backups/vk-efficient-restore-20260603T004715Z.tar.gz`, sha256 `92c9e5e0a557397a90c175cd33dcffee6092a105ed7c36d529443f7ad91a495c`
  - restart package is built: backend sha256 `c083178e5a75a5fefeb01f862dd668929be03fecaf08bb3749f77ca379ffec7f`; staged frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`; asset `/assets/index-BLreFcjw.js` sha256 `8bb6029a2d1fd0e09c208afc1f558feae5646d66ce62ac790ce615c192ffb935`
  - deployed final backend sha256 `722a5b0d14ca2350661cdcd0a271ac2cfea980dae4f2dcafc55b8ffe9470ed75` to both live binary paths
  - `frontend-dist/current` now points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`
  - first post-restart smoke caught nondeterministic active-project ordering caused by synthetic-project `HashMap::values()` iteration
  - fixed project ordering in `crates/server/src/routes/projects.rs`, added `synthetic_projects_have_stable_display_order`, rebuilt, confirmed `0` active executions, and restarted again
  - after final restart, live health/hash/env checks passed, `python3 scripts/vk_live_regression_smoke.py` passed, fake unread/queue route checks returned `404` not `405`, and repeated `/api/projects` reads were stable
- 2026-06-03 duplicate-project follow-up:
  - live duplicates `FoxtrotLima` and `intakeShield` were stale synthetic scratch projects, not real duplicate project rows
  - backed up DB and deleted only the two stale scratch rows, removing duplicates without restart
  - source fix is staged but not live: `projects.rs` now canonicalizes project names and filters synthetic scratch projects whose repo IDs already belong to real projects
  - validation passed with `cargo test -p server routes::projects::tests`
  - include this source fix in the next backend build/restart
- 2026-06-03 mobile archived-projects nav follow-up:
  - root cause was a separate hardcoded mobile drawer path in `SharedAppLayout.tsx`; desktop `AppBar` had the archived-projects wiring, but mobile still showed the old export row
  - source now removes the mobile export row and adds a mobile `Archived projects` footer button that opens `ArchivedProjectsDialog`
  - deployed by refreshable frontend asset swap only; no backend restart; backend PID stayed `3435842`
  - live release is `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tmobile-archive-nav`, asset `/assets/index-CPHsMjmW.js`
  - smoke now checks `mobile-archived-projects` so this mobile-only nav regression is covered
- 2026-06-04 multi-line paste follow-up:
  - source now preserves multi-line plain text paste with `selection.insertRawText(plainText)` in `packages/ui/src/components/PasteMarkdownPlugin.tsx`
  - single-line plain text still uses markdown conversion
  - deployed by refreshable frontend asset swap only; no backend restart; backend PID stayed `3435842`
  - live release is `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260604Tmultiline-paste`, asset `/assets/index-BOrQKfSR.js`
  - smoke now checks `insertRawText` plus the current archive/order/default-column/mobile-nav guards
- 2026-06-08 Plan-to-Auto mode persistence follow-up:
  - source now persists explicit executor/profile override selections in `useExecutorConfig` using a per-session/workspace browser storage key
  - existing sessions use the session ID; new-session mode uses the workspace ID until a session exists
  - deployed by refreshable frontend asset swap only; no backend restart; backend PID stayed `3435842`
  - live release is `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`, asset `/assets/index-CTVtS8yb.js`
  - smoke now checks `vk-executor-config-selection` plus the current archive/order/default-column/mobile-nav/paste guards
- 2026-05-28 docs update:
  - added `VK_AGENT_DEPLOYMENT_RUNBOOK.md` with current live truth, clean-worktree model, frontend-only deploy path, backend restart path, backup requirements, active-agent checks, and mandatory regression smoke.
  - updated `AGENTS.md` required read order so VK agents see the runbook before code work.
  - live service verified active on PID `4182076`; live binary sha is `7c63eb8fa7b2b46f6567ef7f8606df1d7a794bb6685d14cd7bf951c531f00e46`; frontend remains pinned to `20260514Tworkspace-unpin` with asset `/assets/index-BLn8oOcK.js`.
  - one `vk-exec-codex-*` unit was running at verification time, so no restart/deploy should happen without a fresh active-agent check and explicit operator approval.
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
  - Codex-completed child state now overrides stale persisted VK `running` sub-agent rows during deduplication
- Prepared but not deployed:
  - sub-agent preservation now records raw Codex `collabAgentToolCall` / `spawnAgent` completion events even when normalized `spawn_agent` entries are absent
  - `not_found` is no longer treated as terminal for sub-agent jobs; it remains recoverable and still blocks accidental follow-up prompts as unresolved work
  - chat-derived sub-agent activity preserves a known running/unresolved spawned child when a later `wait_agent` result reports `not_found`
- Prepared but not deployed:
  - `mark_seen` clears the workspace-summary cache
- Frontend and backend deployed:
  - queued follow-up status now polls every `3s` while the UI is in `queued` state and refetches on window focus; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260511Tclean-frontend-regression-lock`
  - command menu workspace actions evaluate against the clicked workspace target, not the currently selected route/create-mode context; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tworkspace-actions-spin-off`
  - spin-off workspace now prepares a durable workspace-create draft for linked issue workspaces, surfaces errors, and refuses no-repo workspaces with a visible error; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tworkspace-actions-spin-off`
  - mobile workspace chat no longer autofocuses the editor on open; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tworkspace-actions-spin-off`
  - issue-page status changes now use a direct native selector and update issue `status_id` without depending on the command dialog; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tissue-status-selector`
  - Kanban card drags now compute the next board state synchronously and persist through the project issue mutation collection instead of a raw `bulkUpdateIssues` call; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tkanban-drag-persist`
  - issue-view workspace cards now expose Archive/Unarchive in the three-dot menu; project-linked workspace creation no longer uses global recent repo fallback and can infer exact project/repo matches; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tissue-workspace-archive-repo-defaults`
  - agents can now share workspace images directly in chat by writing them under `.vibe-attachments/` and replying with markdown image syntax; read-only chat renders those images inline from `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tagent-chat-images`
  - generated workspace-level `AGENTS.md` and `CLAUDE.md` now include the image-sharing instruction in source, and 149 existing generated root config files were backfilled without restart
  - project repo-default saves now seed/preserve the full operator status template instead of writing `statuses: []`; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tdefault-project-columns`
  - live DB repair filled the full operator template for `CodexUsage`, `Monitor local`, `LifeOS`, and `Operations` after backup `/home/mcp/backups/vk-pre-default-columns-fix-20260513T221338Z.sqlite`
  - workspace Pin/Unpin now fetches fresh target workspace state before toggling and refreshes the host-scoped workspace record cache; this is live in `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin`
  - backend orphan-queue prevention is live: `POST /api/sessions/:id/queue` rejects queue creation unless a non-dropped running queue-consumer execution exists for that session
  - prompt JSON body limits are live for workspace start, direct follow-up, and queued follow-up routes; this removes the practical long-prompt/workspace-start cap up to `100 MB`
  - 2026-05-11 refreshable frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260511Tqueue-status-refresh` was rolled back after production VK crashed during an event-stream storm
- Prepared but not deployed:
  - workspace action `Mark unread` calls `PUT /api/workspaces/:id/unread`, which marks the latest non-dropped `codingagent` turn unseen and invalidates the workspace-summary cache
  - command menu entry and shortcut `W U` are wired in source
  - the 2026-05-12 frontend-only live release deliberately excluded this action until the backend route is deployed
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

## Validation

- Repointing the service back to cloud/shared API config
- Deploying or validating from dirty canonical checkout instead of a clean worktree
- Losing queued fixes during restart; before restarting, verify the built backend contains the orphan-queue guard, stale sub-agent filter, and prompt body-limit change, and verify the frontend `current` symlink still points to the clean release with collapsed count/mobile/queue polling fixes
- Merging stale feature branches wholesale
- Assuming a feature is live because it exists somewhere in git history
- Calling a deploy ready without a release manifest that names the exact frontend release path, asset hash, source commit, and expected feature set
- Restarting with a backend package that embeds or points at an older frontend dist than the current live `frontend-dist/current`
- Losing PR/issue display state when relying on branch/worktree presence instead of durable DB rows
- Attachment cache files can be missing even when DB rows exist; restore/backfill must verify actual files, not only records.
- Space cleanup can damage VK continuity if it prunes `codex-home`, sessions, or backups without a retention rule.
- Needs-review must not regress to either failure mode already seen:
  - false positive: non-empty `In Review` columns are not review signals by themselves
  - false negative: completed coding-agent turns that were seen while running must become unseen again on successful completion
  - keep the DB UUID-binding regression test in `crates/db/src/models/coding_agent_turn.rs` and run `cargo test -p db completed_coding_agent_turns_are_marked_unseen_by_uuid_blob` for this path
- Kanban drag persistence must not regress:
  - do not compute the persisted update payload through a side effect inside `setItems`
  - do not persist Kanban card drags with a raw `bulkUpdateIssues` call from `KanbanContainer`
  - use `ProjectContext.updateIssues` so optimistic state and fallback refresh stay aligned
- Issue review flags must not regress:
  - keep quick manual issue review flags separate from tags and priority
  - persist `needs_review` as `Issue.extension_metadata.vk_flags.needs_review`
  - keep local fallback task-backed issues able to read/write the flag through `Local Issue Flags` metadata
  - the flag control belongs beside the priority marker on project Kanban cards
- Project workspace repo defaults must not regress:
  - when `projectId` is present, never use a globally recent workspace repo as the default
  - use explicit project repo defaults, exact project/repo inference, or same-project recency only
  - keep `GET /api/projects/:project_id/repos` in the backend deploy queue until the next approved restart makes it live
- Default project columns must not regress:
  - the operator template is `To do`, `In progress`, `On Hold`, `Long Running`, `In review`, hidden `Cancelled`, `To merge`, `In Staging`, `Hotfix Path`, `Done`
  - do not write `PROJECT_REPO_DEFAULTS.statuses: []` from repo-default save flows
  - backend local fallback must use the same operator template for projects with no saved status config
  - verify with `cargo test -p server routes::local_compat::tests` and a live `/v1/fallback/project_statuses` check before claiming the default-column path is safe
- Release verification must not regress:
  - before any deploy/restart, write the feature manifest and smoke plan to `HANDOFF.md`
  - after any deploy/restart, verify active/archived project counts and order, intended left-nav actions, issue workspace menu actions, project repo defaults, needs-review markers, collapsed Kanban counts/mobile layout, Kanban drag persistence, queue reconciliation, workspace action menu completeness, issue status selector, codeblock copy, and attachment feedback
  - if any smoke item cannot be tested, record it as unverified instead of implying the deploy is safe
  - current read-only live smoke command is `python3 scripts/vk_live_regression_smoke.py`; keep it updated when intentional project order/count changes happen
- Sub-agent preservation must not regress:
  - do not require normalized chat tool entries as the only source of spawned child IDs
  - do not mark `not_found` as completed/final in the DB or UI interruption guard
  - do not count stale Codex `open` edges as active when the VK parent execution is already completed and the child has not updated after parent completion
  - do not let a stale persisted VK `running` row outrank a Codex-proven completed child edge for the same agent ID
  - verify with `cargo test -p db not_found_subagent_status_remains_recoverable` and `cargo test -p services raw_codex_spawn_agent`
- Queued follow-up state must not regress:
  - do not rely on a missed completion/websocket event as the only way to clear `queued`
  - keep queue-status polling active while status is `queued`
  - reject/cancel queue creation if there is no running queue consumer for that session
  - consume queued follow-ups before finalizing skipped-cleanup/no-op coding-agent runs
  - keep normal finalization, skipped-cleanup finalization, and parallel-setup completion on the shared queued-follow-up helper
  - keep the `ops:check` source guard that fails when these queue consumption paths disappear
  - verify the frontend stale-running reconciliation is deployed so a terminal backend process does not leave the composer in in-progress mode
- Codex active execution limit must not regress:
  - source fallback must stay above one, currently `DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS = 8`
  - live systemd runtime guardrails must include `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8`
  - run `pnpm run ops:check` before restart/deploy; it fails if the source default or runtime docs lose this guard
- Codex resume must not regress:
  - do not maintain a manual request-variant allowlist for request IDs
  - use the upstream protocol `ClientRequest::id()` so `ThreadResume` and future request variants cannot panic the executor
  - keep `cargo test -p executors` green before restart/deploy
  - do not restart while queued messages exist unless they have been captured and can be replayed, because the queue is in-memory
  - verify with `cargo test -p db queue_consumer_requires_running_non_dropped_follow_up_process`
- Agent chat image rendering must not regress:
  - read-only chat markdown must render `.vibe-attachments/...` image references inline
  - editable composer state must keep compact chips and not replace pending attachments with full inline images
  - preserve the existing image preview and download behavior
  - keep the generated workspace root `AGENTS.md`/`CLAUDE.md` instruction so agents know how to produce inline chat images
- Workspace Pin/Unpin must not regress:
  - do not decide the next pinned value from cache-only workspace state
  - sidebar-targeted command labels must query the effective workspace record, not the currently selected workspace or a stale cache entry
  - after updating pinned state, update the host-scoped workspace record cache and invalidate workspace summaries so the sidebar and command label agree

## Next Safe Steps

1. Rebuild the attachment/frontend fixes from a clean worktree so unrelated project-list UI changes cannot ship again.
2. Raise local VK attachment limit to `100 MB` in both backend and frontend, then deploy only after backup/restart approval.
3. Promote the clean attachment fixes through a clean branch/PR into `staging`.
4. Land the needs-attention server summary-cache invalidation and deploy it with the next approved backend restart.
5. Deploy the sub-agent sidebar indicator fix with the next approved backend restart, then verify against a workspace with open Codex `thread_spawn_edges`.
6. Backfill broader current live `subagent_jobs` rows from Codex `thread_spawn_edges` only after confirming the desired scope; Halley alone was backfilled as a minimal no-restart mitigation.
7. Implement PR snapshot/reconcile/backfill as a separate concern.
8. Verify every feature against live UI/API before production promotion.
9. Rework and redeploy the queued follow-up fix only from a clean minimal build after the event-stream crash is understood; do not reuse the 2026-05-11 dirty checkout asset swap.
10. Deploy manual workspace unread with the next approved backend restart and frontend asset release, then verify that a selected workspace can be marked unread and that the workspace/project needs-review marker returns.
11. Turn the live regression smoke list into an executable script or Playwright check so repeated UI regressions are blocked before deployment instead of rediscovered by the user.
12. Build and deploy the issue needs-review flag after frontend dependencies are restored; include backend restart only when local fallback persistence should go live too.
