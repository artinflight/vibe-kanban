---
title: "Production Protections"
description: "Guardrails that keep workspace agents from touching the live Vibe Kanban service"
---

# Production Protections

This fork has a live local Vibe Kanban deployment that must remain stable while
workspace agents work in isolated branches. Agent work must stay inside the
current workspace, preview, or explicitly approved test instance.

<Warning>
Workspace agents must not touch the live production Vibe Kanban service unless
the operator explicitly approves the exact command first.
</Warning>

## Hard rules for agents

- Do not restart `vibe-kanban.service`.
- Do not write, copy, move, chmod, replace, or delete anything under
  `/home/mcp/.local/bin/vibe-kanban*`.
- Do not edit `/home/mcp/.config/systemd/user/vibe-kanban.service*`.
- Do not use `/home/mcp/.local/share/vibe-kanban` as a test target.
- Do not deploy debug binaries into live production paths.
- Do not run commands that affect live VK unless the operator explicitly
  approves the exact command first.
- Treat `/home/mcp/.local/bin/vibe-kanban-serve-prod` as the production service
  binary and leave it alone unless the operator explicitly approves the exact
  command first.

## Safe validation targets

- Use `pnpm run preview:light` or `pnpm run preview:light:run` for routine
  frontend smoke tests.
- Use workspace-local dev servers for implementation work.
- Use an isolated test instance for backend restart, deployment, database,
  service-manager, or stateful runtime testing.
- Ask before starting anything that binds live ports `4311` or `4312`.

## Production work

Production commands are human-approved operations, not default agent actions.
If production must be inspected or changed, stop and ask for the exact command
approval before running it. Approval for a general goal does not imply approval
to restart the service, replace binaries, edit unit files, or use live state as
a test target.
