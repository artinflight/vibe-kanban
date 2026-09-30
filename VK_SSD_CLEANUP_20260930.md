# SSD Cleanup: September 30, 2026

## Scope

The operator requested removal of old backups and no-longer-needed SSD files.
This pass targets only nine redundant extracted backup verification copies.
No deployment, restart, database restore, worktree removal, archive removal,
attachment retention change or session cleanup is authorised by this log.

Audit and exact allowlist:
`/mnt/vk-storage/vk-ssd-cleanup-20260930/`.
`audit.json` records every selected file's SHA-256, size and retained copy;
`approved.json` freezes the deletion list. `removed.json`, `before.json`,
`after.json` and `service.log` record execution and functional validation.
Removal is complete only when those execution records confirm it.

## Reviewed Paths

All paths below are relative to `/mnt/vk-storage`:

- `vk-green-refresh-20260914/release-tools-restore/release-tools`
- `vk-green-refresh-20260914/release-tools-refresh-20260914T150558Z-restore/release-tools-refresh-20260914T150558Z`
- `vk-green-refresh-20260914/release-tools-refresh-20260914T150346Z-restore/release-tools-refresh-20260914T150346Z`
- `vk-green-refresh-20260915/ready-package-20260915T005151Z-restore/ready-package-20260915T005151Z`
- `vk-blue-pr114-20260914/final-delta-rehearsal-20260914T203604Z/verified-restore/payload`
- `vk-blue-pr114-20260914/ready-package-20260914T200413Z-restore/ready-package-20260914T200413Z`
- `vk-blue-refresh-20260921/ready-package-20260923T153815Z-restore/ready-package-20260923T153815Z`
- `vk-blue-refresh-20260921/ready-package-20260921T153755Z-restore/ready-package-20260921T153755Z`
- `vk-blue-refresh-20260921/ready-package-20260923T185254Z-restore/ready-package-20260923T185254Z`

Each selected regular file matches its retained original by SHA-256. Every
symlink matches its retained counterpart. The only attachment-name matches
are copied `historical/find_attachments.py` scripts, not uploaded payloads.
The final execution rechecks contents and accessible process/unit references
before removal. Root-owned process internals are not accessible without sudo;
the relevant VK services and selected directories belong to mcp.

Seventeen other candidates were excluded because SQLite WAL/shared-memory
sidecars were not identical to the retained copy. Their purpose was not
assumed from their names. They remain untouched pending separate review.

## Preservation

Retain all archives, original backup payloads, historical recovery exceptions,
live Blue release, Green recovery software, production databases and native
session stores, worktrees, user media, shared Cargo output and attachment roots.
Parent directories receive location notes identifying the retained duplicate.
No old backup may be restored over the current production database.

Fresh Desktop SHA-256 checks matched the September 23 deployment records:

- `B:/vk-backups/vk-blue-refresh-20260921/ready-package-20260923T185254Z.tar.zst`:
  `21f879e8ce91ea15ad47a6744314a6093f41cb652268f904a366a0ccad6c6406`.
- `B:/vk-backups/vk-blue-refresh-20260921/final-boundary-20260923T185413Z.tar.zst`:
  `1cf49f2bf02402b2dc164d2f2440c3eee60498df0d41a576e525b41d02d4e33f`.

These checks verify those two remote archives, not every historical backup.
The deletion safety proof is the exact local retained-copy comparison.

## Validation

Before cleanup: SSD mounted as ext4 on `/dev/sdb1`, approximately 103 GiB free.
Blue PID 764264 and CodexUsage PID 2545246 are active. Green recovery is inactive.
All five protected attachment directory roots belong to mcp:mcp with mode 755.

`pnpm run ops:check` passed. `pnpm run format` passed Rust formatting, then failed
because this worktree lacks Prettier. No dependencies were installed just for
this cleanup, and no application source changed. The broad disk inventory
could not read ext4 `lost+found`; that protected directory is outside the scope.

All nine reviewed copies were removed: 6,139,359,232 allocated file bytes
(5.72 GiB), with directory overhead additional. Final `df` shows 109 GiB free
on the SSD (77% used), compared with approximately 103 GiB before this task.
Other processes were active, so the filesystem-wide difference is not an
exact isolated measurement of this cleanup.

Blue and CodexUsage retained their original PIDs and active states. Green
remained inactive. All five protected directory owners and modes are unchanged.
Live health returned success. A real attachment upload and byte-identical
download passed through `https://vibe.local`; the retained test artifact ID is
`94ffa685-870c-47a9-84a9-e79ccc11a3c1`. The Blue unit journal contained no entries
during the deletion/validation window. This is not a claim to have tested
every VK feature or historical recovery exception.

No broader cleanup was performed. In particular, runtime replicas, shared
build storage, user media, and the seventeen differing database extraction
copies remain. Any future cleanup needs its own consumer and recovery checks.
