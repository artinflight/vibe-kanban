# STREAM.md

## Stream Identifier

- Branch: `hotfix/recurring-vk-stall-20260505`
- Repo: `/tmp/vk-hotfix-recurring-stall-20260505`
- Base: `fork/main`
- Working mode: production hotfix for recurring live VK stalls

## Objective

- Stop the recurring live VK stall pattern where bad diff streams reconnect indefinitely and VK-owned git commands can wait forever under service cgroup memory pressure.

## In Scope

- Keep workspace diff websockets open with `Ready` when all repo diff streams are skipped, so the frontend does not reconnect into the same failing base-commit lookup loop.
- Add a bounded timeout to centralized Git CLI calls used by VK-owned worktree/status/diff operations.
- Preserve live VK8 state; do not restart the service during investigation.

## Out of Scope

- Restarting or redeploying VK8 without operator approval.
- Quarantining, deleting, or force-stopping live workspaces without explicit confirmation.
- Broad worktree-manager redesign beyond bounded Git CLI behavior.

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

## Relevant Files / Modules

- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`
- `STATE.md`
- `crates/db/src/models/coding_agent_turn.rs`
- `crates/services/src/services/events/streams.rs`
- `crates/local-deployment/src/lib.rs`
- `crates/executors/src/executors/codex.rs`
- `crates/executors/src/executors/codex/review.rs`
- `crates/db/src/models/task.rs`
- `crates/server/src/routes/local_compat.rs`
- `crates/server/src/routes/sessions/mod.rs`
- `crates/server/src/routes/sessions/review.rs`
- `crates/server/src/routes/workspaces/pr.rs`
- `crates/local-deployment/src/container.rs`
- `packages/web-core/src/shared/hooks/useJsonPatchWsStream.ts`
- `packages/web-core/src/shared/hooks/useExecutionProcesses.ts`
- `packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts`
- `/home/mcp/.local/share/vibe-kanban/db.v2.sqlite`
- `/home/mcp/.local/share/vibe-kanban/codex-home/sessions`
- `/home/mcp/.codex/sessions`
- `/home/mcp/code/worktrees/915e-fr-modernize-des/hyroxready-app`
- `/home/mcp/code/worktrees/5a80-fr-orc-generativ/hyroxready-app`
- `/home/mcp/code/worktrees/96e5-fr-generative-pr/hyroxready-app`
- `/home/mcp/.config/systemd/user/vibe-kanban.service.d/fixed-ports.conf`
- `/home/mcp/.config/systemd/user/vibe-kanban.service.d/local-auth.conf`

## Current Status

- Confirmed on live VK8 without restart:
  - `vibe-kanban.service` is active at PID `3441151`.
  - The service cgroup is above `MemoryHigh=18G` at roughly `20G`.
  - No `vk-exec-*` transient agent units are active and the DB has no running execution processes.
  - Three VK-owned `git worktree add` processes for `hyroxready-app` are waiting on `git reset --hard --no-recurse-submodules` children throttled in `mem_cgroup_handle_over_high`.
  - Repeated `FoxtrotLima` diff-stream logs show `failed to get base commit: no merge base found`, indicating a websocket reconnect/error loop against an invalid branch/base state.
- Fixed in this branch:
  - `LocalContainerService::stream_diff` now returns a `Ready` idle stream instead of closing immediately when every repo diff stream is skipped.
  - `GitCli` now applies `VK_GIT_CLI_TIMEOUT_SECS` with a `120s` default to centralized Git CLI calls.
- Validation so far:
  - `cargo fmt`
  - `cargo check -p git -p local-deployment`

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
  - promote PR `#40` into `staging` so the interrupted-context hotfix survives normal deploys

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

1. Monitor and merge PR `#40` into `staging` when acceptable.
2. If live context breaks again, verify latest non-dropped anchors against both Codex session roots and quarantine only specific poisoned rows.
3. If live git operations fail with `Invalid repository` or `already exists`, inspect for symlinks/stale directories before changing DB state.
