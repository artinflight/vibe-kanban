# HANDOFF.md

## 2026-06-26 Multi-Line Rich Clipboard Paste Hotfix Live

- User reported VK chat paste again only inserted content up to the first line.
- Root cause: `PasteMarkdownPlugin` already handled multiline `text/plain`, but it returned early whenever `text/html` existed. Mobile browsers and document apps commonly put both `text/plain` and `text/html` on the clipboard, so Lexical's HTML paste path could take over and drop content after the first line.
- Source change:
  - `packages/ui/src/components/PasteMarkdownPlugin.tsx` now detects multiline `text/plain` before the HTML opt-out and inserts it with `selection.insertRawText(...)`.
  - Single-line rich HTML paste keeps the previous default Lexical behavior.
- Live no-restart frontend hotfix:
  - copied current live release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260618Tbranch-search`
  - patched only the compiled paste handler in the copied release
  - published `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260626Tmultiline-rich-paste`
  - live asset `/assets/index-DXMultilinePaste.js`
  - asset sha256 `bdbd9860c6a240e1256dabc8715d42ab4b96c8f1c098d6e283f3d2bdd972f268`
  - switched `frontend-dist/current` to the new release; no VK restart was performed
- Validation:
  - `pnpm --filter @vibe/ui run check`
  - targeted `git diff --check`
  - live `curl` confirms `/` references `/assets/index-DXMultilinePaste.js`
  - live asset contains new multiline rich-clipboard guard `u&&!d?!1` and `if(d){f.insertRawText(c);return}`
  - live `python3 scripts/vk_live_regression_smoke.py` passed after updating expected active project order to current live data (`matchSubs`, `BBinvoice`, `DeNest` are now active before the prior list)
- Important deploy note:
  - next proper frontend build must include the source `PasteMarkdownPlugin.tsx` fix, not just the compiled asset patch
  - do not roll `frontend-dist/current` back behind `20260626Tmultiline-rich-paste`

## 2026-06-21 Project Sidebar Flyout / Customization Prepared

- User asked for the left project rail to reveal full project names via a triangle flyout and to support project rename, abbreviation edits, and pastel project button colors.
- Source change prepared, not deployed:
  - `packages/ui/src/components/AppBar.tsx` adds a triangle flyout beside the narrow project rail, shows full project names, and adds an edit dialog with name, 1-3 character abbreviation, and pastel color picker.
  - `packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx` wires local/remote project display overrides into the AppBar and persists abbreviation/color in UI preferences scratch.
  - `crates/server/src/routes/projects.rs`, `crates/db/src/models/project.rs`, and `packages/web-core/src/shared/lib/api.ts` allow local project rename through the existing project update route while preserving archive updates.
  - `crates/db/src/models/scratch.rs`, `crates/server/src/bin/generate_types.rs`, `shared/types.ts`, `useUiPreferencesStore.ts`, and `useUiPreferencesScratch.ts` add `local_project_customizations`.
- Deployment boundary:
  - frontend asset release is needed before the flyout/edit UI appears in live `vibe.local`.
  - backend build/restart is needed before local project rename works live.
  - do not deploy the old `20260612TissueReviewFlag` frontend; rebuild forward from at least the current live `20260618Tbranch-search` release so branch search and all prior frontend hotfixes stay present.
- Validation completed:
  - `pnpm install --offline --frozen-lockfile`
  - `pnpm run generate-types`
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `cargo check -p server`
  - `cargo test -p server routes::projects::tests`
  - targeted `git diff --check` for touched project-customization files
- Existing warnings during Rust validation were unchanged: `db::SqlitePool`, `services::events::scratch::Scratch`, and local-compat dead-code warnings.
- Operational note: no VK restart, no frontend symlink switch, and no live deploy were performed.
- Space note: after the outage/resume, root had previously filled during type generation; rebuildable `/home/mcp/_vibe_kanban_repo/target` and stale worktree `node_modules` older than four days were removed before dependencies were restored from the pnpm offline store.

## 2026-06-18 Branch Base Search Hotfix Live

- User reported workspace creation base-branch typing only matched exact branch substrings, making slash-heavy branch names hard to find.
- Deployed no-restart frontend release:
  - release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260618Tbranch-search`
  - asset: `/assets/index-CCBiSGB0.js`
  - asset sha256: `47a882a77d1d918006b7536e449927a72292b37fbc3299d513c43ff918bcf0dd`
  - backend PID stayed `3435842`; no VK restart was performed
- Source changes:
  - `packages/ui/src/components/CommandBar.tsx`
  - `packages/web-core/src/shared/components/tasks/BranchSelector.tsx`
  - branch matching now tolerates separators and token searches, e.g. `program gen` can match `codex/program-generation-v3-llm-first`
- Validation:
  - clean worktree `/tmp/vk-frontend-branch-search-20260618`
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `git diff --check`
  - `pnpm --filter @vibe/local-web run build`
  - live `python3 scripts/vk_live_regression_smoke.py` passed
- Important deploy note:
  - a first candidate rebuilt only from the live manifest commit missed existing live hotfix markers and was rolled back before smoke passed
  - future frontend releases must verify marker coverage before swapping `frontend-dist/current`
  - next restart package must not roll frontend back to `20260612TIssueReviewFlag`; rebuild/merge forward so it includes at least `20260618Tbranch-search`

## 2026-06-12 Restart Candidate Refreshed With Issue Flag

- User asked to get back to the restart-ready point with the project Kanban issue review flag included.
- No VK restart was performed, and the live frontend pointer was not switched.
- Clean restart candidate:
  - worktree: `/home/mcp/vk-restart-candidate-20260611T112143Z`
  - branch: `deploy/restart-candidate-20260611T112143Z`
  - commit: `a055ce585b7b682dba53b5c99860f023f32e3ed3`
- Staged restart package:
  - package dir: `/home/mcp/vk-restart-staging-20260612TissueReviewFlag`
  - backend binaries: `bin/vibe-kanban-serve` and `bin/vibe-kanban-serve-prod`
  - backend sha256: `32cebd5835faeae2007905e5b15593097699d735e8b7d0ea93020a4375238ed9`
  - installed next-restart binaries at `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod` have the same sha256
  - frontend release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260612TissueReviewFlag`
  - frontend asset: `/assets/index-DA7R5Mdm.js`
  - frontend asset sha256: `aa7021c20affeaae6eea6fc6715bf66d45da0a9d21fa58e8ba8cdf4ddaccf262`
  - release manifest: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260612TissueReviewFlag/RELEASE_MANIFEST.txt`
- Validation completed from the clean candidate:
  - `pnpm install --offline --frozen-lockfile`
  - `cargo fmt --check`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `cargo test -p server local_issue_flags_metadata_round_trips`
  - `SQLX_OFFLINE=true cargo build --release --bin server`
  - `pnpm --filter @vibe/local-web run build`
  - staged marker checks found `Mark needs review`, `vk_flags`, `needs_review`, `Local Issue Flags`, `wait_for_capacity`, and `VK_CODEX_MAX_ACTIVE_EXECUTIONS`
- Existing warnings observed:
  - Rust: existing `db::SqlitePool`, `services::events::scratch::Scratch`, `services::remote_client` `unused_mut`, and local-compat dead-code warnings
  - Frontend build: existing Browserslist/Tailwind/dynamic-import/chunk-size/Sentry warnings
- Current live state after staging:
  - `vibe-kanban.service` remained active on PID `3435842`
  - live frontend pointer still resolves to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`
  - restart is currently blocked by one active agent: workspace `FR::ORC::Generative Programming`, branch `codex/program-generation-v3-llm-first`, prompt `Proceed`, unit `vk-exec-codex-412d6a0806a5448ea3a0b7827f2dbc6e.service`
- Remaining restart window steps:
  1. Recheck active agents with `systemctl --user list-units 'vk-exec-*' --state=running --no-legend` and the DB `execution_processes` running count.
  2. If the active FR generative-programming agent is still running, wait or get explicit operator approval before restarting.
  3. Switch frontend pointer: `ln -sfn /home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260612TissueReviewFlag /home/mcp/.local/share/vibe-kanban/frontend-dist/current`.
  4. Restart: `systemctl --user restart vibe-kanban.service`.
  5. Verify `/api/info`, `/assets/index-DA7R5Mdm.js`, backend sha `32cebd5835faeae2007905e5b15593097699d735e8b7d0ea93020a4375238ed9`, runtime env, and `python3 scripts/vk_live_regression_smoke.py`.

## 2026-06-12 Issue Needs-Review Flag Prepared

- User asked for a quick project Kanban action to flag an issue for review, similar to the unread notification marker, with the flag sitting beside the priority marker.
- Source change prepared, not deployed:
  - `packages/ui/src/components/KanbanCardContent.tsx` renders a compact flag button beside the priority control.
  - `packages/web-core/src/features/kanban/ui/KanbanContainer.tsx` toggles `vk_flags.needs_review` in `Issue.extension_metadata` through the normal `updateIssue` mutation.
  - `crates/server/src/routes/local_compat.rs` now preserves local fallback issue flags by storing enabled flags in task description metadata as `Local Issue Flags`.
- Intended behavior:
  - clicking the flag on a Kanban card toggles `needs_review`
  - active state uses a filled warning-colored flag icon
  - the flag is not a tag and does not change issue priority
- Validation so far:
  - `cargo fmt`
  - `git diff --check -- packages/ui/src/components/KanbanCardContent.tsx packages/web-core/src/features/kanban/ui/KanbanContainer.tsx crates/server/src/routes/local_compat.rs`
  - `cargo test -p server local_issue_flags_metadata_round_trips` passed after a cold dependency rebuild; existing unrelated warnings were `db::SqlitePool`, `services::events::scratch::Scratch`, and local-compat dead code.
- Not validated yet:
  - frontend typecheck/build, because `node_modules` is currently absent after disk cleanup
  - live UI behavior, because no frontend release was built/swapped and no VK restart was performed

## 2026-06-11 Restart Candidate Built / Targeted Backup Complete

- User asked to prepare the VK restart package and backup, then stop before the actual restart.
- No VK restart was performed.
- Clean restart candidate:
  - worktree: `/home/mcp/vk-restart-candidate-20260611T112143Z`
  - branch: `deploy/restart-candidate-20260611T112143Z`
  - commit: `2a32636534c6365452777f6d67f3b64583180160`
  - candidate commit contains the current prepared VK fixes from the canonical dirty checkout plus `VK_AGENT_DEPLOYMENT_RUNBOOK.md`; `.vk-preview/` was intentionally excluded.
- Backend package:
  - release build command: `CARGO_TARGET_DIR=/home/mcp/_vibe_kanban_repo/target cargo build --release --bin server`
  - staged package: `/home/mcp/vk-restart-staging-20260611T112143Z`
  - installed next-restart binaries:
    - `/home/mcp/.local/bin/vibe-kanban-serve`
    - `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - installed binary sha256: `fcf8832cf5a53bf67042661bd314774cfcfeaa687e458c237aeef1648004d582`
  - running VK process is still old PID `3435842`; it will not use the installed binary until service restart.
  - binary marker checks found: `Codex execution limit reached`, `VK_CODEX_MAX_ACTIVE_EXECUTIONS`, `ThreadResume`, `Local Sort Order`, `wait_for_capacity`, `ntfy`, and `unread`.
- Frontend package:
  - build command: `pnpm --filter @vibe/local-web run build`
  - staged release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260611Trestart-candidate`
  - staged asset: `/assets/index-Bm8ag4JP.js`
  - staged asset sha256: `b2a3ab5030a8a15904b2742be2ebd9252cdcdd6cfd704a198e2d18e079264715`
  - release manifest: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260611Trestart-candidate/RELEASE_MANIFEST.txt`
  - live frontend pointer was not switched; it still points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`.
  - staged asset marker checks found: `vk-executor-config-selection`, `mobile-archived-projects`, `insertRawText`, `queued`, `Mark unread`, `Rename`, `Archive`, and `copy`.
- Backup:
  - stock `scripts/vk_lean_backup.py --mirror-desktop` was attempted with a lower preflight threshold, but it ballooned to roughly `40G` staged because current live sessions/Codex state are much larger than the 2026-06-03 backup; it was stopped before filling disk and only the incomplete `.tmp` backup was removed.
  - successful targeted restart-restore backup:
    - local dir: `/home/mcp/backups/vk-targeted-restart-restore-20260611T123534Z`
    - local tar: `/home/mcp/backups/vk-targeted-restart-restore-20260611T123534Z.tar.gz`
    - Desktop tar: `desktop:B:/vk-backups/vk-targeted-restart-restore-20260611T123534Z.tar.gz`
    - sha256: `af5f3380ae4648a19cef910985944dc2cf8d7964d81b2947a781deb16c9d195d`
    - Desktop verification showed the archive and `.sha256` in `B:\vk-backups`.
  - targeted backup scope: live SQLite backup, live config/signing key, systemd service/drop-ins, current live binaries, current frontend release pointer and release copy, staged frontend release, staged backend binaries, candidate/canonical source metadata and diff, active execution/session logs, and matching VK Codex continuity files for active thread IDs.
- Cleanup performed to make space:
  - removed rebuildable `/home/mcp/_vibe_kanban_repo/target` after staging the backend binary
  - removed one stale worktree `node_modules` older than four days
  - removed rebuildable Node/npm/Rust/Gradle caches and temporary Android QA/download/screenshot artifacts
  - did not remove VK DB, VK sessions, VK Codex state, registered worktrees, or completed backup artifacts.
- Remaining restart window steps:
  - final readiness check during this handoff showed VK still running on PID `3435842`, `4` running `vk-exec-*` units, `4` non-dropped DB rows with `status='running'`, installed binary sha `fcf8832cf5a53bf67042661bd314774cfcfeaa687e458c237aeef1648004d582`, live frontend still on `20260608Tmode-persistence`, staged frontend ready at `20260611Trestart-candidate`, and `/home/mcp` at about `35G` free / `85%` used.
  1. Recheck active agents: `systemctl --user list-units 'vk-exec-*' --state=running --no-legend` and DB `execution_processes where status='running' and dropped=0`.
  2. If active agents remain, wait or ask the operator before restarting.
  3. Switch frontend pointer: `ln -sfn /home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260611Trestart-candidate /home/mcp/.local/share/vibe-kanban/frontend-dist/current`.
  4. Restart: `systemctl --user restart vibe-kanban.service`.
  5. Verify `/api/info`, live frontend asset, installed binary sha, runtime env, and `python3 scripts/vk_live_regression_smoke.py`.

## 2026-06-11 Codex Capacity Queue Fix Prepared

- User reported direct chat sends fail with a red error when the global Codex execution cap is full: `Codex execution limit reached: 8 active, limit 8`.
- Desired behavior: the message should be accepted as queued and start automatically when any Codex slot opens, instead of failing the composer send.
- Source change prepared, not deployed:
  - `ExecutorError::ExecutionLimitReached` is now a typed error, not only an `I/O error` string.
  - Codex capacity checks return the typed error before process spawn.
  - `ContainerService::start_execution` preflights coding-agent Codex capacity before creating a visible execution row; if a late spawn still hits the limit, it soft-drops the placeholder process instead of writing a red stderr failure log.
  - `POST /api/sessions/:id/follow-up` catches the typed capacity error, stores the prompt in `QueuedMessageService::queue_for_capacity`, tracks `follow_up_queued_for_capacity`, and returns a typed queued status.
  - `LocalContainerService` drains the oldest capacity-waiting queued message after any process completion.
  - Frontend send hooks treat that typed queued response as successful, refresh queue/workspace summaries, and clear the composer without showing the red send error.
  - `shared/types.ts` was regenerated; `QueuedMessage` now includes `wait_for_capacity`.
- Important implementation note:
  - existing per-session queues are still in-memory; this fix uses the same in-memory queue service and does not make queued prompts restart-durable.
  - this covers workspace chat follow-up sends, including the new-session path that creates a session then calls follow-up. Direct workspace create-and-start routes were not changed in this pass.
  - backend build/restart is required before live VK gets this behavior; no VK restart was performed for this work.
- Validation completed:
  - `pnpm run generate-types`
  - `cargo test -p services takes_oldest_capacity_queue_without_consuming_normal_queue`
  - `cargo check -p services -p local-deployment -p server`
  - `pnpm --filter @vibe/web-core run check`
- Existing unrelated warnings observed during Rust validation:
  - `db` unused import `SqlitePool`
  - `services::events` unused import `scratch::Scratch`
  - `server::routes::local_compat` dead-code warnings for older local-compat paths

## 2026-06-11 Kanban Card Reorder Fix Prepared

- User reported cards reordered within a Kanban column bounce back.
- Findings:
  - frontend `KanbanContainer` discarded within-column drops unless the current view was already sorted by `sort_order`
  - local fallback boards deserialize issue create/update payloads through narrowed local structs that omitted `sort_order`
  - local fallback issue rows are backed by `tasks`, and `list_fallback_issues` derived `sort_order` from issue number, so even successful optimistic drags reverted on the next sync
- Source change prepared, not deployed:
  - any Kanban card drag now switches the current project view to manual `sort_order asc` before applying the drag
  - local fallback create/update/bulk update request structs now accept `sort_order`
  - local fallback tasks persist manual order in the existing task description metadata as `Local Sort Order`
  - local fallback issue listing reads `Local Sort Order` back into `CompatIssue.sort_order`
- Deployment note:
  - frontend behavior can ship by asset release, but local fallback persistence requires backend build/restart
  - no VK restart was performed
- Validation completed:
  - `pnpm --filter @vibe/web-core run check`
  - `cargo test -p server local_sort_order_metadata_round_trips`
  - `cargo check -p server`

## 2026-06-08 Plan-to-Auto Mode Persistence Hotfix

- User reported sessions started in Plan mode kept snapping back to Plan after switching to Auto, especially across turns/remounts.
- Root cause:
  - the Codex executor already supports Auto correctly: `PermissionPolicy::Auto` sets `ask_for_approval = Never` and `plan = false`
  - the frontend follow-up path sends the current `executor_config`, but explicit user executor/mode overrides lived only in React state plus draft scratch
  - when a Plan-started session remounted, the draft cleared, or execution-process data refreshed, the UI could rebuild from the latest Plan process config and lose the user's explicit Auto selection
- Source change:
  - `packages/web-core/src/shared/hooks/useExecutorConfig.ts` now accepts `persistenceKey` and stores explicit executor/model/mode overrides in browser localStorage under `vk-executor-config-selection:*`
  - `packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx` keys the persisted selection by `sessionId` for existing sessions and `workspaceId` for new-session mode
  - `crates/executors/src/executors/codex.rs` has regression coverage proving Auto exits plan mode at executor override level
- Deployed without restarting VK:
  - build worktree: `/tmp/vk-frontend-mode-hotfix-20260608`
  - published refreshable release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`
  - live asset: `/assets/index-CTVtS8yb.js`
  - index sha256: `1b35a15ec2cb88ce9979a9b31f232f760ff7c621144ce0e824a5ed4362b539ca`
  - asset sha256: `4f4f28ac083d4817fbac125d267da194a7917b67e753ef19e5e21998f76d4ce1`
  - backend PID stayed `3435842`; no backend restart was performed
- Validation:
  - `pnpm --filter @vibe/web-core run check`
  - `cargo test -p executors codex_auto_permission_override_exits_plan_mode`
  - `pnpm run format`
  - clean worktree `pnpm install --offline --frozen-lockfile`
  - clean worktree `pnpm --filter @vibe/web-core run check`
  - clean worktree `pnpm --filter @vibe/local-web run build`
  - `python3 -m py_compile scripts/vk_live_regression_smoke.py`
  - `git diff --check`
  - live `python3 scripts/vk_live_regression_smoke.py` passed
- Live smoke note:
  - first smoke after the symlink switch caught a project baseline mismatch, not a frontend deploy regression
  - current live `/api/projects` already had `Iniandi` active and `caspian-app` archived with pre-hotfix `updated_at` values, so the smoke baseline was updated to the current live DB truth
- Important:
  - this release carries forward the 2026-06-04 multi-line paste hotfix and the 2026-06-03 mobile archive-nav hotfix
  - do not roll `frontend-dist/current` back behind `20260608Tmode-persistence`
  - future mode/executor UI work must preserve `vk-executor-config-selection` behavior and keep the live smoke marker

## 2026-06-04 Multi-Line Paste Hotfix

- User reported VK chat paste only inserted content up to the first line break.
- Root cause:
  - editable chat composers use `packages/ui/src/components/PasteMarkdownPlugin.tsx`
  - that plugin intercepted plain-text paste and sent all text through Lexical markdown import before inserting children from a temporary paragraph
  - multi-line prompt text can collapse/truncate through that markdown-import path, so prompts with line breaks lost content after the first break
- Source change:
  - multi-line plain text now uses `selection.insertRawText(plainText)`
  - single-line plain text still uses the existing markdown conversion path
  - the fix is intentionally scoped to paste behavior; no backend behavior changed
- Deployed without restarting VK:
  - build worktree: `/tmp/vk-frontend-paste-hotfix-20260604` (removed after release copy to avoid leaving another `node_modules` tree)
  - built command: `pnpm --filter @vibe/local-web run build`
  - published refreshable release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260604Tmultiline-paste`
  - live asset: `/assets/index-BOrQKfSR.js`
  - asset sha256: `33b5ce6faf4f76275c3ac1a21474d2b6b0a84c6e2d9a586f0baf803d1482caf9`
  - release manifest: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260604Tmultiline-paste/RELEASE_MANIFEST.txt`
  - backend PID stayed `3435842`; no backend restart was performed
- Validation:
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/local-web run build`
  - live `python3 scripts/vk_live_regression_smoke.py` passed
  - live smoke confirmed active/archived project order, default columns, mobile archive nav marker, queued marker, codeblock copy marker, rename marker, and `insertRawText` marker
- Important:
  - this release carries forward the 2026-06-03 mobile archive-nav hotfix; do not roll `frontend-dist/current` back behind `20260604Tmultiline-paste`
  - future paste work must preserve multi-line chat prompts as raw text unless the user explicitly asks for markdown transformation

## 2026-06-03 Mobile Archived-Projects Nav Hotfix

- User reported mobile navigation still showed `Export data` and did not show the archive entry.
- Root cause:
  - desktop left nav uses `AppBar` props with `showExportButton={false}` and `onOpenArchivedProjects`
  - mobile uses a separate hardcoded drawer in `SharedAppLayout.tsx`
  - that mobile drawer still rendered the old `Export data` row and never wired the archived-projects dialog
- Source change:
  - `packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx` now removes the mobile-only export row
  - the mobile drawer footer now shows `Archived projects` when archived projects exist and opens `ArchivedProjectsDialog`
  - the button carries `data-testid="mobile-archived-projects"` so the live smoke catches this path
- Deployed without restarting VK:
  - built command: `pnpm --filter @vibe/local-web run build`
  - published refreshable release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tmobile-archive-nav`
  - live asset: `/assets/index-CPHsMjmW.js`
  - asset sha256: `9cbb1b097ce79ebe4a9250945d2b9f4ed3e797ecb0fc8f173d090a31219f276d`
  - `frontend-dist/current` now points to the mobile archive release
  - backend PID stayed `3435842`; no backend restart was performed
- Validation:
  - staged bundle contained `mobile-archived-projects` plus existing hotfix markers: queue, unread/archive/rename/default-column/code-copy/sub-agent markers
  - live `python3 scripts/vk_live_regression_smoke.py` passed after updating the project archive baseline to current live `/api/projects`
  - live asset check confirms `https://vibe.local/` serves `/assets/index-CPHsMjmW.js`
- Note:
  - the string `Export data` still exists in the built bundle because the optional desktop `AppBar` export code remains compiled; the mobile drawer path no longer renders it
  - the current live project archive state is active: `CodexUsage`, `VL`, `LifeOS`, `Operations`, `OSTP`, `programming`, `intake-shield`, `caspian-app`, `hyroxready-app`, `VK Sub-Agent Monitor`

## 2026-06-03 Duplicate Project Cleanup / Pending Source Fix

- User reported duplicated projects in VK after the 2026-06-03 deploy.
- Live symptom:
  - real projects were visible: `foxtrot-lima`, `intake-shield`
  - stale synthetic projects were also visible: `FoxtrotLima`, `intakeShield`
- Root cause:
  - `/api/projects` combines real `projects` rows with synthetic projects derived from `PROJECT_REPO_DEFAULTS` scratch records
  - the previous dedupe only compared trimmed lowercase names, so it did not treat kebab-case and camel/Pascal-case variants as the same project
  - synthetic candidates also were not filtered by repo ownership, even though the duplicate synthetic rows pointed at repos already attached to real projects through `project_repos`
- Immediate live cleanup completed without restarting VK:
  - took SQLite backup: `/home/mcp/backups/vk-project-duplicate-scratch-cleanup-20260603T160156Z/db.v2.sqlite`
  - saved deleted payloads: `/home/mcp/backups/vk-project-duplicate-scratch-cleanup-20260603T160156Z/deleted-scratch-records.json`
  - deleted only two stale `PROJECT_REPO_DEFAULTS` scratch rows:
    - `7e139609-715c-4724-971a-ab986ce9ba79` (`FoxtrotLima`)
    - `59b947c5-7bb3-442e-bb7f-f752da7efcc4` (`intakeShield`)
  - live `/api/projects` now shows active count `14`
  - `FoxtrotLima` and `intakeShield` no longer appear
  - `foxtrot-lima` and `intake-shield` each appear exactly once
- Pending source fix staged for the next backend restart:
  - `crates/server/src/routes/projects.rs` now canonicalizes project names by removing non-alphanumeric characters for dedupe, so `foxtrot-lima` matches `FoxtrotLima` and `intake-shield` matches `intakeShield`
  - synthetic scratch projects are filtered out if any of their repo IDs already exists in `project_repos`
  - synthetic-only projects, such as `VK Sub-Agent Monitor`, are still retained
  - `scripts/vk_live_regression_smoke.py` was updated to expect the current duplicate-free active project list
- Validation:
  - live `/api/projects` duplicate check passed after scratch cleanup
  - `cargo test -p server routes::projects::tests` passed: 4 tests
- Important:
  - the source fix is not live until the next backend build/restart
  - do not re-add stale scratch rows to solve project defaults; restore only from the saved payload backup if the user explicitly asks
  - if `target/debug` was rebuilt by tests, it can be removed again as rebuildable cache after validation

## 2026-06-03 Restart Recovery / Queue / Backup Deployment

- User approved a restart only if workspace/agent progress is preserved and prior fixes do not regress.
- Active-agent check before cleanup/restart prep showed:
  - `systemctl --user list-units 'vk-exec-*' --state=running`: no running units
  - live DB non-dropped `running` execution rows: `0`
- Disk is critically low before cleanup: `/home/mcp` is at `98%` with about `5.6G` free.
- Backup requirement clarified by user:
  - use the efficient restore-grade backup, not a huge full copy
  - backup must be sufficient to restore VK DB/workspace state/agent continuity if restart goes sideways
  - mirror the backup off MCP to Desktop using the established desktop target
- Queue regression is in scope for this restart:
  - live symptom: queued messages do not reliably start when the agent finishes, and the workspace can keep looking in progress
  - source currently contains queue-consumption paths in normal finalization, skipped-cleanup/no-op finalization, and setup completion
  - source currently contains frontend queued-status polling and running-process reconciliation
  - restart/deploy must verify both backend queue consumption and frontend stale-running reconciliation are in the deployed package
- Required restart package contents:
  - `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8` runtime env
  - Codex resume panic fix using `ClientRequest::id()`
  - queued follow-up consumption before finalization
  - frontend running-process/queued-status reconciliation
  - previously staged unread/ntfy fixes
- Do not restart until:
  - rebuildable disk cleanup has created enough space
  - restore-grade backup exists locally and on Desktop
  - backup manifest/integrity checks pass
  - built backend/frontend artifacts are verified to contain the fixes above
  - active-agent check still shows `0`
- Restart package build completed:
  - backend build command: `cargo build --release --bin server`
  - backend artifact sha256: `c083178e5a75a5fefeb01f862dd668929be03fecaf08bb3749f77ca379ffec7f`
  - frontend build command: `pnpm --filter @vibe/local-web run build`
  - staged frontend release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`
  - staged frontend asset: `/assets/index-BLreFcjw.js`
  - staged frontend asset sha256: `8bb6029a2d1fd0e09c208afc1f558feae5646d66ce62ac790ce615c192ffb935`
  - release manifest: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active/RELEASE_MANIFEST.txt`
- Build artifact checks before install:
  - frontend asset contains queue/unread/archive/rename/default-column/code-copy/sub-agent guard strings
  - backend artifact contains `VK_CODEX_MAX_ACTIVE_EXECUTIONS`, `Codex execution limit reached`, queued-message, `ThreadResume`, unread, and ntfy strings
  - backend artifact does not contain the old `unsupported request variant` panic text
- Current live project order/archive snapshot was captured before restart and written into `scripts/vk_live_regression_smoke.py` so the smoke test detects archive/order regression against the actual current state.
- Deployment completed:
  - first restart activated the queue/resume/max-active/unread/ntfy package, but the smoke caught unstable active project ordering for synthetic projects
  - root cause of order churn: `crates/server/src/routes/projects.rs` appended synthetic projects by iterating `HashMap::values()`, so tied synthetic projects could appear in a different order on repeated `/api/projects` reads
  - follow-up source fix sorts synthetic projects deterministically by `updated_at DESC`, `name ASC`, then `id ASC`
  - added regression test `routes::projects::tests::synthetic_projects_have_stable_display_order`
  - final deployed backend sha256: `722a5b0d14ca2350661cdcd0a271ac2cfea980dae4f2dcafc55b8ffe9470ed75`
  - final live PID after restart: `3435842`
  - final live frontend release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`
  - final live frontend asset: `/assets/index-BLreFcjw.js`
  - final live env includes `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8`
  - both restart journals reported `Found 0 running processes to kill`
  - active execution checks remained `0` before/after restart
  - fake unread and queue-status requests returned `404`, not `405`, proving the routes exist
  - `scripts/vk_live_regression_smoke.py` passes after the order fix
  - eight repeated `/api/projects` reads returned the same active project order after the order fix
  - rebuilt `target/debug` was deleted after validation; disk recovered to about `39G` free / `83%` used
- Final validation:
  - `cargo test -p executors`
  - `cargo test -p server synthetic_projects_have_stable_display_order`
  - `cargo build --release --bin server`
  - `pnpm --filter @vibe/local-web run build`
  - `pnpm run format`
  - `pnpm run ops:check`
  - `git diff --check`
  - live `/api/info`
  - live frontend asset check
  - live env/hash check
  - `python3 scripts/vk_live_regression_smoke.py`
- Backup completed:
  - local restore archive: `/home/mcp/backups/vk-efficient-restore-20260603T004715Z.tar.gz`
  - Desktop restore archive: `desktop:B:/vk-backups/vk-efficient-restore-20260603T004715Z.tar.gz`
  - Desktop latest pointer archive: `desktop:B:/vk-backups/vk-efficient-restore-latest.tar.gz`
  - source-state tar on Desktop: `desktop:B:/vk-backups/vk-pre-restart-source-state-20260603T002809Z.tar.gz`
  - scope: 226 non-archived workspaces, 233 Codex thread IDs, 252 rollout files, DB snapshot, selected latest process logs, isolated Codex auth/config/state, systemd config, live binaries, frontend current release, source diff/untracked snapshot, and workspace git metadata/small untracked files
  - archive size: `405,891,419` bytes
  - archive entry count: `4923`
  - restore archive sha256: `92c9e5e0a557397a90c175cd33dcffee6092a105ed7c36d529443f7ad91a495c`
  - source-state archive sha256: `74df1f9dc0bf6ba4f4cf0687eb4d3fe8ec1c377778ffff16b7b0cf6a9722b401`
  - Desktop mirror was verified with `rclone ls desktop:B:/vk-backups` before restart prep

## 2026-06-02 Codex Active-Agent Limit Regression Repair

- User reported VK rejected new agents with: `Codex execution limit reached: 1 active, limit 1. Set VK_CODEX_MAX_ACTIVE_EXECUTIONS to override.`
- Finding: live `vibe-kanban.service` had one running `vk-exec-codex-*` unit and no `VK_CODEX_MAX_ACTIVE_EXECUTIONS` in its environment, so the executor fell back to the hardcoded default of `1`.
- Follow-up finding on 2026-06-03: the apparently hung `IS::UI Usability Pass` run was already killed in DB/systemd, and the live journal showed a backend panic at `crates/executors/src/executors/codex/client.rs:989`: `request_id called for unsupported request variant`. The failed run died before it established an agent session ID.
- Source repair:
  - changed Codex executor fallback to `DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS = 8`
  - parse helper now ignores invalid, zero, and negative env values
  - added unit coverage for the parser/default invariant
  - changed Codex client `request_id()` to use `ClientRequest::id()` so `ThreadResume` and future request variants do not panic
  - added regression coverage for `ThreadResume`
  - extended `pnpm run ops:check` so it fails if the source fallback or required runtime docs regress to single-agent mode
- Runtime repair:
  - persisted `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8` in `/home/mcp/.config/systemd/user/vibe-kanban.service.d/runtime-guardrails.conf`
  - ran `systemctl --user daemon-reload`
  - no VK restart was performed
- Validation:
  - `cargo test -p executors`
  - `pnpm run format`
  - `pnpm run ops:check`
  - `git diff --check`
- Important: the running VK process cannot see this env/source change until the next approved build and restart. After restart, verify `systemctl --user show vibe-kanban.service -p Environment` contains `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8`.

## 2026-06-01 FR::ORC::Generative Programming Codex Auth Repair

- User reported auth errors in VK workspace `FR::ORC::Generative Programming`.
- Workspace ID: `5a8066b0-c3ff-46d2-8953-f39a90ce3f0c`; branch `codex/program-generation-v3-llm-first`; worktree `/home/mcp/code/worktrees/5a80-fr-orc-generativ`.
- Latest process log showed repeated Codex ChatGPT auth failures: `refresh_token_reused`, `token_expired`, MCP startup 401, then a failed turn with no agent items. Do not print tokens from those logs.
- Root cause: VK's isolated `CODEX_HOME` auth at `/home/mcp/.local/share/vibe-kanban/codex-home/auth.json` was stale from `2026-05-21`, while interactive Codex auth at `/home/mcp/.codex/auth.json` had refreshed on `2026-06-01`.
- Fix applied without restarting VK:
  - backed up stale VK auth to `/home/mcp/backups/vk-auth/codex-home-auth-before-refresh-20260601T085017Z.json`
  - copied `/home/mcp/.codex/auth.json` into `/home/mcp/.local/share/vibe-kanban/codex-home/auth.json` with mode `600`
- Verification:
  - VK isolated auth sha now matches global Codex auth sha prefix `44c647618796`
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home codex login status` returns `Logged in using ChatGPT`
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home codex debug models` exits `0` and fetched the model catalog
- Existing failed turn remains failed/empty; the fix applies to the next VK Codex turn launched from that workspace.

## 2026-05-30 Canonical Unread / Ntfy Redeploy Correction

- User reported `Mark unread` returns `405` after the ntfy restart.
- Root cause: the deployed ntfy binary was built from `/tmp/vk-ntfy-turn-completion-20260528`, which had bounded ntfy but did not include the canonical manual unread backend route. The live frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin` calls `PUT /api/workspaces/:id/unread`, but the running backend only exposes `/seen`.
- Corrected canonical source now combines both required pieces:
  - `PUT /api/workspaces/:id/unread`
  - `CodingAgentTurn::mark_latest_unseen_by_workspace_id`
  - bounded queued ntfy publisher using `VK_TURN_COMPLETION_NTFY_*` with legacy `VK_NTFY_*` fallback
  - latest coding-agent final summary/profile label lookup for turn-completion notices
- Build/validation completed from `/home/mcp/_vibe_kanban_repo`:
  - `cargo fmt --check`
  - `cargo test -p services services::notification`
  - `cargo test -p db latest_workspace_turn_can_be_marked_unseen`
  - `cargo test -p db completed_coding_agent_turns_are_marked_unseen_by_uuid_blob`
  - `cargo build --release --bin server`
  - `git diff --check`
- A minimal compile fix was made in `crates/server/src/routes/projects.rs` for an existing dirty change that moved `repo` before computing `target_branch`.
- Corrected binary is staged at both installed paths with sha256 `1ca98fdffa8d2f172ab7d94cb513e3c79e26c6a179365963d1d581ac0e45ef1a`.
- Running VK process is still old sha256 `be377483fccfe825fe93b10c6cba848871018e0f01d892e85c43ee072d7d19ee`; the staged fix will not take effect until restart.
- Do not restart while active agents are running. Last check showed `3` running `vk-exec-*` units and `3` non-dropped running execution rows.
- Ntfy subscription auth:
  - server: `https://opntfy.fly.dev`
  - topic: `vk-workspace-turns`
  - anonymous subscribe returns `403`; bearer-token subscribe returns `200`
  - do not print the token in docs/chat; retrieve it locally from the systemd drop-in when needed

## 2026-05-28 VK Agent Deployment Docs

- User asked to update docs so agents inside VK can work on and deploy the VK repo without breaking or regressing anything.
- Added `VK_AGENT_DEPLOYMENT_RUNBOOK.md` as the single operational checklist for VK agents. It covers current live truth, clean worktree rules, frontend-only deploys, backend build/restart deploys, backups, active-agent checks, mandatory regression smoke, and known regression traps.
- Updated `AGENTS.md` required read order so VK agents read `VK_WORKFLOW.md` and `VK_AGENT_DEPLOYMENT_RUNBOOK.md` before code/deploy work.
- Updated `STATE.md` and `STREAM.md` with the 2026-05-28 live deployment facts:
  - service active on PID `4182076`
  - live binary sha `7c63eb8fa7b2b46f6567ef7f8606df1d7a794bb6685d14cd7bf951c531f00e46`
  - frontend pointer `/home/mcp/.local/share/vibe-kanban/frontend-dist/current -> /home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin`
  - live asset `/assets/index-BLn8oOcK.js`
  - one `vk-exec-codex-*` unit was running during verification
- Important: this was documentation-only. No build, frontend asset swap, restart, DB edit, or live deploy was performed.
- Current canonical checkout still has unrelated dirty source files; future agents must not deploy from it while dirty.

## 2026-05-14 Workspace Unpin Repair

- User reported pinned workspaces could not be unpinned.
- Release manifest:
  - source commit: `b12a238a230df1df9f4c92d15be147f650d2d93d`
  - build worktree: `/home/mcp/_vibe_kanban_repo`
  - frontend release path: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin`
  - frontend asset: `/assets/index-BLn8oOcK.js`
  - frontend asset sha256: `25732813002c090ba72e414bd5e3102a48f12f09c61690f2b1a64999bec8d52b`
  - backend binary sha256: `251d51ca5e831775768339c45addc6488b5298a138594accb944782db7dcc6a0`
  - backend PID after frontend swap: `913128`
  - expected retained features: archived-project separation/order, archived-project access, issue workspace Rename/Archive/Unarchive tokens, codeblock copy token, queued-state token, default project column template, and workspace pin/unpin
- Root cause:
  - the workspace action label and toggle path used cached `workspaceRecord` data for sidebar-targeted workspaces
  - after pinning, that cache could still say `pinned: false`
  - clicking `Unpin` then sent `{ pinned: true }` again, so the UI appeared to do nothing
- Source repair:
  - `PinWorkspace.execute` fetches fresh workspace state with `workspacesApi.get(workspaceId)` before toggling
  - the update response is written back into the host-scoped workspace record cache
  - workspace invalidation now targets the host-scoped record key and workspace summaries
  - `CommandBarDialog` uses `useWorkspaceRecord` for the effective target workspace instead of cache-only `getQueryData`, so Pin/Unpin labels refresh for sidebar actions
- Deployed live without restarting VK in frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin`.
- Live `GET /` references `/assets/index-BLn8oOcK.js`; backend PID stayed `913128`.
- Live API validation toggled pinned state on workspace `407b575b-ec65-4b39-8a6b-23d2595c9c05` (`IS::Main`) from `true` to `false` to `true` and restored the original value.
- Validation passed:
  - `pnpm run format`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm --filter @vibe/local-web run build`
  - `python3 -m py_compile scripts/vk_live_regression_smoke.py`
  - `git diff --check`
  - live asset returned `200`
  - `python3 scripts/vk_live_regression_smoke.py`

## 2026-05-13 Default Project Columns Repair

- User reported default columns for new projects disappeared.
- Release manifest:
  - source commit: `871b910b926778d1643cd54b5c49444b90c175bc`
  - build worktree: `/home/mcp/_vibe_kanban_repo`
  - frontend release path: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tdefault-project-columns`
  - frontend asset: `/assets/index-DiSUCc_7.js`
  - frontend asset sha256: `f2c0fbc14c9610c8f39867da18dcd9bcd6791cb54e76dbca9a0912a6379721dd`
  - backend binary sha256: `251d51ca5e831775768339c45addc6488b5298a138594accb944782db7dcc6a0`
  - backend PID after frontend swap: `913128`
  - expected retained features: archived-project separation/order, archived-project access, issue workspace Rename/Archive/Unarchive tokens, codeblock copy token, queued-state token, and default project column template
- Root cause:
  - frontend project repo-default saves could create or preserve `PROJECT_REPO_DEFAULTS` rows with `statuses: []`
  - backend local fallback still used the old five-column template when a project had no saved status config
  - result: new or empty-config projects could show only `To do`, `In progress`, `In review`, `Done`, and hidden `Cancelled`
- Operator default template is now documented and guarded: `To do`, `In progress`, `On Hold`, `Long Running`, `In review`, hidden `Cancelled`, `To merge`, `In Staging`, `Hotfix Path`, `Done`.
- Live DB repair:
  - took backup `/home/mcp/backups/vk-pre-default-columns-fix-20260513T221338Z.sqlite`
  - backfilled full status templates for `CodexUsage`, `Monitor local`, `LifeOS`, and `Operations`
  - verified live `/v1/fallback/project_statuses` returns the full ten-column template for all four projects
- Source repair:
  - `packages/web-core/src/shared/hooks/useProjectRepoDefaults.ts` seeds/saves the full status template instead of `[]` when repo defaults are created or repaired
  - `crates/server/src/routes/local_compat.rs` uses the same operator template for empty local status configs
  - added local compat tests for the default status list and empty-config fallback
- Deployed live without restarting VK in frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tdefault-project-columns`.
- Live `GET /` references `/assets/index-DiSUCc_7.js`; backend PID stayed `913128`.
- Backend fallback source fix is not live until the next approved backend restart, but the repaired live DB rows and frontend guard cover the reported disappearing-column path now.
- Validation passed:
  - `pnpm run format`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm --filter @vibe/local-web run build`
  - `cargo test -p server local_default_statuses`
  - `cargo test -p server routes::local_compat::tests`
  - `git diff --check`
  - live asset returned `200` and contains `Long Running` / `Hotfix Path`
  - `python3 scripts/vk_live_regression_smoke.py`

## 2026-05-13 Live Regression Smoke Script

- Added read-only smoke script `scripts/vk_live_regression_smoke.py`.
- Current checks:
  - `frontend-dist/current` points at `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260514Tworkspace-unpin`
  - live HTML references `/assets/index-BLn8oOcK.js`
  - backend service has a nonzero PID
  - live asset contains guard tokens for default columns, archived projects, Rename/Archive/Unarchive, codeblock copy, and queued state
  - active project order is `CodexUsage | VL | Monitor local | LifeOS | Operations | programming | ops-playbook | intake-shield | foxtrot-lima | hyroxready-app`
  - archived project order is `Monitor | OSTP | virtualCard | Champions Nutrition | caspian-ova-dashboard | vibe-kanban | vibe-kanban-orchestrator | caspian-app`
  - `CodexUsage`, `Monitor local`, `LifeOS`, and `Operations` return the full default column template from `/v1/fallback/project_statuses`
- Result on 2026-05-14: all checks passed.
- Limit: this is a read-only API/static-asset smoke, not a full Playwright UI interaction test; Playwright is not installed in this checkout.

## 2026-05-13 Agent Chat Image Sharing

- User asked whether agents can share images directly in chat.
- Source fix:
  - read-only chat markdown now renders image references as inline images instead of compact attachment chips
  - editable composer attachment chips keep the existing compact behavior
  - workspace-local image paths are resolved through the existing attachment metadata/file routes, so no new backend endpoint was needed
  - click opens the existing image preview; the inline image also keeps a download action
- Agent workflow:
  - create the image file inside the workspace/session under `.vibe-attachments/`
  - include normal markdown in the assistant reply, for example `![caption](.vibe-attachments/example.png)`
  - the chat renderer will display the image inline after refresh/live asset load
- Agent instruction source:
  - `LocalContainerService::create_workspace_config_files` now writes a small VK workspace section into generated root `AGENTS.md` and `CLAUDE.md`
  - the section tells agents to save generated chat images under `.vibe-attachments/` and reference them with markdown image syntax
  - existing generated import-only workspace config files are upgraded in place; custom root config files are left untouched
  - this generator change is source-only until the next approved backend restart
- No-restart operational backfill:
  - updated 149 existing generated root workspace config files under `/home/mcp/code/worktrees/*/{AGENTS.md,CLAUDE.md}`
  - skipped 9 files that were custom or unreadable
  - repo-local `AGENTS.md`/`CLAUDE.md` files were not touched
- Deployed live without restarting VK in frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tagent-chat-images`.
- Live `GET /` references `/assets/index-D0-81B_L.js`; backend PID stayed `913128`.
- Validation passed:
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `cargo test -p local-deployment workspace_config`
  - `git diff --check`
  - `pnpm --filter @vibe/local-web run build`
  - live asset returned `200` and contains the inline image classes

## 2026-05-13 Queue Regression Repaired In Source

- User reported queued follow-ups regressed again.
- Root cause: historical fix `f8524d79f` was present in git history but its behavior had disappeared from current `crates/local-deployment/src/container.rs`.
- Broken path:
  - when a coding-agent run made no changes, VK skipped the cleanup action
  - that bypass path finalized the task immediately
  - it did not consume an already queued follow-up first
  - result: queued prompt could remain queued and never start
- Source repair:
  - restored a shared `consume_queued_follow_up` helper
  - normal finalization, skipped-cleanup finalization, and parallel-setup completion all use the same queued-follow-up consumption path
  - skipped-cleanup finalization now starts queued follow-up before finalizing the completed turn
  - `scripts/check-ops-playbook.mjs` now fails `pnpm run ops:check` if the three required queue consumption paths disappear again
- Validation passed:
  - `pnpm run format`
  - `pnpm run ops:check`
  - `cargo check -p local-deployment`
- Not deployed live yet. This is backend runtime behavior and requires a backend build/restart after explicit approval.
- Live caution: queued follow-ups are currently in-memory. Before any restart, capture live queued messages from `/api/sessions/:id/queue` and replay or preserve them intentionally; otherwise a restart can drop queued prompts.

## 2026-05-13 Regression Prevention Gate

- User asked what must change so fixed VK features stop disappearing after later work.
- New rule written to `STATE.md` and `STREAM.md`: no deploy, restart, or frontend asset swap may be called ready without a release manifest and recorded regression smoke result.
- The manifest must name the exact source commit, build worktree, release path, frontend asset hash, backend binary hash when applicable, and the full expected feature set.
- The mandatory smoke list now includes the recurring regressions:
  - active/archived project count and order
  - intended left-nav actions and archive access
  - issue-view workspace menu actions, including Rename and Archive/Unarchive
  - project-scoped repo defaults
  - needs-review marker behavior
  - collapsed Kanban mobile layout and counts
  - Kanban drag persistence
  - queued follow-up reconciliation
  - workspace action menu completeness and spin-off
  - direct issue status selector
  - codeblock copy and attachment feedback
- Practical requirement: repeated regressions need automated coverage or a scripted smoke check before the next related deploy; documentation alone is not enough.

## 2026-05-13 Issue Workspace Archive + Project Repo Defaults

- User requested two fixes:
  - issue-view workspace cards need an Archive/Unarchive action in the three-dot menu
  - creating a workspace from an issue inside a project must default to that project's repo, not the globally most recent repo
- Source fix:
  - `IssueWorkspaceCard` now renders Archive/Unarchive beside Rename/Unlink/Delete when the card resolves to a local workspace owned by the current user.
  - `IssueWorkspacesSectionContainer` toggles `workspacesApi.update(workspaceId, { archived })`, invalidates workspace summary/list caches, and refreshes issue workspace links.
  - `workspaceDefaults` now tries project repo association defaults before project-local recency.
  - `workspaceDefaults` no longer falls back to the globally most recent workspace when a `projectId` is known; that global fallback is allowed only for non-project create flows.
  - frontend fallback can infer a repo when project name/default working dir exactly matches one repo name/display/path basename/default working dir, which covers `intake-shield` -> `intakeShield`.
  - backend route `GET /api/projects/:project_id/repos` is implemented for permanence, using scratch repo defaults first and then `project_repos`; it requires a future approved backend restart to be live.
- Deployed live without restarting VK in frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tissue-workspace-archive-repo-defaults`.
- Live `GET /` references `/assets/index-DSo-m_0N.js`; backend PID remained `913128`.
- Validation passed:
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `cargo check -p server`
  - `pnpm run format`
  - `pnpm --filter @vibe/local-web run build`

## 2026-05-13 Issue View Workspace Rename

- User requested a Rename option in the three-dot menu for workspaces shown inside an issue view.
- Source fix:
  - `IssueWorkspaceCard` now supports an `onRename` action and renders a pencil-icon `Rename` item in the existing workspace card menu.
  - `IssueWorkspacesSection` passes the rename action only for linked local workspaces owned by the current user, matching the existing open/delete ownership behavior.
  - `IssueWorkspacesSectionContainer` opens the existing `RenameWorkspaceDialog`, calls `workspacesApi.update(workspaceId, { name })`, invalidates workspace caches, and dispatches the project workspace refresh event so the issue view updates without a page reload.
  - issue workspace cards prefer the resolved local workspace name when a local workspace is linked, so local fallback project rows show the new name immediately after rename.
- Deployed live without restarting VK in frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tissue-workspace-rename`.
- Live `GET /` references `/assets/index-D2W033ux.js`; that JS contains the rename action and cache invalidation wiring.

## 2026-05-13 Scaleway CLI / SSH Setup

- Installed Scaleway CLI `scw` version `2.55.0` to `/home/mcp/.local/bin/scw`.
- CLI config lives at `/home/mcp/.config/scw/config.yaml` with `0600` permissions. Do not print or commit this file; it contains the Scaleway secret key.
- Configured default project/organization `cd72c9f8-12c2-4e5b-925d-94da82c9606d` (`fitRDY`), default region `fr-par`, and default zone `fr-par-1`.
- Verified auth with `scw account project list`; it returned project `fitRDY`.
- Registered existing SSH public key `/home/mcp/.ssh/id_ed25519_mcp.pub` with Scaleway IAM:
  - key name `mcp-server-id_ed25519_mcp`
  - key ID `d980864c-f353-4b3a-a4e7-ff9fc9d766be`
  - project ID `cd72c9f8-12c2-4e5b-925d-94da82c9606d`
- SSH local setup:
  - `~/.ssh` set to `0700`
  - `~/.ssh/id_ed25519_mcp` set to `0600`
  - `~/.ssh/id_ed25519_mcp.pub` set to `0644`
  - backed up SSH config to `/home/mcp/.ssh/config.bak.scaleway-20260513T112056Z`
  - added `Include scaleway.config` to `/home/mcp/.ssh/config`
  - generated `/home/mcp/.ssh/scaleway.config`
- There were no Scaleway instances in the default project at setup time, so `/home/mcp/.ssh/scaleway.config` is currently empty. After creating instances, rerun:
  - `scw instance ssh install-config zone=all`
- Validation passed:
  - `scw version`
  - `scw info`
  - `scw account project list`
  - `scw iam ssh-key list`
  - `scw iam ssh-key get d980864c-f353-4b3a-a4e7-ff9fc9d766be`
  - `scw instance server list`

## 2026-05-11 Manual Workspace Unread Marker

- User requested a way to mark a workspace unread after glancing at it so the needs-review marker returns as a later review reminder.
- Source fix prepared:
  - backend route `PUT /api/workspaces/:id/unread`
  - DB helper marks only the latest non-dropped `codingagent` turn for that workspace `seen = 0`
  - route invalidates the workspace-summary cache, same as `mark_seen`
  - frontend API action `workspacesApi.markUnread`
  - workspace command menu action `Mark unread`
  - keyboard shortcut `W U`
  - command-bar workspace actions now use the targeted workspace id for visibility when opened from a sidebar workspace row, instead of hiding actions based on the currently selected workspace/create-mode context
- Regression guard:
  - test `latest_workspace_turn_can_be_marked_unseen` verifies the helper ignores older turns, non-coding runs, dropped runs, and other workspaces.
- Validation passed:
  - `pnpm run format`
  - `cargo test -p db latest_workspace_turn_can_be_marked_unseen`
  - `cargo check -p server`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `git diff --check`
- Not deployed live yet. This needs a backend build/restart plus frontend asset release before `https://vibe.local` can use it.

## 2026-05-11 Mobile Workspace Chat Autofocus

- User reported mobile workspace open immediately raises the keyboard, making it hard to read the workspace report first.
- Source fix prepared in `packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx`:
  - existing-session/new-session workspace chat still autofocuses on desktop
  - real mobile devices now render the chat editor with `autoFocus={false}` so opening a workspace does not summon the keyboard
- Not deployed live yet. This is frontend-only and can ship with the next clean frontend asset release.

## 2026-05-12 Workspace Actions / Spin-Off Repair

- User reported `Spin off workspace` did nothing, then the workspace action menu regressed to only a small option set.
- Menu root cause already fixed in source: `CommandBarDialog` must evaluate workspace action visibility against the clicked/sidebar target `workspaceId`, not the currently selected workspace or create-mode context.
- Spin-off root cause found:
  - the action swallowed all errors, so failed workspace/repo lookup or draft prep closed the menu with no visible result
  - it only used transient create-mode seed state, which is fragile when invoked from project/issue workspace routes
- Source fix prepared:
  - spin-off now throws visible errors through the existing action error dialog
  - refuses to spin off a workspace with no repos configured
  - creates a durable workspace-create draft for linked project/issue workspaces and navigates to the project issue workspace-create route
  - still seeds the global workspace-create flow for unlinked workspaces
- Deployed live without restarting VK in clean frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tworkspace-actions-spin-off`.
- The live release was built from clean worktree `/tmp/vk-frontend-workspace-actions-20260512` pinned to the previous clean frontend boundary, with only:
  - command menu target-workspace visibility fix
  - spin-off durable draft/error-surfacing fix
  - mobile chat autofocus suppression
- The live frontend-only release intentionally excludes the manual unread action because the running backend still lacks `PUT /api/workspaces/:id/unread`.
- Validation passed:
  - `pnpm run format`
  - `git diff --check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm --filter @vibe/local-web run build`
  - live `GET /` references `/assets/index-BFwa8gDf.js`
  - live JS/CSS assets return `200`
  - live JS contains `spin-off-workspace` and `Cannot spin off a workspace with no repos configured`
  - live JS does not contain `mark-workspace-unread`, `/unread`, or `Mark unread`

## 2026-05-12 Issue Status Selector Repair

- User reported the issue-page status control could no longer be clicked to change issue status.
- Live browser check showed the old command-dialog status path could work, but the issue panel unnecessarily depended on global command/modal plumbing for a local property edit.
- Source fix:
  - `IssuePropertyRow` now renders the issue status as a native status selector when `onStatusChange` is supplied
  - `KanbanIssuePanel` passes direct status changes through `onFormChange`
  - `KanbanIssuePanelContainer` updates create-mode draft status directly and updates edit-mode issue `status_id` directly; the command-dialog status picker remains as a fallback path for non-direct interactions
- Deployed live without restarting VK in clean frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260512Tissue-status-selector`.
- This live release also retains the earlier frontend-only workspace-action/spin-off/mobile-autofocus fixes and still excludes manual unread because the running backend lacks `PUT /api/workspaces/:id/unread`.
- Validation passed:
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `git diff --check`
  - clean release `pnpm --filter @vibe/local-web run build`
  - live `GET /` references `/assets/index-lHRVY0wK.js` and `/assets/index-DgGNwRiN.css`
  - live JS/CSS assets return `200`
  - live browser test changed VL test issue `T8` from `todo` to `in_progress`, then restored it to `todo`, with both `PATCH /v1/issues/:id` requests confirmed

## 2026-05-11 Regression Lockdown / Deployment Queue

- Live frontend is currently `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260511Tclean-frontend-regression-lock`.
- Backend restart/deploy completed on 2026-05-11 after backup `/home/mcp/backups/vk-pre-restart-20260511T144352Z`.
- Deployed binary sha256 is `251d51ca5e831775768339c45addc6488b5298a138594accb944782db7dcc6a0` for both `/home/mcp/.local/bin/vibe-kanban-serve-prod` and `/home/mcp/.local/bin/vibe-kanban-serve`.
- No-restart frontend fixes deployed from clean release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260511Tclean-frontend-regression-lock`:
  - collapsed Kanban column count badge
  - compact horizontal mobile collapsed Kanban columns
  - queued follow-up status polling every `3s` while the UI still reports `queued`
- Rollback target before this swap was `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260510T123551Z-rc-876eb7936`.
- Backend fixes deployed in the restart:
  - reject/cancel orphan queued follow-ups when no running queue-consumer execution exists
  - stale sub-agent filtering so only genuinely active children count as active
  - prompt JSON body limit raised to `100 MB` for workspace start, session follow-up, and queued follow-up routes
- Post-restart verification:
  - `GET /api/info` passed
  - live frontend still references `/assets/index-C_nfyFbD.js` and `/assets/index-Cchj_gnC.css`
  - project list stayed at `9` active and `8` archived projects; archived projects did not reappear in the active left nav data
  - no running `vk-exec-*` services and `0` non-dropped running `execution_processes`
  - orphan queued follow-up returns `409`
  - a `3 MB` queued prompt body reaches the route and returns the expected `409`, proving the old small JSON body limit is no longer blocking that path
- The prompt/workspace text limit was the server JSON body cap, not a deliberate frontend textarea limit. NGINX already allows large bodies; these JSON routes now allow `100 MB`.
- Regression prevention rule: do not deploy from a dirty maintenance checkout. Build frontend hotfixes from a clean worktree pinned to the current live release commit plus only the intended frontend patch, then verify the live HTML asset hash and feature behavior after the symlink swap.
- Restart prevention rule: before any future backend restart, confirm the deployed binary/source contains every queued backend fix, confirm the frontend `current` symlink points at the intended clean release, and keep the previous release path for rollback.

## 2026-05-11 Collapsed Kanban Count Regression

- User reported collapsed Kanban column counts disappeared after the production frontend rollback.
- Source finding: `CollapsedKanbanColumn` rendered the status label, color dot, and needs-review marker, but no count; the visible count was not a durable part of the collapsed-column component.
- Source fix prepared in `packages/web-core/src/features/kanban/ui/KanbanContainer.tsx`:
  - added `issueCount` to `CollapsedKanbanColumn`
  - passes `issueIds.length` from the status render loop
  - renders a compact count badge for both desktop collapsed rails and mobile collapsed rows
- Deployed without restarting VK in clean frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260511Tclean-frontend-regression-lock`.

## 2026-05-10 Android Parity Stale Sub-Agent Count Repair

- User reported `FR::ORC::Android Parity` showed "42 sub-agents may still be active" after the sub-agent sidebar deployment.
- Root cause: the Codex fallback path merged every historical `thread_spawn_edges.status = open` row for every parent `coding_agent_turns.agent_session_id` in the VK session. Android Parity has a long-lived session with many historical parent turns, so stale open Codex edges from completed parents were counted as active.
- Live mitigation, no VK restart:
  - backed up Codex state to `/home/mcp/backups/codex-state-before-android-subagent-stale-close-20260510T191916Z.sqlite`
  - closed stale Android Parity Codex edges only when the parent VK execution was terminal and the child thread had not updated after parent completion, or when the child thread metadata was missing
  - verified the live API now reports `46` completed historical sub-agents and only `2` running current sub-agents for session `a7cd1444-b385-4edd-b8ef-cc14994cd8ba`
- Current live running Android Parity children are legitimate new work from the user's `2026-05-10T19:20:12Z` prompt:
  - `019e1355-ba15-7fa1-bdad-8ca4dffffe08`
  - `019e1355-baca-7042-9691-3f1348b6a596`
- Follow-up correction: those two Android children later proved stale too after the parent execution completed at `2026-05-10T19:23:36Z`; the initial mitigation had not handled persisted VK `subagent_jobs` rows that still said `running`.
- User also reported false active counts for `FR::ORC::Generative Programming` (`18`), `VL::Investigate repo workflow` (`7`), and `FR::Open AI API usage` (`10`).
- Broader no-restart live mitigation:
  - backed up Codex state to `/home/mcp/backups/codex-state-before-stale-subagent-sweep-20260510T225425Z.sqlite`
  - closed `37` stale Codex open edges across those four workspaces
  - backed up the VK DB to `/home/mcp/backups/vk-db-before-stale-subagent-jobs-20260510T225546Z.sqlite`
  - marked the remaining `3` stale persisted `subagent_jobs` rows completed
  - verified live workspace summaries now show `active_subagent_count = 0` and `unresolved_subagent_count = 0` for all four reported workspaces
- 2026-05-11 recurrence:
  - Android Parity showed `2 possibly active` again for latest parent execution `e1cbe279-6785-4c62-ab71-234f9b9dadbc`
  - the two children were `Meitner` (`019e1424-990e-7431-beda-31de82af1b6c`) and `Peirce` (`019e1424-9ad8-73e2-adf6-7c47e7f79618`)
  - parent completed at `2026-05-10T23:24:06Z`; both children updated before parent completion and no Android Parity `vk-exec-*` unit was running
  - backed up Codex state to `/home/mcp/backups/codex-state-before-android-open-edge-close-20260511T000615Z.sqlite`
  - closed those two stale Codex open edges and verified Android Parity live summary now reports `active_subagent_count = 0` and `unresolved_subagent_count = 0`
- Source repair prepared in `crates/db/src/models/subagent_job.rs`:
  - include parent `execution_processes.completed_at` when mapping VK parent threads to Codex child edges
  - treat a Codex `open` edge as completed when its VK parent execution is completed and the child was last updated within 30 seconds of parent completion, or has no child update timestamp
  - keep genuinely current child activity running when the child updated after parent completion or the parent is still running
  - prefer Codex-proven terminal child state over stale persisted VK `running` state for the same child agent ID
- Validation passed:
  - `cargo test -p db completed_parent_codex_open_edge_is_not_counted_as_running_when_stale`
  - `cargo test -p db codex_completed_status_overrides_stale_persisted_running_status`
  - `cargo test -p db not_found_subagent_status_remains_recoverable`
  - `git diff --check`
- No VK restart was performed for the live mitigation. The source repair requires the next backend deploy/restart to become permanent for future stale Codex edges.

## 2026-05-10 Mobile Collapsed Kanban Column Repair

- User reported collapsed Kanban columns regressed on mobile and rendered their labels vertically instead of horizontally.
- Root cause: `CollapsedKanbanColumn` always applied `[writing-mode:vertical-rl]`, even though mobile Kanban switches to a single-column layout where collapsed statuses should render as horizontal bars.
- Follow-up root cause: the outer `KanbanBoard` still had its default `min-h-40`, so the mobile label was horizontal but the collapsed row kept the old tall vertical footprint.
- Source fix:
  - `packages/web-core/src/features/kanban/ui/KanbanContainer.tsx`
  - added an `isMobile` prop to `CollapsedKanbanColumn`
  - desktop keeps the narrow vertical collapsed rail
  - mobile now renders a compact horizontal collapsed bar with normal text flow and a `min-h-12` collapsed board footprint
- Deployed without restarting VK by building `packages/local-web` and swapping refreshable frontend assets to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260510Tmobile-collapsed-columns-height`.
- Updated staged restart frontend artifact `/home/mcp/.local/share/vibe-kanban/pending-releases/20260510T123551Z-rc-876eb7936/frontend-dist` with the same build so a later restart does not roll this fix back.
- No backend restart was performed; `vibe-kanban.service` main PID remained `2063361`.
- Validation passed: `pnpm --filter @vibe/web-core run check`, `pnpm run format`, `pnpm --filter @vibe/local-web run build`, `git diff --check`, live HTML references `/assets/index-Cjdk6Zpg.js` and `/assets/index-DO7PuNtw.css`.

## 2026-05-10 Sub-Agent Preservation Repair

- User reported a spawned sub-agent named Halley returned an agent ID but later status checks came back `not_found`, making the work unretrievable from VK.
- Root cause confirmed in live state:
  - live `subagent_jobs` was empty
  - Codex isolated state DB had the Halley edge in `thread_spawn_edges`
  - the parent VK session was `d5986796-aef1-46cd-9dcc-82e877ec032d`
  - parent execution was `a15b9802-4a21-4311-b798-477dafe15b68`
  - child thread was `019e0d97-27ff-7c43-b252-28979c51d3e9`
  - live API returned an empty sub-agent list for the session because VK had not persisted a durable row
- Source repair prepared:
  - raw Codex stdout `item/completed` events for completed `collabAgentToolCall` / `spawnAgent` calls now persist receiver child thread IDs as running sub-agent jobs
  - parent `thread/status/changed` events are intentionally ignored so the parent thread is not mistaken for a child
  - `not_found` is recoverable, not terminal, in `SubagentJob` DB state
  - `not_found` still counts as unresolved/attention-worthy in sidebar and chat send guards
  - chat-derived sub-agent activity preserves a known running/unresolved child when a later `wait_agent` result says `not_found`
- No-restart live mitigation:
  - took backup `/home/mcp/backups/vk-pre-subagent-halley-backfill-20260510T120326Z.sqlite`
  - inserted the Halley child into live `subagent_jobs` from Codex `thread_spawn_edges`
  - verified `GET /api/execution-processes/subagents/session?session_id=d5986796-aef1-46cd-9dcc-82e877ec032d` returns Halley with status `running`
- No VK restart has been performed for this repair.

## 2026-05-10 Left Nav Archive Button Hotfix

- User reported live VK left nav had regressed to the wrong AppBar: Remote, Export, GitHub, and Discord buttons were visible again and archived projects were not reachable from the archive button.
- Root cause found: the current AppBar/SharedAppLayout source had drifted away from the `39daa526d` archive-modal implementation and back toward the older inline/archive-list or always-visible-link paths.
- Restored the archive-modal nav behavior in source:
  - `packages/ui/src/components/AppBar.tsx`
  - `packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx`
  - `packages/web-core/src/shared/dialogs/kanban/ArchivedProjectsDialog.tsx`
- Deployed without restarting VK by building `packages/local-web` and swapping `/home/mcp/.local/share/vibe-kanban/frontend-dist/current` to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260510Tnav-archive-restore`.
- Live HTML now references `/assets/index-DiBpPjdc.js` and `/assets/index-CLXyXw2Z.css`; `vibe-kanban.service` main PID remained `2063361`.
- Validation passed: `pnpm --filter @vibe/ui run check`, `pnpm --filter @vibe/web-core run check`, `pnpm --filter @vibe/local-web run build`, `pnpm run format`, live asset `200`, and live `/api/projects` shows `7` active plus `10` archived projects.
- Note: the frontend release was built from the current maintenance checkout, which contains other in-progress frontend changes. Keep this visible when promoting or rebuilding the release cleanly.

## 2026-05-10 Needs-Review vs Running Icon Repair

- User reported workspace sidebar icons did not switch from in-progress/running to needs-review without a page refresh.
- Root cause: `useWorkspaces` merged two status sources but let the websocket `WorkspaceWithStatus.is_running` field drive `SidebarWorkspace.isRunning` even when the polled `/api/workspaces/summaries` endpoint already had a fresher terminal `latest_process_status`.
- Frontend fix: when `summary.latest_process_status` is present, derive `isRunning` from that value; fall back to stream `ws.is_running` only when summary status is absent.
- Live deploy: built `packages/local-web` and swapped refreshable frontend assets to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260510Tneeds-review-status-precedence`.
- No backend restart was performed; `vibe-kanban.service` main PID remained `2063361`.
- Validation passed: `pnpm --filter @vibe/web-core run check`, `pnpm --filter @vibe/local-web run build`, `pnpm run format`, live HTML references `/assets/index-BAxdBJfQ.js`, asset returns `200`, and live summaries show terminal statuses plus unseen flags needed for Needs Attention.

## 2026-05-09 Sub-Agent Sidebar Indicator Repair

- User reported no visible indication for workspaces with running sub-agents after the earlier sub-agent UI work.
- Root cause: live `subagent_jobs` in VK DB was empty, while real Codex child-agent state existed in isolated Codex state DB `/home/mcp/.local/share/vibe-kanban/codex-home/state_5.sqlite`, table `thread_spawn_edges`.
- Example found during investigation: `FR::ORC::Android Parity` had open Codex child threads under parent `019e0eb1-d0aa-7310-8160-45cde419368f`, but VK only rendered sub-agent activity inside the open chat composer and did not expose it in workspace summaries/sidebar.
- Source fix prepared:
  - `SubagentJob` now merges persisted VK `subagent_jobs` with live Codex `thread_spawn_edges` by joining current `coding_agent_turns.agent_session_id`.
  - Workspace summaries now include `active_subagent_count` and `unresolved_subagent_count`.
  - Sidebar workspace cards show a warning-colored stack icon/count when a latest session has active/unresolved sub-agents and keep those workspaces in the Running section.
  - `spawn_agent` / `wait_agent` capture now accepts namespaced tool names and singular `target` arguments, so future durable rows are less brittle.
- Current live state changed while investigating: by the end, only `FR::ORC::Generative Programming` was still running and it had no open Codex child edges at that moment.
- Validation passed:
  - `pnpm run generate-types`
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `cargo check -p server` with existing warnings only
  - targeted `git diff --check`
- No VK restart or live backend deploy was performed. This fix requires a backend deploy/restart before `https://vibe.local` can show the new sidebar sub-agent marker.

## 2026-05-08 opNVLP VK Project Setup

- Added `opNVLP` to live VK as local project abbreviation `VL`.
- Existing repo row was already present for `/home/mcp/code/opNVLP` (`e53d1297-0f47-4554-af65-6806c7506934`); updated repo defaults through the live API to `default_target_branch = main` and `default_working_dir = /home/mcp/code/opNVLP`.
- Took live DB backup first: `/home/mcp/backups/opnvlp-project-pre-create-20260508T143346Z.sqlite`.
- Created project `VL` (`20dea20e-4276-46b0-86df-165deb071ccf`), linked it to the opNVLP repo, and wrote `PROJECT_REPO_DEFAULTS` with repo target branch `main` plus standard local statuses.
- Verified through `/api/projects`, `/api/repos/e53d1297-0f47-4554-af65-6806c7506934`, `/api/repos/.../branches`, and direct SQLite joins. No VK restart was performed.

## 2026-05-08 FL Needs-Review Bubble Repair

- User reported the `foxtrot-lima` left-column needs-review bubble persisted even though FL had no outstanding review items.
- Live DB evidence showed the only FL unseen turn was on archived/done workspace `FL::Dark Mode` (`e7c44673-a5af-496b-af22-f294f0e96b76`), latest unseen turn `2026-05-01T16:49:39Z`.
- Took live DB backup before repair: `/home/mcp/backups/fl-needs-review-pre-seen-20260508T140719Z.sqlite`.
- Cleared the stale live flag through the existing API: `PUT /api/workspaces/e7c44673-a5af-496b-af22-f294f0e96b76/seen`.
- Verified FL now has zero unseen coding-agent turns and zero active workspace IDs that should light the project needs-review marker.
- Source fix restored the project needs-review AppBar marker path that had been lost from the checkout and changed project-marker aggregation to use active workspace summaries only. Archived workspaces may still show their own archived-view marker, but they no longer keep an active project bubble lit.
- Follow-up rule: failed/killed/interrupted workspaces now do not light the project-column needs-review bubble. The workspace card can still show the triangle status, but the project bubble is reserved for actionable review state.
- Touched files:
  - `packages/ui/src/components/AppBar.tsx`
  - `packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx`
  - `packages/web-core/src/shared/lib/api.ts`
- Validation passed:
  - `pnpm run format`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm --filter @vibe/ui run check`
  - live API/SQLite verification for FL marker state
- No VK restart was performed. Lightweight preview is running at `http://127.0.0.1:3003/` against backend `127.0.0.1:4311`.

## 2026-05-07 Disk Space Regression

- Root filesystem hit `99%` full with only `3.8G` free; inode usage was normal (`23%`), so the failure was byte exhaustion.
- Cause: hourly lean backup cron (`17 * * * * /home/mcp/_vibe_kanban_repo/scripts/run_vk_lean_backup.sh`) created large local backup artifacts after the prior cleanup. The 08:17 run failed during gzip archive with `OSError: [Errno 28] No space left on device`.
- Removed only failed 08:17 artifacts: `/home/mcp/backups/.vk-lean-restore-20260507T081701Z.tmp` (`18G`), partial `/home/mcp/backups/vk-lean-restore-20260507T081701Z.tar.gz` (`4.7G`), and incomplete `/home/mcp/backups/vk-lean-restore-20260507T081701Z` (`16M`). Root recovered to about `25G` free.
- Valid latest backup was verified on Desktop at `desktop:B:/vk-backups/vk-lean-restore-20260507T071701Z.tar.gz` before removing the MCP duplicate copy.
- Replaced the wrapper-only free-space skip with backup-script preflight cleanup. `scripts/vk_lean_backup.py` now removes stale `.tmp` backups, applies local retention before starting, and if needed deletes extracted timestamped backup directories that already have a valid `.tar.gz` archive.
- The backup still refuses to start if preflight cleanup cannot create at least `40G` free, but that is now after cleanup rather than before cleanup.
- Implemented the Desktop-vault policy: hourly full-context backups are still created on MCP and mirrored to `desktop:B:/vk-backups`, but after a successful Desktop mirror the script removes local full backup directories and tarballs from MCP.
- MCP now keeps `/home/mcp/backups/vk-lean-restore-latest.desktop.json` as the local pointer to the latest Desktop full-context backup. If the Desktop mirror fails, the local full backup is preserved instead of deleted.
- `scripts/run_vk_restore_latest.sh` now restores from the local latest tar when present; otherwise it pulls `vk-lean-restore-latest.tar.gz` back from Desktop using the pointer file and restores that copy.
- Applied the policy immediately after verifying the Desktop copy: removed `/home/mcp/backups/vk-lean-restore-20260507T071701Z`, `/home/mcp/backups/vk-lean-restore-20260507T071701Z.tar.gz`, and the old local latest symlinks. Root disk recovered to about `67G` free / `70%` used.
- Added failed-run cleanup to `scripts/vk_lean_backup.py` so incomplete temp directories and partial tarballs are removed when a run exits before local backup completion.
- Also corrected backup staging so repo metadata is written under the temp backup directory, not the final timestamp directory before promotion.
- Validation: `bash -n scripts/run_vk_lean_backup.sh`, `bash -n scripts/run_vk_restore_latest.sh`, Python compile check for `scripts/vk_lean_backup.py`, and temp-root cleanup tests for preflight pruning and Desktop-only local pruning.

## 2026-05-07 Hyrox Column Repair

- User reported `hyroxready-app` columns were wrong. Investigation found the project scratch row `PROJECT_REPO_DEFAULTS` for project `a3b03aaa-1a7b-4176-8249-20a879593aba` was overwritten at `2026-05-07 16:57:31 UTC`.
- Bad live state had reordered columns and dropped `status_tomerge` / `To merge`.
- Compared Desktop backup DBs without restoring them:
  - `20260507T071701Z`: good columns, repo default was `integration/nutrition-timing`
  - `20260507T091701Z`: good columns, repo default was `staging`
  - `20260507T161701Z`: scratch statuses were empty
- Took small live DB backup before repair: `/home/mcp/backups/hyrox-columns-pre-fix-20260507T1705Z.sqlite`.
- Restored only the Hyrox `PROJECT_REPO_DEFAULTS.statuses` list from the `20260507T091701Z` backup, preserving the current repo default `staging`.
- Verified live fallback status API returns: `To do`, `In progress`, `On Hold`, `Long Running`, `In review`, hidden `Cancelled`, `To merge`, `In Staging`, `Hotfix Path`, `Done`.
- No VK restart was performed.

## 2026-05-06 Dysfunctional Feature Audit

- Investigated broken live features on branch `vk/land-live-fixes-20260422` in canonical repo `/home/mcp/_vibe_kanban_repo`; live production is still copy-deployed from `/home/mcp/.local/bin/vibe-kanban-serve-prod`, not from this dirty checkout.
- Left-column needs-attention bubbles:
  - Root cause: the sidebar reads `workspace_summary.has_unseen_turns` and `has_pending_approval`. Coding-agent turns are inserted as `seen = 0`, but the selected workspace only called `markSeen` on route/workspace-id change. If a turn became unseen while the workspace was already open, or if the user clicked the already-selected workspace, the marker could persist.
  - Root cause 2: `/api/workspaces/summaries` has a short server-side cache and `PUT /api/workspaces/:id/seen` did not invalidate it, so even a successful mark-seen could briefly re-serve stale marker state.
  - Live DB evidence: active unseen rows currently include `FR::HRV Stream`, `FR::Canada vs USA`, `PG::Leeann Program Design v2`, `FR::Android Parity`, and several older VK/Hyrox workspaces. Some rows are from completed turns, some from running turns, and older archived rows remain unseen until those archived workspaces are opened.
  - Code fix prepared in this checkout: `WorkspaceProvider` now re-marks the current workspace seen when its summary flips to unseen, and `mark_seen` now invalidates the workspace-summary cache.
- Codeblock copy:
  - The original copy-button commits are in `main`/`staging`, but the later reliability fixes are not in production/integration.
  - The latest known working fix is `26dc77a62 Fix codeblock copy button rendering`; it is not an ancestor of current production.
  - Do not merge `vk/codeblock-copy-20260429` wholesale; it is stale and would bring unrelated reversions/deletions. Port the minimal codeblock files/commits onto fresh `staging`.
- Rename workspaces:
  - The rename UI code is landed, but local fallback workspace rows can have `owner_user_id = ""`.
  - The issue workspace card only exposes rename/delete when `workspace.owner_user_id === userId`, so local-only workspaces can hide working actions.
  - Fix direction: treat locally linked workspaces with `local_workspace_id` as actionable in local fallback mode, or populate fallback `owner_user_id` with the local user id.
- PR details in issues / merged PRs:
  - The fallback PR endpoint can render PRs when `pull_requests` rows exist; the `vibe-kanban` project proves this.
  - Several Hyrox in-staging issues have no `pull_requests` rows and no PR metadata in descriptions, so the UI has nothing durable to render.
  - `VK_DISABLE_PR_MONITOR=1` is intentionally set in live production for stability, so merged-state polling is not keeping all PR rows fresh.
  - Fix direction: capture a durable PR snapshot at PR creation/merge time, add a safe manual/on-demand reconcile path, and backfill rows from GitHub where branch/issue metadata still exists.
- Why these features failed together:
  - Fixes were split across stale branches, direct hotfixes, staging/main promotions, and refreshable frontend assets without a single post-merge live verification checklist.
  - Some agents used task worktrees or stale branches as if they were canonical source.
  - Several features relied on transient derived state: current worktree branch, GitHub polling, route-change side effects, or frontend-only ownership assumptions. Those do not survive branch reuse, archived workspaces, disabled monitors, or partial deployments.
  - The canonical checkout is dirty and `STREAM.md` had stale branch intent, so future agents can easily start from the wrong mental model unless this audit stays visible.

## Repair Plan

1. Land the needs-attention marker fix from this checkout on a fresh branch from current `staging`, with focused frontend and backend checks.
2. Port the minimal latest codeblock-copy fix onto fresh `staging`; do not merge the stale feature branch.
3. Fix local fallback workspace action ownership so local issue workspaces can be renamed/deleted when linked locally.
4. Add durable PR snapshot/reconcile behavior, then backfill missing PR rows for affected Hyrox and VK issues.
5. Add a live feature verification checklist for every deployed UI fix: browser refresh, live asset hash, one positive UI assertion per feature, and API/DB evidence where the UI depends on local state.
6. Keep hotfixes small, backfill them immediately to `staging`, and record whether the fix is backend-restart-required or frontend-refresh-only.

## 2026-05-06 Attachment And Space Findings

- User reports attachment paste/select often does nothing. Investigation found multiple causes:
  - Existing workspace "new session" mode can have no `sessionId`; the attach button remains enabled but `useSessionAttachments` returns early when `sessionId` is missing, so the UI silently no-ops.
  - Attachment upload hooks catch errors and only log to browser console, so upload failures are invisible in the chat UI.
  - Live logs show real attachment upload `500`s. Earlier failures coincided with `No space left on device`; current failures include `No such file or directory`.
  - Live backend expects `/home/mcp/.cache/utils/attachments`, but that directory is missing. `FileService::new` creates it only at service startup, so the running service can fail uploads until the dir is recreated or the backend restarts.
  - Sampled recent attachment DB rows exist, but corresponding cache files were missing from `/home/mcp/.cache/utils/attachments`; sampled workspace `.vibe-attachments` paths also lacked at least one recent file. Some historical attachments may be dangling unless restored from backups/worktrees.
- No attachment repair or cleanup was executed yet.
- Immediate no-restart repair candidate:
  - recreate `/home/mcp/.cache/utils/attachments`
  - verify an attachment upload against live VK
  - scan backups/worktrees for missing attachment files and restore only known cache files
- Frontend-only repair candidates:
  - surface attachment upload errors in the composer
  - disable or explain attachment controls when upload cannot work
  - show uploading/progress state so attachment selection is never invisible
- Backend-restart repair candidates:
  - make `FileService::store_file` recreate the attachment cache directory before every write
  - make `serve_file` return a clean 404 for missing cache files instead of a 500
  - support attachments in existing-workspace new-session mode by carrying pending attachment IDs through session creation/follow-up
- Space report from tmux session `opSpace`:
  - root filesystem: `233G` total, `192G` used, `31G` free, `87%` full
  - largest areas: `/home/mcp/backups` `52G`, `/home/mcp/code` `47G`, `/home/mcp/.local` `29G`, `/home/mcp/_vibe_kanban_repo` `15G`, Android SDK/AVD about `9.8G`, systemd journals `3.1G`
  - largest cleanup candidates:
    - `/home/mcp/backups/vk-pre-restart-manual-20260505T161804Z` `19G`
    - `/home/mcp/backups/vk-lean-restore-20260506T141701Z` `15G`
    - `/home/mcp/backups/vk-pre-worktree-fix-deploy-20260501T203246Z` `9.5G`
    - `/home/mcp/_vibe_kanban_repo/target` `13G`
    - `/home/mcp/code/worktrees/hyroxready-app` `21G`, mostly repeated dependencies/worktrees
    - `/home/mcp/code/archive` `8.5G`
    - `/home/mcp/.local/share/vibe-kanban/codex-home/sessions` about `9.9G`
    - `/home/mcp/.local/share/vibe-kanban/sessions` about `4.2G`
    - `/home/mcp/.codex/sessions` about `2.0G`
- Cleanup plan before executing fixes:
  1. Take no action until user approves exact cleanup list.
  2. Prefer rebuildable outputs first: Rust `target/`, archived/worktree `node_modules`, and capped systemd journals.
  3. Treat VK backups, VK `codex-home`, and VK session history as continuity-sensitive; only prune them with explicit retention rules and after confirming a valid current backup exists.
  4. Do not remove registered Git worktrees until checking for uncommitted changes and active VK agents.
  5. After freeing space, repair the attachment cache directory and run live upload/readback smoke tests before deploying code changes.
- Executed safe `node_modules` cleanup after user approval:
  - active VK workspaces were excluded first: `/home/mcp/code/worktrees/c961-fr-orc-android-p`, `/home/mcp/code/worktrees/2fa0-fr-fix-heartrate`, `/home/mcp/code/worktrees/6e87-fr-enhance-dashb`, `/home/mcp/code/worktrees/2482-pg-logging`
  - qualifying rule used: worktree had no non-`node_modules` files modified in the last 4 days
  - removed `node_modules` from:
    - `/home/mcp/code/worktrees/3714-vk-codeblock-onl/_vibe_kanban_repo`
    - `/home/mcp/code/worktrees/679c-fr-orc-coaches-f/hyroxready-app`
    - `/home/mcp/code/worktrees/fcd0-fr-coaches-featu/hyroxready-app`
    - `/home/mcp/code/worktrees/hyroxready-app/codex-android-member-parity`
    - `/home/mcp/code/worktrees/hyroxready-app/program-generation-v4-real-example-coach`
  - result: root filesystem moved from about `31G` free / `87%` used to about `33G` free / `86%` used
  - no VK restart was performed

## What Changed This Session

- Hotfixed and deployed the recurring VK git/worktree stall on `2026-05-05`:
  - manual backup: `/home/mcp/backups/vk-pre-restart-manual-20260505T161804Z`
  - invalid backup attempt to ignore: `/home/mcp/backups/vk-lean-restore-20260505T160819Z`
  - hotfix worktree: `/tmp/vk-hotfix-recurring-stall-20260505`
  - built commit: `b6575aed90e4ecf7ddb5279528292f68a0545212`
  - production merge commit: `3cfe96ab8f8c6a83652f4c84a9d4244ca4e37a9f`
  - staging backfill merge commit: `91e2f9d1a30842fd0d770cdfda39c27932bfa084`
  - main PR: `https://github.com/artinflight/vibe-kanban/pull/55`
  - staging backfill PR: `https://github.com/artinflight/vibe-kanban/pull/56`
  - deployed binaries: `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - deployed sha256: `c903c345859a1838fbe27b3de47f8bcf178849d3e62f9b0e8f808d2cc161c570`
  - validation: `pnpm --filter @vibe/local-web run build`, `cargo build --release --bin server`, API smoke checks, live asset checks, and post-restart execution audits
- Fix scope:
  - `LocalContainerService::stream_diff` now returns an idle ready stream when all repo diff streams are skipped, instead of closing the workspace websocket and leaving the UI stale
  - `GitCli` commands now default to a bounded `120s` timeout through `VK_GIT_CLI_TIMEOUT_SECS`
  - PR `#55` also deployed the already-merged needs-review marker UI and refreshable frontend asset support
- Restart and preservation notes:
  - pre-restart audit found `0` running execution rows and no active `vk-exec-*` units
  - `systemctl --user restart vibe-kanban.service` stuck in `deactivating`, so only the old VK main PID `3441151` was force-killed after a grace wait
  - service came back active on PID `3962645`
  - post-restart audits still showed `0` running execution rows and no active `vk-exec-*` units
  - `/api/info`, `/`, `https://vibe.local/`, `/api/projects`, and `/assets/index-CErwigwv.js` returned healthy responses
  - VK memory settled around `260-280 MB`
- Refreshable frontend assets are active:
  - systemd drop-in: `/home/mcp/.config/systemd/user/vibe-kanban.service.d/frontend-dist.conf`
  - env: `VK_FRONTEND_DIST_DIR=/home/mcp/.local/share/vibe-kanban/frontend-dist/current`
  - current release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260505T1648Z`
  - future frontend-only swaps can update the `current` symlink and browser refresh without rebuilding/restarting the backend, provided the running backend already supports `VK_FRONTEND_DIST_DIR`

- Promoted current VK fixes from `staging` to `main` and redeployed production on `2026-05-03`:
  - backup: `/home/mcp/backups/vk-pre-restore-guardrails-main-merge-20260503T115553Z`
  - merge worktree: `/tmp/vk-main-merge-staging-20260503T1155`
  - production commit: `5ddde0b6460393e7d34301d676b1dd86c8b99bc5`
  - deployed binaries: `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - deployed sha256: `e2f86f5ccc880cfeeba4684cf1a0ecdd05bc27e63d2b39a0a9d4a6ce47256d5c`
  - validation: `pnpm run format`, `pnpm run ops:check`, `pnpm run ops:live-runtime-guardrails`, `pnpm --filter @vibe/local-web run build`, and `DATABASE_URL=sqlite:/tmp/vk-main-merge-build.sqlite cargo build --release --bin server`
- Restored live runtime guardrails after the live launcher lost them:
  - persistent drop-in: `/home/mcp/.config/systemd/user/vibe-kanban.service.d/runtime-guardrails.conf`
  - required env includes `CODEX_HOME`, `VK_USE_SYSTEMD_RUN=1`, `VK_DISABLE_PR_MONITOR=1`, `VK_TRANSIENT_MEMORY_HIGH=1500M`, `VK_TRANSIENT_MEMORY_MAX=3000M`, and `VK_CODEX_BASE_COMMAND=/home/mcp/.local/bin/codex`
  - repo-tracked guardrail material was added on `main` in `docs/self-hosting/systemd/runtime-guardrails.conf` and `scripts/check-live-vk-runtime-guardrails.sh`
- Restarted `vibe-kanban.service` after explicit user approval:
  - restart initially stuck in `deactivating`; only the old VK main PID was force-killed after a grace wait
  - service came back active on PID `3441151`
  - `/api/info`, `/`, and `https://vibe.local/` returned `200`
  - VK memory dropped from roughly `20G` before restart to about `200M`; VK swap was `0`
  - running executions in DB after restart: `0`
  - existing active executions were interrupted by the restart and marked failed on startup
- Important follow-up:
  - May 3 guardrail/check commits and the May 5 recurring-stall hotfix have both been backfilled to `staging`; continue new VK platform work from refreshed `staging`.

- Permanently fixed the recurring "new workspace does not link to its issue" failure in repo code:
  - main hotfix PR: `https://github.com/artinflight/vibe-kanban/pull/44`
  - main merge commit: `21815da2b9bbdd57f5711cfe9e6c481fa0aeb2ae`
  - staging backfill PR: `https://github.com/artinflight/vibe-kanban/pull/45`
  - staging merge commit: `24a2dbe3ad5b7457beea772c4cbe6ea0a070944f`
  - core behavior: when workspace start/create receives no `task_id`, infer a local linked issue from the selected repo(s) and exact workspace title, but only when there is exactly one matching local issue
  - intentionally does not link ambiguous matches
- Live repair already done for OSTP:
  - project added for `/home/mcp/code/OSTP`
  - workspace `c40cbc4a-4939-4b66-be36-05be0d30784f` linked to issue `83b227d8-f91c-4cf8-bcef-1ef5dc795720`
- Validation for the issue-link hotfix/backfill:
  - PR `#44` GitHub checks passed before merge
  - PR `#45` GitHub checks passed before merge
  - local backfill validation included `pnpm run generate-types:check`, `pnpm run backend:format`, temp SQLite migrations, clippy, `cargo check -p server`, targeted server tests, and `git diff --check`
- Deployment:
  - backup completed first: `/home/mcp/backups/vk-lean-restore-20260428T135054Z.tar.gz`
  - deploy worktree: `/tmp/vk-deploy-permanent-issue-links-20260428T1358Z`
  - deployed merge commit: `21815da2b9bbdd57f5711cfe9e6c481fa0aeb2ae`
  - installed binary: `/home/mcp/.local/bin/vibe-kanban-serve`
  - old binary backup: `/home/mcp/backups/vibe-kanban-serve-before-permanent-issue-links-20260428T1416Z`
  - live binary sha256: `20c614ea3547f1564eb1a3523f84a74b3b369e3c10988957f2957684e69a479c`
  - pre-restart audit found `0` running non-devserver executions and `0` `vk-exec-*` units
  - restarted `vibe-kanban.service` after user permission
  - post-deploy verification passed: service active, running process sha matches installed binary, `/api/info` healthy, `/` `200`, `/assets/index-BbxAzB0F.js` `200`, and `0` running execution processes

- Hotfixed and deployed the stale in-progress execution-process UI bug:
  - worktree: `/tmp/vk-hotfix-stuck-running-reconcile`
  - commit: `d77e95cad fix: reconcile stale running process status`
  - main PR: `https://github.com/artinflight/vibe-kanban/pull/41`
  - staging backfill PR: `https://github.com/artinflight/vibe-kanban/pull/43`
  - deployed merge commit: `de679dfba4d00fb4e7227c0474e1f783861d908a`
  - staging merge commit: `1e208123694b420c5688c5098bdbe5b7ec1aa158`
- Fix scope:
  - `packages/web-core/src/shared/hooks/useExecutionProcesses.ts`
  - while a blocking process is streamed as `running`, the frontend now polls that process detail every `3s`
  - if the detail endpoint shows a terminal status, the hook reconciles local state so the composer can leave the stale in-progress state without a page refresh
- Validation:
  - PR `#41` GitHub checks passed before merge
  - PR `#43` GitHub checks passed before merge
  - `pnpm install --frozen-lockfile`
  - `GITHUB_BASE_REF=main ./scripts/check-i18n.sh`
  - `GITHUB_BASE_REF=staging ./scripts/check-i18n.sh`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run build`
  - `pnpm run format`
  - `git diff --check`
  - `DATABASE_URL=sqlite:/tmp/vk-deploy-sqlx-build.sqlite cargo build --release --bin server`
- Deployment:
  - deploy worktree: `/tmp/vk-deploy-stuck-running-reconcile`
  - installed binary: `/home/mcp/.local/bin/vibe-kanban-serve`
  - live binary sha256: `a6862b6a9439ab4fd114a3a9204aeba65da533f9a05acf7c6888bea8d70cea8f`
  - checked for active non-devserver executions immediately before restart: `0`
  - restarted `vibe-kanban.service` after user permission
  - verified service active, running process sha matches installed binary, `/api/info` healthy, `/` `200`, `/assets/index-D4KCtbF2.js` `200`

- Deployed current `fork/staging` to the live production VK service from a clean detached worktree:
  - worktree: `/tmp/vk-staging-deploy-20260423T082907Z`
  - commit: `4337e20e1638495b5f8b8aa6124678a18357d09b`
  - included PR: `Fix mobile collapsed kanban labels (#9)`
- Avoided using the dirty canonical checkout for the production artifact.
- Installed the built release binary to:
  - `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
- Restarted `vibe-kanban.service` and verified it is active.
- Verified the live process is running the installed binary and both sha256 values match:
  - `9b73d5f94dec505bc5dbd0384802c80c4b014ac55c4fc35abbde5298a84d76bf`
- Verified live HTTP endpoints:
  - `/api/info` healthy
  - `/` returns `200`
  - `/assets/index-48sjVvVl.js` returns `200`
- Validation in the clean staging deploy worktree:
  - `pnpm install --frozen-lockfile`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/ui run check`
  - `cargo check -p server`
  - `pnpm --filter @vibe/local-web run build`
  - `pnpm run format`
  - `cargo build --release --bin server`
- Note: `pnpm run format` passed but would rewrap two TypeScript expressions on `fork/staging`; those temp formatting-only changes were reverted before `cargo build --release --bin server` so the deployed artifact corresponds to the exact fetched staging commit.
- Follow-up investigation after the staging deploy found the checked-out local `staging` worktree at `/home/mcp/code/worktrees/3714-vk-codeblock-onl/_vibe_kanban_repo` was still one commit behind `fork/staging`.
- That local `staging` worktree was clean and was fast-forwarded from `6c0ce663a4548277f1ad774654b2bf82841cc126` to deployed head `4337e20e1638495b5f8b8aa6124678a18357d09b`.
- PR `#9` / T18 was squash-merged as single-parent commit `4337e20e1638495b5f8b8aa6124678a18357d09b` on top of `6c0ce663a4548277f1ad774654b2bf82841cc126`; it did not overwrite T12 because T12 was not in staging and there was no changed-file overlap.
- Missing/misleading deployment state from the audit:
  - ART-50 branch `vk/recover-kanban-columns-20260415` is not an ancestor of `fork/staging`; only its collapsible-column patch is patch-equivalent in staging, while the branch as a whole is a divergent recovery branch and conflicts if bulk-merged.
  - ART-52 branch `codex/fix-workspace-chat-scroll-jumps` is not in `fork/staging` and conflicts if merged directly.
  - ART-53 branch `vk/401e-vk-fix-mobile-co` is not in `fork/staging`; T18/PR `#9` is the deployed replacement for the mobile collapsed-label behavior.
  - T6, T7, and T8 are ancestors of `fork/staging` and their markers are present in the live frontend asset.
  - T12 branch `vk/508a-vk-renaming-work` is not in `fork/staging`, has no GitHub PR, and merge-tree tests cleanly against current `fork/staging`.

## Earlier Session Context

- Built and used an isolated VK lab instance on `127.0.0.1:4411` with separate state and separate `CODEX_HOME`.
- Confirmed a major backend/DB root-cause direction in the lab:
  - SQLite `DELETE` journaling was a real contributor to the stalls
  - the `VK_DISABLE_PR_MONITOR=1` env var was being ignored in code
  - the unseen-turn query was missing a useful unseen-turn index
- Tested the lab in stages:
  - baseline `DELETE` mode
  - `WAL`
  - `WAL` + lower DB pool + real PR monitor disable
  - then a scratch/event-fanout reduction for scratch create/update
- Verified the strongest gain came from:
  - `WAL`
  - smaller SQLite pool
  - PR monitor actually disabled
- Verified the remaining main hotspot is still `UI_PREFERENCES` scratch upserts.
- Fixed a kanban/workspace loading regression that was driving the local VK server back to multi-GB RSS and eventual hangs.
- The concrete hotfix was:
  - stop aggressive workspace-summary refetching in `packages/web-core/src/shared/hooks/useWorkspaces.ts`
  - stop redundant no-op `UI_PREFERENCES` scratch upserts in `packages/web-core/src/shared/hooks/useUiPreferencesScratch.ts`
- Fixed a second frontend churn path in mounted workspace views:
  - stop default 5-second polling in `packages/web-core/src/shared/hooks/useBranchStatus.ts`
  - stop default 5-second polling in `packages/web-core/src/shared/hooks/useTaskWorkspaces.ts`
- Rebuilt and redeployed the local server binary after the fix, then stress-tested the live service with repeated kanban/workspace traffic.
- Preserved the old divergent canonical `staging` tip on rescue branches.
- Reset the canonical local `staging` checkout to match `fork/staging`.
- Split `ca67946ab` into a clean branch, `vk/ops-backup-retention-20260419`.
- Opened PR `#6` for the backup retention change.
- Updated the branch-local continuity docs so they match the backup retention stream.
- Isolated VK from tmux/interactive Codex auth by moving the service onto its own `CODEX_HOME`:
  - `/home/mcp/.local/share/vibe-kanban/codex-home`
- Copied the existing Codex rollout/session state into that VK-only `CODEX_HOME` after confirming that old workspace threads were failing to fork without the old rollout files.
- Closed the earlier upstream official issue/PR for the first partial fix because it was not complete:
  - `BloopAI/vibe-kanban#3372`
  - `BloopAI/vibe-kanban#3373`

## Validation

- The live local install is the source of truth.
- The canonical VK source repo is:
  - `/home/mcp/_vibe_kanban_repo`
- The live service does not run directly from the repo checkout.
- Production runs through:
  - binary: `/home/mcp/.local/bin/vibe-kanban-serve`
  - deployed binary: `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - current sha256: `c903c345859a1838fbe27b3de47f8bcf178849d3e62f9b0e8f808d2cc161c570`
- VK workspaces/worktrees live under:
  - `/home/mcp/code/worktrees/...`
- Those worktree paths are not the canonical product repo.
- `/api/info` reports `shared_api_base: null`.
- The best current root-cause evidence is now backend/DB-related, not just frontend polling:
  - SQLite `DELETE` mode was materially worse than `WAL`
  - PR monitor disable was not honored before the lab patch
  - the remaining heavy hotspot is still scratch upsert churn
- Two concrete frontend polling regressions are fixed in the live service and in `staging`.
- Current verification after the hotfix:
  - repeated mixed kanban/workspace bursts passed with `0` failures
  - a 2-minute mixed soak (`21,070` requests) passed with `0` failures
  - live service stayed under roughly `90 MB RSS` with `0` swap
- Additional verification after the second workspace-polling hotfix:
  - repeated browser-like workspace-open traffic against `OpsPB::Linking in reports`, `VK:: Wire Ntfy`, and `Vk::Ops` stayed roughly in the `32–51 MB` range
  - no `git inspection timeout`, DB pool timeout, or slow-query churn appeared during that controlled test
- Additional isolated lab verification:
  - baseline mixed workload in `DELETE` mode stalled badly:
    - writes up to `3.5s`
    - summaries up to `3.3s`
    - `git/status` up to `7.0s`
    - `projects` up to `7.5s`
  - after `WAL` + lower pool + PR monitor off:
    - repeated mixed load had `0` failures
    - long soak with repeated `_vibe_kanban_repo` workspace starts had `0` failures
    - memory stayed under about `1.24 GB`
  - after reducing scratch create/update fanout in the lab:
    - short heavy run improved further
    - long soak improved further
    - but scratch writes still occasionally hit `1-2.2s`
- The board/issue data now lives locally in `~/.local/share/vibe-kanban/db.v2.sqlite`.
- The canonical local checkout is dirty with multiple existing changes; do not deploy from it directly.
- The active branch recorded by this stream remains `vk/ops-backup-retention-20260419`, but current live production was deployed from clean hotfix/promote worktrees.
- PR `#6` is the isolated path for `ops(backups): add tiered lean backup retention`.
- The VK service wrapper exports:
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
- VK must not share `~/.codex/auth.json` with tmux Codex sessions anymore.
- Current path/deploy map is documented in:
  - `VK_WORKFLOW.md`
  - `LIVE_DEPLOYMENT.json`

## Validation Gaps / Failures

- Initial `pnpm run generate-types` failed with `No space left on device`; fixed
  by removing old reproducible build artifacts and reran successfully.
- Plain `pnpm run check` failed in `local-web:check` with Node heap OOM; reran
  with `NODE_OPTIONS=--max-old-space-size=4096`.
- The enlarged-heap `pnpm run check` passed frontend checks, then failed in
  `backend:check` because the environment lacks system `glib-2.0.pc`.
- No live service restart, deployment, or browser smoke was performed.

## Next Safe Steps

- Git history sync checks passed:
  - canonical `staging` now matches `fork/staging`
  - `vk/ops-backup-retention-20260419` is exactly one commit ahead of `staging`
- Not rerun in this cleanup stream:
  - repo build/test validation for the backup retention change itself

## What The Next Agent Should Do

- Start from:
  - `/home/mcp/_vibe_kanban_repo`
- Read first:
  - `HANDOFF.md`
  - `STATE.md`
  - `DELTA.md`
  - `VK_WORKFLOW.md`
- Keep further root-cause work in the isolated lab, not prod.
- Treat these as the current best candidate fixes:
  1. switch SQLite handling off `DELETE`
  2. reduce SQLite pool size materially
  3. honor `VK_DISABLE_PR_MONITOR`
  4. add the unseen-turn index
  5. reduce `UI_PREFERENCES` scratch write amplification
- Treat `c6a5dd7d9 fix: stop kanban polling and scratch churn` as the baseline fix for the recent kanban/workspace hang regression.
- Treat `88c0ebd59 fix: stop workspace status polling churn` as the second required frontend fix for the same broad stability stream.
- If VK starts re-bloating again, compare the current behavior against this session’s stress results before assuming it is the same bug.
- Do not reopen an upstream official issue/PR until the remaining heavy-child / DB-lock path is root-caused and fixed.
- Merge PR `#6`.
- Keep the rescue branches until there is no more need to recover anything from the old divergent `staging`.
- After PR `#6` lands, bring the remaining queued PRs to `staging` one at a time.
- Build and use an isolated lab/test instance for further diagnosis instead of continuing to use production VK as the test bed.
- Do not port lab fixes to prod or `staging` without explicit user confirmation.

## What The Next Agent Must Not Do

- Do not treat `/home/mcp/code/worktrees/...` as the canonical VK repo unless the task is explicitly about a specific workspace/worktree.
- Do not invent or assume a `/home/mcp/code/vibe-kanban` checkout.
- Do not re-enable `VK_SHARED_API_BASE` or `VK_SHARED_RELAY_API_BASE` for the local install.
- Do not delete the rescue branches before confirming the divergence cleanup is complete.
- Do not reintroduce direct local-only commits onto the canonical `staging` checkout.
- Do not assume PR `#6` has fresh validation beyond the preserved commit history unless it is rerun explicitly.
- Do not point VK back at `~/.codex` unless you intentionally want VK and tmux Codex sessions to share refresh-token rotation again.
- Do not copy only `auth.json` into a fresh VK `CODEX_HOME`; old workspace thread fork/resume needs the Codex rollout/session state too.
- Do not touch tmux or interactive Codex sessions while diagnosing VK service failures.
- Do not claim the issue is fully fixed just because raw endpoint stress tests pass; the earlier miss came from not reproducing mounted browser/UI polling and live child-process load together.

## Verification Required Before Further Changes

- `curl -s http://127.0.0.1:4311/api/info` and confirm `shared_api_base` is `null`
- if continuing lab DB work, capture before/after timings for:
  - scratch writes
  - `/api/workspaces/summaries`
  - `/api/workspaces/:id/git/status`
  - `/api/projects`
  - `_vibe_kanban_repo` workspace starts
- `git status --short --branch`
- Task-specific validation for backup retention behavior if the change is modified further
- `systemctl --user show vibe-kanban.service -p ExecStart -p Environment`
- `tr '\\0' '\\n' < /proc/$(systemctl --user show -p MainPID --value vibe-kanban.service)/environ | rg '^CODEX_HOME='`
- If prod VK wedges while you need the board back quickly:
  - back up `db.v2.sqlite`
  - restart `vibe-kanban.service`
  - if it gets stuck in `deactivating (stop-sigterm)`, wait briefly for normal cleanup
  - if it still does not exit, force-kill only the stuck VK main PID and let systemd bring it back
  - do not kill tmux or unrelated Codex sessions

## Verification Status From This Session

- canonical `staging` sync cleanup completed
- PR `#6` exists for the isolated backup retention commit
- branch-local docs now match the backup retention stream
- the second workspace-polling fix is committed to `staging`
- prod VK recovery by forced service-main-PID kill was used successfully when the service got stuck in `stop-sigterm`
- isolated lab findings now show real backend improvement from `WAL`/pool/PR-monitor changes, but not a full fix

## Session Metadata

- Branch: `vk/ops-backup-retention-20260419`
- Repo: `/home/mcp/_vibe_kanban_repo`
- Focus: canonical staging sync cleanup, isolated backup retention PR, and continued VK stability diagnosis
- Workflow map: `VK_WORKFLOW.md`
  Latest lab conclusion:

- We now have two separate root-cause areas, and both are real:
  1. DB/scratch/backend pressure inside VK
  2. heavy preview/install child workload sharing the same service cgroup
- Lab-only fixes for (1) have shown major improvement.
- A lab-only transient-unit prototype for (2) also worked:
  - heavy `vibe-kanban` preview/install work no longer inflated the main VK lab service
  - the load moved into transient `vk-lab-codex-*.service` units
  - VK stop/cleanup successfully removed those units

Important:

- This isolation work is still lab-only.
- Nothing from the lab should be ported to prod or `staging` without explicit user confirmation.

Current production baseline:

- The user later explicitly approved porting the proven lab fixes to production.
- Prod now uses the DB/scratch fixes plus transient execution isolation.
- Heavy Codex/script child work should now land in separate `vk-exec-*.service` transient units instead of inflating the main `vibe-kanban.service` cgroup directly.
- The prod wrapper now exports:
  - `VK_USE_SYSTEMD_RUN=1`
  - `VK_TRANSIENT_MEMORY_HIGH=1500M`
  - `VK_TRANSIENT_MEMORY_MAX=3000M`

Open workspace send-state note:

- 2026-04-20: follow-up prompts in an already-open workspace could succeed server-side while the UI still looked idle until the workspace view remounted.
- Fix now live:
  - a websocket reconnect fix landed in `packages/web-core/src/shared/hooks/useJsonPatchWsStream.ts`
  - an additional session refresh/remount mitigation is live via:
    - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
    - `packages/web-core/src/pages/workspaces/WorkspacesMainContainer.tsx`
    - `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`
    - `packages/web-core/src/shared/lib/sessionStreamRefresh.ts`

## 2026-04-21 Current Handoff

- Immediate auth breakage in prod VK was repaired by resyncing the isolated VK auth store:
  - source: `/home/mcp/.codex/auth.json`
  - target: `/home/mcp/.local/share/vibe-kanban/codex-home/auth.json`
- Verification after the resync:
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home codex login status` returned logged-in
  - a real VK follow-up on `VC::ops Playbook` completed with summary `auth-path-ok`
- Important nuance:
  - this repaired the stale auth file
  - it did not eliminate the underlying concurrency risk from multiple VK-owned Codex workers sharing one ChatGPT token family

- Stale visible auth/bubblewrap errors were not only in failed execution rows.
- The larger source was stored process transcript files under:
  - `/home/mcp/.local/share/vibe-kanban/sessions/.../processes/*.jsonl`
- Remediation performed:
  - deleted stale empty failed/killed codingagent rows from `db.v2.sqlite`
  - restored process logs after an over-broad orphan cleanup attempt
  - sanitized process log files in place to remove only stale auth/bubblewrap noise
- Sanitization result:
  - `513` process log files touched
  - `8698` stale lines removed
  - removed patterns included:
    - `bubblewrap`
    - `user namespaces`
    - `Failed to refresh token`
    - `refresh_token_reused`
    - `token_expired`
- Example verified:
  - `VC:: Build` workspace/session:
    - workspace id: `458c9eb5-0127-4439-8952-4dc0c64e4f66`
    - session id: `bf133b52-0de2-424b-8dae-a933b57668cc`
  - the stale auth/bubblewrap lines were in process log:
    - `59d6a63b-33bc-4bfd-95a6-9a84103f3377.jsonl`
  - that file no longer contains those stale auth/bubblewrap lines

- `VC::ops Playbook` was unlinked from its issue and was repaired:
  - workspace id: `0b00ce25-fb2b-4742-b310-4bf6aaa1e7e7`
  - linked task id: `69a9dbf6-2cb9-48f2-8d9f-d160fe7a5107`

- New-workspace visibility was patched in:
  - `packages/web-core/src/shared/hooks/useCreateWorkspace.ts`
- This is intended to make new issue-linked workspaces appear under Issues without leaving and reopening the issue.

- Current unresolved problem:
  - the old chat-side remount workaround has been removed
  - the real root cause was backend-side: follow-up sends created the new `execution_process` row immediately, but the session execution-process websocket was not surfacing the first add promptly enough for the open workspace
- Current chat/live-update fix now live:
  - `crates/server/src/routes/sessions/mod.rs`
    - after successful follow-up spawn, VK now immediately pushes:
      - `execution_process_patch::add(&execution_process)`
      - `workspace_patch::replace(&workspace_with_status)`
    - this restores prompt-send visibility through the normal live event stream instead of waiting on a later refresh
  - removed the client-side forced refresh/remount workaround from:
    - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
    - `packages/web-core/src/pages/workspaces/WorkspacesMainContainer.tsx`
    - `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`
  - deleted:
    - `packages/web-core/src/shared/lib/sessionStreamRefresh.ts`
- Current remaining chat risk:
  - if the chat still feels stale after this fix, the next agent should inspect the session execution-process websocket path first, not add more UI remount logic
- Relevant files for future chat tracing:
  - `crates/server/src/routes/sessions/mod.rs`
  - `crates/server/src/routes/execution_processes.rs`
  - `crates/services/src/services/events/streams.rs`
  - `packages/web-core/src/shared/hooks/useExecutionProcesses.ts`
  - `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts`
  - `packages/web-core/src/shared/hooks/useJsonPatchWsStream.ts`

- Additional workspace relink completed:
  - `FR:: Garmin Sync Down`
  - workspace id: `25e19656-bc9f-4315-9712-a1d5468bdc00`
  - linked task id: `7d046622-1dd5-4025-bf04-fe2bfebd10a3`

- Recent backups relevant to this stream:
  - `/home/mcp/backups/vk-workspace-visibility-rollout-20260421T091514Z`
  - `/home/mcp/backups/vk-workspace-live-refresh-fix-20260421T094438Z`
  - `/home/mcp/backups/vk-orphan-process-log-cleanup-20260421T100138Z`
  - `/home/mcp/backups/vk-sanitize-stale-process-errors-20260421T100315Z`
  - `/home/mcp/backups/vk-remove-final-orphan-20260421T100416Z`
  - `/home/mcp/backups/vk-chat-live-refresh-rollout-20260421T100956Z`
  - `/home/mcp/backups/vk-vc-ops-playbook-relink-20260421T102339Z`
  - `/home/mcp/backups/vk-chat-root-fix-20260421T104346Z`
  - `/home/mcp/backups/vk-fr-garmin-relink-20260421T110337Z`

Codex follow-up recovery note, 2026-04-20:

- The `no rollout found for thread id ...` failures were not caused by missing backup data alone.
- The real production bug was in transient execution env propagation:
  - with `VK_USE_SYSTEMD_RUN=1`, VK launched Codex app-server in transient user units
  - those transient units were missing inherited wrapper env, especially `CODEX_HOME`
  - app-server therefore looked in `~/.codex` instead of `/home/mcp/.local/share/vibe-kanban/codex-home`
  - result: follow-up fork failed even though the rollout files and thread metadata existed
- Direct `codex fork` with `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home` was the proof: it succeeded against the same thread ids that VK app-server was rejecting.
- Production fix now live:
  - transient Codex units inherit `PATH`, `HOME`, `CODEX_HOME`, `SHELL`, `BASH_ENV`, and `VK_CODEX_BASE_COMMAND`
  - Codex executor base command is configurable through `VK_CODEX_BASE_COMMAND`
  - live wrapper exports:
    - `VK_CODEX_BASE_COMMAND=/home/mcp/.local/bin/codex`
- Also hardened:
  - Codex follow-up fork now uses a minimal `ThreadForkParams` instead of copying the full `ThreadStartParams` into `thread/fork`
- Result:
  - the previously interrupted sessions resumed and stayed `running` again without fresh `no rollout found` errors

If prod degrades again:

1. check whether main `vibe-kanban.service` memory is growing, or only a transient `vk-exec-*` unit
2. check whether scratch writes / DB locks are back, or whether the problem is now isolated to a transient child unit
3. preserve DB first, then inspect transient units before restarting the main service

- If VK starts logging:
  - `Codex's Linux sandbox uses bubblewrap and needs access to create user namespaces.`
- check these host settings first:
  - `/proc/sys/kernel/unprivileged_userns_clone`
  - `/proc/sys/kernel/apparmor_restrict_unprivileged_userns`
- On this MCP host, AppArmor currently blocks unprivileged user namespaces even though `unprivileged_userns_clone=1`.
- Direct repro:
  - `unshare -Ur true`
  - `bwrap --ro-bind / / --proc /proc --dev /dev true`
- VK now mitigates this in `crates/executors/src/executors/codex.rs` by forcing Codex sandbox mode to `danger-full-access` when `apparmor_restrict_unprivileged_userns=1`.
- Optional override:
  - `VK_ASSUME_USERNS_BLOCKED=1` to force the mitigation
  - `VK_ASSUME_USERNS_BLOCKED=0` to disable it

2026-04-21 residual red-chat follow-up note:

- The user still saw red bubblewrap-style errors in chats even after the earlier transcript cleanup.
- Fresh evidence:
  - live process logs on `2026-04-21` still contained:
    - `Codex's Linux sandbox uses bubblewrap and needs access to create user namespaces.`
  - example sessions:
    - `VC::ops Playbook`
      - session id `e73f8d43-be83-4714-a108-d120537e6691`
    - `VC:: Build`
      - session id `bf133b52-0de2-424b-8dae-a933b57668cc`
- Root cause was two-part:
  1. legacy follow-up forks were still effectively carrying old `workspaceWrite` sandbox settings into Codex app-server on resumed threads
  2. the Codex log normalizer treated warning/configWarning events as red `error_message` rows instead of neutral system messages
- Production repair now deployed:
  - rebuilt `/home/mcp/_vibe_kanban_repo/target/release/server`
  - rolled binary to:
    - `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - sha256 `47c15955156cddb47252823c110859c8450eb0767a9d19933322dded5c99bf6b`
  - restarted:
    - `vibe-kanban.service`
- Code changes relevant to this residual chat-noise fix:
  - `crates/executors/src/executors/codex.rs`
    - follow-up fork request now explicitly overrides forked thread config so stale legacy sandbox settings are not inherited
    - host userns/AppArmor mitigation remains in place
  - `crates/executors/src/executors/codex/normalize_logs.rs`
    - `configWarning` and warning events now normalize to `SystemMessage`
    - duplicate bubblewrap stderr line is suppressed
- Post-rollout cleanup:
  - rewrote `13` process log files under:
    - `/home/mcp/.local/share/vibe-kanban/sessions/.../processes/*.jsonl`
  - removed `26` fresh bubblewrap warning lines that were still replaying into chat history
  - direct `rg` check after cleanup returned no remaining matches for that exact bubblewrap warning string in stored process logs
- Validation run for this repair:
  - `cargo test -p executors renders_warning_events_as_system_messages`
  - `cargo test -p executors suppresses_duplicate_bubblewrap_stderr_warning`
  - `cargo check -p executors -p server`
  - `pnpm run format`
  - `cargo build --release --bin server`
  - `systemctl --user restart vibe-kanban.service`
  - `curl -s http://127.0.0.1:4311/api/info`

2026-04-21 chat-behavior follow-up:

- The remaining chat problem was not just stale websocket state.
- Three concrete UI-side faults were addressed in `staging`:
  1. local pending-send acknowledgment logic kept the composer and status in a fake in-between state after the server had already accepted the follow-up
  2. `useConversationHistory` could miss new turns that arrived already completed, because they skipped the running-state path and never got loaded into the displayed timeline
  3. bottom-lock correction only reran on row-count / virtualizer-size changes, so streaming growth inside the unvirtualized tail could leave the viewport stuck above the real bottom
- Current fix set:
  - `packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx`
    - remove pending follow-up acknowledgment state
    - clear the editor immediately after a successful follow-up POST
  - `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts`
    - detect newly added already-completed processes and load their historic entries immediately
    - update completed processes even when the final stored entry list is empty
  - `packages/web-core/src/features/workspace-chat/model/useConversationVirtualizer.ts`
    - refresh bottom-lock correction on every timeline content update
    - release bottom lock based on leaving the near-bottom region, not only upward-scroll delta heuristics
  - `packages/web-core/src/features/workspace-chat/ui/ConversationListContainer.tsx`
    - pass the conversation content version through to the virtualizer
- Targeted validation passed:
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm run format`
- Repo-wide validation is still environment-blocked here:
  - `pnpm run check`
  - `pnpm run lint`
  - both fail during backend Rust compilation because `pkg-config` cannot find system `glib-2.0`

2026-04-21 chat stream root cause confirmed and deployed:

- The stuck-chat symptom was confirmed in the live service journal, not just inferred:
  - repeated lines like `MsgStore broadcast lagged ... messages dropped for this subscriber`
- Why that matters:
  - running chat/process log streams are incremental JSON-patch streams
  - once messages are silently dropped, the client can no longer reconstruct the turn correctly
  - reopening the app works because it reconnects and replays history from scratch
- Current repair:
  - `crates/utils/src/msg_store.rs`
    - added `history_plus_stream_strict()`
    - broadcast lag now becomes a stream error for patch-stream consumers
  - `crates/services/src/services/container.rs`
    - running raw/normalized process log websocket streams now use the strict mode so lagged subscribers fail closed instead of drifting stale
  - `packages/web-core/src/shared/lib/streamJsonPatchEntries.ts`
    - unexpected websocket close/error now triggers reconnect with replay-state reset and rebuild
- Validation for this repair:
  - `pnpm --filter @vibe/web-core run check`
  - `cargo check -p utils -p services -p server`
  - `cargo test -p utils --lib msg_store`
  - `pnpm --filter @vibe/local-web run build`
  - `cargo build --release --bin server`
  - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - `curl -s http://127.0.0.1:4311/api/info`
- Live binary sha256 after this 2026-04-20 repair:
  - `946a4211438d532614a7055672c2fa25c710312b9b38923abf812fbb602bc964`

2026-04-21 frontend 404 follow-up:

- After the chat-stream redeploy, the live service could answer `/api/info` but returned `404 Not Found` at `/`.
- Root cause was build invalidation, not routing logic:
  - `crates/server/src/routes/frontend.rs` and the router were correct
  - the real problem was `crates/server/build.rs` not tracking `packages/local-web/dist`
  - after `pnpm --filter @vibe/local-web run build`, Cargo could still reuse a stale server build that did not contain the current embedded frontend assets
- Repair now landed in source:
  - `crates/server/build.rs`
    - recursively emits `cargo:rerun-if-changed` for `packages/local-web/dist`
- Repair now deployed:
  - rebuilt `target/release/server`
  - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - live sha256 now `a6d17ed54f8ceba064928404ab2af055ae00d855e5bd889e193df265ef6b45b3`
- Live verification after redeploy:
  - `curl -i http://127.0.0.1:4311/` returns `200 OK` with `index.html`
  - `curl -i http://127.0.0.1:4311/assets/index-DWkKdBPw.js` returns `200 OK`
  - `curl -s http://127.0.0.1:4311/api/info` still returns healthy config JSON

2026-04-21 chat history load follow-up:

- After the 404 fix, the next live failure was “chats aren’t loading”.
- Root cause was not session selection or the session execution-process stream:
  - `/api/sessions?workspace_id=...` returned valid sessions
  - `/api/execution-processes/stream/session/ws?...` returned initial snapshot + `Ready`
  - the stuck path was the historic normalized log websocket for finished coding-agent processes
- Verified failure before fix:
  - raw log replay for execution process `ac4680a0-2573-4a78-b71d-8a879caf56b8` returned data
  - normalized replay for the same process opened but emitted nothing and timed out
- Actual backend cause:
  - `crates/services/src/services/container.rs`
  - finished-process normalized replay used a temp `MsgStore` with a history-plus-live subscription model
  - final normalized `JsonPatch` / `Ready` messages could race between history snapshot capture and broadcast receiver subscription
  - when the race lost, the websocket stayed open with no replayed entries, so the chat UI looked blank/loading forever
- Repair now landed and deployed:
  - finished-process normalized replay now awaits normalization, deduplicates the resulting patch history in-memory, and serves a finite replay stream
  - running-process replay path is unchanged
- Live verification after redeploy:
  - normalized replay for `ac4680a0-2573-4a78-b71d-8a879caf56b8` now returns normalized entries immediately
  - `/api/info` returns `200`
  - live sha256 now `e0b3704dcce3f4cf70031141b85c5e2fea0169a6f0d6e0daf458f0fc3656f461`
- Operational note:
  - `systemctl --user restart vibe-kanban.service` got stuck in `deactivating (stop-sigterm)` again during rollout
  - recovered using the documented path by killing only the stuck main PID `2225915`, after which systemd restarted the service cleanly

2026-04-21 Garmin historic replay follow-up:

- The earlier finished-process replay fix was still not enough for `FR:: Garmin Sync Down`.
- Exact failing workspace/session:
  - workspace id `25e19656-bc9f-4315-9712-a1d5468bdc00`
  - session id `3a014c6c-4d98-409f-87d9-1a7f111644c0`
- Exact failing process:
  - `123302ac-b1d5-4587-90b6-5d3bba2d712e`
  - persisted transcript file:
    - `/home/mcp/.local/share/vibe-kanban/sessions/3a/3a014c6c-4d98-409f-87d9-1a7f111644c0/processes/123302ac-b1d5-4587-90b6-5d3bba2d712e.jsonl`
    - `31,667` lines
    - `83,902,430` bytes
  - file validity:
    - valid JSONL
    - only raw `Stdout` / `Stderr` records, no persisted `JsonPatch` rows
- Actual remaining root cause:
  - historical replay still loaded large finished transcripts monolithically before sending the first websocket message
  - `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts` still treated historic replay as all-or-nothing, so one slow recent process could blank the entire conversation during initial load
- Current repair now landed and deployed:
  - `crates/utils/src/execution_logs.rs`
    - added streaming file reads for persisted process logs
  - `crates/services/src/services/execution_process.rs`
    - historical raw replay now streams parsed `LogMsg` values incrementally from disk
  - `crates/services/src/services/container.rs`
    - finished normalized replay now feeds persisted raw logs into the normalizer incrementally and streams patches as they are produced
    - removed `ensure_container_exists()` from historical normalization so chat replay does not recreate worktrees or trigger git inspection
  - `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts`
    - initial/newly-completed/reloaded history now paints partial historic replay while a process is still loading
- Live validation after redeploy:
  - `/api/execution-processes/123302ac-b1d5-4587-90b6-5d3bba2d712e/raw-logs/ws`
    - first replay patch in about `67 ms`
  - `/api/execution-processes/123302ac-b1d5-4587-90b6-5d3bba2d712e/normalized-logs/ws`
    - first normalized replay patch in about `61 ms`
  - `curl -I http://127.0.0.1:4311/`
    - `200 OK`
  - `curl -s http://127.0.0.1:4311/api/info`
    - healthy
- Rollout:
  - rebuilt `packages/local-web/dist`
  - rebuilt `target/release/server`
  - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service` cleanly
  - live sha256 now `2288ec455166a1057c7567763555e3545bd71f87892942aec46ea149f6f961e4`

2026-04-21 attachment/workspace-create slowdown follow-up:

- User reported three live symptoms together:
  - VK felt extremely slow
  - attachment insertion errored from the UI
  - creating a new workspace showed `failed to fetch`
- Verified live narrowing before fix:
  - direct `POST /api/workspaces` already succeeded, so workspace creation was degraded by live server saturation rather than missing route wiring
  - direct global `POST /api/attachments/upload` failed with backend `500`
  - journal showed `UNIQUE constraint failed: attachments.hash`
  - journal also showed repeated slow query bursts and slow pool acquires around workspace summaries
- Fixes now landed and deployed:
  - `crates/services/src/services/file.rs`
    - duplicate attachment hash insert collisions now fall back to `find_by_hash` and return the existing attachment instead of failing the request
  - `crates/server/src/routes/workspaces/workspace_summary.rs`
    - added a small `2s` cache keyed by `archived` to reduce identical summary storms against SQLite
- Validation after redeploy:
  - `cargo check -p services -p server`
  - `cargo build --release --bin server`
  - `pnpm run format`
  - `curl http://127.0.0.1:4311/api/info`
    - `200` in about `9 ms`
  - `POST /api/workspaces`
    - `200` in about `8 ms`
  - duplicate `POST /api/attachments/upload` with the same file payload
    - first call `200` in about `5 ms`
    - second call `200` in about `2 ms`
    - second call returned the same attachment id, confirming dedupe reuse instead of `500`
- Rollout notes:
  - copied new server binary into `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - `systemctl --user restart vibe-kanban.service` hung in `deactivating` again
  - systemd eventually killed old PID `2388147` with `SIGKILL` and started new main PID `2444957`
  - live sha256 now `719712f0cc78503eb9d04908f4d9480d9cb11fb820294995138ed62e66a6083b`

2026-04-21 chat reset / first-screen attachment follow-up:

- User then reported two residual UI problems:
  - agent messages could finish without the chat ending cleanly, leaving the composer blocked
  - after a delay, the chat pane could reset to the empty-state copy:
    - `Your workspace conversation will appear here once a new turn starts.`
  - attachment insertion still failed from the initial workspace screen even though it worked from the second screen
- Actual frontend causes identified in code:
  - `packages/web-core/src/shared/hooks/useWorkspaceSessions.ts`
    - follow-up-related session refreshes could replace or clear the current selection even when the selected session still existed
    - once selection dropped, `ConversationListContainer.tsx` showed the empty-state string above
  - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
    - existing-session follow-ups were invalidating the workspace session list unnecessarily
  - `packages/ui/src/components/attachment-node.tsx` and `packages/ui/src/components/image-node.tsx`
    - the editor nodes still used raw `/api/...` paths for attachment metadata and proxy URLs instead of host-scoped paths
- Repair now landed:
  - `packages/web-core/src/shared/hooks/useWorkspaceSessions.ts`
    - preserve the current existing-session selection in the same workspace when it still exists
    - only clear selection on empty results when the workspace actually changed
  - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
    - removed workspace-session invalidation on follow-up send
  - `packages/ui/src/components/WorkspaceContext.tsx`
    - added `HostIdContext` and `scopeLocalApiPath(...)`
  - `packages/web-core/src/shared/components/WYSIWYGEditor.tsx`
    - now passes host id into UI editor-node context
  - `packages/ui/src/components/attachment-node.tsx`
  - `packages/ui/src/components/image-node.tsx`
    - host-scope local attachment metadata/proxy/file URLs consistently
- Validation completed:
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/local-web run build`
  - `cargo build --release --bin server`
  - `pnpm run format`
  - `curl -s http://127.0.0.1:4311/api/info`
  - `curl -sI http://127.0.0.1:4311/`
  - `sha256sum /proc/$(systemctl --user show -p MainPID --value vibe-kanban.service)/exe /home/mcp/.local/bin/vibe-kanban-server-cleanfix`
- Live state now:
  - `vibe-kanban.service` is active
  - the running process matches deployed binary sha `8b3b3f9e72dc37f99df018e88fa8f321cfd65b7df7b72b1136426f62832e15af`
- Still not directly UI-verified in the desktop session:
  - reopening the affected chat and confirming it no longer falls back to the empty state after a completed turn
  - retrying attachment insertion from the initial workspace screen

2026-04-22 chat live-update follow-up:

- User reported that `FR:: Coaches Feature Stream` started streaming a few thought/log lines and then stopped updating while the blinking thinking indicator remained.
- Exact live workspace chain:
  - workspace id `fcd0ec67-a0fe-42a8-9337-ef3228ceee80`
  - session id `a97647d3-6d95-4470-a320-fe6bf415edd8`
  - process id `b20d10a2-bf5b-43c2-97ef-ac1186664201`
  - DB state showed the process completed at `2026-04-22T11:40:54Z`
- Important live evidence:
  - the journal showed repeated `MsgStore broadcast lagged ... messages dropped for this subscriber` bursts at `2026-04-22T11:40:49Z` while that workspace was active
  - this strongly indicated the UI was stuck on stale stream state rather than the agent still truly running
- Actual remaining backend cause:
  - `crates/services/src/services/events/streams.rs` still used raw `BroadcastStream` subscriptions for session/workspace/scratch event websockets
  - those paths silently swallowed lagged broadcast errors instead of failing and letting the client reconnect
  - the result was that the session execution-process websocket could miss the completion/update patch and leave the chat UI stuck in stale `running`
- Repair now landed and deployed:
  - `crates/services/src/services/events/streams.rs`
    - convert `BroadcastStreamRecvError::Lagged(n)` into an `io::Error`
    - applies to:
      - `stream_execution_processes_for_session_raw`
      - `stream_scratch_raw`
      - `stream_workspaces_raw`
    - intent is fail-closed + reconnect instead of silent stale state
- Validation completed:
  - `cargo check -p services -p server`
  - `cargo build --release --bin server`
  - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified:
    - `curl -sf http://127.0.0.1:4311/api/info`
    - active PID executable path is `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - running PID sha matches deployed file sha `9ad30eadb01eb7a357493a6232ffdddc3c212d32d8ae2dd050ff35ec742acad2`
- Operational note:
  - the first post-build restart raced the file replacement and briefly relaunched the deleted old inode
  - the second clean restart after the rename picked up the new binary correctly
- Still needs real UI confirmation:
  - reopen `FR:: Coaches Feature Stream`
  - confirm the chat continues to stream until completion instead of freezing on thinking state

2026-04-22 issue/workspace relink follow-up:

- User reported that three new local issues were not linked to the workspaces created for them.
- Verified broken live pairs before repair:
  - task `af85bbe0-7c78-46ea-b0ec-91476596850c` (`FR:: Coaches Feature Stream `)
    - workspace `fcd0ec67-a0fe-42a8-9337-ef3228ceee80`
    - workspace had `task_id = null`
  - task `6bc54000-384e-4164-8995-b1c5a7d2469b` (`FR::Investigate today's active burn calories`)
    - workspace `ff6bfbf1-8f71-4787-9e92-df7910c0928f`
    - workspace had `task_id = null`
  - task `f0933141-23fd-4a0e-89d3-5d2202325cea` (`FR::Investigate today's active burn calories`)
    - workspace `e9c522ad-a455-42c7-9a4d-74ed6bf8ee98`
    - workspace had `task_id = null`
- Root cause now addressed in code:
  - `packages/web-core/src/shared/components/CreateChatBoxContainer.tsx`
    - added `forcedLinkedIssue` so submit can use an explicit issue/project from route context instead of relying only on create-mode draft state
  - `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`
    - issue-route workspace-create panel now passes the current route issue/project directly into `CreateChatBoxContainer`
  - `crates/server/src/routes/workspaces/create.rs`
    - added bounded retry for local task resolution during create-and-start when `linked_issue` is present but the first lookup misses
- Why this matters:
  - this covers both failure modes seen in practice:
    1. route-linked issue context getting lost before submit
    2. newly created local issues not yet resolving on the first backend lookup
- Live repairs already performed:
  - linked `fcd0ec67-a0fe-42a8-9337-ef3228ceee80` -> `af85bbe0-7c78-46ea-b0ec-91476596850c`
  - linked `ff6bfbf1-8f71-4787-9e92-df7910c0928f` -> `6bc54000-384e-4164-8995-b1c5a7d2469b`
  - linked `e9c522ad-a455-42c7-9a4d-74ed6bf8ee98` -> `f0933141-23fd-4a0e-89d3-5d2202325cea`
- Validation completed:
  - `cargo check -p server -p services`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run build`
  - `cargo build --release --bin server`
  - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified running PID sha matches deployed binary sha `ebbdb9041fd2b6f517606005b53bca8ff1980f68553c1fa9135169b5dc6395cc`
- Operational note:
  - the first restart after replace again came up on the deleted old inode
  - a second clean restart after the rename picked up the new binary correctly
- Still needs real UI confirmation:
  - create one new workspace from an issue route and confirm it appears linked immediately
  - then continue retesting the chat stream behavior in `FR:: Coaches Feature Stream`

2026-04-22 chat streaming follow-up:

- User reported that the orchestration workspace under `FR:: Coaches Feature Stream` would briefly stream a few lines and then appear stuck/busy.
- Exact live chain investigated:
  - workspace `679c24ec-7368-4a08-8f82-931f8d0ea896`
  - session `65c4bde9-df70-4e12-91fd-210c41e7aa3a`
  - latest process `d928142b-d587-4a16-9e23-013d1a6df622`
  - DB showed that latest process was already `completed` at `2026-04-22T12:39:44Z`
- Actual remaining root cause:
  - the normalized logs websocket was replaying a pathological stream of repeated `replace` patches for the same entry path while the response text grew
  - live probe before fix on `/api/execution-processes/d928142b-d587-4a16-9e23-013d1a6df622/normalized-logs/ws` saw about `3872` patch messages and `~5.07 GB` of websocket JSON in `20s`, dominated by `/entries/5`
- Repair now landed and deployed:
  - `crates/server/src/routes/execution_processes.rs`
    - batch normalized websocket patches in `50ms` windows
    - coalesce repeated ops by path so only the latest write in the window is sent
    - includes unit tests for the coalescing helper
  - `crates/server/Cargo.toml`
    - added direct `json-patch` dependency for the new server-side batching logic
- Validation completed:
  - `cargo test -p server coalesce_patch_ops -- --nocapture`
  - `cargo check -p server -p services`
  - `cargo build --release --bin server`
  - `pnpm run format`
  - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified live sha `4a5e3356b9c7dc4dff3b5e82d5e451ce58d789d8db48420bbe207517d2e70ba4`
  - repeated the same normalized-log websocket probe after deploy and saw about `60` patch messages, `128` patch ops, and `~109.6 MB` total JSON, with `finished` received in about `16.1s`
- Still needs real UI confirmation:
  - reopen the orchestration workspace in `FR:: Coaches Feature Stream`
  - confirm the live chat continues updating instead of freezing after a couple of lines

2026-04-22 orchestration replay follow-up:

- User asked whether the orchestration agent had stopped prematurely in `FR:: Coaches Feature Stream`.
- Exact chain reviewed:
  - workspace `679c24ec-7368-4a08-8f82-931f8d0ea896`
  - session `65c4bde9-df70-4e12-91fd-210c41e7aa3a`
  - process `d928142b-d587-4a16-9e23-013d1a6df622`
- Confirmed:
  - the process completed successfully
  - the raw process log file exists and contains the full final answer
  - the visible “stopped dead” behavior was the replay path, not the agent
- Root cause:
  - the direct app-server `CommandExecutionOutputDelta` path in `crates/executors/src/executors/codex/normalize_logs.rs` was still appending command stdout without truncation
  - one orchestration `rg` command therefore inflated normalized replay enough to make the chat look frozen
- Repair now live:
  - direct command-output delta normalization now uses `append_truncated_tail`
  - streaming command-output preview reduced to `8 KiB`
  - final command-output preview reduced to `16 KiB`
- Validation:
  - `cargo check -p executors -p server`
  - `cargo build --release --bin server`
  - `pnpm run format`
  - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified `/api/info` healthy
  - verified the exact normalized replay for `d928142b-d587-4a16-9e23-013d1a6df622` now completes in about `367 ms` across `8` websocket messages
- Still needs real UI confirmation:
  - reopen the orchestration workspace in `FR:: Coaches Feature Stream`
  - confirm the chat now loads the full transcript instead of appearing stuck after the first few lines

2026-04-22 websocket reconnect follow-up:

- User reported the orchestration workspace looked hung again even though prior replay fixes were live.
- Same workspace/session rechecked:
  - workspace `679c24ec-7368-4a08-8f82-931f8d0ea896`
  - session `65c4bde9-df70-4e12-91fd-210c41e7aa3a`
- Latest reviewed completed processes:
  - `e9217d86-70b9-40f1-99d3-eea14c70975e`
  - `58ef1157-6d7f-4a45-9c74-36722839475f`
- Confirmed:
  - both processes completed successfully and their raw `.jsonl` logs contain the full final answer plus `turn/completed`
  - the backend was not actually hanging on those runs
  - normalized replay for `e9217d86-70b9-40f1-99d3-eea14c70975e` completed in about `71 ms` with `2` websocket messages after the redeploy
  - the session execution-process websocket still sends the initial snapshot plus `Ready`
- Root cause found:
  - `packages/web-core/src/shared/hooks/useJsonPatchWsStream.ts` was clearing `data`, `dataRef`, and initialization state every time the reconnect effect cleaned up
  - because reconnects are driven by `retryNonce`, a transient close for the same endpoint could blank the chat even though the backend stream had recoverable state
- Repair now live:
  - reset logic moved into a separate `[enabled, endpoint]` effect
  - reconnect cleanup no longer wipes the current stream snapshot for the same endpoint
- Validation:
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run build`
  - `cargo build --release --bin server`
  - `pnpm run format`
  - rebuilt and redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified `/` returns `200`
  - verified `/api/info` healthy
- Still needs real UI confirmation:
  - reopen the orchestration workspace without refreshing/remounting
  - confirm a transient websocket hiccup no longer blanks or freezes the visible chat

2026-04-22 staging deploy:

- User asked to merge and deploy the current `staging` fixes.
- The canonical checkout `/home/mcp/_vibe_kanban_repo` was dirty, and local `staging` was also behind `fork/staging`.
- To avoid colliding with unrelated local edits, deployment was done from a clean detached worktree instead of an in-place merge:
  - `/tmp/vk-staging-deploy-20260422`
  - commit `6c0ce663a4548277f1ad774654b2bf82841cc126`
- Relevant staging commits included:
  - `76702b4d8 fix: persist local app bar project drag order`
  - `877748d2a Merge pull request #4 from artinflight/vk/9fea-vk-cleanup-left`
  - `04caf51a6 Clean up left column links and local compat flow`
- Validation from the clean staging tree:
  - `pnpm install --frozen-lockfile`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/ui run check`
  - `cargo check -p db -p server`
  - `pnpm --filter @vibe/local-web run build`
  - `cargo build --release --bin server`
  - `pnpm run format`
- Live deploy now points at:
  - binary `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - sha `36671ede4bd0971a00b6256c1bb252d537b369da7d9de5a39e6003689226ce43`
- The checked-out local `staging` worktree was also fast-forwarded cleanly:
  - `/home/mcp/code/worktrees/3714-vk-codeblock-onl/_vibe_kanban_repo`
  - now at `6c0ce663a4548277f1ad774654b2bf82841cc126`
- Health after deploy:
  - `vibe-kanban.service` active
  - `/` returns `200`
  - `/api/info` healthy

2026-04-22 local issue/workspace linking follow-up:

- User reported new workspaces created inside new local issues were still landing unlinked.
- Fresh live failure confirmed:
  - issue/task `36de33b5-5fe7-4996-831a-c966c89d7bb5`
  - workspace `6fdd2862-9fcf-4624-8b45-0b9dd1b109dc`
  - title `VK::Fix collapsed mobile columns tk2`
  - task timestamp `2026-04-22 20:23:15.643`
  - workspace timestamp `2026-04-22 20:23:23.803`
  - workspace still had `task_id = null`
- Root cause found:
  - `crates/server/src/routes/workspaces/links.rs`
  - the fallback local `/api/workspaces/:id/links` path still used a one-shot local task lookup and then fell through toward remote-link behavior
- Repair now live:
  - local link requests retry local task resolution `8` times with `250 ms` delay
  - unresolved local issue links now return a local bad-request error instead of drifting into remote-client behavior
- Live data repair:
  - relinked workspace `6fdd2862-9fcf-4624-8b45-0b9dd1b109dc` to task `36de33b5-5fe7-4996-831a-c966c89d7bb5`
- Validation:
  - `cargo check -p server`
  - `cargo build --release --bin server`
  - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified `/api/info` healthy
  - created disposable issue `VK LINK TEST 20260422T203516Z`
  - created disposable linked workspace `7dee992f-ce10-4326-84e2-fbdd1da3d40c`
  - verified the workspace row immediately stored task `d3e32d0a-c67e-417b-a7af-30072d71a1d4`
  - deleted the disposable issue and workspace after validation

2026-04-22 orphan link cleanup:

- User asked to find any remaining unlinked issues/workspaces and link them.
- Additional live relinks applied:
  - workspace `69108907-ee4c-4c2d-8d96-fe496bb2b6bd` `FR::Fix Quick Add`
    - linked to task `4c7065b5-b43a-41f9-b524-e6f3068d39a2` `ART-34 · FR fix quick add`
  - workspace `5db38b19-2e12-4e77-a746-c7ae2b515ab7` `Expand Quick Add Food`
    - linked to task `77762500-bfcb-4636-b8e4-f268f6da1b95` `ART-32 · Expand Quick Add Food`
- Remaining unlinked workspace rows were reviewed and intentionally left alone:
  - `probe-ws`
  - `probe-ws-postfix`
    - probe/test rows with no issue match
  - `FR::Investigate today's active burn calories`
  - `VK::Auto archive when 'Done'`
    - exact-title issue matches already have linked workspaces, so linking these would recreate duplicate workspace associations
  - `OVA::Dashboard Init Build`
  - `FR::Refactor - Merge Rules`
  - `The Dashboard nutrition card is WAY too verbose. It's breaking the layout and overloading the user`
    - no confident local issue match was found, so they were left untouched to avoid bad data repair

2026-04-27 Hyrox Ready agent repetition investigation:

- Investigated recent Vibe Kanban/Codex sessions for the Hyrox Ready app after agents appeared to repeat themselves.
- Live VK service was missing `CODEX_HOME`, so Codex app-server processes were using shared `/home/mcp/.codex` instead of the intended isolated `/home/mcp/.local/share/vibe-kanban/codex-home`.
- Restored systemd drop-in:
  - `/home/mcp/.config/systemd/user/vibe-kanban.service.d/codex-home.conf`
  - `Environment=CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
- Ran `systemctl --user daemon-reload`; waited for Hyrox process `d128a1215d024e8887bf3eb27c7b3468` to finish, then restarted `vibe-kanban.service`.
- Verified the restarted live process environment includes `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home` and `/api/info` is healthy.
- Evidence sampled:
  - last 25 detectable Hyrox Codex app-server inits all reported `codexHome: /home/mcp/.codex`
  - raw logs include large full-thread `turns` payloads, which can look like repeated transcript history
  - normalized log handling ignores `ThreadStartResponse`/`ThreadForkResponse` turns and only records the session id/model params
  - no broad automatic prompt replay loop was found in recent Hyrox execution rows
- Current active Hyrox repetition pattern in `FR::Update Name` was explained by repeated `HANDOFF.md`/`STREAM.md` conflicts while replaying multiple metadata commits during rebase/merge.

2026-04-29 Codex isolated-home rollout migration:

- User hit `thread/fork request failed: no rollout found for thread id 019dce56-2737-7d13-9965-e8996caca9dd`.
- VK service still had the correct live environment:
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
- Root cause was stale DB continuity from the period when VK was accidentally writing Codex rollouts under shared `/home/mcp/.codex`.
- The specific missing rollout existed only at:
  - `/home/mcp/.codex/sessions/2026/04/27/rollout-2026-04-27T09-47-25-019dce56-2737-7d13-9965-e8996caca9dd.jsonl`
- Copied all DB-referenced missing rollouts from `/home/mcp/.codex` into `/home/mcp/.local/share/vibe-kanban/codex-home`.
- Result:
  - `121` rollout files copied
  - `121` matching shell snapshots copied
  - follow-up audit found `0` DB `agent_session_id` values missing from the isolated Codex home
- No service restart was performed because active agents were running and the service environment was already correct.

2026-05-06 follow-up safe disk cleanup:

- User pushed back that more space should be available and that previously described safe items had not all been cleaned.
- Completed the safe rebuildable cleanup that does not touch continuity state:
  - removed all `/home/mcp/code/archive/**/node_modules`; follow-up count is `0`
  - removed rebuildable Rust `target` trees from:
    - `/home/mcp/_vibe_kanban_repo/target`
    - `/home/mcp/code/worktrees/6685-vk-pr-details-hi/_vibe_kanban_repo/target`
    - `/home/mcp/code/worktrees/ea3c-vk-auto-archive/_vibe_kanban_repo/target`
  - removed stale strict-eligible worktree install:
    - `/home/mcp/code/worktrees/c961-fr-orc-android-p/hyroxready-app/node_modules`
  - removed `/home/mcp/_vibe_kanban_repo/scripts/__pycache__`
- Current disk state:
  - `df -h /home/mcp`: `233G` total, `164G` used, `59G` free, `74%` used
- Corrected the worktree `node_modules` scan to group by actual Git repo root, not only the first path segment under `/home/mcp/code/worktrees`.
- Remaining worktree `node_modules` count is `68`, but under the approved rule they are either active or below `>4 days untouched`; several large VK/Hyrox installs are near the threshold and can be removed later without changing policy.
- Attempted journal vacuum did not reduce `journalctl --disk-usage`, so do not claim journal cleanup succeeded.
- Did not touch backups, VK DB, VK `codex-home`, VK sessions, source files, package-manager global caches, Android SDK/AVD, or running services.

2026-05-06 no-restart frontend repair:

- User asked to return to VK and fix the items that do not require a restart.
- Operational repair:
  - recreated `/home/mcp/.cache/utils/attachments`
  - permissions are `0700`
  - generic upload/delete smoke test against `http://127.0.0.1:4311/api/attachments/upload` passed
  - smoke-test attachment DB rows and files were deleted afterward
- Frontend fixes now built and published through refreshable frontend assets:
  - codeblock copy button overlay in read-only chat markdown/code blocks
  - clipboard fallback now tries `document.execCommand('copy')` before VS Code parent bridge fallback
  - local fallback workspace rename/delete actions treat `owner_user_id = ""` as owned only when a matching local workspace exists
  - workspace chat attachment upload reports missing workspace/session and upload failures instead of silently no-oping
  - mobile attachment picker activation now uses a native label/input control instead of a hidden input clicked from JS
  - create-mode attachment upload failures are surfaced in the composer instead of only being logged
  - files over the backend `20 MB` upload cap are rejected client-side with a visible message
- Published release:
  - base UI repair: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1531Z-no-restart-ui-fixes`
  - mobile attachment follow-up: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1548Z-mobile-attachment-fix`
  - attachment visible-error follow-up: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1625Z-attachment-visible-errors`
  - `frontend-dist/current` points to that release
  - live page references `/assets/index-D-47mEIl.js` and `/assets/index-DvZydbR5.css`
- Verification:
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/ui run check`
  - targeted prettier for touched frontend files
  - `pnpm --filter @vibe/local-web run build`
  - targeted `git diff --check`
  - `https://vibe.local/` returned `200` with the new asset names using `curl -k`
  - `http://127.0.0.1:4311/api/info` returned healthy JSON
  - `POST /api/attachments/upload` small-file smoke passed after the follow-up and the smoke attachment was deleted
- No restart happened:
  - `vibe-kanban.service` stayed active/running
  - main PID remained `3962645`
- Disk note:
  - the no-restart frontend release is only `73M`
  - current `df -h /home/mcp` is `42G` free / `82%` used
  - the jump is from `/home/mcp/backups/.vk-lean-restore-20260506T151701Z.tmp`, an incomplete-looking backup temp directory around `16G`
  - no matching `vk_lean_backup`, tar, or rsync process was active when checked
  - did not remove it because backup paths require explicit cleanup approval
- Important remaining restart-required work:
  - backend attachment cache-dir self-healing
  - true existing-workspace new-session attachment support
  - needs-attention server summary-cache invalidation
  - durable PR snapshot/reconcile/backfill
- Promotion note:
  - the live frontend hotfix was built from the current dirty repair checkout, which already contained earlier UI repair edits in this stream
  - move these changes through a clean branch/PR before treating them as permanent

2026-05-06 frontend rollback after project-list regression:

- User reported that old projects came back and project ordering was lost after hard-refreshing the no-restart frontend bundle.
- Cause: the refreshable frontend repair builds were made from the dirty repair checkout, so unrelated local project/nav UI edits rode along with the attachment/codeblock fixes.
- Immediate mitigation completed without restart:
  - repointed `/home/mcp/.local/share/vibe-kanban/frontend-dist/current` back to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260505T1648Z`
  - live `/` now references `/assets/index-CErwigwv.js` and `/assets/index-xIIrANvd.css`
  - `vibe-kanban.service` stayed active/running on PID `3962645`
- Consequence:
  - the attachment visible-error/mobile picker/codeblock-copy no-restart bundles are no longer live
  - rebuild any frontend hotfix from a clean worktree and apply only the intended files
- 100 MB attachment limit work:
  - local code now raises local VK attachment caps from `20 MB` to `100 MB` in `FileService`, both Axum upload routes, and the frontend preflight constant
  - this is not live until the backend binary is built/deployed and VK is restarted with approval

2026-05-06 clean codeblock-copy frontend rebuild:

- User reported codeblock copy was not working after the rollback.
- Built from clean worktree `/tmp/vk-codeblock-copy-clean-20260506T165520Z` on `fork/main` commit `3cfe96ab8`.
- Only source change in that clean worktree:
  - `packages/web-core/src/shared/lib/clipboard.ts`
  - adds `document.execCommand('copy')` fallback between `navigator.clipboard.writeText` and the VS Code parent bridge fallback
- Existing `fork/main` codeblock-copy UI files were included:
  - `packages/web-core/src/shared/components/CodeBlockCopyButton.tsx`
  - `packages/web-core/src/shared/components/ReadOnlyCodeBlockCopyPlugin.tsx`
  - `packages/web-core/src/shared/components/WYSIWYGEditor.tsx`
- Published without restart:
  - `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1701Z-clean-codeblock-copy`
  - `frontend-dist/current` points to that release
  - `vibe-kanban.service` stayed active/running on PID `3962645`
- Validation:
  - clean worktree `pnpm install --prefer-offline --frozen-lockfile`
  - targeted prettier
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run build`
  - bundle contains `Copy code`, `vscode-iframe-clipboard-copy`, and `execCommand`
- Caveat:
  - live HTTP verification through `http://127.0.0.1:4311` and `https://vibe.local` timed out because the running VK process is saturated around `19 GB` RSS
  - do not restart without user approval

User QA checklist for the no-restart frontend repair:

- Hard refresh `https://vibe.local` so the browser loads `/assets/index-D-47mEIl.js`.
- Codeblock copy:
  - open any workspace chat with a fenced code block in an agent response
  - hover the code block
  - click the copy icon in the upper-right of the code block
  - paste elsewhere and confirm only that code block copied
- Workspace rename/delete:
  - open an issue with a linked local workspace whose action menu previously hid rename/delete
  - confirm rename/delete actions are visible
  - rename a low-risk workspace and verify the new name persists after refresh
- Attachments:
  - on mobile, tap the paperclip and confirm the OS file picker opens
  - after selecting a file, confirm VK shows `Uploading attachment...`, inserts markdown/previews the attachment, or shows a clear error
  - in an existing workspace with an existing session selected, paste or attach a small file/image
  - confirm markdown is inserted into the composer and the preview renders
  - in new-session mode for an existing workspace, paste/attach a file and confirm VK now shows a clear limitation/error instead of silently doing nothing
- Needs-review marker:
  - browser-refresh the project list after checking a workspace
  - if a marker still persists, that is expected until the backend summary-cache invalidation ships with a restart-approved backend deploy

2026-05-08 needs-review project marker refresh-only deploy:

- User still saw needs-review icons on PR/programming and VK even though neither had active agents needing review.
- Live-data cause:
  - `programming` was being lit by archived completed workspace `PG::Remove blockquote wrapper from Sophia`
  - `vibe-kanban` was being lit by archived completed workspaces `VK::Merged PRs`, `VK::PR details not showing up in Issue cards`, and `VK::Fix Flyout Workspace Links`
  - those rows had unseen completed turns, but no active running/pending agent review requirement
- Source behavior now used by the project marker:
  - fetch only active workspace summaries for the left-column project marker
  - count pending approvals
  - count unseen non-running active workspaces
  - ignore failed/killed/interrupted latest process statuses so the triangle state does not create a project marker
- Published without restarting VK:
  - built `packages/local-web`
  - copied the build to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260508Tneeds-review-active-only`
  - updated `frontend-dist/current` to that release
  - live `/` now references `/assets/index-D9TtF3Pk.js`
- Validation:
  - `pnpm --filter @vibe/web-core run check` passed earlier for this source patch
  - `pnpm --filter @vibe/local-web run check` passed earlier for this source patch
  - `pnpm --filter @vibe/local-web run build` passed for the deployed bundle
  - `curl -sS http://127.0.0.1:4311/` confirms the live page references `index-D9TtF3Pk.js`
  - `curl -sSI http://127.0.0.1:4311/assets/index-D9TtF3Pk.js` returns `200 OK`
- No restart happened.
- User test:
  - refresh `https://vibe.local`
  - PR/programming and VK should no longer show a needs-review project marker from the archived stale rows above

2026-05-08 needs-review deploy rollback after project-list regression:

- User reported archived projects returned and project order was lost after the refresh-only frontend deploy.
- Cause:
  - the deployed `20260508Tneeds-review-active-only` bundle was built from the dirty repair checkout
  - that dirty checkout still contains unrelated project/nav UI changes that previously caused the archived-project/order regression
- Immediate rollback completed without restarting VK:
  - restored `/home/mcp/.local/share/vibe-kanban/frontend-dist/current` to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260507Tandroid-scroll-hotfix`
  - live `/` now references `/assets/index-BqGLQj9b.js` and `/assets/index-xIIrANvd.css`
- Targeted PR/VK marker cleanup completed instead of shipping another bundle:
  - backup: `/home/mcp/backups/pr-vk-stale-needs-review-pre-seen-20260508T154218Z.sqlite`
  - marked these stale archived completed workspaces seen through the live API:
    - `PG::Remove blockquote wrapper from Sophia`
    - `VK::Merged PRs`
    - `VK::PR details not showing up in Issue cards`
    - `VK::Fix Flyout Workspace Links`
  - verified live summaries now have no remaining attention rows for `programming` or `vibe-kanban`
- Do not deploy frontend bundles from `/home/mcp/_vibe_kanban_repo` while it is dirty with unrelated UI repair work.
- For any future refresh-only frontend hotfix, build from the exact currently-live release/source baseline or a clean worktree with only the intended patch.

2026-05-08 project order restore after dirty frontend deploy:

- User reported project sort order was still not fixed after the frontend rollback.
- Cause:
  - the bad dirty frontend bundle wrote `local_project_order: []` into the server `UI_PREFERENCES` scratch record
  - rollback restored the older frontend code but did not restore the wiped saved preference
- Live repair completed without restarting VK:
  - backup: `/home/mcp/backups/ui-project-order-restore-pre-20260508T154532Z.sqlite`
  - restored `local_project_order` from the latest good backup order
  - appended newer active projects at the end: `ops-playbook`, `Monitor local`, `VL`
  - verified live scratch now has 12 project IDs in `local_project_order`
  - live frontend remains `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260507Tandroid-scroll-hotfix`
- Source repair completed so future builds do not erase the saved order:
  - `crates/db/src/models/scratch.rs` includes `UiPreferencesData.local_project_order`
  - `crates/server/src/bin/generate_types.rs` exports `ProjectStatusConfigData`, needed by generated scratch types
  - `shared/types.ts` regenerated with `local_project_order`
  - `useUiPreferencesScratch` now round-trips `local_project_order`
  - `useUiPreferencesStore` now stores and updates `localProjectOrder`
  - `SharedAppLayout` orders local projects by `localProjectOrder` and persists local drag reorder through scratch
- Validation:
  - `pnpm run generate-types`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm run format`
- User may need a hard browser refresh if the old bad JS is still loaded in the tab.

2026-05-08 collapsed kanban column needs-review marker:

- Source patch completed in `packages/web-core/src/features/kanban/ui/KanbanContainer.tsx`.
- Collapsed status columns now show a small brand marker when the collapsed column contains either an active linked workspace needing review or any issue in a review-named status.
- Marker logic is actionable-only:
  - includes pending approvals
  - includes unseen completed/non-running active workspace activity
  - includes non-empty `review` / `in review` / `needs review` / `ready for review` columns
  - excludes failed/killed/interrupted triangle states
  - excludes archived or missing local workspaces
- The marker is computed independently from the "show workspaces" display preference, so collapsed columns can still indicate hidden workspace attention.
- Validation:
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm run format`
  - `git diff --check -- packages/web-core/src/features/kanban/ui/KanbanContainer.tsx`
- Not deployed to live VK and no restart performed.

2026-05-08 workspace PR badge stacking:

- Source patch completed in `packages/ui/src/components/IssueWorkspaceCard.tsx`.
- Workspaces with 3+ linked PRs now wrap PR badges onto a separate line under the live status/stats row.
- Workspaces with 0-2 PRs keep the existing single-row layout.
- This keeps running dots, pending-approval hand, unseen activity, dev-server, and failed/killed indicators visible instead of letting PR badges squeeze/cover them.
- Live no-restart frontend hotfix also applied after user reported no visible change:
  - copied current live release `20260507Tandroid-scroll-hotfix`
  - patched only the three unique workspace-card class expressions in the copied JS asset
  - updated live symlink to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260508Tworkspace-pr-stack-hotfix`
  - live HTML now serves `/assets/index-BqGLQj9b-prstack.js`
  - no backend restart and no dirty full frontend rebuild
- Validation:
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm run format`
  - `curl -sS http://127.0.0.1:4311/` shows `index-BqGLQj9b-prstack.js`
  - `curl -sSI http://127.0.0.1:4311/assets/index-BqGLQj9b-prstack.js` returns `200 OK`
- No restart performed.

2026-05-09 hyroxready-app persistent needs-review bubble finding:

- User asked why the left-nav needs-review bubble works for other repos but stays on for `hyroxready-app`.
- Live frontend is still serving the patched old release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260508Tworkspace-pr-stack-hotfix`, based on `20260507Tandroid-scroll-hotfix`.
- That live bundle still has the older left-nav marker logic:
  - fetches both active and archived workspace summaries
  - builds needs-review IDs from `active + archived`
  - treats `has_unseen_turns && latest_process_status !== "running"` as needs-review
- Source `SharedAppLayout.tsx` has the newer intended behavior that only uses active summaries and excludes failed/killed states.
- Live data that lights `hyroxready-app` under the old bundle:
  - `FR::Custom Workout Layout` / `7b574b94-0349-49dc-a497-db9497ed09f1`
  - `FR::Equipment in Custom Workout` / `5b62c8b4-21db-4274-8496-45cf549ead3a`
  - `FR::Onboarding` / `d8fb6ef1-9b91-4c2e-9795-8e1f7150b1dd`
  - `FR::Modernize Design` / `915ede80-a3ba-46fc-8665-ed8b368a0bac`
  - `FR::Rebuild Timer for Metcons` / `17674426-6580-4861-8664-8b71ea3d69ed`
- All five are archived hyrox workspaces with completed latest process and `has_unseen_turns: true`.
- Active-summary check showed only one actionable active row, and it belongs to `VL::Investigate repo workflow`, not `hyroxready-app`.
- Live no-restart frontend hotfix applied after user said to fix it:
  - copied current live release `20260508Tworkspace-pr-stack-hotfix`
  - patched live asset to make `hXt` ignore failed/killed and build needs-review IDs from active summaries only
  - updated live symlink to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260509Tneeds-review-active-only-prstack`
  - live HTML now serves `/assets/index-BqGLQj9b-prstack-nractive.js`
  - no backend restart and no dirty full frontend rebuild
- Verification:
  - live asset has `failed/killed` exclusion in `hXt`
  - stale `active + archived` marker expression count is `0`
  - active-only marker expression count is `1`
  - `curl -sSI http://127.0.0.1:4311/assets/index-BqGLQj9b-prstack-nractive.js` returns `200 OK`

2026-05-09 FR::ORC::Android Parity agent persistence finding:

- User asked whether VK setup prevents agents from staying active because `FR::ORC::Android Parity` should be running sub-agents and monitoring them but keeps stopping short.
- Workspace:
  - project `hyroxready-app` / `a3b03aaa-1a7b-4176-8249-20a879593aba`
  - workspace `FR::ORC::Android Parity` / `c96132c9-6f2c-458d-a7cf-a455cf0ea632`
  - latest session `a7cd1444-b385-4edd-b8ef-cc14994cd8ba`
  - PR `https://github.com/artinflight/hyroxready-app/pull/795`
- Current summary showed the latest Android Parity process completed normally:
  - latest process status `completed`
  - completed at `2026-05-09T09:38:50.997296939Z`
  - no pending approval
  - no running dev server
  - no matching running OS process for workspace `c96132c9-6f2c-458d-a7cf-a455cf0ea632`
- Recent execution records for this workspace were `completed` with exit code `0`, not `failed`, `killed`, or dropped.
- Session transcripts show the agent spawned/waited on sub-agents in at least one turn, then returned a final answer anyway. One relevant summary said it was closing/replacing an emulator-management sub-agent because it was not returning in a useful window.
- Source behavior matches the DB evidence:
  - Codex runs as an app-server child process for each VK execution.
  - VK finalizes normal coding runs when the executor action has no `next_action`.
  - Codex sub-agents are not modeled as separate VK workspace execution processes.
  - After the parent agent emits a final answer and the process exits successfully, VK has nothing durable to keep awake and monitor child agents.
- Finding: this does not look like VK killing Android Parity. It looks like a workflow/setup mismatch. The parent Codex turn is a request/response execution, not a persistent supervisor daemon, and it can voluntarily finalize even if the user expected it to keep polling child agents.
- Practical blockers seen in the Android Parity history:
  - emulator / Google Play sign-in problems required human runtime retest
  - parent agent admitted it both tasked a sub-agent and performed direct work
  - parent agent waited only briefly on at least one sub-agent before moving on
- Durable fix options to consider:
  - product fix: expose child-agent/job state to VK and prevent/flag finalization while child jobs are still running
  - workflow fix: require the parent agent to keep a foreground wait loop open and not send final until all delegated agents have completed or timed out with a status report
  - operational fix: avoid using VK conversational turns as unattended long-running supervisors until child-agent liveness is visible in VK
- No VK restart was performed.

2026-05-09 sub-agent visibility source fix:

- Implemented a frontend source fix for the first pass at child-agent visibility.
- New file `packages/web-core/src/features/workspace-chat/model/subagentActivity.ts` derives child-agent state from selected-session normalized log entries:
  - `spawn_agent` result creates an unresolved sub-agent record using `agent_id` and nickname when present.
  - in-flight `wait_agent` calls mark target agents as running.
  - completed `wait_agent` output marks targets as completed, `not_found`, running when timed out, or unresolved when ambiguous.
- `SessionChatBoxContainer` now passes the derived state to the chat box and asks for browser confirmation before sending a new prompt while the selected session has running/unresolved sub-agents.
- `SessionChatBox` now renders a warning banner above the composer when running/unresolved sub-agents are present.
- Limitation: this is log-derived state, not a new backend child-process registry. If a parent agent spawned a child and never waited on it, VK can only show the child as unresolved/may-still-be-active until a later `wait_agent` result resolves it.
- Validation:
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/ui run format`
  - `pnpm --filter @vibe/web-core run format`
  - `git diff --check -- packages/web-core/src/features/workspace-chat/model/subagentActivity.ts packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx packages/ui/src/components/SessionChatBox.tsx`
- No VK restart was performed. This is source-only until built/deployed as a frontend release.

2026-05-09 sub-agent visibility permanent source implementation:

- User confirmed the first-pass fix should not be deployed yet and asked to develop the permanent version while holding deployment/restart.
- Current live status:
  - the first-pass frontend/log-derived fix is in source only, not confirmed live-deployed
  - no VK restart or live deployment was performed for this permanent version
- Implemented durable source pieces:
  - migration `crates/db/migrations/20260509000000_add_subagent_jobs.sql`
  - DB model `crates/db/src/models/subagent_job.rs`
  - execution log parser updates in `crates/services/src/services/execution_process.rs`
  - API route `/api/execution-processes/subagents/session?session_id=...`
  - generated Rust-to-TS types for `SubagentJob` and `SubagentJobStatus`
  - frontend query hook `packages/web-core/src/shared/hooks/useSubagentJobs.ts`
  - chat composer integration that prefers backend sub-agent rows when available and falls back to log-derived state otherwise
- Behavior after deployment:
  - future `spawn_agent` calls create durable `subagent_jobs` rows
  - `wait_agent` starts and completions update those rows to running/completed/not_found/failed where Codex reports enough detail
  - the chat UI can poll these rows and warn/confirm before the user sends a prompt while child work is still running or unresolved
- Important limitation:
  - VK can only persist and display sub-agent state that Codex exposes through streamed tool calls/results
  - if a parent agent spawns a sub-agent and never waits on it, VK can preserve that child as unresolved, but cannot independently prove completion without a Codex/global child-agent registry
  - historical sessions before this backend deploy will not have DB rows unless a backfill is added; the frontend fallback still derives what it can from existing normalized logs
- Validation:
  - `pnpm run generate-types`
  - `cargo check -p db -p services -p server` passed with existing warnings in `db`, `services`, and `server`
  - `pnpm --filter @vibe/ui run check`
  - `pnpm --filter @vibe/web-core run check`
  - `pnpm --filter @vibe/local-web run check`
  - `pnpm run format`
  - `git diff --check --` on the touched sub-agent tracking paths
- Deployment status: held. This needs an intentional backend migration/restart later to activate durable DB-backed tracking.

2026-05-09 live deployment of queued VK fixes:

- User gave explicit approval to deploy/restart after backups.
- Backups:
  - full lean restore completed and mirrored to `desktop:B:/vk-backups/vk-lean-restore-20260509T191834Z.tar.gz`
  - local desktop pointer: `/home/mcp/backups/vk-lean-restore-latest.desktop.json`
  - post-work delta backup: `/home/mcp/backups/vk-pre-restart-delta-20260509T203101Z.tar.gz`
- Pre-restart checks before the successful activation showed 0 running execution rows and 0 active `vk-exec-*` units.
- First activation attempt failed because the live DB had `_sqlx_migrations` version `20260425000000` but source no longer had that migration file, causing SQLx `VersionMissing(20260425000000)`.
- Immediate recovery:
  - rolled live binary/frontend back from `/home/mcp/backups/vk-live-artifact-before-20260509T202103Z-source-fixes`
  - restored live API before rebuilding
  - re-added `crates/db/migrations/20260425000000_add_workspace_summary_hotfix_indexes.sql` from commit `481e2823`
  - reran `pnpm run prepare-db`
  - rebuilt with `SQLX_OFFLINE=true cargo build --release --bin server`
- Successful activation:
  - live binary `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - staged copy `/home/mcp/.local/bin/vibe-kanban-serve-prod-20260509T210006Z-source-fixes-migration-restore`
  - binary sha `8ea4a561ccb20fd39969270b8bf5103ab5c85c40f6cffb79b45351bd7da03ee9`
  - frontend `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260509T202103Z-source-fixes`
  - current asset `/assets/index-B9DdfbP2.js`
- Post-restart validation:
  - `vibe-kanban.service` active/running, PID `2063361`, restart counter `0`
  - `/api/info` OK
  - `http://127.0.0.1:4311/` OK
  - `https://vibe.local/` OK
  - `/assets/index-B9DdfbP2.js` OK
  - `subagent_jobs` table exists
  - migrations `20260425000000` and `20260509000000` are present/successful in live DB
  - `/api/execution-processes/subagents/session?session_id=...` returns success
  - generic 25 MB attachment upload to `/api/attachments/upload` succeeded and the test attachment was deleted
  - 0 running execution rows and 0 active `vk-exec-*` units after smoke checks

2026-05-09 archived project left-nav regression hotfix:

- Symptom after the source-fixes deploy: archived local projects were visible again in the left app nav.
- Cause: the deployed frontend included a newly added archived-project section in `SharedAppLayout`/`AppBar`, and the server still served embedded frontend assets despite `VK_FRONTEND_DIST_DIR`, so a plain `frontend-dist/current` symlink swap did not reach `vibe.local`.
- Source fixes:
  - removed archived-project rendering from desktop app bar and mobile drawer
  - added external `VK_FRONTEND_DIST_DIR` support in `crates/server/src/routes/frontend.rs` so future backend builds can serve refreshable frontend assets directly
- Live no-VK-restart mitigation:
  - started `vk-frontend-static.service` on port `4313`, serving `/home/mcp/.local/share/vibe-kanban/frontend-dist/current`
  - reloaded homelab nginx so `vibe.local` sends `/api/` and `/v1/` to VK on `4311`, and frontend routes/assets to `4313`
  - `vibe-kanban.service` was not restarted; PID remained `2063361`
- Live frontend release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260509T214040Z-hide-archived-nav-final`, asset `/assets/index-2sBlc7fu.js`.
- Validation: `pnpm run format`; `pnpm --filter @vibe/ui run check`; `pnpm --filter @vibe/web-core run check`; `cargo check -p server` with existing warnings; `pnpm --filter @vibe/local-web run build`; `https://vibe.local/`, `/workspaces/anything`, `/assets/index-2sBlc7fu.js`, and `/api/info` OK; `archived-project-list` absent from served assets.

2026-05-10 Kanban In Review false needs-review marker:

- User reported the In Review Kanban was showing an issue needing review when no issue/workspace actually needed review.
- Live `/api/workspaces/summaries` showed no active `has_unseen_turns` or `has_pending_approval` rows at investigation time.
- Root cause: `KanbanContainer` treated any non-empty status named `Review`, `In Review`, `Needs Review`, or `Ready for Review` as needing review via `statusNameIndicatesNeedsReview`.
- Fix: removed the status-name fallback. Column review markers now only come from actual linked workspace review state via `needsReviewByStatusId`.
- Deployed as frontend-only release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260510Tkanban-review-marker-source`; no VK restart; PID stayed `2063361`.
- Validation: `pnpm --filter @vibe/web-core run check`; `pnpm --filter @vibe/local-web run build`; `pnpm run format`; live asset check for `/assets/index-DFKXNNA3.js`.

2026-05-10 Needs-review completion signal repair:

- User reported needs-review icons stopped showing anywhere when an agent finished.
- Root cause: `CodingAgentTurn::mark_unseen_by_execution_process_id` bound `execution_process_id` as a string, while SQLite stores UUIDs as blobs. The completion hook therefore updated zero rows after a viewed/running turn finished.
- Secondary issue: `WorkspaceProvider` automatically called `markSeen` whenever the currently open workspace gained unseen activity, immediately clearing the finished-agent review marker.
- Source fixes:
  - bind the UUID value directly in `mark_unseen_by_execution_process_id`
  - add `mark_completed_unseen_by_execution_process_id` and call it from the completion path so only successful coding-agent completions become needs-review
  - remove the frontend auto-clear-on-unseen effect; navigating/selecting a workspace still marks it seen
- Live no-restart mitigation:
  - backup: `/home/mcp/backups/vk-pre-needs-review-trigger-20260510T111112Z.sqlite`
  - installed SQLite trigger `trg_coding_agent_completed_unseen` so future coding-agent `running -> completed` status updates mark the turn unseen without a backend restart
  - repaired recent active completed workspaces after `2026-05-10T09:00:00Z`
  - deployed frontend-only release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260510Tneeds-review-completion-unseen`; no VK restart; PID stayed `2063361`
- Verification: live `/api/workspaces/summaries` changed from zero active review flags to seven active `has_unseen_turns` rows after several agents completed.
- Validation: `pnpm --filter @vibe/web-core run check`; `cargo check -p db -p local-deployment` with existing warnings; `pnpm --filter @vibe/local-web run build`; `pnpm run format`; live asset check for `/assets/index-CCpZ4_G_.js`.

2026-05-10 Needs-review no-regression guard:

- User explicitly asked that this never regress again.
- Added the invariant to `STATE.md` and `STREAM.md`: successful coding-agent completion must re-mark a previously seen/running turn as unseen; IDs must be bound as `Uuid` blobs; mounted workspace summary polling must not auto-clear the marker; failed/killed/interrupted states are not project needs-review markers.
- Added focused DB regression coverage in `crates/db/src/models/coding_agent_turn.rs`:
  - `completed_coding_agent_turns_are_marked_unseen_by_uuid_blob`
  - proves completed coding-agent turns flip from `seen = 1` to `seen = 0` when addressed by UUID blob binding
  - proves running coding-agent and completed non-coding turns are ignored by the completed-only helper
  - proves the lower-level UUID binding helper updates a UUID-stored row
- Added `tokio` as a `db` dev-dependency for the async DB test.

2026-05-13 Kanban drag persistence hotfix:

- User reported dragging an issue card to another Kanban column looked like it worked, then bounced back shortly after.
- Live backend bulk issue updates were verified directly against VL issue `T8`: moving `todo -> in_progress` persisted, then the test issue was restored to `todo`.
- Root cause was frontend-side: `KanbanContainer` built the bulk update payload by mutating `newItems` inside a React `setItems` updater, then called raw `bulkUpdateIssues`. If the updater side effect was not available synchronously or the Electric collection refreshed first, the move could be shown locally without a durable issue mutation and then be overwritten by the next synced snapshot.
- Source fix:
  - `ProjectContext` now exposes `updateIssues`
  - Kanban drag computes `newItems` synchronously from current `items`
  - drag persistence uses the project issue mutation collection (`updateIssues(...).persisted`) so optimistic state, fallback refresh, and bulk `/v1/issues/bulk` persistence stay aligned
  - failed mutations restore the previous board state immediately
- Live frontend-only deploy: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260513Tkanban-drag-persist`, asset `/assets/index-CmLP2jfq.js`.
- No VK restart; `vibe-kanban.service` PID stayed `913128`.
- Validation: `pnpm --filter @vibe/web-core run check`; `pnpm --filter @vibe/local-web run check`; `pnpm run format`; `pnpm --filter @vibe/local-web run build`; `https://vibe.local/` serves `/assets/index-CmLP2jfq.js`; live JS contains the `updateIssues` drag mutation path; `/api/info` OK.

2026-07-13 live-to-staging backfill recovery:

- User found staging preview was missing live-only VK work, including colored project icons/flyout behavior and other local deploy fixes.
- Live frontend manifest pointed at `frontend/20260626TmobileProjectEdit`, based on `deploy/restart-ready-20260626TrestartReady`, both at `11ae04d59`.
- Created branch `vk/4e18-live-backfill-to-staging` from staging preview base `758f6b2ce`.
- Full merge from the live deploy branch produced broad conflicts and was aborted; then the live commit range was cherry-picked onto staging instead.
- Kept staging's newer preview script behavior during the first cherry-pick conflict and restored `preview:light:run`.
- Resolved integration artifacts from duplicate props/imports/effects and Rust API drift after the cherry-pick sequence.
- Validation before committing the integration repair:
  - `git diff --check`
  - `pnpm --filter @vibe/ui run check`
  - `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
  - `cargo check -p executors -p services -p local-deployment -p server`
  - `pnpm run generate-types`
  - `pnpm run format`
- `pnpm run generate-types:check` previously compiled but hung in the final linker step on this host; `pnpm run generate-types` completed and regenerated `shared/types.ts`.
- Next step: review/push/open PR from `vk/4e18-live-backfill-to-staging` into `staging`, then run human QA on the staging preview before any `staging -> main` promotion.
