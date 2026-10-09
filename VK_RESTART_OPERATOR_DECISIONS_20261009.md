# Restart: two exact operator decisions (read-only findings, 2026-10-09)

No production, permissions, routing, scope, backup or cleanup changed. PR230/231
remain draft/unmerged. The incumbent remains running. All original B evidence
and448/145/transcript415/journal/mode/link exceptions remain protected.

## 1. Native candidate capacity on MCP

The two-instance workflow still means incumbent plus ONE eventual replacement:
restore, rehearse, final fenced catch-up and promote that same replacement.
There is no third full rehearsal. Desktop's existing B guest can serve as an
approved isolated builder; it is not MCP's eventual production candidate.

The SSD filled again because the October7 preparation retained two new capture
sets (OP measured53.88GiB combined), plus compatibility/shared build growth.
PR229's direct-to-B correction prevents another archive/snapshot accumulating
locally; it does not reclaim these existing protected copies. The27older
archives/64.43GiB were already retired with B breadcrumbs; their current reclaim
is ZERO. Both existing disks are fully partitioned according to lsblk; no spare
native volume or candidate allocation is identified. Proposed new mountpoint
/mnt/vk-storage/vk-cutover-candidate-20261009 is absent and not a symlink.

Full historical preservation is already authenticated on B:25006383044compressed
bytes,93864377002regular-file payload bytes (87.42GiB),76SQLite snapshots,
archive735e211552c315f9f9be78eda9f28d175f2406847032f5df6a5d2307d8362ef5.
This is neither a minimum boot footprint nor a demand for two historical restores.

Read-only current DB/reference joins against the authenticated retained catalog:

| Set | Payload | Meaning |
| --- | ---: | --- |
| VK execution logs |30567346069bytes /28.47GiB|All31873backed-up log files match current execution IDs; zero unmatched files. Existing source reads logs directly, without an archive-backed runtime reader. |
| Native index-referenced rollouts |35333497230bytes /32.91GiB|13223files referenced by retained current native indexes; includes historical continuity/CU scan sources, not just a currently running thread. |
|20explicit current dependency DBs|6185500672bytes /5.76GiB|Consistent snapshot bytes, not raw live WAL size. |
|Above reference-backed preservation floor|72086343971bytes /67.14GiB|Before worktrees, Git, attachments, plugins, software and reserve. Not a proven minimum-to-boot or complete operational peak. |
|Existing46-root unreduced operational proposal, B-mapped portion|89801729231bytes /83.63GiB|82440422607file bytes plus72included DB snapshots; broad roots include unclassified material. No proposal reduction applied or approved. |

Do not call all indexed history intentionally retired or infer that it must all
be duplicated merely to boot. The current continuity requirement preserves
current feature/history access. A smaller exact operational set is NOT yet
proved: cross-root Git/hardlink/symlink closure, references outside the catalog,
relative native paths and generated-build-root policy remain to be bound. Those
are engineering checks, not permission to omit material. SharedCargo74.56GiB is
outside the old backup plan. The new capacity policy requires existing absolute
build directories, not the old contents; an empty private generated-build cache
is a possible tested policy, not an adopted exclusion or safe-reclaim clearance.

Required storage arithmetic: current B-mapped operational proposal plus existing
8GiB working floor =98391663823bytes /91.63GiB; unchanged full preservation plus
that floor =102454311594bytes /95.42GiB. Add actual directory/block overhead,
package bytes, newly discovered dependencies and retained test/final-catch-up
quarantine. These are payload lower bounds, not measured acceptance peaks.
The secondary currently has273444864bytes /0.255GiB free; root has39.62GiB.
Root alone cannot fit even the reference-backed continuity set, and bulk use
also requires a storage-policy exception. A DB-only rehearsal is insufficient.

**Concrete no-deletion decision:** approve attaching/mounting a NEW120GiB native
Linux ext4 volume at /mnt/vk-storage/vk-cutover-candidate-20261009 and assigning
UID/GID1000 to ONLY its new task root. Device identity must be provided/verified
before any mount/provision command; do not repartition/format existing sda/sdb or
Desktop's data image. This allocation would typically provide about111GiB usable
at normal ext4 reservation, leaving roughly16GiB above even the full unchanged
payload+8GiBfloor. Actual available blocks/inodes and restore/quarantine/RAM peaks
remain measured fail-closed gates;120GiB is an allocation proposal, not certified
cutover capacity. No historical scope reduction is requested to make it fit.

Conditional local reclamation options (none approved or performed):

| Exact target | Allocated reclaim | Proof and required action |
| --- | ---: | --- |
|/mnt/vk-storage/vk-runtime-backup-20261007/backups/checkpoint-/02136af9b9c24c08bccba0868864e597/checkpoint--02136af9b9c24c08bccba0868864e597.tar.zst|23449710592bytes /21.84GiB|B:/vk-backups/vk-runtime-backup-20261007/checkpoint--02136af9b9c24c08bccba0868864e597.tar.zst; receipt SHA9beef7c6ca1e533b9861f186d6654e5db0c4d7e13482bdddc70f0673b9b32e4d, existing full-stream/SQLite audit. Approve only local file retirement after required QA, refreshed local/Bhash+size/use checks, provider/consumer binding and breadcrumb. Keep descriptor, Bpayload and delta chain. |
|/mnt/vk-storage/vk-runtime-backup-20261007/backups/delta-/430d3a842f5d4216862a1703e33232b8/delta--430d3a842f5d4216862a1703e33232b8.tar.zst|319234048bytes /0.30GiB|B:/vk-backups/vk-runtime-backup-20261007/delta--430d3a842f5d4216862a1703e33232b8.tar.zst; receipt SHA4b2a3881da51148f0c66f773ac292476fab9b3a973f734f09af17e37680f0c53. Same exact file-only/provider/QA gates; checkpoint ancestry remains required. |
|/mnt/vk-storage/vk-connector-repair-20261007/cargo-target-compat|6008930304bytes /5.60GiB|Generated output; source/test receipts retained. Owner/QA release and fresh open/mapped inode+dependency clearance required; approve only this generated child, no source/evidence/sharedCargo. |
|/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst|23441530880bytes /21.83GiB|Failed-capture incident evidence; NOT an established verified duplicate. No reclaim credit until a preservation-only Btransfer/hash/audit/consumer check and exact later retirement approval. |

The two verified duplicate archive candidates together yield22.14GiB; including
compat output yields27.73GiB, still below even67.14GiB+reserve. Their QA/clearance
requirements mean they cannot be treated as already available. lsof found no
accessible exact checkpoint handle but reported protected nsfs inspection
warnings; this is not universal inactive-use proof. Do not touch sharedCargo,
incumbent/fallback, handover/incident/recovery fixtures or directories. Automatic
cleanup stays technically unavailable until Seamus's human QA.

## 2. Exact isolated builder decision

Current PR230c3c48e6324f778ccd03a5761c2314b440e9ceac3 Test37888935110passed472backend
tests,10skips and actualscanner73contracts; remote private checks still skipped.
Artifact37888935082 installed bwrap but failed mandatory namespace preflight:
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. No package uploaded.
Do not change runner security policy, retry with sudo/root or disable the sandbox.

**Minimum proposed permission decision:** explicitly approve using existing
Desktop WSL VK-Candidate-20261009 ONLY as the non-root isolated Linux builder,
and the still-unanswered ownership assignment UID/GID1000 for ONLY:

- /mnt/vk-storage/vk-safe-release-20261009/combined-source (currently0:0,0700)
- /mnt/vk-storage/vk-safe-release-20261009/isolated-validation (currently0:0,0755)

Ownership assignment is recursive only within these new generated folders,
without following symlinks. No chmod, root test invocation, backup/data-image/
quarantine ownership change, Windows ACL/security change or credential copying.
Risk: changes generated-source metadata and permits the ordinary build UID to
write these two trees. Preserve original byte hashes/patches/receipts; fail if
unexpected mounts/special files or source mismatches are found. Approval has NOT
arrived and neither action nor a new builder/sandbox test is performed.

Supported source configuration: guestUbuntu24.04/GCC13.3/Python3.12,
Rustnightly2025-12-04 with locked Cargo acceptance profile, Node24.13.1,
pnpm10.13.1 with frozen lockfile, reviewed Gitleaks8.30.1, actual
scripts/build-scheduled-goal-artifacts.py from exact c3c48e63 and its mandatory
namespace/module verification. MCP isUbuntu24.04/glibc2.39 as well. Existing
retained guest namespace probe passed in its original owning invocation; it is
NOT a UID1000 acceptance receipt or proof of the exact current preflight. After
approval run that UID1000 preflight ONCE; on denial report and hold, no root retry.

Create fresh pinned source/artifact/target/cargo/temp outputs only UNDER the
approved isolated-validation directory, e.g. build-c3c48e63/{source,target,artifacts,
cargo-home,tmp}; use existing read-only toolchain executables directly so no
ownership change of toolchain or inherited Cargo registry is necessary. Source
gets the current published Git objects through established MCP transfer without
copying credentials; preserved old source/149overlay is not overwritten.
Protect /mnt/b archives and incumbent/shares with the reviewed isolation boundary;
no writable backup or production roots, host manager access or paid/native tasks.
Dependencies/tool caches must use only the new approved builder output roots.
Verify namespace support, no .env, exact source/tree, scanner/module/controller,
source formatting and complete manifest/artifact hashes. Download/publish artifacts
through existing authorized routes only. B currently has138139041792bytes free;
the existing data container has119767830528usable bytes, but neither is MCP-native
storage. No new Linux provisioning or full rehearsal is required for this builder.

## Sequence after the decisions

Build the source-bound package; finish explicit dependency/metadata scope accounting
without omitting B-preserved history. Restore and verify the SAME native MCP candidate,
accept its actual provider/supervisor/controller/native/scanner/consent boundaries,
then safely drain sessions and hold writers. Fresh B boundary/catch-up must preserve
newer writes and reconcile test edits. Test latest-data fallback and promote only
after all deployment checks pass. PR230/231 remain unmerged until then. Human QA
keeps cleanup unavailable; no historical zero-loss/recovery-complete sign-off invented.
