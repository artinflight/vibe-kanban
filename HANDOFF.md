# HANDOFF.md

## What Changed This Session

- Investigated the recurring live VK wedge after memory reached roughly `19.6 GB` RSS with many dead sockets on `:4311`.
- Found an additional retention path: execution-log websocket sends were unbounded, and normalized historical replay feeder work did not cancel when the websocket/stream was dropped.
- Added a `5s` execution-log websocket send timeout.
- Added cancel-on-drop for normalized log replay streams so historical raw replay feeder tasks stop when the client disconnects.
- Took a preservation backup, force-killed only the wedged VK main PID after stop hung, installed the patched backend binary, and restarted VK.
- Fixed local-only issue/comment attachment upload routing so the frontend uses `/api/attachments/upload` instead of the remote `/v1/attachments/init` Azure flow when `shared_api_base` is empty.
- Built and deployed a refresh-only frontend release at `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506Tattach-local-upload-hotfix`.
- Fixed the mobile picker no-op by keeping the hidden dropzone file input mounted even when the native picker blurs the description editor.
- Built and deployed refresh-only frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506Tmobile-attachment-input-hotfix`.
- Replaced the paperclip button's dropzone `open()` path with a direct native file input path for mobile browsers.
- Built and deployed refresh-only frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506Tmobile-direct-input-hotfix`.
- Broadened the direct native input fix to issue comments, create chat, and session chat attachment buttons so no mobile attachment surface relies on programmatic `.click()`.
- Built and deployed refresh-only frontend release `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506Tmobile-all-attachment-inputs-hotfix`.
- Raised attachment size limits from `20MB` to `100MB` in source. The frontend limit is live after refresh; the backend limit requires the next safe backend restart because three VK execution units were active at verification time.

## Current Hotfix Truth

- Branch: `hotfix/bound-historical-log-replay-20260506T1715Z`
- Worktree: `/tmp/vk-hotfix-historical-replay-20260506T1715Z`
- Base: `fork/main`
- Live binary SHA-256: `832d64203bc89e44b0e5524a4986b902bdd44fd26d4d0b2cea2f679edb33eb6a`
- Backup: `/home/mcp/backups/vk-pre-kill-preserve-agents-20260506T173550Z`
- Validation: `cargo fmt --check --package services --package server`; `cargo check -p services -p server`; `cargo test -p services cancel_on_drop_stream_signals_replay_tasks`; live `/api/info`, `/`, and `https://vibe.local/` OK after restart.
- Attachment validation: `pnpm --filter @vibe/web-core run format`; `pnpm --filter @vibe/local-web run build`; `cargo check -p services -p server`; live `/api/attachments/upload` multipart smoke test returned success.
- Mobile attachment validation: `pnpm --filter @vibe/ui run format`; `pnpm --filter @vibe/local-web run build`; deployed frontend symlink and verified `https://vibe.local/` returns `200`.
- Remote crate validation note: `cargo check --manifest-path crates/remote/Cargo.toml` was blocked by private `vibe-kanban-private` git dependency authentication.
- Remaining condition: commit/push/PR promotion is still required so the deployed fix survives future deploys.
- Important restart result: startup orphan cleanup marked `FR::HRV Stream`, `FR::Exploring Women's Specific Needs`, and `FR::ORC::Android Parity` failed. Their worktrees, DB rows, Codex session ids, and pre-kill snapshots were preserved, but the in-flight turns did not survive as running processes.

## Previous Context

- Recovered live agent resume context after several agents resumed into stale, poisoned, or wrong repository state.
- Quarantined bad execution-process rows by setting `execution_processes.dropped = 1` instead of deleting chat/process history.
- Restored `FR::ORC::Generative Programming` to the correct Generative Programming context and stopped it from selecting Quick Add / Nutrition / PR `#844` turns as resume anchors.
- Quarantined the bad `FR::Modernize Design` resume row that reported PR `#840` from the wrong checkout.
- Quarantined the useless post-cut T52 `resume` row while preserving the actual interrupted T52 user instruction as later recovery context.
- Added a source hotfix so interrupted/killed/failed prompt text after the latest safe resume anchor is injected into the next direct follow-up, queued follow-up, PR-description follow-up, or review start.
- Built and deployed the hotfix binary to the live local service after confirming zero running coding-agent processes.
- Opened PR `#40` into `staging` for the resume-context hotfix.
- Repaired the live worktree breakage caused by an earlier symlink workaround: Modernize and Generative workspaces now use real registered git worktrees, not symlinks.

## What Is True Right Now

- Branch: `hotfix/bound-historical-log-replay-20260506T1715Z`
- Worktree: `/tmp/vk-hotfix-historical-replay-20260506T1715Z`
- PR: not opened yet for this hotfix.
- Latest commit: pending.
- Branch is not pushed yet.
- Live binary: `/home/mcp/.local/bin/vibe-kanban-serve`
- Live binary SHA-256: `832d64203bc89e44b0e5524a4986b902bdd44fd26d4d0b2cea2f679edb33eb6a`
- `vibe-kanban.service` is active at `0.0.0.0:4311`.
- `http://127.0.0.1:4311/api/info`, `http://127.0.0.1:4311/`, and `https://vibe.local/` return OK.
- Live frontend symlink now points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260506Tmobile-all-attachment-inputs-hotfix`.
- No `vk-exec-*` units were active immediately after restart; the three previously active rows were marked failed by VK startup cleanup.
- Later attachment verification found three active `vk-exec-*` units, so the backend was not restarted for the `100MB` limit change.

## Agent Context Repairs

- `FR::ORC::Generative Programming`
  - Correct branch/path: `codex/program-generation-v3-llm-first` at `/home/mcp/code/worktrees/5a80-fr-orc-generativ/hyroxready-app`
  - Bad rows quarantined: `8a644a33-3ad8-4fb7-99f3-17ec934f9bfa`, `753aa30a-c80f-4c4d-81d1-42c6040d927c`, plus failed launch rows `e9373f3f-6a22-4803-8cfb-e996135985c9` and `bed53320-a4fc-4ca5-ad2c-e51e29d6f105`
  - Current verified latest anchor after recovery: `287ea7c6-45d8-4c83-9a16-b7506c8e93ba`, agent session `019dcc1f-1550-7a41-93d0-2c5af37db38c`
- `FR::Modernize Design`
  - Correct branch/path: `codex/modernize-design-system` at `/home/mcp/code/worktrees/915e-fr-modernize-des/hyroxready-app`
  - Bad row quarantined: `c071aff7-5771-4102-8248-42fe32e094f2`
  - Current verified latest anchor: `8f9f86f4-24c9-4bb8-9d2c-37ce612b1746`, agent session `019dcc1d-fd71-7cb2-b06d-88f0e621ea71`
- `FR::Rebuild Timer for Metcons` / T52
  - Correct branch/path: `vk/1767-fr-rebuild-timer` at `/home/mcp/code/worktrees/1767-fr-rebuild-timer/hyroxready-app`
  - Bad row quarantined: `9e0618d8-8c5c-4ddf-8b19-f31689eab3bf`
  - Current verified latest completed anchor: `44821fb6-e809-480a-beb0-a7865986100c`, agent session `019dc9c4-f19d-7331-a844-79440eee1462`
  - Important preserved interrupted prompt row: `aff821d6-bf1a-413e-8af1-034114d63907`
- `FR::Staging Check`
  - Verified clean; no repair was needed.
  - Current verified latest anchor: `5370541a-989f-4e84-81c2-a2f2009c90c9`, agent session `019dcbd7-1c99-79d2-bf0d-e4781180ecc0`
- `FR::Android Parity`
  - Verified clean; no repair was needed.
  - Current verified latest anchor: `f2aee7de-c990-4da7-8528-b2fc7ffaba81`, agent session `019dcbd6-3ee7-7321-93ac-53c45180e3c9`

## Worktree Repairs

- Do not recreate the symlink workaround. Vibe expects the repo path inside `container_ref` to be a real git worktree.
- These paths are now real registered git worktrees and should remain that way:
  - `/home/mcp/code/worktrees/915e-fr-modernize-des/hyroxready-app` on `codex/modernize-design-system`
  - `/home/mcp/code/worktrees/5a80-fr-orc-generativ/hyroxready-app` on `codex/program-generation-v3-llm-first`
  - `/home/mcp/code/worktrees/96e5-fr-generative-pr/hyroxready-app` on `codex/program-generation-v3-llm-first`
- Mispointed directories were preserved beside the wrappers:
  - `/home/mcp/code/worktrees/915e-fr-modernize-des/hyroxready-app.mispointed-20260426T230958Z`
  - `/home/mcp/code/worktrees/5a80-fr-orc-generativ/hyroxready-app.mispointed-20260426T230958Z`

## Backups Created

- `/home/mcp/backups/vk-pre-kill-preserve-agents-20260506T173550Z`
- `/home/mcp/backups/vk-agent-context-repair-20260426T230936Z/db.v2.sqlite`
- `/home/mcp/backups/vk-orc-restore-good-anchor-20260426T231708Z/db.v2.sqlite`
- `/home/mcp/backups/vk-agent-anchor-repair-rest-20260426T232649Z/db.v2.sqlite`
- `/home/mcp/backups/vibe-kanban-serve-before-resume-context-20260426T232800Z`

## Known Good Validation

- `cargo fmt --check --package services --package server`
- `cargo check -p services -p server`
- `cargo test -p services cancel_on_drop_stream_signals_replay_tasks`
- `cargo build --release --bin server`
- deployed binary hash matched `target/release/server`
- service active after restart, `/api/info` OK, `/` OK, `https://vibe.local/` OK
- socket check showed no `CLOSE_WAIT` pile on `:4311` immediately after restart
- `pnpm --filter @vibe/local-web run build`
- live local attachment upload endpoint returned success for a multipart image
- `cargo check -p server -p local-deployment`
- `pnpm run format`
- `cargo build --release -p server`
- Live service restarted only after confirming zero running coding agents.
- Live service health returned `200`.
- Deployed binary hash matched `target/release/server`.
- Recent agent anchor scan verified each latest non-dropped anchor has a real rollout file.
- Worktree verification confirmed Modernize and both Generative paths are real git worktrees, not symlinks.

## What The Next Agent Should Do

- Commit/push/open PR for `hotfix/bound-historical-log-replay-20260506T1715Z`.
- When no VK execution units are running, rebuild/redeploy the backend if the live install must accept files larger than `20MB`; the source limit is already `100MB`.
- If mobile attachment selection still produces no upload request after a hard refresh, instrument the direct file-input `change` handler in the live frontend; the backend upload endpoint already succeeds from multipart smoke tests.
- When resuming the interrupted 2026-05-06 workspaces, use the preserved workspace/session context rather than starting unrelated fresh workspaces.
- If another agent reports lost context, first inspect that workspace session’s latest non-dropped completed anchor and verify its rollout exists under either `/home/mcp/.local/share/vibe-kanban/codex-home/sessions` or `/home/mcp/.codex/sessions`.
- If another workspace reports `Invalid repository` or `already exists`, check whether the Vibe-managed repo path is a symlink or stale directory before touching DB context.

## What The Next Agent Must Not Do

- Do not delete process/chat history to repair context.
- Do not mark broad sets of execution rows dropped; only quarantine known poisoned or useless rows.
- Do not use symlinks for Vibe-managed repo paths under `container_ref`.
- Do not restart `vibe-kanban.service` while any coding-agent process is running.
- Do not assume missing rollouts only live under the Vibe-specific Codex home; also check `/home/mcp/.codex/sessions`.

## Session Metadata

- Date: 2026-05-06 UTC
- Focus: live VK execution-log replay retention hotfix and restart with preservation backup
