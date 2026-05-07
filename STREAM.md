# STREAM.md

## Stream Identifier

- Branch: `hotfix/bound-historical-log-replay-20260506T1715Z`
- Repo: `/tmp/vk-hotfix-historical-replay-20260506T1715Z`
- Base: `fork/main`
- Working mode: production hotfix for recurring live VK execution-log replay stalls

## Objective

- Stop the recurring live VK stall pattern where dead browser execution-log websocket connections and historical normalized log replay can keep backend replay/feed work alive after clients disconnect.

## In Scope

- Add bounded sends for execution-log websocket messages.
- Cancel historical normalized log replay feeder work when the returned stream is dropped.
- Preserve live VK state as much as possible with a DB/session/process snapshot before forced restart.
- Deploy the patched backend binary to the local live service.

## Out of Scope

- Restarting or redeploying VK without operator approval.
- Quarantining, deleting, or force-stopping live workspaces without explicit confirmation.
- Broad websocket, database, worktree, or frontend redesign beyond the observed retention path.

## Stream-Specific Decisions

- Local runtime expectations from `STATE.md` remain in force, including `shared_api_base: null`.
- Resume continuity should only anchor to successful coding-agent turns: completed process, exit code `0`, non-null agent session id, and non-empty final summary.
- Empty or missing rollout files are live-state corruption, not valid resume anchors.
- Execution-process streams are long-lived state streams; non-patch terminal messages must not make mounted workspace views keep stale running snapshots.
- `vibe.local` requires the user service to bind `HOST=0.0.0.0` on `BACKEND_PORT=4311` for the external LAN nginx proxy.
- Local-only installs with no shared API base must report `LoggedIn { profile: None }` so the UI does not show remote sign-in prompts.
- If Codex rejects a stored rollout during `thread/fork`, start a fresh thread instead of failing the user prompt; stale rollout pointers are an optimization, not a hard dependency.
- Local fallback issue creation must honor a caller-supplied issue `id`; the workspace draft stores that id before workspace creation, so replacing it server-side creates orphaned workspaces with `task_id = null`.
- If a service restart or failed launch interrupts a turn after the latest safe resume anchor, the next prompt must carry that interrupted prompt text explicitly.
- `execution_processes.dropped = 1` is the preferred live quarantine mechanism for poisoned/unusable rows; do not delete process rows or coding-agent turns.
- Vibe-managed repo paths inside `container_ref` must be actual registered git worktrees. Symlinks can make `git worktree add` fail with `already exists`.
- Dropping a normalized execution-log replay stream must cancel feeder work; websocket send failures must be bounded so dead browsers cannot retain historical replay state indefinitely.

## Relevant Files / Modules

- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`
- `STATE.md`
- `crates/services/src/services/container.rs`
- `crates/server/src/routes/execution_processes.rs`
- `/home/mcp/.local/share/vibe-kanban/db.v2.sqlite`
- `/home/mcp/.local/share/vibe-kanban/codex-home/sessions`
- `/home/mcp/.codex/sessions`
- `/home/mcp/code/worktrees/915e-fr-modernize-des/hyroxready-app`
- `/home/mcp/code/worktrees/5a80-fr-orc-generativ/hyroxready-app`
- `/home/mcp/code/worktrees/96e5-fr-generative-pr/hyroxready-app`
- `/home/mcp/.config/systemd/user/vibe-kanban.service.d/fixed-ports.conf`
- `/home/mcp/.config/systemd/user/vibe-kanban.service.d/local-auth.conf`

## Current Status

- 2026-05-07 controlled deploy completed after confirming no live agents were running:
  - no running `vk-exec-*` units
  - zero active `execution_processes` rows
  - backup saved at `/home/mcp/backups/vk-pre-pr57-deploy-20260506T234920Z`
  - backend rebuilt with `cargo build --release -p server`
  - live binaries installed with SHA-256 `78f37c51ea3c392985652cdb4ae513ed2b2771a9ad16fc506cc175299ee6f93f`
  - `vibe-kanban.service` restarted once at `2026-05-07 00:04:39 UTC`
  - `https://vibe.local/` and `/api/info` return OK
  - `21MB` upload through `https://vibe.local` succeeds and the smoke artifact was deleted
  - frontend symlink points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260507Tandroid-scroll-hotfix`
- The hotfix branch now also includes the previously missing codeblock-copy reliability commit `d3fe6d53e`.
- `FR::ORC::Android Parity` long-history scroll-up fix is frontend-only:
  - upward wheel/touch input now releases conversation bottom-lock immediately
  - older-history pagination preserves the first visible row anchor after prepending rows
  - deployed without restarting VK while four other agents were running
- Confirmed on live VK before restart:
  - `vibe-kanban.service` had reached roughly `19.6 GB` RSS with dozens of `CLOSE_WAIT` sockets on `:4311`.
  - Three execution processes were running: `FR::HRV Stream`, `FR::Exploring Women's Specific Needs`, and `FR::ORC::Android Parity`.
  - A preservation backup was created at `/home/mcp/backups/vk-pre-kill-preserve-agents-20260506T173550Z`.
- Fixed in this branch:
  - execution-log websocket sends use a `5s` timeout
  - normalized historical replay streams send cancel-on-drop to their raw replay feeder task
- Deployed:
  - `/home/mcp/.local/bin/vibe-kanban-serve`
  - `/home/mcp/.local/bin/vibe-kanban-serve-prod`
  - SHA-256 `832d64203bc89e44b0e5524a4986b902bdd44fd26d4d0b2cea2f679edb33eb6a`
- Validation so far:
  - `cargo fmt --check --package services --package server`
  - `cargo check -p services -p server`
  - `cargo test -p services cancel_on_drop_stream_signals_replay_tasks`
  - live `/api/info` returned OK after restart
  - live `/` returned `200`
  - `https://vibe.local/` returned `200`
  - `ss` showed listener on `:4311` and no `CLOSE_WAIT` pile immediately after restart
- Important restart result:
  - Startup orphan cleanup marked the three active execution processes failed. Their DB rows, worktrees, Codex session ids, and pre-kill session snapshots remain available for resume/recovery, but the in-flight processes themselves did not survive.

- Confirmed:
  - the reported zero-byte rollout was `019dc72a-9fba-7961-9c36-a3f8f8a63036`
  - the reported `019dc9bd-ef72-76f2-b08e-4c83659f0369` rollout is non-empty
  - the live DB repair cleared four invalid `agent_session_id` pointers whose rollout files were empty or missing
  - a DB backup was saved at `/home/mcp/backups/vk-rollout-repair-20260426T122842Z`
  - the local service is rebuilt/restarted with the rollout guard and execution-process stream hotfix
  - `vibe.local` returns `200` through nginx after binding VK to `0.0.0.0:4311`
- Completed locally:
  - committed rollout continuity guard
  - committed execution-status stream and `vibe.local` hotfix
  - merged PR `#37` into `staging`
  - confirmed the live left-nav sign-in regression was caused by `/api/info` returning `login_status: loggedout` for a local-only install
  - added the live `VK_DISABLE_AUTH=1` systemd drop-in and verified `/api/info` returns `login_status: loggedin`
  - hardened source so local-only installs with no shared API base report `LoggedIn { profile: None }`
  - rebuilt and redeployed `/home/mcp/.local/bin/vibe-kanban-serve` with SHA-256 `8d348fb20f36bb25d0dc0737aa5ae3df6e8e8c2243003bff6ffc27f2985f6525`
  - verified `vibe.local` still returns `200` after restart
  - repaired live pointer `019dc44c-03d6-7401-a6f5-52353f438bcf` by backing up the DB to `/home/mcp/backups/vk-rollout-repair-20260426T-thread019dc44c/db.v2.sqlite` and clearing only that stale `agent_session_id`
  - added a Codex executor fallback so missing, empty, or unloadable stored rollouts start a fresh thread for both normal prompts and reviews
  - rebuilt and redeployed `/home/mcp/.local/bin/vibe-kanban-serve` with SHA-256 `4a87753855846cde85227e582c3fb0fc3fe23b297b5cd5fd74c65b802f81cc6b`
  - verified the service is active, `/api/info` is logged in with `shared_api_base: null`, and `vibe.local` returns `200`
  - traced new workspaces missing from Issues to the local fallback `/v1/issues` endpoint dropping the optimistic issue UUID generated by the frontend
  - repaired workspace `915ede80-a3ba-46fc-8665-ed8b368a0bac` by linking it to task `b6d2320a-f63c-463f-97ec-d41f4b7f9617` after backing up the DB to `/home/mcp/backups/vk-issue-workspace-link-repair-20260426T2208/db.v2.sqlite`
  - changed local issue creation to insert with the caller-provided UUID and return idempotently if the same issue already exists in the same project
  - rebuilt and redeployed `/home/mcp/.local/bin/vibe-kanban-serve` with SHA-256 `aa04de0df56aad09c6180200c332c5cfa56f30125e84462355cf2f8a76a2c733`
  - smoke-tested the live endpoint with temporary issue id `48344d12-121d-43cd-bb4f-5abde908d78c`; it appeared with that exact id, was deleted, and the DB count returned `0`
- Completed in the latest session:
  - quarantined poisoned ORC rows for Quick Add / Nutrition / PR `#844` and restored ORC to the Generative Programming PR `#732` context
  - quarantined the Modernize bad PR `#840` resume row
  - quarantined the useless T52 post-cut `resume` row while preserving the actual interrupted timer instruction
  - added interrupted-context prompt recovery for direct follow-ups, queued follow-ups, PR-description follow-ups, and review starts
  - rebuilt and redeployed `/home/mcp/.local/bin/vibe-kanban-serve` with SHA-256 `ce0a192f4216aa184a36b495d8d3d5deb76c764927b401ad123c8d6bd12b9c04`
  - opened PR `#40`: `https://github.com/artinflight/vibe-kanban/pull/40`
  - fixed the broken symlink repair by converting Modernize and Generative Vibe repo paths into real registered git worktrees
- In progress:
  - merge/promote PR `#57` so the live hotfix survives future deploys

## Risks / Regression Traps

- Trusting stale continuity docs instead of the checked-out branch and code
- Treating any non-null `agent_session_id` as resumable without checking the source process outcome
- Treating a DB-valid `agent_session_id` as forkable after Codex has already rejected the rollout
- Nulling all historical agent session IDs instead of only invalid live-state pointers
- Letting execution-process WebSocket streams treat clean closes or unrelated `finished` messages as terminal state for a mounted workspace
- Removing the fixed `HOST=0.0.0.0`, `BACKEND_PORT=4311`, and `PREVIEW_PROXY_PORT=4312` systemd drop-in will break `vibe.local`
- Removing the live `VK_DISABLE_AUTH=1` drop-in should not break local UI gates after the source hardening deploy, but keeping it is still harmless defense in depth.
- Ignoring frontend-provided issue ids in local fallback mode will orphan newly created workspaces again because the workspace create request links against the optimistic issue id.
- Symlinking a Vibe-managed repo path will break git operations when Vibe tries to create or reset a worktree at that exact path.
- Checking only `/home/mcp/.local/share/vibe-kanban/codex-home/sessions` can falsely report missing rollouts; newer sessions may live under `/home/mcp/.codex/sessions`.
- Dropping T52's interrupted prompt row `aff821d6-bf1a-413e-8af1-034114d63907` would remove the exact user instruction that needs to be recovered.

## Next Safe Steps

1. Merge/promote PR `#57` so the deployed fix is not lost.
2. If the user resumes the interrupted workspaces, use the same workspace/session context and include the interrupted prompt text from each failed row where needed.
3. If live memory climbs again, inspect execution-log websocket replay behavior first, then workspace summary query cost.
