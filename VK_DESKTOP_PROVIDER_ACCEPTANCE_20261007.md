# Desktop B Sole Archive Provider: October 7 Acceptance

## Approved Retirement Completed

The later specific user approval is fulfilled: exactly27 listed local archive
copies are removed after fresh hashes/chains/package checks, reclaiming64.427711GiB.
Read VK_ARCHIVE_RETIREMENT_20261007.md for exact approval, receipts,76.172085GiB
post-operation free space and successful real B-only reader validation. All B
copies, directories and local recovery metadata remain. The pending-approval and
zero-reclaim figures below are the preserved earlier acceptance boundary, not
current state. This cleanup is not a production deployment or rehearsal pass.

## Outcome And Boundaries

Implemented, tested and packaged; retirement awaits specific approval. Desktop B
is the sole retained archive provider, not a second optional copy. No production
service, routing, Recommend setting, pending overnight release or protected archive
was changed. No older database was restored over production. Historical journal
and later-unbacked-edit exceptions remain unchanged.

Operational code is committed and pushed in draft PR149 at
`312ac0b20d3d626a4ac1afaf473e6a8325191671` on
`fix/vk-desktop-backed-recovery`. It includes the PR142 backup hardening. This is
not application promotion or a merge. Future preparation must use that verified
pin or a validated descendant through its package installer; do not replay an
old consumed controller or alter a historical sealed package.

## Correctness And Validation

- 192 deployment regressions pass, including eight hardlink cases and five
  bounded-recovery safety cases. Regular and SQLite overwrites detach only the
  overwritten private hardlink name; untouched aliases retain their contents.
- Ops governance and diff checks pass. Required formatting was attempted: owner
  Rust formatting passes, then missing frontend Prettier blocks completion. The
  sparse operational checkout lacks a Cargo member. No full application checks,
  paid-provider tests or new CI workflow runs were initiated for these Python ops.
- The defect was reproduced privately. All27 authenticated real member inventories
  contain zero hardlink entries; this does not establish actual user-data loss.
- Every one of27 B archives passed fresh complete SHA256/size verification using
  exact recorded locators. Six chain graphs and their descriptors verify. Earlier
  matching per-archive member/SQLite integrity audits remain applicable.
- Actual packaged capture with its parent only at B, interrupted-publication
  resume, default restore, rehearsal Desktop reader and CLI audit pass. The tiny
  fixture archives were retained but absent at advertised local paths. Missing or
  corrupt B data fails closed rather than silently using a local duplicate.
- Actual next-preparation template installation verifies47 bound files. The
  portable recovery package verifies70 files, including27 descriptors and6 heads.
- Bounded real-reader recovery streamed and authenticated the complete latest
  four-archive chain, restoring all67 required databases and32 selected files
  across settings, session history, attachments and workspace data. Final hashes
  pass. Duration382.720s; sampled stage peak4.597GiB; sampled minimum free13.276GiB,
  above the2GiB floor. Sampling was once per second, not an absolute peak bound.
- Unselected non-database files were authenticated in complete archive streams,
  not materialized. This is provider acceptance, not a full current-data deployment
  rehearsal. Old full-extraction/fresh-checkpoint capacity estimates still apply
  to those separate operations, not to mandatory local archive retention.

Receipt root: `/mnt/vk-storage/vk-desktop-provider-20261007/`.
Key files: `regression-provider-result.json`, `desktop-provider-progress.json`,
`staged-provider-acceptance.json`, `packaged-consumer-acceptance.json`,
`installer-acceptance.json`, `next-preparation-tools.json`.
Prior full archive audit:
`/mnt/vk-storage/vk-desktop-backup-20261007/real-chain-audit-3/chain-audit.json`.
The18 explicit acceptance/approval records plus their file manifest are also
retained in
`desktop:B:/vk-backups/vk-desktop-provider-20261007/desktop-provider-acceptance-20261007.tar.gz`:
SHA256 `52336ca3ff9ebc8f819090cbc90c0f550d7944da22d86dc9faa0b0213e0ecf66`,
3,717,262 bytes, fully remote-verified in `acceptance-evidence-desktop.json`.

## Retained Recovery And Next Consumer

Local operational source: `/mnt/vk-storage/vk-desktop-backup-20261007/source`.
Package: `/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-312ac0b20`.
Retained tool bundle:
`desktop:B:/vk-backups/vk-desktop-provider-20261007/desktop-provider-recovery-312ac0b20.tar.gz`.
Full SHA256: `2fc9c7ec66158fc827069e807bbd3fdbc79d10830ab8eef49602224ab1cda138`.
Size4,783,521 bytes; remote verification is in `portable-package-desktop.json`.
The installed tool/descriptor package resolves exact historical B locators,
including October5 deltas under the scope-release directory. Never infer them
from local directory names. Latest-data process rollback is independent of old
archive paths; retain its production inputs. Old sealed packages remain evidence,
not approved future preparation entrypoints. PR149 still requires integration;
the tested explicit source pin is the current adoption path.

## Specific Retirement Decision

Approval requested for exactly27 redundant local `.tar.zst` copies in
`retirement-approval-manifest.json`, with readable `retirement-approval-files.csv`.
Manifest SHA256:
`e3c9b6909c65365254e08db1d8193f8eee4aaa1f2b408b60a30bb580e0cc62b8`.
The request and manifest are evidence/approval inputs, not executable deletion
authority. Preserve all B copies, directories, descriptors, manifests, source,
workspaces and unique recovery evidence. Before approved unlink, refresh exact
integrity/use/dependency checks and write the recorded location/checksum notes.
Visible exact-file process checks found no opens; namespace-access warnings are
retained and are not universal privileged-process clearance. Skip uncertainty;
never bypass denied information or permissions.

Actual archive bytes reclaimed:0. Proposed allocated reclaim:69,178,728,448 bytes
(64.428GiB). At manifest capture, SSD free15.571GiB; conditional post-retirement
free79.998GiB. These are measurements/projections, not a capacity guarantee.
No further storage purchase or simultaneous full-tree restore is required merely
to approve B as the retained provider. Fresh overnight capture/rehearsal capacity,
readiness and explicit production rollout approval remain separate requirements.
