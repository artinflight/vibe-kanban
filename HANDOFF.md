# HANDOFF.md

## Pickup Note

- Branch: `vk/576e-vk-attachment-er`
- Worktree:
  `/home/mcp/code/worktrees/576e-vk-attachment-er/_vibe_kanban_repo`
- Current focus: local VK attachment upload failure.
- Live deploy/restart status: none performed in this branch session.

## What Changed This Session

- Investigated the reported upload error:
  `Failed to upload Screenshot_20260709_143531_Chrome.jpg`.
- Live logs showed `POST /api/workspaces/.../attachments/upload` failed with
  `FileError(Io(NotFound))`, exposed to the client as
  `Failed to process file. Please try again.`
- Confirmed the live release cache path
  `/home/mcp/.cache/utils/attachments` was missing.
- Recreated that live cache directory with `mkdir -p` so the currently running
  service can retry uploads without a restart.
- Updated `crates/services/src/services/file.rs`:
  - cached attachment writes now create the parent directory immediately before
    writing the uploaded bytes
  - added a focused unit test for recreating a missing attachment cache parent
- Investigated a later local-only Kanban upload failure:
  `Failed to upload Screenshot_20260816_052528_Chrome.jpg: Failed to init attachment upload (405 )`.
- Found that Kanban issue/comment attachments were still using the remote
  `/v1/attachments/init` Azure upload flow in local-only mode, where the local
  `/v1` compatibility router has no POST attachment-init route.
- Updated `packages/web-core/src/shared/lib/remoteApi.ts`:
  - `setRemoteApiBase(null)` now clears the build-time shared API base instead
    of falling back to it.
  - local `attachment://...` file/thumbnail URLs resolve to
    `/api/attachments/{id}/file`.
  - remote attachment commit calls no-op in local mode.
  - abandoned local attachments delete through `/api/attachments/{id}`.
- Updated `packages/web-core/src/shared/hooks/useAzureAttachments.ts`:
  - when no remote API base is configured, uploads go directly to local
    `/api/attachments/upload`
  - temporary pending markdown is replaced with `attachment://{local_id}`

## Validation

- `cargo fmt --all --check`
- `cargo fmt --all --manifest-path crates/remote/Cargo.toml --check`
- `git diff --check`
- `pnpm i --frozen-lockfile`
- `pnpm run format`
- `pnpm run local-web:legacy-path-guard`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run web-core:check`
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run local-web:check`

## Validation Gaps / Failures

- `cargo test -p services cached_file_write_recreates_missing_parent_dir`
- Parallel default-heap `web-core:check` and `local-web:check` runs OOMed at
  Node's heap limit; sequential larger-heap checks passed.
- No live service restart or deployment was performed.
- No browser upload retry was performed from the UI after the source fix.

## Operational Notes

- Disk was later freed; `df -h /` showed about `27G` free.
- Earlier live logs also contained repeated `No space left on device` errors
  from execution log appends.

## Next Safe Steps

1. Validate a real attachment upload in the local VK UI after deploying the
   frontend/backend update.
2. Deploy/restart only through the normal VK deployment workflow after source
   validation passes.
