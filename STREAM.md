# STREAM.md

## Stream Identifier

- Branch: `vk/a306-vk-sub-agents`
- Worktree: `/home/mcp/code/worktrees/a306-vk-sub-agents/_vibe_kanban_repo`
- Base: current `fork/staging` at `8c82e47ea` (verified 2026-09-10).
  `origin` is upstream BloopAI; `fork` is this fork's integration remote.

## Objective

Let workspace agents close stale Codex sub-agents so they can stop waiting for
those children and finish their turns.

## In Scope

- `list_subagents` and `close_subagent` in global and orchestrator VK MCP modes.
- Enforce workspace context and session membership; reject parent thread IDs.
- Close the selected child through its owning live Codex app-server using
  `thread/archive`, which removes the loaded thread and requests shutdown while
  retaining the transcript. Nested children are closed individually.
- Persist terminal tracking only after acknowledgement; preserve error and
  timeout uncertainty instead of reporting a stopped child.
- Ignore child turn notifications when updating/completing the parent execution.
- Focused runtime, MCP, and tracking regression coverage and usage documentation.

## Boundaries and Deployment

- No live services, Codex state, attachments, or worktrees are mutated by this
  implementation task. No frontend change or database migration is required.
- Activation requires a matching backend and VK MCP binary. A frontend preview
  cannot exercise this feature.
- The owning runtime must be connected; this is not an OS-process kill tool.
  Already archived children can return an archive error. A timeout is uncertain.
- Follow `VK_AGENT_DEPLOYMENT_RUNBOOK.md` before a coordinated green deployment;
  verify a disposable child's closure and the parent's final completion live.

## Validation

- Passed `cargo test -p executors --lib executors::codex::client::tests`
  (5 tests), `cargo test -p db -p mcp --lib` (12 DB + 11 MCP tests), and
  `cargo check -p server -p mcp`.
- Cargo commands used `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target`,
  `CARGO_INCREMENTAL=0`, and `SQLX_OFFLINE=true`.
- Passed `pnpm run format`, `pnpm run ops:check`, and `git diff --check`.
  Formatting initially lacked Prettier in this worktree; the successful run
  used the canonical checkout's matching Prettier 3.6.1 via
  `PATH=/home/mcp/_vibe_kanban_repo/packages/web-core/node_modules/.bin:$PATH`.
- Coverage includes the owning-runtime archive RPC (mock app-server), parent
  rejection, unavailable runtime, child/malformed notification isolation,
  terminal tracking versus late events, and workspace-scoped MCP HTTP calls.
- Logs: `/mnt/vk-storage/agent-checkpoints/a306-{executor-tests,db-mcp-tests,check,format}.log`.
- Not exercised: real Codex child shutdown, live green rollout, full workspace
  tests/lint, or frontend checks. Run the required full PR baseline and a
  controlled local runtime smoke test before promotion into `staging`.
