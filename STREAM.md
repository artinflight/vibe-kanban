# STREAM.md

## Stream Identifier

- Branch: `vk/3c0b-vk-production-pr`
- Repo: `/home/mcp/code/worktrees/3c0b-vk-production-pr/_vibe_kanban_repo`
- Base: `fork/staging`
- Working mode: production-protection guardrails

## Objective

- Add durable repo guardrails so workspace agents do not restart, replace,
  configure, or test against the live production Vibe Kanban service unless the
  operator explicitly approves the exact command first.

## In Scope

- Stable agent instructions in `AGENTS.md`
- Operator docs for production protection and release safety
- Lightweight preview guidance for safe workspace validation
- `ops:check` assertions that keep the protection language present
- Branch continuity notes for this stream

## Out of Scope

- Restarting or inspecting `vibe-kanban.service`
- Writing, copying, moving, chmodding, replacing, or deleting anything under `/home/mcp/.local/bin/vibe-kanban*`
- Editing `/home/mcp/.config/systemd/user/vibe-kanban.service*`
- Using `/home/mcp/.local/share/vibe-kanban` as a test target
- Starting services on ports `4311` or `4312`
- Deploying or testing binaries in live production paths

## Stream-Specific Decisions

- The live production binary is `/home/mcp/.local/bin/vibe-kanban-serve-prod`; leave it alone unless the operator explicitly approves the exact command first.
- Workspace agents should use `pnpm run preview:light`, `pnpm run preview:light:run`, or isolated workspace-local dev servers.
- Backend validation that needs live ports `4311` or `4312` requires an operator check before binding those ports.
- Historical continuity can mention past live repairs, but current instructions must make the new production boundary unambiguous.

## Relevant Files / Modules

- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`
- `STATE.md`
- `AGENTS.md`
- `README.md`
- `docs/docs.json`
- `docs/operations/release-safety.md`
- `docs/operations/production-protections.md`
- `docs/self-hosting/lightweight-agent-preview.mdx`
- `scripts/check-ops-playbook.mjs`

## Current Status

- In progress:
  - adding the production-protection guardrails and validation checks
- Not touched:
  - live service
  - live binary paths
  - live systemd unit files
  - live state directory
  - live ports `4311` and `4312`

## Risks / Regression Traps

- Historical docs include examples of production restarts and live DB/binary repairs. Current work must supersede that history with explicit protection language.
- A future agent may treat release-safety hotfix steps as permission to deploy. The updated docs must say exact command approval is required.
- Preview docs can imply port `4311` is generally safe. They must say agents cannot bind live ports without asking.

## Next Safe Steps

1. Finish docs and `ops:check` updates.
2. Run `pnpm run format`.
3. Run `pnpm run ops:check`.
4. Document that no live production command was run.
