# STREAM.md

## Stream Identifier

- Branch: `vk/576e-vk-attachment-er`
- Repo:
  `/home/mcp/code/worktrees/576e-vk-attachment-er/_vibe_kanban_repo`
- Base: local `staging`
- Working mode: VK local attachment upload error fix

## Objective

- Investigate and fix local VK attachment upload failures that returned:
  `Failed to process file. Please try again.`
- Investigate and fix local-only Kanban issue/comment attachment uploads that
  returned: `Failed to init attachment upload (405 )`.

## In Scope

- Local attachment storage and workspace attachment upload behavior.
- Local-only Kanban issue/comment attachment upload behavior.
- Focused validation for the attachment cache write path.
- Minimal live-state repair for the missing local attachment cache directory.

## Out of Scope

- Broad disk cleanup under `/home/mcp`.
- Deploying or restarting the live `vibe-kanban.service`.
- Remote/cloud backend attachment upload paths.

## Current Status

- Live logs showed the failed upload endpoint returned `FileError` from
  `std::io::ErrorKind::NotFound` (`os error 2`) for:
  - workspace `1e8249f8-1fad-4f75-a30b-e7917179e82c`
  - session `3bd13739-a3df-4989-a444-068cce68f70d`
- The release attachment cache directory
  `/home/mcp/.cache/utils/attachments` was missing while the service was
  still running.
- Source fix added:
  - `FileService::store_file` now writes cached files through a helper that
    recreates the parent cache directory before `fs::write`.
  - A focused unit test covers writing a cached attachment when the parent
    directory is missing.
- Live-state repair performed:
  - recreated `/home/mcp/.cache/utils/attachments` with `mkdir -p`.
- Root filesystem remains critically low on space, so large uploads may still
  fail with `No space left on device` until disk usage is reduced.
- A later retry after freeing disk failed with
  `Failed to init attachment upload (405 )`.
- That came from the Kanban issue/comment attachment hook using the remote
  `/v1/attachments/init` Azure upload flow in local-only mode.
- Source fix added:
  - `setRemoteApiBase(null)` now actually clears the build-time shared API base
    for local-only mode.
  - `useAzureAttachments` falls back to local `/api/attachments/upload` when no
    remote API base is configured.
  - local `attachment://...` rendering resolves through
    `/api/attachments/{id}/file`.
  - remote attachment commit calls no-op locally, and abandoned local
    attachments delete through the local attachment API.

## Validation

- `cargo fmt --all --check`
- `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
- `git diff --check`
- `pnpm i --frozen-lockfile`
- `pnpm run format`
- `pnpm run local-web:legacy-path-guard`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run web-core:check`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run local-web:check`
- `cargo test -p services cached_file_write_recreates_missing_parent_dir`

## Validation Notes

- Parallel default-heap `web-core:check` and `local-web:check` runs both OOMed
  at Node's heap limit. Sequential checks with a larger heap passed.

## Next Safe Steps

1. Validate a real Kanban issue/comment attachment upload in the local UI after
   deploying the frontend/backend update.
2. Deploy/restart only through the normal VK deployment workflow after
   validation passes.
