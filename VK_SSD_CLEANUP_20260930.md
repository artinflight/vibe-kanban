# SSD Cleanup: September 30, 2026

## Extended Pass Complete

The operator correctly challenged the first pass as incomplete. It removed
only easy duplicates, not all deployment leftovers. The follow-up inventories
six deployment/test roots and records consumers in `extended-inventory.json`.
Do not describe this as an exhaustive host-wide cleanup.

Completed removals, measured as allocated file bytes:

| Group | Count | Bytes Removed |
| --- | ---: | ---: |
| Inactive history test copies | 4 | 54,890,143,744 |
| Database restore-test copies | 17 | 19,341,225,984 |
| Older mirrored backup archives | 5 | 15,737,974,784 |
| Obsolete prepared package copies | 7 | 4,468,252,672 |
| **Extended pass total** | **33** | **94,437,597,184** |

The extended pass freed 87.95 GiB of file allocation. Together with the first
pass, 100,576,956,416 bytes (93.67 GiB) were retired from the SSD. Final `df`
reports 196 GiB available and 57% used. Active unrelated workloads mean the
filesystem-wide free-space change is not an exact isolated measure.

All 21 new offload receipts are complete. Their Desktop archives total
27,364,382,166 compressed bytes; those and their per-file manifests were
SHA-256 verified remotely. The five old archives remain in their established
Desktop locations. Seven package archives remain both locally and on Desktop.
Temporary archive staging for completed offloads was removed.

Final live acceptance passed (`extended-live-after.json`):

- Blue764264 and CU2545246 remained active with unchanged PIDs; Green recovery
  remained inactive. No service lifecycle or routing changes occurred.
- All 12 saved-message rows matched their pre-cleanup hashes. Baseline IDs for
  40 projects, 968 tasks, 990 workspaces, 1,031 sessions and 876 attachments
  remained present.
- All 6,032 baseline native thread paths remained unchanged, and every file
  available before cleanup remained available. The baseline already had
  2,282 index entries pointing to absent files: this is not a claim to repair
  historical recovery gaps or prove all indexed conversations resumable.
- VK and native SQLite `quick_check` returned `ok`. Required attachment-root
  ownership and permissions were unchanged. Live health and attachment
  upload/download passed; retained test attachment ID:
  `d761a0fa-64fc-42d0-a3da-145e0b3e81d4`.
- The service log showed one approvals WebSocket reset warning at 13:28:12 UTC,
  but no missing-path or upload errors in the reviewed cleanup window. No
  cause is attributed to that warning by this cleanup audit.

Ops and diff checks passed. Full formatting again passed Rust formatting and
stopped at missing Prettier; application code was not changed.

The extended allowlists and receipts live in the same SSD audit directory:

- `offload-approved.json`: four inactive runtime Codex-home copies, separately
  archived by generation. Live native indexes do not reference these copies.
- `restore-offload-approved.json`: seventeen inactive database restore-test
  payloads previously excluded for differing SQLite sidecars. Preserve the
  actual contents in new archives rather than assuming the differences harmless.
- `old-archive-approved.json`: five older online-backup archives. Retire their
  SSD copies only after a fresh Desktop hash matches the local file.
- `packages-reviewed.json`: seven obsolete extracted software packages,
  checked file by file against retained local archives whose Desktop hashes
  also match. `packages-removed.json` records retirement; the latest prepared
  deployment package is excluded.

New archives and per-file manifests go to
`desktop:B:/vk-backups/ssd-cleanup-20260930/`. Archive contents are streamed and
checked against source SHA-256 values before transfer. Remote archive and
manifest hashes must match before SSD payload removal. The source inventory
and consumer checks are repeated before retirement. All directory roots remain,
with adjacent and internal location notes. A `*.offload.json` receipt with
`complete: true` is the authority for each completed offload. An incomplete
receipt needs reconciliation, not an automatic rerun.

No services are stopped or restarted. Existing loaded test environments,
production/recovery releases, original worktrees, current recovery archives
and original backup payloads remain. The live-before evidence records native
thread paths/availability, saved-message hashes and project/task/workspace/
session/attachment identities for the final functional check.

### Retained Boundaries

- Production state, session stores, attachment roots, original worktrees,
  shared Cargo storage, live Blue software and Green recovery software.
- September 11 test/warm services and their referenced readiness files;
  old loaded production generations and installed rehearsal definitions.
  This cleanup does not authorise starting, stopping or thawing them.
- The base backup chain, current final backup and original backup payloads.
- `vk-cutover-20260911/window-rehearsals` mixes fixture Git repositories and
  attachment copies. The whole root is not a safe blanket-deletion candidate.
- Feature source/evidence folders inventoried in `auxiliary-inventory.json`,
  including model-selector, goal-rendering and ownership-handover work.

The audit covers six deployment/test roots and eight related maintenance roots.
It does not classify other agents' media, projects or shared host tooling as
disposable, and it cannot inspect privileged process internals without sudo.
Remaining installed-service references and mixed repositories/attachments need
their own retirement review. No claim is made that every remaining byte is
essential or that every historical file created by this conversation is gone.

## Initial Pass Scope

The operator requested removal of old backups and no-longer-needed SSD files.
The initial pass targeted only nine redundant extracted backup verification
copies. It did not perform deployment, restart, database restore, worktree
removal, archive removal, attachment retention changes or session cleanup.
The separately reviewed extended pass is described above.

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

At the end of the initial pass, no broader cleanup had been performed. Runtime
replicas, shared build storage, user media and seventeen differing database
extraction copies remained. The extended pass above supersedes that initial
disposition for its explicitly reviewed paths only.
