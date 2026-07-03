# HANDOFF.md

## Current Preview Status — 2026-07-03

- Branch: `vk/a5ed-vk-saved-message`
- Worktree:
  `/home/mcp/code/worktrees/a5ed-vk-saved-message/_vibe_kanban_repo`
- Preview status: local origin is running, but the operator-facing `.local`
  HTTPS route is blocked.
- Command used: `scripts/preview.sh start`
- Working directory:
  `/home/mcp/code/worktrees/a5ed-vk-saved-message/_vibe_kanban_repo`
- Port: `3025`
- Local URL: `http://127.0.0.1:3025/`
- `.local` HTTPS URL intended for operator access:
  `https://vibe-kanban.local/`
- Service name: `vk-preview-vibe-kanban`
- Logs command: `journalctl --user -u vk-preview-vibe-kanban`
- Stop command: `scripts/preview.sh stop`
- DNS/proxy route owner: homelab host `10.0.0.97`; Docker `nginx`
  container config under
  `/home/homelab1/docker/network/nginx/config/conf.d`; Pi-hole DNS under
  `/home/homelab1/docker/network/pihole`.
- Access limits: SSH user `mcp@homelab` can inspect the homelab route, but
  cannot write nginx config, SSL certs, or Pi-hole config without sudo. The
  current `https://vibe-kanban.local/` route resolves through `10.0.0.97` to
  the homelab homepage, not this preview.
- Validation commands and results:
  - `scripts/preview.sh start` passed and started
    `vk-preview-vibe-kanban`.
  - `curl --silent --fail --max-time 5 http://127.0.0.1:3025/ | rg -q
    'Vibe Kanban'` passed via `scripts/preview.sh verify`.
  - `curl -k -I --resolve vibe-kanban.local:443:10.0.0.97
    https://vibe-kanban.local/` returned HTTP `200`, but from the homelab
    homepage.
  - `curl -k --resolve vibe-kanban.local:443:10.0.0.97
    https://vibe-kanban.local/ | rg 'Vibe Kanban'` failed, proving the
    operator-facing route is not wired to this preview.
- Required route work:
  - Add DNS/Pi-hole entry for `vibe-kanban.local -> 10.0.0.97`.
  - Add homelab nginx HTTPS `server_name vibe-kanban.local`, certificate/key,
    and proxy to `http://10.0.0.129:3010`.
  - Add MCP local host-router route for `vibe-kanban.local` to
    `127.0.0.1:3025`.

## Pickup Note

- Branch: `staging`
- Worktree:
  `/home/mcp/code/worktrees/a6c2-vk-multi-line-in/_vibe_kanban_repo`
- Current focus: staging integration of completed VK feature/fix branches.
- Live deploy/restart status: none performed from this worktree.

## What Is True Right Now

- Local `staging` was clean before merging `fork/staging`.
- `fork/staging` contributed the workspace chat replay stability fix:
  - `packages/web-core/src/shared/lib/streamJsonPatchEntries.ts`
  - `packages/web-core/src/shared/lib/streamJsonPatchEntries.test.ts`
- Local `staging` already contained:
  - multiline paste preservation in workspace creation
  - archive-to-Done linked workspace cleanup
  - ntfy agent turn-completion notification work
- The current operator request is to rebase and merge
  `vk/a5ed-vk-saved-message` into `staging`.

## Validation Known From Landed Streams

- Ntfy turn-completion stream:
  - `cargo fmt --all --check`
  - `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
  - `pnpm install --offline --frozen-lockfile`
  - `cargo test -p services notification::tests`
  - `pnpm run format`
- Chat replay stream:
  - `pnpm install --offline --frozen-lockfile`
  - `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
  - `pnpm run format`
- Saved messages stream:
  - `pnpm run format`
  - `pnpm --filter @vibe/ui run format`
  - `pnpm --filter @vibe/ui run format:check`
  - `pnpm --filter @vibe/ui run check`
  - `NODE_OPTIONS=--max-old-space-size=4096 pnpm --filter @vibe/web-core run check`
  - `scripts/preview.sh verify`

## Validation Gaps / Failures

- No live production deploy or restart has been performed from this staging
  worktree.
- The chat replay Vitest command could not run because `vitest` is not a
  project dependency.

## Next Safe Steps

1. Finish the `fork/staging` merge.
2. Rebase `vk/a5ed-vk-saved-message` onto local `staging`.
3. Merge `vk/a5ed-vk-saved-message` into local `staging`.
4. Run final formatting and focused checks for the staging result.
