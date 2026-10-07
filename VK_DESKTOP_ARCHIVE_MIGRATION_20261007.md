# October 7 Desktop Archive Migration: Recovery Tools Ready, Retirement Held

Production remains the accepted October5 release. The final overnight application
VK9b3f82538/CU95e7aea47 is not deployed. No services, settings or routing changed.
All27 original archives and directories remain; no recovery-chain parent was deleted.

## Implemented, tested and adopted

Operational source is `fix/vk-desktop-backed-recovery`, draft
[PR149](https://github.com/artinflight/vibe-kanban/pull/149), pin
`6bd0b39e546ba1f2337cac5dbf27f3b14446fe91`. It includes published PR142 hardening,
exact Desktop locators, portable legacy descriptors, closed/WAL/move guards,
fail-closed unavailable/corrupt Desktop handling, and capture/resume/restore support.
176 Python regressions pass; Ops governance and diff checks pass. Full formatting
was attempted but sparse ops source lacks Cargo members; owner checkout lacks
frontend Prettier. No unrelated application build/dependency installation occurred.

All receipts are at `/mnt/vk-storage/vk-desktop-backup-20261007/`:

- `real-chain-audit-3/chain-audit.json`: fresh complete local/Desktop hashes for
  27archives, six descriptor graphs and every SQLite snapshot's restored hash/
  integrity.69,178,571,021 compressed bytes streamed. Non-DB files were streamed,
  not installed as a complete filesystem. Valid completed earlier receipts were
  reused only after fresh full hashes and bound member inventory verification.
- `final-consumer-acceptance.json`: final packaged actual rehearsal consumer
  downloads only verified metadata, streams two fixture archives from Desktop
  with both local fixture archives absent, restores latest SQLite/attachment/
  dirty-file content, and retires only its two verified private DB duplicates.
- `final-wiring-check.json`: new package installs committed tools into copies
  of actual handover templates, binds41files and replaces the local-parent-only
  check. Historical coverage is fixture identity, not new deployment readiness.
- `next-preparation-tools-final.json`: exact source/package/installer binding.
  A future handover must install this pin into a NEW unsealed package and then
  verify current coverage/readiness; no old sealed package was rewritten.

Portable recovery package: `recovery-package-6bd0b39e5`,64hash-bound files,
27legacy descriptors and six heads. Verified retained copy:
`desktop:B:/vk-backups/vk-desktop-backup-20261007/desktop-recovery-6bd0b39e5.tar.gz`,
SHA256 `79c8bf9a19cd9d0d4c9fe5b7f7a404f5d71271dfbf453547726ba405d633c3c6`.
Use its bound `tools/vk_recovery_package.py --root PACKAGE --` entrypoint with
normal rolling-backup arguments. Direct-LAN options preserve established Desktop
host-key identity; no network/security setting changed. Original small manifests,
results, descriptors and the externally recorded package digest remain essential.

This is operational source and recovery-consumer adoption, not a production
deployment or completed full-sized private rehearsal. Do not deploy this ops
branch's application tree. PR149 remains draft, unmerged.

## Space and remaining dependency

Original allocated bytes:69,178,728,448 (64.428GiB). The21ancestor subset is
47,308,333,056bytes; six direct heads are21,870,395,392bytes. Exact locators come
from receipts, including October5 deltas stored under Desktop scope-release.
`retirement-candidates.json`/`.csv` record exact paths, checksums and current gates;
they are a conditional inventory, NOT a deletion manifest or blanket approval.

`real-chain-space-plan.json` models ordered writes/deletes and all DB assertions.
Largest low-peak historical restore:84,809,768,960bytes (78.985GiB), versus
100,742,590,464bytes normally. At sizing, free19,321,933,824bytes (17.995GiB).
Retiring only21ancestors would leave62.06GiB and cannot support that full restore.
All27 conditional retirements would leave82.423GiB, just0.437GiB beyond the
78.985GiB estimate plus2GiBfloor and1GiBgrowth reserve. Refresh before using it.
This is a conservative ordered estimate, NOT a measured full filesystem restore.

Complete fresh capture is larger:91.214GiB no-compression upper estimate before
floor/reserve. Even after all27, the conservative gap is11.791GiB; compression
has not been measured for the new complete source. A combined backup/rehearsal
peak is not yet proven. No broad cleanup, system-disk exception or weakened
recovery check is an acceptable substitute. The current journal retains44move
errors; two have unresolved original-source provenance. A new full checkpoint
must preserve these historical limitations, not fabricate a clean delta chain.

Exact-path visible open-file checks found no matching original archive references;
inaccessible namespaces were not bypassed. Refresh use/dependencies before any
approved unlink. Old consumed controllers retain historical local checks and are
not future recovery entrypoints. Latest-data production cutback uses live state,
not an archive. Overnight fallback remains the compatible v2 reader SHA256
`2494f1dc7ca2de8ed26806603b86f9fa3e466c9f19a00e4aab2c8b9712a70c97`.

## Retired and next decision

Zero of the27 original archives retired. Only six proven completed audit SQLite
duplicates were retired,481,775,616allocated bytes. A partial282,066,944byte copy
remains because verification was incomplete. These scratch savings are not the
64.428GiB durable migration outcome. All incident/current candidate evidence stays.

The next operator decision is whether to authorize a conditional migration of the
exact27 redundant local archives to their already verified Desktop locations,
with fresh use/free-space checks and retained locator breadcrumbs. That would
enable the historical full restore test but does not by itself establish fresh
backup or overnight rollout readiness. If full filesystem restore must precede
any original unlink, additional approved scratch capacity is necessary instead.
Separately measure/bound the fresh compressed capture and sequential rehearsal
before rollout approval. No archive removal or overnight switch is authorized now.
