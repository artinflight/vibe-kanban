# HANDOFF.md

## What Changed This Session

- Added production-protection rules to `AGENTS.md`.
- Added `docs/operations/production-protections.md`.
- Tightened `docs/operations/release-safety.md` so production hotfix planning does not imply permission to execute live commands.
- Updated `docs/self-hosting/lightweight-agent-preview.mdx` to steer agents toward isolated preview and away from live restarts, live state, and live port binding.
- Linked the new guardrail doc from `README.md` and `docs/docs.json`.
- Extended `pnpm run ops:check` so required production-protection language must remain present.
- Did not touch the live service, production binary paths, systemd unit files, live state directory, or live ports.

## What Is True Right Now

- The checked-out branch in this worktree is `vk/3c0b-vk-production-pr`.
- The repo now states that workspace agents must not touch the live production VK service unless the operator explicitly approves the exact command first.
- The production service binary is documented as `/home/mcp/.local/bin/vibe-kanban-serve-prod`; agents must leave it alone without exact command approval.
- Safe validation should use `pnpm run preview:light`, `pnpm run preview:light:run`, workspace-local dev servers, or isolated test instances.
- Starting anything that binds live ports `4311` or `4312` requires asking the operator first.

## Known Good Validation

- `pnpm run format`
- `pnpm run ops:check`

## What The Next Agent Should Do

- Preserve the exact-command approval rule for live VK operations.
- Keep production-protection language in `AGENTS.md`, `docs/operations/release-safety.md`, and `docs/operations/production-protections.md`.
- Keep preview guidance explicit that agents must not restart the live backend or bind live ports without asking.
- If stronger enforcement is needed later, add shell-level wrappers outside this repo; this branch only adds repo-visible guardrails and an ops check.

## What The Next Agent Must Not Do

- Do not restart `vibe-kanban.service`.
- Do not write, copy, move, chmod, replace, or delete anything under `/home/mcp/.local/bin/vibe-kanban*`.
- Do not edit `/home/mcp/.config/systemd/user/vibe-kanban.service*`.
- Do not use `/home/mcp/.local/share/vibe-kanban` as a test target.
- Do not deploy debug binaries into live production paths.
- Do not run commands that affect live VK unless the operator explicitly approves the exact command first.
- Do not start anything that binds ports `4311` or `4312` without asking first.

## Verification Required Before Further Changes

- `pnpm run format`
- `pnpm run ops:check`

## Verification Status From This Session

- `pnpm run format` passed after `pnpm install` restored missing frontend formatter dependencies.
- `pnpm run ops:check` passed.
- No live production command was run.

## Session Metadata

- Branch: `vk/3c0b-vk-production-pr`
- Repo: `/home/mcp/code/worktrees/3c0b-vk-production-pr/_vibe_kanban_repo`
- Focus: durable production-protection guardrails for workspace agents
