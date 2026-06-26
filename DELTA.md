# DELTA.md

## 2026-06-11T12:45:00Z | vk/land-live-fixes-20260422 | restart candidate and targeted backup

- Prepared a clean restart candidate from the current VK fix set without restarting live VK.
- Candidate worktree: `/home/mcp/vk-restart-candidate-20260611T112143Z`; branch `deploy/restart-candidate-20260611T112143Z`; commit `2a32636534c6365452777f6d67f3b64583180160`.
- Built backend from the candidate with `CARGO_TARGET_DIR=/home/mcp/_vibe_kanban_repo/target cargo build --release --bin server`.
- Installed next-restart binaries to `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`; sha256 `fcf8832cf5a53bf67042661bd314774cfcfeaa687e458c237aeef1648004d582`.
- Running VK PID remained `3435842`; no restart was performed.
- Built and staged frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260611Trestart-candidate`; asset `/assets/index-Bm8ag4JP.js`; sha256 `b2a3ab5030a8a15904b2742be2ebd9252cdcdd6cfd704a198e2d18e079264715`.
- Did not switch live frontend pointer; it still targets `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`.
- Stock lean backup was attempted but aborted after current sessions/Codex state made it grow to about `40G` staged; incomplete temp data was removed.
- Completed targeted restart-restore backup and mirrored it to Desktop:
  - local: `/home/mcp/backups/vk-targeted-restart-restore-20260611T123534Z.tar.gz`
  - Desktop: `desktop:B:/vk-backups/vk-targeted-restart-restore-20260611T123534Z.tar.gz`
  - sha256: `af5f3380ae4648a19cef910985944dc2cf8d7964d81b2947a781deb16c9d195d`
- Cleanup touched only rebuildable caches/build outputs/temp artifacts; VK DB, live sessions, VK Codex state, registered worktrees, and completed backups were preserved.

## 2026-06-03T16:05:00Z | vk/land-live-fixes-20260422 | duplicate project cleanup

- User reported duplicated projects in VK.
- Root cause: `/api/projects` merged real project rows with `PROJECT_REPO_DEFAULTS` synthetic projects; dedupe only trimmed/lowercased names, so `foxtrot-lima` did not match `FoxtrotLima` and `intake-shield` did not match `intakeShield`.
- Took live SQLite backup at `/home/mcp/backups/vk-project-duplicate-scratch-cleanup-20260603T160156Z/db.v2.sqlite` and saved deleted payloads in `deleted-scratch-records.json`.
- Deleted only the two stale visible duplicate scratch rows: `7e139609-715c-4724-971a-ab986ce9ba79` and `59b947c5-7bb3-442e-bb7f-f752da7efcc4`.
- Live `/api/projects` now shows active count `14`; `FoxtrotLima` and `intakeShield` are gone; `foxtrot-lima` and `intake-shield` remain once each.
- Staged source fix in `crates/server/src/routes/projects.rs`: stronger name canonicalization plus repo-ownership filtering for synthetic scratch projects, while retaining legitimate synthetic-only projects.
- Updated `scripts/vk_live_regression_smoke.py` to expect the duplicate-free active project list.
- Validation passed: `cargo test -p server routes::projects::tests`.
- No VK restart was performed; source fix waits for the next backend build/restart.

## 2026-06-03T00:25:00Z | vk/land-live-fixes-20260422 | restart safety and queue recovery plan

- User approved cleanup/build/restart only with an efficient restore-grade backup mirrored off MCP to Desktop.
- Preflight active-agent check showed no running `vk-exec-*` units and `0` non-dropped DB execution rows with `status='running'`.
- Disk was critically low at about `5.6G` free / `98%` used.
- Rebuildable cleanup removed stale worktree `node_modules`, VK `target/debug`, and npm cache; free space rose to about `42G`.
- Aborted the stock lean backup after it copied too much historical Codex state (`29G` temp set) and removed its temp directory.
- Created custom efficient restore archive `/home/mcp/backups/vk-efficient-restore-20260603T004715Z.tar.gz` and mirrored it to `desktop:B:/vk-backups/vk-efficient-restore-20260603T004715Z.tar.gz` plus `desktop:B:/vk-backups/vk-efficient-restore-latest.tar.gz`.
- Mirrored source-state snapshot to `desktop:B:/vk-backups/vk-pre-restart-source-state-20260603T002809Z.tar.gz`.
- Backup scope: 226 non-archived workspaces, 233 thread IDs, 252 rollout files, DB snapshot, selected latest process logs, isolated Codex auth/config/state, systemd config, live binaries, current frontend release, source diff/untracked snapshot, and workspace git metadata.
- Backup integrity: restore archive size `405,891,419` bytes, `4923` entries, sha256 `92c9e5e0a557397a90c175cd33dcffee6092a105ed7c36d529443f7ad91a495c`; source-state archive sha256 `74df1f9dc0bf6ba4f4cf0687eb4d3fe8ec1c377778ffff16b7b0cf6a9722b401`.
- Queue regression remains in scope: deployed package must include backend queued-follow-up consumption and frontend stale-running/queued-status reconciliation.
- Docs now record that backup must be lean but sufficient to restore VK DB, sessions, isolated Codex continuity state, systemd config, binaries, frontend pointer, and workspace git metadata.
- Built restart package from the canonical VK checkout:
  - backend `target/release/server` sha256 `c083178e5a75a5fefeb01f862dd668929be03fecaf08bb3749f77ca379ffec7f`
  - frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`
  - frontend asset `/assets/index-BLreFcjw.js` sha256 `8bb6029a2d1fd0e09c208afc1f558feae5646d66ce62ac790ce615c192ffb935`
  - release manifest records included backend/frontend fixes and backup pointer.
- Updated `scripts/vk_live_regression_smoke.py` to expect the staged release asset and the current live project active/archive order captured immediately before restart.
- Restarted VK after confirming `0` active executions; live backend/frontend came up healthy with `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8`.
- Initial smoke caught nondeterministic active project ordering for synthetic projects. Root cause was `HashMap::values()` iteration in `crates/server/src/routes/projects.rs`.
- Added deterministic synthetic-project sorting plus regression test `synthetic_projects_have_stable_display_order`, rebuilt release, confirmed `0` active executions again, and restarted a second time.
- Final live backend sha256 is `722a5b0d14ca2350661cdcd0a271ac2cfea980dae4f2dcafc55b8ffe9470ed75`; live PID `3435842`; frontend remains `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active` with `/assets/index-BLreFcjw.js`.
- Final smoke passed; eight repeated `/api/projects` reads returned stable active project order; fake unread/queue routes returned `404` rather than `405`; active executions remained `0`.
- Removed rebuilt `target/debug` after validation; `/home/mcp` returned to about `39G` free / `83%` used.

## 2026-06-02T00:05:00Z | vk/land-live-fixes-20260422 | Codex active-agent limit repair

- User reported VK was again blocking new agents with `Codex execution limit reached: 1 active, limit 1`.
- Live service env lacked `VK_CODEX_MAX_ACTIVE_EXECUTIONS`, so the executor fell back to hardcoded limit `1`.
- Changed source fallback to `DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS = 8` and added parser/default unit coverage.
- Updated `ops:check` to guard the source fallback and runtime docs.
- Persisted `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8` in the live systemd runtime guardrails and ran `systemctl --user daemon-reload`.
- Later investigation showed `IS::UI Usability Pass` was not actually running; it had been killed after live VK panicked on `ClientRequest::ThreadResume`.
- Changed Codex client request ID extraction to use `ClientRequest::id()` and added regression coverage for `ThreadResume`.
- Did not restart VK; the running process needs an approved build/restart to pick up the env and resume-panic fix.

## 2026-05-30T11:25:00Z | vk/land-live-fixes-20260422 | unread regression correction staged

- Intent: repair the `Mark unread` 405 regression introduced by deploying the ntfy-only binary.
- Root cause:
  - live frontend release calls `PUT /api/workspaces/:id/unread`
  - previous ntfy restart deployed a binary from `/tmp/vk-ntfy-turn-completion-20260528`
  - that binary had bounded ntfy but did not include the canonical unread backend route
- Completed:
  - ported bounded ntfy worker into canonical `/home/mcp/_vibe_kanban_repo`
  - kept canonical manual unread backend route and DB helper
  - added latest coding-agent turn/profile lookup for ntfy final summaries
  - fixed existing dirty `projects.rs` move/borrow compile error by computing `target_branch` before moving `repo`
  - built corrected release binary and installed it to both live binary paths
- Validation:
  - `cargo fmt --check`
  - `cargo test -p services services::notification`
  - `cargo test -p db latest_workspace_turn_can_be_marked_unseen`
  - `cargo test -p db completed_coding_agent_turns_are_marked_unseen_by_uuid_blob`
  - `cargo build --release --bin server`
  - `git diff --check`
- Deployment state:
  - staged binary sha256: `1ca98fdffa8d2f172ab7d94cb513e3c79e26c6a179365963d1d581ac0e45ef1a`
  - running process sha256 remains `be377483fccfe825fe93b10c6cba848871018e0f01d892e85c43ee072d7d19ee`
  - no restart performed because active agents appeared during build; last check showed `3` running units/rows
- Ntfy:
  - server `https://opntfy.fly.dev`
  - topic `vk-workspace-turns`
  - bearer-token subscribe tested `200`; anonymous subscribe tested `403`
  - token must stay out of docs/chat

## 2026-05-28T18:30:00Z | vk/land-live-fixes-20260422 | VK agent deploy runbook

- Intent: make future VK agents able to work on and deploy the VK repo from inside VK without repeating dirty-checkout deploys, frontend rollback, active-agent interruption, or unverified regressions.
- Completed:
  - added `VK_AGENT_DEPLOYMENT_RUNBOOK.md`
  - added the runbook to `AGENTS.md` required read order
  - recorded current live truth in `STATE.md` and `STREAM.md`
  - prepended `HANDOFF.md` with pickup notes
- Live facts verified:
  - `vibe-kanban.service` active/running on PID `4182076`
  - live binary sha `7c63eb8fa7b2b46f6567ef7f8606df1d7a794bb6685d14cd7bf951c531f00e46`
  - frontend pointer `frontend-dist/current -> releases/20260514Tworkspace-unpin`
  - live asset `/assets/index-BLn8oOcK.js`
  - one `vk-exec-codex-*` unit was running, so no restart was attempted
- Not done:
  - no build, deploy, frontend asset swap, DB edit, or restart
  - canonical checkout remains dirty with unrelated source edits

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

## 2026-04-19T00:00:00Z | vk/53b2-vk-needs-review | app bar needs-review project bubbles

- Intent: show a project-level visual indicator when a project has linked workspaces with agents that have finished or are waiting for review.
- Completed:
  - added project icon bubbles in the left app bar for projects with review-needed workspaces
  - aggregated review-needed state from existing workspace summary signals
  - added local helper APIs for workspace summaries and local project workspace lookup
  - committed the feature as `5c5f83855`
- Files changed:
  - `packages/ui/src/components/AppBar.tsx`
  - `packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx`
  - `packages/web-core/src/shared/lib/api.ts`
  - `STREAM.md`
  - `HANDOFF.md`
- Verified:
  - `git diff --check` passed for the touched frontend files
- Not complete / known gaps:
  - `pnpm run format` could not complete because `prettier` was missing
  - `pnpm run check` could not complete because `tsc` was missing
  - original branch push/PR preview state has since changed; see current branch history and PR state instead of this older branch-note wording

## 2026-04-24T00:00:00Z | vk/7b9a-vk-worktree-clea | immediate post-merge worktree cleanup

- Intent: remove workspace worktree folders as soon as a tracked PR lands in `staging` instead of waiting for the archived-workspace retention window.
- Completed:
  - added a shared container helper that deletes archived worktrees for workspaces with merged tracked PRs targeting `staging`
  - called that helper from both the background PR monitor and the attach-existing-PR route
  - added a retry after archive-script completion so archive scripts can finish before the worktree is removed
  - archived linked local workspaces and cleaned up their worktrees when their issues move into `In Staging`, including bulk issue updates
  - documented the new behavior in `VK_WORKFLOW.md`
- Files changed:
  - `crates/services/src/services/container.rs`
  - `crates/services/src/services/pr_monitor.rs`
  - `crates/local-deployment/src/container.rs`
  - `crates/server/src/routes/local_compat.rs`
  - `crates/server/src/routes/workspaces/pr.rs`
  - `VK_WORKFLOW.md`
  - `STREAM.md`
  - `HANDOFF.md`
- Verified:
  - added unit coverage for the merged-to-`staging` PR detection helper
  - `cargo fmt --all` completed
- Not complete / known gaps:
  - PR `#6` still needs merge
  - backup retention validation was not rerun during the sync cleanup step
  - full test validation was not rerun after the final cleanup behavior adjustments
  - pinned workspaces still keep the existing auto-archive exception
# 2026-04-19 Workspace Polling Hotfix

- A second frontend churn path was identified after the earlier kanban/sidebar fix.
- Root cause: mounted workspace views were still polling branch status and issue-linked workspaces every 5 seconds.
- Primary files:
  - `packages/web-core/src/shared/hooks/useBranchStatus.ts`
  - `packages/web-core/src/shared/hooks/useTaskWorkspaces.ts`
- Fix:
  - disable default 5s polling for both hooks
  - add `staleTime`
  - disable `refetchOnWindowFocus`
  - disable `refetchOnMount`
- Why this mattered:
  - the first stress test only exercised raw HTTP endpoints and missed the browser-mounted polling path
  - real workspace UI usage could still drive repeated `/api/workspaces/:id/git/status` and `/api/workspaces?task_id=...` calls
  - under sustained live use, that recreated the same multi-GB server bloat / timeout pattern
- Post-fix validation:
  - repeated workspace-open emulation for `OpsPB::Linking in reports`, `VK:: Wire Ntfy`, and `Vk::Ops`
  - combined polling plus summaries POST load
  - no endpoint failures
  - RSS stayed roughly in the `32–51 MB` range instead of climbing into GB territory

## 2026-04-20T00:00:00Z | vk/ea3c-vk-auto-archive | continuity refresh for staging-equivalent worktree

- Intent: resume from the real checked-out workspace state and correct stale branch-local continuity notes.
- Completed:
  - confirmed the checked-out branch is `vk/ea3c-vk-auto-archive`
  - confirmed the worktree is clean and matches `staging` at `88c0ebd59`
  - replaced stale backup-retention stream notes in `STREAM.md` and `HANDOFF.md`
- Verified:
  - `git status --short --branch`
  - `git diff --stat`
  - `git diff --name-only staging...HEAD`
  - `git log --oneline staging..HEAD`
  - `curl -s http://127.0.0.1:4311/api/info` confirmed `shared_api_base: null`
- Not complete / known gaps:
  - `pnpm run format` did not complete because `packages/web-core` could not resolve `prettier`

## 2026-04-26T12:35:00Z | vk/ea3c-vk-auto-archive | Codex rollout continuity repair

- Intent: stop empty or failed Codex rollout launches from poisoning follow-up turns in the local Vibe Kanban install.
- Completed:
  - identified `019dc72a-9fba-7961-9c36-a3f8f8a63036` as a true zero-byte rollout file
  - confirmed `019dc9bd-ef72-76f2-b08e-4c83659f0369` was non-empty despite the late `thread not found` log
  - changed resume lookup to only use completed exit-0 coding-agent turns with a non-empty summary
  - backed up the live DB to `/home/mcp/backups/vk-rollout-repair-20260426T122842Z`
  - cleared four live DB `agent_session_id` pointers whose rollout files were empty or missing
- Verified:
  - `cargo fmt --all`
  - `env DATABASE_URL=sqlite:///home/mcp/.local/share/vibe-kanban/db.v2.sqlite cargo check -p db`
  - post-repair live DB scan returned `bad_rollout_agent_session_rows_after 0`
- Not complete / known gaps:
  - the zero-byte rollout cannot be reconstructed because no persisted session content exists
  - the upstream Codex late-finalization `thread not found` log may still appear, but it no longer points at an empty rollout anchor in the live DB

## 2026-04-26T14:55:00Z | vk/ea3c-vk-auto-archive | execution status and vibe.local hotfix

- Intent: stop mounted workspace pages from showing completed agents as still running until manual refresh, and restore `vibe.local` after the local deploy.
- Completed:
  - changed execution-process WebSocket consumers to reconnect after clean closes and reload a fresh process snapshot
  - stopped the execution-process server stream from forwarding unrelated non-patch messages such as `finished`
  - rebuilt `packages/local-web/dist` so the frontend fix is embedded in the local server binary
  - rebuilt and redeployed `/home/mcp/.local/bin/vibe-kanban-serve`
  - restored LAN proxy reachability by setting `HOST=0.0.0.0`, `BACKEND_PORT=4311`, and `PREVIEW_PROXY_PORT=4312` in the user service drop-in
- Verified:
  - `pnpm install`
  - `pnpm run format`
  - `pnpm --filter @vibe/local-web run build`
  - `env DATABASE_URL=sqlite:///home/mcp/.local/share/vibe-kanban/db.v2.sqlite cargo check -p services -p db`
  - `env DATABASE_URL=sqlite:///home/mcp/.local/share/vibe-kanban/db.v2.sqlite cargo build --release -p server --bin server`
  - `https://vibe.local` returned `200`
  - execution-process WebSocket returned initial snapshot plus `Ready`
- Not complete / known gaps:
  - no browser-driven long-running agent test was performed; the smoke test covered the stream path and deployed service health

## 2026-04-26T16:05:00Z | vk/ea3c-vk-auto-archive | local-only auth gate hotfix

- Intent: stop local-only Vibe Kanban from showing a remote sign-in prompt in the left nav after service restarts or deploys.
- Completed:
  - traced the regression to `/api/info` returning `login_status: loggedout` while `shared_api_base` was intentionally `null`
  - added the live user-service drop-in `/home/mcp/.config/systemd/user/vibe-kanban.service.d/local-auth.conf` with `VK_DISABLE_AUTH=1`
  - changed local deployment login status so an install with no shared API base reports `LoggedIn { profile: None }`
- Verified:
  - live `/api/info` returned `login_status: loggedin` and `shared_api_base: null` after the service drop-in
  - `https://vibe.local` returned `200` after restart
  - `pnpm run format`
  - `env DATABASE_URL=sqlite:///home/mcp/.local/share/vibe-kanban/db.v2.sqlite cargo check -p local-deployment -p server`
  - `pnpm --filter @vibe/local-web run build`
  - `env DATABASE_URL=sqlite:///home/mcp/.local/share/vibe-kanban/db.v2.sqlite cargo build --release -p server --bin server`
  - active workspace summaries showed no `running` execution-process statuses before restart
  - deployed binary hash matched `target/release/server`: `8d348fb20f36bb25d0dc0737aa5ae3df6e8e8c2243003bff6ffc27f2985f6525`
  - post-restart service state was `active/running`
  - post-restart `/api/info` returned `login_status: loggedin` and `shared_api_base: null`
  - post-restart `https://vibe.local` returned `200`
- Not complete / known gaps:
  - local-auth source hardening still needs commit/push/staging promotion

- Backup retention hardened again after MCP local backups bloated past `40G`:
  - Desktop mirror target is now `B:\vk-backups`
  - MCP keeps only the current local lean restore set:
    - newest unpacked restore directory
    - newest restore archive
    - `latest` symlinks
  - older local hourly lean restore directories and archives are deleted
  - Desktop is now the retention system of record for older hourly history
- `scripts/vk_lean_backup.py` now stages each new backup into a temporary directory and only promotes it into a timestamped restore directory after the archive is written successfully.
  - this prevents interrupted backup runs from leaving behind huge partial timestamped restore directories on MCP
- VK isolated auth broke again because `/home/mcp/.local/share/vibe-kanban/codex-home/auth.json` was stale relative to `/home/mcp/.codex/auth.json`.
  - immediate prod repair was to resync the isolated VK auth file from the fresh main auth file
  - verified by a successful real VK follow-up on `VC::ops Playbook` with summary `auth-path-ok`
  - this is an operational repair, not a full architectural fix for concurrent token refresh races
- Cleared stale visible auth/bubblewrap noise from workspace transcripts:
  - deleted stale empty failed/killed codingagent rows from `db.v2.sqlite`
  - restored session process logs after an over-broad orphan cleanup attempt
  - sanitized `513` stored process log files under `~/.local/share/vibe-kanban/sessions/.../processes/*.jsonl`
  - removed `8698` stale lines matching auth/bubblewrap noise such as:
    - `bubblewrap`
    - `user namespaces`
    - `Failed to refresh token`
    - `refresh_token_reused`
    - `token_expired`
- Workspace visibility repair:
  - patched `packages/web-core/src/shared/hooks/useCreateWorkspace.ts`
  - intended effect is that newly created issue-linked workspaces appear in Issues without leaving and reopening the issue
- Chat/live-update mitigation rolled out:
  - websocket close/reconnect fix in `packages/web-core/src/shared/hooks/useJsonPatchWsStream.ts`
  - send-triggered session refresh/remount mitigation in:
    - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
    - `packages/web-core/src/pages/workspaces/WorkspacesMainContainer.tsx`
    - `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`
    - `packages/web-core/src/shared/lib/sessionStreamRefresh.ts`
  - important: this is not considered the final proper fix
  - remaining root-cause work is to restore the intended end-to-end live-update path without remount hacks
- Re-linked `VC::ops Playbook` workspace to its issue:
  - workspace id `0b00ce25-fb2b-4742-b310-4bf6aaa1e7e7`
  - task id `69a9dbf6-2cb9-48f2-8d9f-d160fe7a5107`
- Chat live-update root fix:
  - removed the forced session refresh/remount workaround
  - deleted `packages/web-core/src/shared/lib/sessionStreamRefresh.ts`
  - removed the event-driven remount logic from:
    - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
    - `packages/web-core/src/pages/workspaces/WorkspacesMainContainer.tsx`
    - `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`
  - real fix moved to the backend:
    - `crates/server/src/routes/sessions/mod.rs`
    - after successful follow-up spawn, VK now immediately pushes:
      - `execution_process_patch::add(&execution_process)`
      - `workspace_patch::replace(&workspace_with_status)`
  - purpose:
    - make the open workspace chat see the new execution immediately through the normal live stream instead of waiting for a later refresh
  - backup before rollout:
    - `/home/mcp/backups/vk-chat-root-fix-20260421T104346Z`
- Re-linked `FR:: Garmin Sync Down` workspace to its issue:
  - workspace id `25e19656-bc9f-4315-9712-a1d5468bdc00`
  - task id `7d046622-1dd5-4025-bf04-fe2bfebd10a3`
  - backup:
    - `/home/mcp/backups/vk-fr-garmin-relink-20260421T110337Z`
- Residual red chat-error cleanup and root fix:
  - fresh process logs still showed the bubblewrap/userns warning on `2026-04-21`, so the remaining red rows were not only stale history
  - root cause:
    1. legacy follow-up forks still carried old `workspaceWrite` sandbox state into Codex app-server on resumed threads
    2. Codex warning/configWarning notifications were normalized as red `error_message` rows
  - product fix now deployed:
    - `crates/executors/src/executors/codex.rs`
      - explicitly override forked thread config with the current computed sandbox/approval/config params so stale legacy sandbox settings are not inherited
      - continue forcing `danger-full-access` when host AppArmor blocks unprivileged user namespaces
    - `crates/executors/src/executors/codex/normalize_logs.rs`
      - treat warning/configWarning as `SystemMessage`
      - suppress duplicate bubblewrap stderr line
  - rollout:
    - rebuilt `target/release/server`
    - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - live sha256 now `47c15955156cddb47252823c110859c8450eb0767a9d19933322dded5c99bf6b`
    - restarted `vibe-kanban.service`
  - transcript cleanup after rollout:
    - rewrote `13` process log files
    - removed `26` stored lines containing the exact bubblewrap warning string
    - post-cleanup `rg` found `0` remaining matches for that exact warning in `~/.local/share/vibe-kanban/sessions/.../processes/*.jsonl`
- Chat behavior fix, 2026-04-21:
  - removed the client-side pending follow-up acknowledgment state in `packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx`
  - follow-up sends now clear the composer immediately after a successful POST instead of waiting for later process-count heuristics
  - `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts` now loads newly added already-completed processes into the conversation, fixing the fast-finish case where a real turn could be accepted server-side but fail to materialize in chat
  - `packages/web-core/src/features/workspace-chat/model/useConversationVirtualizer.ts` now refreshes bottom-lock correction on every conversation content update, including streaming growth inside the unvirtualized tail, so bottom follow can keep up with a live final row
  - targeted validation passed:
    - `pnpm --filter @vibe/local-web run check`
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/ui run check`
    - `pnpm run format`
  - repo-wide `pnpm run check` / `pnpm run lint` are still blocked in this environment because backend Rust compilation cannot find `glib-2.0` via `pkg-config`
- Chat stream root fix and rollout, 2026-04-21:
  - confirmed the live production root cause in `journalctl --user -u vibe-kanban.service`:
    - repeated `MsgStore broadcast lagged ... messages dropped for this subscriber`
  - `crates/utils/src/msg_store.rs`
    - added strict history/live streaming for patch-based consumers so lag becomes a hard error instead of a silent skip
  - `crates/services/src/services/container.rs`
    - running raw/normalized process log websocket streams now use the strict mode
  - `packages/web-core/src/shared/lib/streamJsonPatchEntries.ts`
    - process log websockets now reconnect and rebuild after unexpected close/error
  - rollout:
    - rebuilt `packages/local-web/dist`
    - rebuilt `target/release/server`
    - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - live sha256 now `946a4211438d532614a7055672c2fa25c710312b9b38923abf812fbb602bc964`
- Frontend 404 repair, 2026-04-21:
  - symptom:
    - live service healthy on `/api/info`
    - root route `/` returned `404 Not Found`
  - verified routing code was already correct in:
    - `crates/server/src/routes/mod.rs`
    - `crates/server/src/routes/frontend.rs`
  - actual cause:
    - `crates/server/build.rs` did not mark `packages/local-web/dist` as a Cargo build dependency
    - after rebuilding the frontend, Cargo could still reuse a stale server compile without the current embedded frontend assets
  - fix:
    - `crates/server/build.rs`
      - added recursive `cargo:rerun-if-changed` tracking for `packages/local-web/dist`
  - validation:
    - `cargo clean -p server`
    - `cargo build --release --bin server`
    - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - `curl -i http://127.0.0.1:4311/`
    - `curl -i http://127.0.0.1:4311/assets/index-DWkKdBPw.js`
    - `curl -s http://127.0.0.1:4311/api/info`
  - result:
    - `/` now returns `200`
    - frontend assets now return `200`
    - live sha256 now `a6d17ed54f8ceba064928404ab2af055ae00d855e5bd889e193df265ef6b45b3`
- Chat history load repair, 2026-04-21:
  - symptom:
    - workspace page loaded
    - chats could remain blank/loading
  - verified live narrowing:
    - `/api/sessions?workspace_id=...` returned valid session data
    - `/api/execution-processes/stream/session/ws?...` returned initial execution-process snapshot + `Ready`
    - `/api/execution-processes/ac4680a0-2573-4a78-b71d-8a879caf56b8/raw-logs/ws` replayed raw logs
    - `/api/execution-processes/ac4680a0-2573-4a78-b71d-8a879caf56b8/normalized-logs/ws` opened but emitted nothing before timeout
  - actual cause:
    - `crates/services/src/services/container.rs`
    - the finished-process normalized replay path used a temp `MsgStore` history/live subscription pattern
    - normalized `JsonPatch` / `Ready` messages could be published during the snapshot/subscribe gap and get lost
    - that left the normalized websocket open with no replayed chat entries
  - fix:
    - `crates/services/src/services/container.rs`
      - finished-process normalized replay now awaits normalization completion
      - deduplicates normalized patch history in-memory
      - returns a finite replay stream instead of relying on live `Ready` signaling
  - validation:
    - `cargo check -p services -p server`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - deployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - forced recovery from stuck `systemctl --user restart vibe-kanban.service` by killing only main PID `2225915`
    - `curl -s http://127.0.0.1:4311/api/info`
    - direct normalized replay websocket probe for `ac4680a0-2573-4a78-b71d-8a879caf56b8`
  - result:
    - normalized replay now emits entries immediately instead of hanging
    - live sha256 now `e0b3704dcce3f4cf70031141b85c5e2fea0169a6f0d6e0daf458f0fc3656f461`
- Garmin historic replay repair, 2026-04-21:
  - symptom:
    - `FR:: Garmin Sync Down` still opened with blank/loading chat after the earlier replay-race fix
    - the newest completed process replay path stayed effectively silent long enough to make the UI look dead
  - verified live narrowing:
    - workspace id `25e19656-bc9f-4315-9712-a1d5468bdc00`
    - session id `3a014c6c-4d98-409f-87d9-1a7f111644c0`
    - process id `123302ac-b1d5-4587-90b6-5d3bba2d712e`
    - persisted process log file was valid JSONL with `31,667` lines and `83,902,430` bytes
    - file contained only raw `Stdout` / `Stderr` rows, so opening the workspace forced historical normalization from scratch every time
  - actual cause:
    - historical replay still did whole-file loading before sending the first websocket event
    - `useConversationHistory` still waited for full replay completion before painting historic entries
  - fix:
    - `crates/utils/src/execution_logs.rs`
      - added streaming reads for persisted execution log files
    - `crates/services/src/services/execution_process.rs`
      - added streamed raw-log replay from disk
    - `crates/services/src/services/container.rs`
      - finished normalized replay now streams persisted raw transcript lines into the executor normalizer and emits patches as they are produced
      - removed `ensure_container_exists()` from this historical replay path
    - `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts`
      - initial/newly-completed/reloaded history now paints partial replay state while a historic process is still loading
  - validation:
    - `cargo check -p services -p server`
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/local-web run build`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - direct websocket probes of `/api/execution-processes/123302ac-b1d5-4587-90b6-5d3bba2d712e/raw-logs/ws` and `/api/execution-processes/123302ac-b1d5-4587-90b6-5d3bba2d712e/normalized-logs/ws`
    - `curl -I http://127.0.0.1:4311/`
    - `curl -s http://127.0.0.1:4311/api/info`
  - result:
    - first raw replay patch now arrives in about `67 ms`
    - first normalized replay patch now arrives in about `61 ms`
    - live sha256 now `2288ec455166a1057c7567763555e3545bd71f87892942aec46ea149f6f961e4`
- 2026-04-21 attachment/workspace-create slowdown follow-up:
  - symptom:
    - VK felt extremely slow
    - attachment insertion errored from the UI
    - creating a new workspace surfaced `failed to fetch`
  - verified narrowing before fix:
    - direct `POST /api/workspaces` already returned `200`, so workspace creation was not fundamentally broken
    - direct `POST /api/attachments/upload` failed with backend `500`
    - journal showed `UNIQUE constraint failed: attachments.hash`
    - journal also showed repeated slow workspace-summary traffic and slow pool acquires
  - fix:
    - `crates/services/src/services/file.rs`
      - duplicate attachment hash collisions now fall back to `find_by_hash` and return the existing attachment row instead of returning `500`
    - `crates/server/src/routes/workspaces/workspace_summary.rs`
      - added a short `2s` cache keyed by `archived` so repeated identical summary requests stop hammering SQLite
  - validation:
    - `cargo check -p services -p server`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - `curl http://127.0.0.1:4311/api/info`
    - live `POST /api/workspaces`
    - live duplicate-content `POST /api/attachments/upload` twice
  - result:
    - `/api/info` returned `200` in about `9 ms`
    - workspace creation returned `200` in about `8 ms`
    - first duplicate-file upload returned `200` in about `5 ms`
    - second identical upload returned `200` in about `2 ms` and reused attachment id `2c54f409-7091-492f-9e07-4b4aa6092bf2`
    - live sha256 now `719712f0cc78503eb9d04908f4d9480d9cb11fb820294995138ed62e66a6083b`
- 2026-04-21 chat reset / first-screen attachment follow-up:
  - symptom:
    - completed agent turns could leave the composer blocked and the chat later reset to:
      - `Your workspace conversation will appear here once a new turn starts.`
    - attachment insertion still failed from the initial workspace screen even though it worked from the second screen
  - fix:
    - `packages/web-core/src/shared/hooks/useWorkspaceSessions.ts`
      - preserve the current existing-session selection when the same workspace still contains that session
      - only clear selection on empty-session results when the workspace itself changed
    - `packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
      - removed follow-up-triggered workspace-session invalidation
    - `packages/ui/src/components/WorkspaceContext.tsx`
      - added `HostIdContext` and `scopeLocalApiPath(...)`
    - `packages/web-core/src/shared/components/WYSIWYGEditor.tsx`
      - now passes host id into the editor-node context
    - `packages/ui/src/components/attachment-node.tsx`
    - `packages/ui/src/components/image-node.tsx`
      - scope local attachment metadata/proxy/file URLs through the current host path
  - validation:
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/ui run check`
    - `pnpm --filter @vibe/local-web run build`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - `curl -s http://127.0.0.1:4311/api/info`
    - `curl -sI http://127.0.0.1:4311/`
    - `sha256sum /proc/$(systemctl --user show -p MainPID --value vibe-kanban.service)/exe /home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - result:
    - live service is active
    - running process and deployed binary both match sha `8b3b3f9e72dc37f99df018e88fa8f321cfd65b7df7b72b1136426f62832e15af`
    - UI confirmation of the exact affected flows is still pending a real user pass
- 2026-04-22 chat live-update follow-up:
  - symptom:
    - `FR:: Coaches Feature Stream` stopped showing new agent lines while the blinking thinking indicator remained
    - DB state showed the process completed, so the UI was stale rather than the agent still truly running
  - verified live evidence:
    - workspace `fcd0ec67-a0fe-42a8-9337-ef3228ceee80`
    - session `a97647d3-6d95-4470-a320-fe6bf415edd8`
    - process `b20d10a2-bf5b-43c2-97ef-ac1186664201`
    - repeated `MsgStore broadcast lagged ... messages dropped for this subscriber` in the live journal during that run
  - fix:
    - `crates/services/src/services/events/streams.rs`
      - session/workspace/scratch event websockets now turn `BroadcastStreamRecvError::Lagged(n)` into `io::Error` instead of swallowing it
      - this forces the client stream to reconnect and replay a fresh snapshot instead of staying stale
  - validation:
    - `cargo check -p services -p server`
    - `cargo build --release --bin server`
    - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - verified `/api/info` healthy
    - verified running PID executable path and sha match deployed binary
  - result:
    - live running binary sha now `9ad30eadb01eb7a357493a6232ffdddc3c212d32d8ae2dd050ff35ec742acad2`
    - direct UI confirmation still pending one real workspace retest
- 2026-04-22 issue/workspace relink follow-up:
  - symptom:
    - three newly created issue-scoped workspaces were live with `task_id = null` instead of linking back to their originating issues
  - verified broken live pairs before repair:
    - workspace `fcd0ec67-a0fe-42a8-9337-ef3228ceee80` (`FR:: Coaches Feature Stream`) missing link to task `af85bbe0-7c78-46ea-b0ec-91476596850c`
    - workspace `ff6bfbf1-8f71-4787-9e92-df7910c0928f` (`FR::Investigate today's active burn calories`) missing link to task `6bc54000-384e-4164-8995-b1c5a7d2469b`
    - workspace `e9c522ad-a455-42c7-9a4d-74ed6bf8ee98` (`FR::Investigate today's active burn calories`) missing link to task `f0933141-23fd-4a0e-89d3-5d2202325cea`
  - fix:
    - `packages/web-core/src/shared/components/CreateChatBoxContainer.tsx`
      - added `forcedLinkedIssue` so submits from the issue route use explicit issue/project context instead of relying only on draft state
    - `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`
      - issue-route workspace-create panel now passes the current route issue/project directly into `CreateChatBoxContainer`
    - `crates/server/src/routes/workspaces/create.rs`
      - added bounded retry for linked local task resolution during create-and-start when `linked_issue` is present but the first lookup misses
  - live repairs already applied:
    - linked workspace `fcd0ec67-a0fe-42a8-9337-ef3228ceee80` -> task `af85bbe0-7c78-46ea-b0ec-91476596850c`
    - linked workspace `ff6bfbf1-8f71-4787-9e92-df7910c0928f` -> task `6bc54000-384e-4164-8995-b1c5a7d2469b`
    - linked workspace `e9c522ad-a455-42c7-9a4d-74ed6bf8ee98` -> task `f0933141-23fd-4a0e-89d3-5d2202325cea`
  - validation:
    - `cargo check -p server -p services`
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/local-web run build`
    - `cargo build --release --bin server`
    - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - verified `/api/info` healthy and `/` returns `200`
    - verified running PID executable sha matches deployed binary sha `ebbdb9041fd2b6f517606005b53bca8ff1980f68553c1fa9135169b5dc6395cc`
  - result:
    - underlying issue-route workspace linking path is fixed in both the frontend submit path and the backend create-and-start resolution path
    - the three known broken workspaces are relinked live
- 2026-04-22 chat streaming follow-up:
  - symptom:
    - the orchestration workspace under `FR:: Coaches Feature Stream` streamed a few lines and then appeared stuck/busy
  - verified live chain:
    - workspace `679c24ec-7368-4a08-8f82-931f8d0ea896`
    - session `65c4bde9-df70-4e12-91fd-210c41e7aa3a`
    - latest process `d928142b-d587-4a16-9e23-013d1a6df622`
    - DB showed that process had already completed at `2026-04-22T12:39:44Z`
  - root cause:
    - normalized chat replay was flooding the client with repeated `replace` patches for the same `/entries/<n>` path while the response text grew
    - direct probe before fix saw about `3872` patch messages and `~5.07 GB` of websocket JSON over `20s`
  - fix:
    - `crates/server/src/routes/execution_processes.rs`
      - normalized-log websocket delivery now batches patches in `50ms` windows
      - repeated ops on the same path are coalesced before serialization/send
      - added unit tests covering last-write-wins coalescing
    - `crates/server/Cargo.toml`
      - added direct `json-patch` dependency for the new route logic
  - validation:
    - `cargo test -p server coalesce_patch_ops -- --nocapture`
    - `cargo check -p server -p services`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - verified running PID executable sha matches deployed binary sha `4a5e3356b9c7dc4dff3b5e82d5e451ce58d789d8db48420bbe207517d2e70ba4`
    - repeated the same websocket probe after deploy and saw about `60` patch messages, `128` patch ops, and `~109.6 MB` total JSON, with `finished` in about `16.1s`

- 2026-04-22 orchestration replay follow-up:
  - investigated workspace `679c24ec-7368-4a08-8f82-931f8d0ea896`, session `65c4bde9-df70-4e12-91fd-210c41e7aa3a`, process `d928142b-d587-4a16-9e23-013d1a6df622`
  - determined the process itself completed successfully and the full raw transcript was present on disk
  - narrowed the remaining visible freeze to direct app-server command-output delta normalization in `crates/executors/src/executors/codex/normalize_logs.rs`
  - fixed that path to use truncated-tail buffering and reduced chat command-output preview budgets to `8 KiB` streaming / `16 KiB` final
  - validation:
    - `cargo check -p executors -p server`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - exact normalized replay for `d928142b-d587-4a16-9e23-013d1a6df622` now completes in about `367 ms` across `8` websocket messages

- 2026-04-22 websocket reconnect follow-up:
  - rechecked workspace `679c24ec-7368-4a08-8f82-931f8d0ea896`, session `65c4bde9-df70-4e12-91fd-210c41e7aa3a`
  - confirmed newer orchestration processes `e9217d86-70b9-40f1-99d3-eea14c70975e` and `58ef1157-6d7f-4a45-9c74-36722839475f` both completed successfully with final answers present in raw `.jsonl` logs
  - confirmed post-restart normalized replay for `e9217d86-70b9-40f1-99d3-eea14c70975e` completes in about `71 ms` with `2` websocket messages and the session execution-process stream still emits snapshot plus `Ready`
  - traced the remaining blank/stale chat behavior to `packages/web-core/src/shared/hooks/useJsonPatchWsStream.ts`
  - fixed reconnect handling so retry cleanup no longer clears stream state for the same endpoint; full reset now happens only when `enabled` or `endpoint` changes
  - validation:
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/local-web run build`
    - `cargo build --release --bin server`
    - `pnpm run format`
    - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - verified `/` returns `200`
    - verified `/api/info` healthy

- 2026-04-22 staging deploy:
  - fetched `fork/staging` and confirmed local `staging` checkout was behind the remote branch
  - avoided merging into the dirty canonical checkout because it overlaps unrelated local edits
  - created detached clean worktree at `/tmp/vk-staging-deploy-20260422` on `fork/staging` commit `6c0ce663a4548277f1ad774654b2bf82841cc126`
  - validated in the clean staging worktree:
    - `pnpm install --frozen-lockfile`
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/ui run check`
    - `cargo check -p db -p server`
    - `pnpm --filter @vibe/local-web run build`
    - `cargo build --release --bin server`
    - `pnpm run format`
  - deployed `/tmp/vk-staging-deploy-20260422/target/release/server` to `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified service `active`, `/` returns `200`, `/api/info` healthy
  - live binary sha after deploy: `36671ede4bd0971a00b6256c1bb252d537b369da7d9de5a39e6003689226ce43`
  - fast-forwarded the checked-out local `staging` worktree at `/home/mcp/code/worktrees/3714-vk-codeblock-onl/_vibe_kanban_repo` to the same commit so rebases can target the deployed head

- 2026-04-22 local issue/workspace linking repair:
  - confirmed fresh broken local pair:
    - issue/task `36de33b5-5fe7-4996-831a-c966c89d7bb5`
    - workspace `6fdd2862-9fcf-4624-8b45-0b9dd1b109dc`
    - both titled `VK::Fix collapsed mobile columns tk2`
    - task created `2026-04-22 20:23:15.643`
    - workspace created `2026-04-22 20:23:23.803`
    - workspace had `task_id = null`
  - fixed `crates/server/src/routes/workspaces/links.rs` so local link requests retry local task resolution and no longer fall through toward remote-link behavior for local projects
  - validation:
    - `cargo check -p server`
    - `cargo build --release --bin server`
    - redeployed `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
    - restarted `vibe-kanban.service`
    - verified `/api/info` healthy
  - repaired the live orphan through `POST /api/workspaces/:id/links`
    - workspace `6fdd2862-9fcf-4624-8b45-0b9dd1b109dc`
    - task `36de33b5-5fe7-4996-831a-c966c89d7bb5`
  - end-to-end disposable live verification:
    - created issue `VK LINK TEST 20260422T203516Z`
    - created linked workspace `7dee992f-ce10-4326-84e2-fbdd1da3d40c`
    - verified row stored `task_id = d3e32d0a-c67e-417b-a7af-30072d71a1d4` immediately
    - deleted the disposable issue and workspace after the check

- 2026-04-22 orphan link cleanup:
  - audited all remaining `workspaces.task_id is null` rows in the live DB
  - safely relinked:
    - workspace `69108907-ee4c-4c2d-8d96-fe496bb2b6bd` -> task `4c7065b5-b43a-41f9-b524-e6f3068d39a2`
    - workspace `5db38b19-2e12-4e77-a746-c7ae2b515ab7` -> task `77762500-bfcb-4636-b8e4-f268f6da1b95`
  - intentionally skipped:
    - `probe-ws`
    - `probe-ws-postfix`
    - no issue matches
  - intentionally skipped duplicates:
    - `FR::Investigate today's active burn calories`
    - `VK::Auto archive when 'Done'`
    - matching issues already had linked workspaces
  - intentionally skipped ambiguous historic rows with no confident issue match:
    - `OVA::Dashboard Init Build`
    - `FR::Refactor - Merge Rules`
    - `The Dashboard nutrition card is WAY too verbose. It's breaking the layout and overloading the user`

- 2026-04-23 staging production deploy:
  - fetched and deployed `fork/staging` commit `4337e20e1638495b5f8b8aa6124678a18357d09b` from clean detached worktree `/tmp/vk-staging-deploy-20260423T082907Z`
  - avoided deploying from the dirty canonical checkout at `/home/mcp/_vibe_kanban_repo`
  - validation in the clean worktree:
    - `pnpm install --frozen-lockfile`
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/ui run check`
    - `cargo check -p server`
    - `pnpm --filter @vibe/local-web run build`
    - `pnpm run format`
    - `cargo build --release --bin server`
  - `pnpm run format` passed but would rewrap two already-committed TypeScript expressions on staging; reverted those temp formatting-only changes before the release build to deploy the exact staging commit
  - frontend build succeeded; Sentry emitted missing-auth-token noise but did not fail the build
  - installed release binary to `/home/mcp/.local/bin/vibe-kanban-server-cleanfix`
  - restarted `vibe-kanban.service`
  - verified service active, `/api/info` healthy, `/` `200`, `/assets/index-48sjVvVl.js` `200`
  - live binary sha after deploy: `9b73d5f94dec505bc5dbd0384802c80c4b014ac55c4fc35abbde5298a84d76bf`

- 2026-04-23 post-deploy staging/branch audit:
  - checked local and remote git state after the T18/PR `#9` merge
  - found the checked-out local `staging` worktree at `/home/mcp/code/worktrees/3714-vk-codeblock-onl/_vibe_kanban_repo` was clean but still behind `fork/staging` by one commit
  - fast-forwarded that local `staging` worktree from `6c0ce663a4548277f1ad774654b2bf82841cc126` to `4337e20e1638495b5f8b8aa6124678a18357d09b`
  - confirmed PR `#9` / T18 was a squash commit on top of `6c0ce663a4548277f1ad774654b2bf82841cc126`
  - confirmed T18 did not overwrite T12 because T12 was not in staging and there was no changed-file overlap between T12 and the T18 squash diff
  - confirmed deployment visibility state:
    - ART-50 `vk/recover-kanban-columns-20260415` is not an ancestor of `fork/staging`; do not bulk-merge it because it is divergent and conflicts
    - ART-52 `codex/fix-workspace-chat-scroll-jumps` is not in `fork/staging` and direct merge conflicts
    - ART-53 `vk/401e-vk-fix-mobile-co` is not in `fork/staging`; T18/PR `#9` is the current deployed replacement for mobile collapsed labels
    - T6 `vk/3714-vk-codeblock-onl`, T7 `vk/cc95-vk-archive-proje`, and T8 `vk/9fea-vk-cleanup-left` are ancestors of `fork/staging`
    - T12 `vk/508a-vk-renaming-work` is local-only/no GitHub PR and merge-tree tests cleanly into current `fork/staging`
  - confirmed the live frontend asset `/assets/index-48sjVvVl.js` contains markers for T6/T7/T8 such as `Copy code`, `Archive project`, and `Show left column links`

- 2026-04-26 hotfix/stuck-running-reconcile-20260426:
  - investigated the open-workspace symptom where an agent completes and replies, but the VK UI remains stuck in the in-progress state until the page is refreshed
  - root cause direction:
    - the backend can already have the terminal execution-process state while the open page still holds stale streamed `running` state
    - refresh fixes the UI because the fresh snapshot no longer has the stale running process
  - hotfix prepared from clean `fork/main` worktree `/tmp/vk-hotfix-stuck-running-reconcile`
  - code change:
    - `packages/web-core/src/shared/hooks/useExecutionProcesses.ts`
    - while streamed blocking processes are `running`, poll the process detail endpoint every `3s`
    - merge the detail result over the stream for that process so terminal status clears the composer without refresh
  - commit:
    - `cce261c79 fix: reconcile stale running process status`
  - PR:
    - `https://github.com/artinflight/vibe-kanban/pull/41`
  - validation:
    - `pnpm install --frozen-lockfile`
    - `pnpm --filter @vibe/web-core run check`
    - `pnpm --filter @vibe/local-web run build`
    - `pnpm run format`
    - `git diff --check`
  - live service was not restarted; deploy/restart still requires explicit user approval

- 2026-04-27 Hyrox Ready Codex repetition investigation:
  - audited recent Hyrox Ready VK sessions and raw process JSONL logs
  - found VK-launched Codex app-server processes were using `/home/mcp/.codex` because the live service lacked `CODEX_HOME`
  - restored `/home/mcp/.config/systemd/user/vibe-kanban.service.d/codex-home.conf` with the isolated VK Codex home and ran `systemctl --user daemon-reload`
  - waited for Hyrox process `d128a1215d024e8887bf3eb27c7b3468` to finish, restarted VK, and verified the live process has the isolated `CODEX_HOME`
  - sampled logs showed full-thread history payloads and rebase conflict repetition, but no broad automatic prompt replay loop

- 2026-04-29 isolated Codex rollout migration:
  - repaired `thread/fork request failed: no rollout found for thread id 019dce56-2737-7d13-9965-e8996caca9dd`
  - confirmed VK still had `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
  - copied all DB-referenced rollout files and matching shell snapshots that existed in `/home/mcp/.codex` but were missing from the isolated VK Codex home
  - copied `121` rollouts and `121` shell snapshots
  - verified no DB `agent_session_id` remains missing from the isolated Codex home

- 2026-04-28 stale running execution-process hotfix:
  - prepared hotfix from clean `fork/main` worktree `/tmp/vk-hotfix-stuck-running-reconcile`
  - changed `packages/web-core/src/shared/hooks/useExecutionProcesses.ts` so streamed blocking `running` processes poll process details every `3s` and reconcile terminal status without requiring page refresh
  - main PR `#41` merged at `de679dfba4d00fb4e7227c0474e1f783861d908a`
  - staging backfill PR `#43` merged after passing GitHub checks at `1e208123694b420c5688c5098bdbe5b7ec1aa158`
  - deployed from clean worktree `/tmp/vk-deploy-stuck-running-reconcile`
  - pre-restart live audit found `0` running non-devserver executions
  - restarted `vibe-kanban.service` after user permission
  - live binary `/home/mcp/.local/bin/vibe-kanban-serve` sha256 `a6862b6a9439ab4fd114a3a9204aeba65da533f9a05acf7c6888bea8d70cea8f`
  - post-deploy verification passed: service active, running process sha matches installed binary, `/api/info` healthy, `/` `200`, `/assets/index-D4KCtbF2.js` `200`

- 2026-04-28 permanent local issue-link hotfix:
  - repaired the live OSTP data path by adding project `/home/mcp/code/OSTP` and linking workspace `c40cbc4a-4939-4b66-be36-05be0d30784f` to issue `83b227d8-f91c-4cf8-bcef-1ef5dc795720`
  - root cause direction: draft workspace metadata can lose `linked_issue`, so the backend must not depend only on the frontend carrying that field forward
  - main hotfix PR `#44` merged at `21815da2b9bbdd57f5711cfe9e6c481fa0aeb2ae`
  - staging backfill PR `#45` merged at `24a2dbe3ad5b7457beea772c4cbe6ea0a070944f`
  - fix behavior: if a local workspace starts with no `task_id`, infer the local issue from selected repo(s) plus exact workspace title, and link only when exactly one matching local issue exists
  - ambiguity is intentionally left unlinked to avoid attaching workspaces to the wrong issue
  - validation: PR `#44` and PR `#45` GitHub checks passed; local backfill validation covered generated types, format, temp SQLite migrations, clippy, `cargo check -p server`, targeted local issue-link tests, and `git diff --check`
  - live VK was not restarted or redeployed; deployment still requires explicit user approval

- 2026-04-28 permanent local issue-link deploy:
  - took lean backup before restart:
    - `/home/mcp/backups/vk-lean-restore-20260428T135054Z`
    - `/home/mcp/backups/vk-lean-restore-20260428T135054Z.tar.gz`
  - deployed from clean detached worktree `/tmp/vk-deploy-permanent-issue-links-20260428T1358Z` at `fork/main` merge commit `21815da2b9bbdd57f5711cfe9e6c481fa0aeb2ae`
  - validation/build before restart:
    - `pnpm install --frozen-lockfile`
    - `pnpm --filter @vibe/local-web run build`
    - temp SQLite `cargo sqlx migrate run`
    - `DATABASE_URL=sqlite:/tmp/vk-deploy-permanent-issue-links.sqlite cargo build --release --bin server`
  - release binary sha256: `20c614ea3547f1564eb1a3523f84a74b3b369e3c10988957f2957684e69a479c`
  - backed up previous live binary to `/home/mcp/backups/vibe-kanban-serve-before-permanent-issue-links-20260428T1416Z`
  - pre-restart audit found `0` running non-devserver executions and `0` active `vk-exec-*` units
  - restarted `vibe-kanban.service` after explicit user approval
  - post-deploy verification passed:
    - service active
    - running process sha matches installed binary sha
    - `/api/info` healthy
    - `/` returned `200`
    - `/assets/index-BbxAzB0F.js` returned `200`
    - post-restart running execution processes: `0`

- 2026-05-03 staging-to-main promotion and runtime guardrail restore:
  - took pre-op backup `/home/mcp/backups/vk-pre-restore-guardrails-main-merge-20260503T115553Z`
  - restored persistent live service env in `/home/mcp/.config/systemd/user/vibe-kanban.service.d/runtime-guardrails.conf`
  - required live env now includes `CODEX_HOME`, `DISABLE_WORKTREE_CLEANUP=1`, `VK_DISABLE_PR_MONITOR=1`, `VK_USE_SYSTEMD_RUN=1`, `VK_TRANSIENT_MEMORY_HIGH=1500M`, `VK_TRANSIENT_MEMORY_MAX=3000M`, `VK_CODEX_BASE_COMMAND=/home/mcp/.local/bin/codex`, and `VK_ALLOWED_ORIGINS=https://vibe.local`
  - merged `fork/staging` into `fork/main` from clean worktree `/tmp/vk-main-merge-staging-20260503T1155`
  - resolved merge fallout in status sort order by keeping `sort_order` as `i64`
  - added repo-tracked live guardrail material on `main`:
    - `docs/self-hosting/systemd/runtime-guardrails.conf`
    - `scripts/check-live-vk-runtime-guardrails.sh`
    - `pnpm run ops:live-runtime-guardrails`
  - pushed `fork/main` to `5ddde0b6460393e7d34301d676b1dd86c8b99bc5`
  - validation passed:
    - `pnpm run format`
    - `pnpm run ops:check`
    - `pnpm run ops:live-runtime-guardrails`
    - `pnpm --filter @vibe/local-web run build`
    - `DATABASE_URL=sqlite:/tmp/vk-main-merge-build.sqlite cargo build --release --bin server`
  - deployed release artifact sha256 `e2f86f5ccc880cfeeba4684cf1a0ecdd05bc27e63d2b39a0a9d4a6ce47256d5c` to both `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - restarted `vibe-kanban.service` after explicit user approval; restart required killing only the old VK main PID after the service stuck in `deactivating`
  - post-restart checks passed: service active, running process sha matches installed binaries, `/api/info` healthy, `/` `200`, `https://vibe.local/` `200`, running executions in DB `0`
  - the old active executions were interrupted by the restart and marked failed on startup
  - observed VK memory after restart around `200 MB` with `0` VK swap, down from roughly `20 GB` before restart

- 2026-05-05 recurring VK git/worktree stall hotfix and deploy:
  - took manual pre-restart backup `/home/mcp/backups/vk-pre-restart-manual-20260505T161804Z`
  - the earlier lean-backup archive attempt `/home/mcp/backups/vk-lean-restore-20260505T160819Z` failed because a Codex rollout file disappeared mid-copy and is not the valid backup
  - activated refreshable frontend assets through `/home/mcp/.config/systemd/user/vibe-kanban.service.d/frontend-dist.conf`
  - published frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260505T1648Z` and pointed `/home/mcp/.local/share/vibe-kanban/frontend-dist/current` at it
  - built hotfix from clean worktree `/tmp/vk-hotfix-recurring-stall-20260505` at `b6575aed90e4ecf7ddb5279528292f68a0545212`
  - main PR `#55` merged at `3cfe96ab8f8c6a83652f4c84a9d4244ca4e37a9f`
  - staging backfill PR `#56` merged at `91e2f9d1a30842fd0d770cdfda39c27932bfa084`
  - deployed binary sha256 `c903c345859a1838fbe27b3de47f8bcf178849d3e62f9b0e8f808d2cc161c570` to `/home/mcp/.local/bin/vibe-kanban-serve` and `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - fix behavior: `LocalContainerService::stream_diff` keeps skipped repo-diff streams idle/ready instead of closing the workspace websocket, and `GitCli` commands default to a bounded `120s` timeout through `VK_GIT_CLI_TIMEOUT_SECS`
  - validation passed: `pnpm --filter @vibe/local-web run build`, `cargo build --release --bin server`, prior hotfix `cargo check -p git -p local-deployment`, and `pnpm run format` in the clean hotfix worktree
  - pre-restart audit found `0` running execution rows and no active `vk-exec-*` units
  - restart required killing only old VK main PID `3441151` after systemd stuck in `deactivating`; service came back on PID `3962645`
  - post-restart checks passed for `/api/info`, `/`, `https://vibe.local/`, `/api/projects`, `/assets/index-CErwigwv.js`, no running execution rows, no active `vk-exec-*` units, and VK memory around `260-280 MB`

- 2026-05-06 dysfunctional feature audit and needs-attention fix prep:
  - investigated codeblock copy, workspace rename actions, issue PR details, merged PR state, and left-column needs-attention markers
  - found latest codeblock-copy reliability fixes are not safely landed in production/integration; port the minimal latest fix instead of bulk-merging stale `vk/codeblock-copy-20260429`
  - found local rename actions are hidden by remote-owner gating when fallback local workspace rows have `owner_user_id = ""`
  - found issue PR details/merged-state display lacks durable `pull_requests` rows for some affected issues, and live PR monitoring remains intentionally disabled
  - found needs-attention markers persist because already-open workspaces did not re-mark unseen turns as seen and `mark_seen` did not invalidate the workspace-summary cache
  - prepared code changes in the canonical checkout to auto-clear unseen state for the mounted workspace and invalidate summary cache on `PUT /api/workspaces/:id/seen`
  - updated `HANDOFF.md`, `STATE.md`, `STREAM.md`, and `VK_WORKFLOW.md` with findings and repair plan

- 2026-05-06 attachment and disk-space follow-up:
  - reviewed tmux session `opSpace` because the user could not paste the report
  - disk report: root filesystem `233G` total, `192G` used, `31G` free, `87%` full
  - largest reported areas: `/home/mcp/backups` `52G`, `/home/mcp/code` `47G`, `/home/mcp/.local` `29G`, `/home/mcp/_vibe_kanban_repo` `15G`, Android SDK/AVD about `9.8G`, journals `3.1G`
  - recommended cleanup order before executing repairs: rebuildable outputs first, then inactive dependency trees, then journals; treat backups, VK `codex-home`, VK sessions, and registered worktrees as continuity-sensitive
  - attachment findings: existing-workspace new-session attachment controls can silently no-op without `sessionId`; upload errors are swallowed in UI; live logs show attachment upload `500`s; running backend is missing `/home/mcp/.cache/utils/attachments`
  - documented restart split: recreating the cache dir and frontend-only error display can avoid restart; backend cache-dir self-healing, cleaner missing-file errors, and true new-session attachment support require backend deploy/restart

- 2026-05-06 approved stale-worktree `node_modules` cleanup:
  - user approved removing `node_modules` from worktrees untouched for more than 4 days
  - excluded active VK workspaces before deletion:
    - `/home/mcp/code/worktrees/c961-fr-orc-android-p`
    - `/home/mcp/code/worktrees/2fa0-fr-fix-heartrate`
    - `/home/mcp/code/worktrees/6e87-fr-enhance-dashb`
    - `/home/mcp/code/worktrees/2482-pg-logging`
  - removed qualifying `node_modules` from five stale worktrees:
    - `/home/mcp/code/worktrees/3714-vk-codeblock-onl/_vibe_kanban_repo`
    - `/home/mcp/code/worktrees/679c-fr-orc-coaches-f/hyroxready-app`
    - `/home/mcp/code/worktrees/fcd0-fr-coaches-featu/hyroxready-app`
    - `/home/mcp/code/worktrees/hyroxready-app/codex-android-member-parity`
    - `/home/mcp/code/worktrees/hyroxready-app/program-generation-v4-real-example-coach`
  - freed about `2G`; `df -h /home/mcp` moved from `31G` free / `87%` used to `33G` free / `86%` used
  - no source files, backups, VK sessions, `codex-home`, active workspaces, or service state were touched

- 2026-05-06 follow-up safe space cleanup:
  - removed all remaining archive `node_modules` under `/home/mcp/code/archive`; follow-up count is `0`
  - removed rebuildable Rust `target` trees from `/home/mcp/_vibe_kanban_repo`, `/home/mcp/code/worktrees/6685-vk-pr-details-hi/_vibe_kanban_repo`, and `/home/mcp/code/worktrees/ea3c-vk-auto-archive/_vibe_kanban_repo`
  - removed stale worktree install `/home/mcp/code/worktrees/c961-fr-orc-android-p/hyroxready-app/node_modules` after rechecking active VK execution services and process roots
  - removed repo-local `/home/mcp/_vibe_kanban_repo/scripts/__pycache__`
  - current `df -h /home/mcp` is `59G` free / `74%` used
  - corrected scan groups `node_modules` by actual Git root; remaining worktree installs are either active or under the approved `>4 days untouched` threshold, with several near the threshold
  - attempted journal vacuum did not reduce reported journal usage; do not claim journal cleanup succeeded
  - no backups, VK DB, VK `codex-home`, VK sessions, source files, or running services were changed

- 2026-05-06 no-restart VK frontend repair:
  - recreated live attachment cache directory `/home/mcp/.cache/utils/attachments`
  - added/published read-only chat codeblock copy controls using a per-code-block overlay and clipboard fallback
  - changed local fallback workspace ownership checks so rows with `owner_user_id = ""` and a matching local workspace can show rename/delete actions
  - changed workspace-chat attachment handling so missing workspace/session and upload failures surface in the composer instead of silently no-oping
  - true existing-workspace new-session attachment support still needs backend work; the no-restart fix now reports that limitation instead of pretending the paste worked
  - published refreshable frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1531Z-no-restart-ui-fixes`
  - verified live `/` references `/assets/index-DkFp1Jd5.js` and `/assets/index-DvZydbR5.css` through `https://vibe.local` and `http://127.0.0.1:4311`
  - generic attachment upload/delete smoke test passed after recreating the cache directory; smoke-test DB rows and cache files were deleted
  - validation passed: targeted prettier, `pnpm --filter @vibe/web-core run check`, `pnpm --filter @vibe/ui run check`, `pnpm --filter @vibe/local-web run build`, and targeted `git diff --check`
  - no backend binary was replaced and `vibe-kanban.service` was not restarted
  - documented user QA checklist in `HANDOFF.md`: hard refresh, codeblock copy, local workspace rename/delete, attachment upload/error behavior, and known needs-review backend-cache limitation

- 2026-05-06 mobile attachment picker follow-up:
  - user reported mobile attachment selection did nothing
  - fixed `packages/ui/src/components/SessionChatBox.tsx` so the paperclip uses a native label/input activation path instead of JS-clicking a hidden input, which mobile browsers can ignore
  - published refreshable frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1548Z-mobile-attachment-fix`
  - verified live `/` references `/assets/index-DXD0AdX9.js` and `/assets/index-DvZydbR5.css`; `vibe-kanban.service` stayed active/running on PID `3962645`

- 2026-05-06 attachment visible-error follow-up:
  - user clarified mobile picker opened, but selecting a file still produced no visible app-side result
  - found create-mode attachments had a separate hidden-input path and `useCreateAttachments` only logged upload failures
  - changed create-mode attachments to use native label/input activation, show uploading/error feedback, and reject files over the backend `20 MB` cap before upload
  - added the same client-side oversized-file guard to session attachments
  - published refreshable frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1625Z-attachment-visible-errors`
  - verified live `/` references `/assets/index-D-47mEIl.js` and `/assets/index-DvZydbR5.css`; `vibe-kanban.service` stayed active/running on PID `3962645`
  - small-file `POST /api/attachments/upload` smoke passed and the smoke attachment was deleted

- 2026-05-06 frontend rollback after project-list regression:
  - user reported old projects returned and project order was lost after the no-restart frontend bundles
  - determined the repair bundles were built from a dirty checkout that contained unrelated project/nav UI changes
  - rolled live frontend assets back to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260505T1648Z` without restarting VK
  - verified live `/` references `/assets/index-CErwigwv.js` and `/assets/index-xIIrANvd.css`; `vibe-kanban.service` stayed active/running on PID `3962645`
  - no-restart attachment/codeblock frontend fixes are not live after this rollback; rebuild from a clean worktree only
  - prepared local `100 MB` attachment cap change across backend route limits, `FileService`, and frontend preflight; backend deploy/restart is required before large mobile images can upload

- 2026-05-06 clean codeblock-copy frontend rebuild:
  - built from clean `fork/main` worktree `/tmp/vk-codeblock-copy-clean-20260506T165520Z` at `3cfe96ab8`
  - added only clipboard fallback improvement in `packages/web-core/src/shared/lib/clipboard.ts`
  - published `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506T1701Z-clean-codeblock-copy` without restarting VK
  - validation passed: clean install, targeted prettier, `pnpm --filter @vibe/web-core run check`, and `pnpm --filter @vibe/local-web run build`
  - HTTP verification timed out because the running VK process was saturated around `19 GB` RSS and `/api/info` did not answer within `20s`

## 2026-05-09T22:00:00Z | vk/land-live-fixes-20260422 | sub-agent indicator source fix

- Intent: make VK show workspace/sidebar sub-agent activity from durable state instead of only inside the open chat composer.
- Finding: VK `subagent_jobs` was empty, but isolated Codex state had real `thread_spawn_edges`; earlier UI work was incomplete because workspace summaries never read Codex child-thread state.
- Prepared:
  - merged `subagent_jobs` with Codex `thread_spawn_edges` via `coding_agent_turns.agent_session_id`
  - added `active_subagent_count` and `unresolved_subagent_count` to workspace summaries and generated shared TS types
  - rendered a stack/count marker on workspace cards and kept active-subagent workspaces in the Running section
  - broadened live log capture for namespaced `spawn_agent` / `wait_agent` tool names and singular `target`
- Verified: `pnpm run generate-types`, `pnpm run format`, `pnpm --filter @vibe/ui run check`, `pnpm --filter @vibe/web-core run check`, `cargo check -p server`, targeted `git diff --check`.
- Deployment: not deployed; requires approved backend restart/deploy before live `vibe.local` can show the marker.

## 2026-06-01T08:50:00Z | vk/land-live-fixes-20260422 | FR::ORC::Generative Programming auth repair

- Investigated workspace `5a8066b0-c3ff-46d2-8953-f39a90ce3f0c`.
- Latest process log showed repeated Codex ChatGPT `refresh_token_reused` / `token_expired` errors and a failed empty turn.
- Root cause was stale isolated VK Codex auth from `2026-05-21` at `/home/mcp/.local/share/vibe-kanban/codex-home/auth.json`.
- Backed it up to `/home/mcp/backups/vk-auth/codex-home-auth-before-refresh-20260601T085017Z.json`.
- Copied fresh `/home/mcp/.codex/auth.json` into VK isolated Codex home with mode `600`.
- Verified isolated `codex login status` and `codex debug models` succeed.
- No VK restart, no agent kill, and no token output.

## 2026-06-03T22:48:00Z | vk/land-live-fixes-20260422 | mobile archived-projects nav hotfix

- Intent: restore the expected mobile project nav so archived projects are accessible and the stale `Export data` entry is gone from the mobile drawer.
- Finding: desktop `AppBar` already had `onOpenArchivedProjects` and export hidden, but `SharedAppLayout.tsx` has a separate hardcoded mobile drawer that still rendered the old export row and never opened `ArchivedProjectsDialog`.
- Changed `packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx` to remove the mobile export row and add a footer `Archived projects` button with marker `mobile-archived-projects`.
- Deployed no-restart frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tmobile-archive-nav`; live asset `/assets/index-CPHsMjmW.js`; backend PID stayed `3435842`.
- Verified: `pnpm --filter @vibe/local-web run build`, staged/live asset marker checks, `python3 scripts/vk_live_regression_smoke.py`.

## 2026-06-04T08:15:31Z | vk/land-live-fixes-20260422 | multi-line paste hotfix

- Intent: repair VK chat paste so multi-line prompts preserve all lines instead of stopping at the first line break.
- Finding: `PasteMarkdownPlugin.tsx` converted all plain-text paste through Lexical markdown import and then inserted children from a temporary paragraph; multi-line chat prompts can collapse/truncate through that path.
- Changed `packages/ui/src/components/PasteMarkdownPlugin.tsx` so multi-line plain text uses `selection.insertRawText(plainText)` while single-line paste keeps the existing markdown conversion behavior.
- Deployed no-restart frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260604Tmultiline-paste`; live asset `/assets/index-BOrQKfSR.js`; backend PID stayed `3435842`.
- Verified: `pnpm --filter @vibe/ui run check`, `pnpm --filter @vibe/local-web run build`, staged/live asset marker checks, `python3 scripts/vk_live_regression_smoke.py`.

## 2026-06-08T17:06:05Z | vk/land-live-fixes-20260422 | Plan-to-Auto mode persistence hotfix

- Intent: stop Plan-started VK sessions from snapping back to Plan after the user switches them to Auto.
- Finding: backend/Codex Auto overrides already force `plan=false`, but frontend explicit selections were only in React state/draft scratch and could be lost on remount, draft clear, or process-list refresh.
- Changed `useExecutorConfig` to persist explicit executor/model/mode override selections in browser localStorage under `vk-executor-config-selection:*`, keyed by session ID for existing sessions and workspace ID for new-session mode.
- Added executor regression coverage proving `PermissionPolicy::Auto` exits Codex plan mode.
- Deployed no-restart frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260608Tmode-persistence`; live asset `/assets/index-CTVtS8yb.js`; backend PID stayed `3435842`.
- Verified: `pnpm --filter @vibe/web-core run check`, `cargo test -p executors codex_auto_permission_override_exits_plan_mode`, `pnpm run format`, clean worktree install/check/build, `python3 -m py_compile scripts/vk_live_regression_smoke.py`, `git diff --check`, and live `python3 scripts/vk_live_regression_smoke.py`.

## 2026-06-11T00:00:00Z | vk/land-live-fixes-20260422 | Codex capacity queue prepared

- Intent: when global Codex capacity is full, chat sends should queue instead of failing with the red `Codex execution limit reached: 8 active, limit 8` error.
- Finding: the cap was surfaced as an executor start failure; existing queue behavior only covered sessions with a running per-session consumer, not idle sessions waiting for a global slot.
- Changed executor/container/server paths to use typed `ExecutionLimitReached`, queue follow-up prompts with `wait_for_capacity`, avoid visible failed placeholder execution rows, and drain the oldest capacity-waiting queued prompt when any process completes.
- Changed frontend follow-up send paths to treat the typed queued response as a successful queued send and refresh queue/workspace summary state.
- Added queue service regression coverage for oldest-first capacity queue consumption without consuming normal queued messages.
- Verified: `pnpm run generate-types`, `cargo test -p services takes_oldest_capacity_queue_without_consuming_normal_queue`, `cargo check -p services -p local-deployment -p server`, and `pnpm --filter @vibe/web-core run check`.
- Deployment: not deployed; requires backend build/restart before live VK gets this behavior.

## 2026-06-11T00:00:00Z | vk/land-live-fixes-20260422 | Kanban card reorder prepared

- Intent: stop Kanban cards from bouncing back after reordering within a column.
- Finding: `KanbanContainer` discarded within-column drags unless the active view already sorted by `sort_order`, and local fallback issue routes dropped `sort_order` entirely before persisting task-backed issues.
- Changed frontend card drag handling to switch the active project view to manual `sort_order asc` before applying a drag.
- Changed local fallback create/update/bulk issue request structs to accept `sort_order`, store it in task description metadata as `Local Sort Order`, and read it back into fallback issue responses.
- Verified: `pnpm --filter @vibe/web-core run check`, `cargo test -p server local_sort_order_metadata_round_trips`, and `cargo check -p server`.
- Deployment: not deployed; backend build/restart is needed for local fallback persistence.

## 2026-06-12T00:00:00Z | vk/land-live-fixes-20260422 | Issue needs-review flag prepared

- Intent: let the operator quickly flag issues for review from the project Kanban card itself.
- Changed Kanban cards to render a flag button beside the priority marker.
- Changed `KanbanContainer` to persist the flag as `Issue.extension_metadata.vk_flags.needs_review`.
- Changed local fallback issue handling to round-trip enabled flags through task description metadata as `Local Issue Flags`.
- Verified: `cargo fmt`, targeted `git diff --check`, and `cargo test -p server local_issue_flags_metadata_round_trips` after a cold dependency rebuild.
- Deployment: not deployed; live VK needs a frontend release for the button and a backend build/restart for local fallback persistence.

## 2026-06-12T00:00:00Z | deploy/restart-candidate-20260611T112143Z | restart candidate refreshed

- Refreshed the clean restart candidate with the issue needs-review flag.
- Candidate commit: `a055ce585b7b682dba53b5c99860f023f32e3ed3`.
- Staged package: `/home/mcp/vk-restart-staging-20260612TissueReviewFlag`.
- Staged backend sha256: `32cebd5835faeae2007905e5b15593097699d735e8b7d0ea93020a4375238ed9`.
- Staged frontend release: `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260612TissueReviewFlag`, asset `/assets/index-DA7R5Mdm.js`.
- Validation: candidate install/checks, targeted server flag test, backend release build, frontend production build, and staged marker checks passed.
- Deployment: not restarted and live frontend pointer not switched; current restart blocker is active workspace `FR::ORC::Generative Programming`.

## 2026-06-18T00:00:00Z | vk/land-live-fixes-20260422 | branch base search hotfix

- Intent: workspace creation base-branch typing should filter forgivingly instead of requiring exact slash-heavy branch text.
- Changed `CommandBar` and `BranchSelector` branch matching to normalize separators and require all query tokens, while preserving exact substring matching.
- Deployed no-restart frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260618Tbranch-search`; live asset `/assets/index-CCBiSGB0.js`; backend PID stayed `3435842`.
- Verified: `pnpm run format`, UI/web-core checks, `git diff --check`, local-web build, bundle marker check, and live `python3 scripts/vk_live_regression_smoke.py`.
- Guard: future restart/frontend packages must carry forward this release or newer; a candidate that missed live hotfix markers was rolled back before smoke passed.

## 2026-06-21T00:00:00Z | vk/land-live-fixes-20260422 | project sidebar customization prepared

- Intent: let the compact project rail reveal full names on demand and support project rename, short abbreviations, and pastel project colors.
- Changed `AppBar` to add a triangle flyout, full-name project list, and project edit dialog with name/abbreviation/color controls.
- Added UI preference scratch persistence for per-project `local_project_customizations` and wired those overrides through `SharedAppLayout`.
- Added local project rename support to the existing project update route while preserving archive updates; regenerated shared types.
- Verified: `pnpm install --offline --frozen-lockfile`, `pnpm run generate-types`, `pnpm run format`, UI/web-core checks, `cargo check -p server`, focused project route tests, and targeted diff check.
- Deployment: not deployed; frontend release plus backend build/restart are needed, and the next package must rebuild forward from live `20260618Tbranch-search` or newer.

## 2026-06-26T00:00:00Z | vk/land-live-fixes-20260422 | multi-line rich clipboard paste hotfix

- Intent: fix chat paste where multiline text from mobile/rich clipboard sources stopped after the first line.
- Finding: the plugin preserved multiline `text/plain` only after returning early for any clipboard `text/html`; rich clipboard sources include both representations.
- Changed `PasteMarkdownPlugin.tsx` so multiline `text/plain` wins before HTML opt-out and uses `selection.insertRawText`.
- Deployed no-restart frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260626Tmultiline-rich-paste`; live asset `/assets/index-DXMultilinePaste.js`; backend PID stayed running and no service restart was performed.
- Verified: UI typecheck, targeted diff check, live curl marker checks, and live `python3 scripts/vk_live_regression_smoke.py`.
- Guard: future frontend/restart packages must carry forward this source fix and not roll back below `20260626Tmultiline-rich-paste`.
