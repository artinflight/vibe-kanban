# Restart: exact operator decisions (read-only findings, 2026-10-09)

Latest authority: Seamus approved both actions at08:40UTC. Bounded retirement
and B builder ownership/nonroot namespace gates are complete. Actual free99.24GiB
was measured; SAME MCP candidate root is prepared. Existing SSH/B returned
at09:38:29UTC. B-only archive readback passed; fresh isolated buildv7 is running.
General cleanup stays off. See the final section and approved-restart receipt.

Current capacity recommendation after shared-cache inspection: assess the bounded
no-purchase retirement option on the existing MCP secondary ext4 first. The
final source/provenance-conservative manifest could reclaim71.63GiB; with the
previous27.73GiB candidates, approximately99.58GiB native room is possible.
This remains held on QA/owner release, exact approval, protected-consumer clearance
and a held compiler-write boundary. No120GiB spare device exists. The earlier
new-device proposal below is retained as history and superseded by the appended
shared Cargo/native capacity findings; no immediate hardware purchase is justified.

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

| Set                                                              |                    Payload | Meaning                                                                                                                                                       |
| ---------------------------------------------------------------- | -------------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VK execution logs                                                | 30567346069bytes /28.47GiB | All31873backed-up log files match current execution IDs; zero unmatched files. Existing source reads logs directly, without an archive-backed runtime reader. |
| Native index-referenced rollouts                                 | 35333497230bytes /32.91GiB | 13223files referenced by retained current native indexes; includes historical continuity/CU scan sources, not just a currently running thread.                |
| 20explicit current dependency DBs                                |   6185500672bytes /5.76GiB | Consistent snapshot bytes, not raw live WAL size.                                                                                                             |
| Above reference-backed preservation floor                        | 72086343971bytes /67.14GiB | Before worktrees, Git, attachments, plugins, software and reserve. Not a proven minimum-to-boot or complete operational peak.                                 |
| Existing46-root unreduced operational proposal, B-mapped portion | 89801729231bytes /83.63GiB | 82440422607file bytes plus72included DB snapshots; broad roots include unclassified material. No proposal reduction applied or approved.                      |

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

| Exact target                                                                                                                                               |          Allocated reclaim | Proof and required action                                                                                                                                                                                                                                                                                                                                                                        |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| /mnt/vk-storage/vk-runtime-backup-20261007/backups/checkpoint-/02136af9b9c24c08bccba0868864e597/checkpoint--02136af9b9c24c08bccba0868864e597.tar.zst       | 23449710592bytes /21.84GiB | B:/vk-backups/vk-runtime-backup-20261007/checkpoint--02136af9b9c24c08bccba0868864e597.tar.zst; receipt SHA9beef7c6ca1e533b9861f186d6654e5db0c4d7e13482bdddc70f0673b9b32e4d, existing full-stream/SQLite audit. Approve only local file retirement after required QA, refreshed local/Bhash+size/use checks, provider/consumer binding and breadcrumb. Keep descriptor, Bpayload and delta chain. |
| /mnt/vk-storage/vk-runtime-backup-20261007/backups/delta-/430d3a842f5d4216862a1703e33232b8/delta--430d3a842f5d4216862a1703e33232b8.tar.zst                 |    319234048bytes /0.30GiB | B:/vk-backups/vk-runtime-backup-20261007/delta--430d3a842f5d4216862a1703e33232b8.tar.zst; receipt SHA4b2a3881da51148f0c66f773ac292476fab9b3a973f734f09af17e37680f0c53. Same exact file-only/provider/QA gates; checkpoint ancestry remains required.                                                                                                                                             |
| /mnt/vk-storage/vk-connector-repair-20261007/cargo-target-compat                                                                                           |   6008930304bytes /5.60GiB | Generated output; source/test receipts retained. Owner/QA release and fresh open/mapped inode+dependency clearance required; approve only this generated child, no source/evidence/sharedCargo.                                                                                                                                                                                                  |
| /mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst | 23441530880bytes /21.83GiB | Failed-capture incident evidence; NOT an established verified duplicate. No reclaim credit until a preservation-only Btransfer/hash/audit/consumer check and exact later retirement approval.                                                                                                                                                                                                    |

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

## Shared Cargo/native capacity question closed read-only

The previous120GiB new-device proposal was premature. No such device is currently
available: only root/boot/secondary ext4 filesystems are native. Sysfs partition
ranges leave gross2,449,408bytes on sda and1,049,088bytes on sdb, including tables/
alignment. Root LV already spans its sda3 PV apart from at most3,145,728bytes of
metadata/free difference. Raw root-owned block devices were not opened and no
privileged access was attempted. A120GiB volume would require a new attachment;
there is no immediately provisionable existing unallocated volume. Filesystem
reserved blocks are not ordinary available capacity or an approved reclaim path.

Shared /mnt/vk-storage/cargo-target is80,056,377,344allocated bytes (74.56GiB).
Its debug/release subtrees contain54,233regular files; other entries are compiler/
SQLx/node cache metadata and empty namespace guard directories. No symlinks,
special files, external hardlinked inodes or nonstandard DB/archive/credential/
attachment payload names were found. File classification and lack of unusual
names do not establish every historical derived artifact's exact reconstructibility.
The current scoped build was independently compiled by retained hosted CI without
this MCP cache. Standard compiler intermediates are reconstructible from retained
source/lockfile/toolchain/dependencies; unavailable past/private source must not
be silently pronounced recovered. Retain unclassified provenance rather than
claiming bit-identical reconstruction of every old compiled object.

No accessible process exe/cwd/open fd/mapping references the cache or its inode
aliases, and no Cargo/Rust compiler was observed. Protected /proc inspections
remain unreadable:179exe/cwd/fd-directory,44maps. No privilege/identity/route
bypass; universal inactive-use clearance remains an operator read-only check.
Six VK services configure this path as an allowed future build-write root, and
vk_prepare.py still describes it as compiler output. These are future writers/
build consumers, not evidence production executes from the cache. All six actual
service executables are independent paths outside it. Current server, capacity
guard and routing module match SHA256 of the cache release copies and use distinct
inodes; incumbent/fallback copies stay protected. Cache debug/audit/symbol outputs
may be unique historical derived evidence, so do not retire those on assumption.

Provenance review checked6,879dependency rules;23reference422unavailable absolute
source paths. Their21direct output inodes are preserved rather than claiming
that missing source is reconstructed or retired. This is source availability,
not proof of exact historical source identity.

The final conservative cache proposal preserves all top-level debug/release
files and hardlink aliases, every dependency .d file, all .fingerprint provenance,
and every output/alias with an unavailable source. That retains35,060names and
3,108,261,888allocated bytes (2.90GiB), plus all directory structure, .cargo-lock
and empty .git/.codex/.agents namespace guards. The frozen private proposal
lists19,173other regular compiler descendants under
/mnt/vk-storage/cargo-target/{debug,release}/{deps,build,.fingerprint,examples}
with path/device/inode/size/mtime/ctime/nlink/mode. Unique regular-file blocks
conditionally reclaim76,904,693,760bytes /71.63GiB. Directory blocks and retained
output aliases receive no reclaim credit. No retirement implementation added.
Manifest at /mnt/vk-storage/vk-runtime-backup-20261009/cargo-generated-retirement-proposal-v2.private.json,
SHA256aee94e175b2d0f407b364e7af8fdeaff03c5bd0b3d086df60d3b6528041df2df;
this is a proposal, explicitly NOT safe-to-delete-now or a QA/permission receipt.

With the existing exact checkpoint/delta+compat candidates29,777,874,944bytes
(27.73GiB) and currently available245964800bytes, conditional native room is
106928533504bytes /99.58GiB on the EXISTING secondary
ext4. Full unchanged preserved payload+8GiBfloor needs102,454,311,594bytes /95.42GiB,
leaving4.17GiB beyond that floor for directory/block overhead,
package bytes, retained test edits/final catch-up and host growth. The B-mapped
unreduced operational proposal+floor leaves7.95GiB. This is enough for the measured
payload+floor arithmetic, NOT final restore/quarantine peak certification. A
smaller approval omitting the0.30GiB delta yields about99.28GiB; whether that is
sufficient still depends on measured peak. Root's39.6GiB alone does not fit the
67.14GiB reference-backed continuity floor and is not an approved bulk destination.

Other targeted generated inventories: capacity-build-tmp1,079,771,136bytes;
vk-preparation-cache236,290,048; pnpm-store1,018,314,752; npm-cache961,044,480.
They are NOT additionally cleared or included in the capacity credit. Project
build-local/android/carconsole directories are other teams' source/runtime work,
not automatically caches. Unique failed-capture evidence21.83GiB remains excluded
until any separately approved B-preservation/offload and later retirement.

**Recommended conditional no-purchase option:** obtain existing human-QA/owner
release, operator read-only clearance for privileged cache consumers, and a held
cache-write boundary; approve ONLY the frozen generated-file manifest plus the
exact checkpoint/delta/compat targets already listed above. Refresh their
identities, local/Barchive hashes/provider and consumer bindings; preserve source,
unknown provenance and all35,060protected cache output/provenance names and aliases. If any row changes,
use clearance fails or QA is withheld, HOLD rather than expand/bypass the list.
Do not delete root directories, change access settings or enable automatic cleanup.
Retirement risks cold-build latency and concurrent new builds, addressed by owner
clearance, preserved outputs/source and held writer fencing. Preserving selected
unknown generated material on B may be needed before retirement, but no new whole
backup or preservation transfer of cache payload was performed in this review.

After approved bounded retirement, the SAME eventual MCP candidate can be ordinary
independent directories at /mnt/vk-storage/vk-cutover-candidate-20261009 on the
existing ext4; no new device, mount, formatting or ownership change is inherently
required. It must still pass actual included-file/DB/metadata/peak and current-data
catch-up/fallback acceptance. No historical scope reduction is assumed. If the
held QA/retirement gates cannot release these files, there is currently no approved
native capacity route; that is an authorization shortfall, not proof hardware must
be purchased. If measured peaks exceed the resulting space, report the exact
measured deficit before any further reclamation or device request. PR230/231 stay
unmerged; the separate B builder ownership request is still unanswered.

The cache was omitted from actionable reclaim because it is shared, configured
for future builds and not previously cleared for use/provenance/QA. That exclusion
was appropriate for deletion authority, but did not justify recommending new
hardware before the read-only assessment. This update supersedes the unconditional
new-device recommendation. No user/runtime data, source scope or approvals changed.

## Exact owner approval applied; preparation continues (2026-10-09)

Seamus approved both exact pending actions at08:40UTC (`Go`), pinned to
05498ad71d32e2662b475a2584774fbaa47bb134. This is solely the bounded pre-QA
retirement exception and the two new B builder directories. General cleanup
remains technically unavailable; historical exceptions remain unaccepted.

All19,173approved shared-cache names and35,060exclusions refresh unchanged.
Compat inventory has9,752regular files, no special/symlink/external-hardlink
inodes and no missing source in1,147dependency rules. Exact checkpoint/delta
MCP and B SHA256/size match freshly. New unsealed05498ad7 provider package
verifies62bound files,6candidate modules,8reviewed source pins and retained
B-only archive locators. Original descriptors, full backup, directories,
incumbent/fallback artifacts and all excluded/provenance evidence are retained.
Existing Cargo debug/release and compat-debug profile locks are held cooperatively;
no service is frozen for this preparation. Current server/guard/routing artifacts
hash-match independent incumbent copies outside the shared cache.

**Retirement held on authentication, not another deletion approval:** the required
read-only privileged process check returned `sudo: a password is required`. No
alternate identity/route or security change was attempted. Operator on MCP runs:

```bash
sudo python3 -B /mnt/vk-storage/vk-runtime-backup-20261009/approved-retirement-consumer-check.py > /mnt/vk-storage/vk-runtime-backup-20261009/approved-retirement-consumer-clearance.json
```

The helper is read-only apart from this redirected receipt; its SHA256 is
464ad504ec045105153c01c3dc02a46972f02c1d377c75ccfb3ebb090e8204b9. It checks
protected process exe/cwd/FD/mapping inode aliases and compiler activity, requires
the actual lock-holder identity/FDs, reports denial explicitly and performs no
deletions, fencing or permission changes. A stale/failed/incomplete clearance
remains a hold. The frozen approved file list is private and preserved separately;
no paths are expanded during retirement. No file has been retired yet.

B guest ownership is corrected only within combined-source and isolated-validation
to UID/GID1000, without following symlinks;2,944entries/2,553regular-file hashes,
modes and mtimes verified. Toolchains, backups and candidate data are untouched.
WSL has no passwd name for numericUID1000; the launcher drops to the APPROVED
UID/GID using setpriv before any test/build, without creating an account or testing
as root. Exact and nested namespace prerequisites pass as1000.

A fresh independent source copy binds current PR230c3c48e63/tree d8bb5fb0.
The old f8source/149overlay/receipts remain unchanged. Only this new build root
is writable; OS/toolchain are read-only, backups and manager sockets are absent.
Two technical fixture corrections are retained: read-only /bin for the shell
interpreter, and existing /mnt/wsl/resolv.conf read-only at its unchanged target.
No namespace denial, network route/resolver or security setting was bypassed.
Frozen pnpm install and required formatting pass, tracked source remains clean.
Exact candidate/compatible-fallback artifacts are building; no package success
or live acceptance is claimed. B physical free is monitored with32GiB held for
protected backup/future capture.

Production remains MCP PID3027197; fallback1369037 stays frozen. No actual MCP
candidate allocation/restore, final fenced catch-up, cutover or merge occurred.
After consumer clearance, refresh and retire ONLY the frozen approved regular
files/archive copies, preserve directories/exclusions and measure actual free
blocks/inodes. Then restore/rehearse/catch up/promote the SAME MCP roots after
full metadata/capacity/source/package/controller/consent/latest-data fallback gates.
Do not use estimates as measured reserve or erase448/145/transcript415/journal/
mode/link exceptions. No new historical-recovery sign-off is created.

## Approved retirement complete; retained interruption evidence

The required operator-authenticated read-only clearance arrived:09:12:20UTC,
root inspection of74,679inodes found zero consumers, zero compiler processes and
zero denied inspections; all held lock-holder identities/FDs verified. Before
retirement, local/Barchive hashes, provider dependencies and every file identity
were refreshed under the three held Cargo profile locks. The private audit bundle
and final narrowed frozen manifest were hash-read back on B before any removal.

Completed09:22:03UTC:23,007approved generated regular files and the two exact
checkpoint/delta local archive copies retired. The allowlist was narrowed to ALSO
retain5,918compat top-level outputs/aliases, dependency/fingerprint provenance
and lockfiles (334,581,760bytes); no new path was added. Every directory stays.
Actual native free increased106,338,144,256bytes to106,558,427,136bytes /99.24GiB
immediately after retirement. This is measured free, not final restore/catch-up
reserve. Subsequent host growth is separately observed; no capacity promise.

All40,978excluded names match original inode/device/size/allocated blocks/mode/
mtime/ctime/link counts; all11,001directories preserve identity,owner,mode. No
permissions changed. Approved archive path/checksum/B-location breadcrumbs and
original descriptors remain. Incumbent3027197 is running, HTTP200; protected
fallback1369037 stays frozen. General cleanup remains technically unavailable,
with only the granted pre-QA exception consumed. Historical exceptions unchanged.

Retained B evidence before removal:
B:/vk-backups/vk-safe-release-20261009/approved-retirement/approved-retirement-evidence-before-removal-20261009.tar.gz
(3,265,947bytes,SHA25682fff6482dd28e4261ed82aad9fcddb9df6d237818f0a5c9739865e8458f7b30).
Final private frozen subset:
B:/vk-backups/vk-safe-release-20261009/approved-retirement/approved-retirement-final-file-set-20261009.private.json
(8,084,551bytes,SHA256d91b2a7163b42ac7247008907102934eb670eb9ee06517d6da85013af415ec49).
Post-removal journals remain on MCP pending B availability; no private ledger is
published on GitHub. Required post-retirement B-only readback remains pending.

The SAME actual MCP task root now exists at
/mnt/vk-storage/vk-cutover-candidate-20261009 (new0700,UID/GID1000,dev2065,
inode10354930). No mount, formatting or existing ownership change. Tree and
payload remain unmaterialized. Its actual provider registers all77original
roots and requires all76snapshot DBs, archived-atime restoration and an explicit
256MiBmetadata budget. The raw published descriptor matches
`514c96fe5da800b620427ca25da39e8120a2eb7729eef2afba118e70f6645152`. The separate RSS telemetry
wrapper correctly failed descriptor binding; use the original published result
and keep telemetry separate. No checker weakened or source field silently ignored.

B builder setup and UID1000/nested namespace gates are complete. Source-format/
frozen-install/source-clean checks passed. SQLite binding required isolated
hash-verified Ubuntu libclang/LLVM/XML/ICU/resource-header packages under the
NEW approved output root; no system package install or existing-toolchain change.
Configuration v5 selects the official relocated Clang resource directory, retains
all failed attempt logs and uses a fresh artifact directory. It was last observed
compiling; final artifacts/scanner/module/runtime acceptance remain unverified.

**New observed blocker:** existing SSH desktop route now returns255:
`ssh: connect to host 100.70.23.123 port 22: Connection timed out`. Tailscale
reports Desktop offline,last seen09:20UTC. This is actual SSH/B connectivity,
not Dot status. No alternate route,credentials,security setting or root retry.
Operator needs to bring Desktop back on its EXISTING SSH/Tailscale connection
with B available; no new deletion/ownership/GitHub approval is requested. The
GitHub MCP grant still hasworkflow. PR230/231 remain unmerged.

Once that observed connection returns: verify B provider/retirement reads, observe
actual builder outcome and bind all artifacts; run actual whole-state restore
into the SAME MCP roots, measure allocation/RAM/metadata/catch-up reserve and
accept real application/scanner/controller/consent/fallback gates. Fresh final
fenced catch-up still precedes promotion. No restart/cutover/live repair occurred.
No scope reduction or recovery-complete/universal-zero-loss sign-off invented.

## Connection restored; recorded-link preservation and fresh build

Existing SSH desktop returned at09:38:29UTC; the previous timeout is retained
incident evidence, not a current access block. Both retired archives passed
fresh B-only full-stream hashes through the packaged provider after local
retirement. Post-removal journals are being preserved on B.

UID1000 builder namespace/nested module preflights pass. Buildv6 failed at
server linking: interrupted libstarlark archive contained its metadata member
but no compiled object members, despite an existing Cargo completion fingerprint.
Cause is unknown. The prior output is retained; buildv7 uses a fresh independent
target and artifact directory within the SAME approved sandbox. No source,
isolation, credential or security policy bypass; artifact acceptance is pending.

Authenticated retained catalog analysis distinguishes575 recorded links whose
virtual targets are not in the backup namespace:561 targets currently exist on
MCP and14 are currently unavailable. Mostly these reference excluded generated
dependencies; this is NOT an additional proved-loss count or retirement verdict.
All link literals and historical exceptions remain preserved.

The candidate provider now supports an explicit opt-in preservation policy that
binds every missing link literal to its authenticated manifest. Strict validation
remains the default. Virtual resolution handles paths through other symlinks;
cycles, namespace escapes, altered exceptions and host fallthrough still block.
Preserving a recorded missing target does not satisfy operational dependencies:
configured selectors must resolve in independent candidate data, and rehearsal,
promotion and latest-data fallback all additionally require actual operational
dependency-closure acceptance. Fixture acceptance is explicitly labelled.

All77 source roots and76 DB snapshots are still required; no smaller scope is
silently substituted. Actual restore allocation, final catch-up peak, full Linux
metadata, combined application/controller/consent acceptance and compatible
latest-data fallback remain unverified. SAME MCP task root remains the candidate;
B/WSL is solely the builder. Incumbent/frozen fallback and all historical evidence
remain protected. General cleanup remains technically unavailable.

Validation:35 candidate controller/scope regressions and11 actual PAX/direct-B
contract regressions passed after the correction. These are isolated fixtures,
not whole-state restore or application acceptance. Package binding is checked
after committing the operational source, as required by its fail-closed builder.

## Fresh journal boundary and post-removal preservation

All85 candidate regressions pass at01af7c36, including package tamper/refusal
and actual packaged review-loader checks. Remote PR231/branch SHA matches
01af7c36f1ba969fa4457278b8fd0978fe76c2b1; PR230 remains exactc3c48e63 and
unmerged. The actual new provider package binds61files,6candidate modules and
all8 reviewed PR229 files; fixture_only=false, operational_acceptance=false.

The post-removal evidence bundle is independently read back on B:
B:/vk-backups/vk-safe-release-20261009/approved-retirement/post-removal-1019/approved-retirement-post-removal-evidence-20261009-1019.tar.gz
(2,686,733bytes,SHA256df97decf36ee772691e39fa66f1d2ee79529552587650f725e595accf15a25f0).
It preserves action/exclusion/directory proofs, B-only archive checks and current
provider source. Original archives/receipts and pre-removal B bundle remain.

Current original journal.sock returned ConnectionRefusedError/Errno111. No
continuous final-delta coverage can be inferred from the old ready receipt. A
NEW read-only journal uses the unchanged full plan and a new socket, with
55,846watches,zero errors and ready=true,instance5282e0992fa84bcb92845feb3f7edd8a.
Its start does not bridge the earlier gap. A fresh online full checkpoint is
running directly to B to establish a new verified parent for final catch-up,
under MemoryHigh2500MiB/MemoryMax3000MiB. No production fencing/start/switch.
This repeat is necessary after the observed journal failure; it is not a second
restore/rehearsal environment or a historical-recovery acceptance.

The14 unavailable recorded links reference2distinct unavailable targets:12
patch/execution wrapper selectors and2preview-worktree aliases. No direct match
to the currently configured native/MCP launcher paths was found. Lifecycle and
any indirect saved-profile/session dependency remain unknown; neither retirement
nor current functional loss is proved. Full runtime closure remains mandatory.

Fresh builderv7 has produced a first candidate server and is compiling executor
test binaries; its starlark archive has17members/70,140,838bytes versus the
interrupted archive's metadata-only member. All prior failed outputs stay retained.
Final complete artifact manifest/scanner/module/combined runtime acceptance is
still pending. The full B provider verification also remains running.

## Actual full provider proof and explicit candidate bootstrap

Actual packaged provider01af7c36 has now passed both complete B-stream reads and
all per-file/snapshot/header checks:537,645entries including27generated strict
ancestors,76required snapshots,manifestc7c9ec848acb017c059e4ea18e14394f708ed3076d66ff8c42c9efdad7d59503.
Authenticated metadata encodes184,457,754bytes within256MiB; archived timestamps
are bound. All captured members haveUID/GID1000 and no extended-attribute header
was present. This is archive proof, not restored metadata acceptance.

Actual virtual resolution found589missing-link exceptions across ALL4,501links.
The prior575count considered direct out-of-inventory targets only;14additional
indirect chains are now explicit. No host fallthrough or retirement inference.
Full scope remains77roots. Payload93,864,377,002bytes plus regular-file block
rounding lower bound1,291,818,326bytes and8GiBreserve leaves2,075,181,056bytes
before directories/package/catch-up, against105,821,310,976available at proof.
Actual allocation/refresh reserve remains required; estimates do not authorize
cutover or further cleanup.

A read-only live-schema check found no vk_runtime_identity table; DBinode/mtime
were unchanged by the inspection. New source requires explicit candidate-only
bootstrap. The controller now implements a stopped, authenticated required-DB
seed with an atomic transaction, existing-token overwrite prohibition and
incumbent protection. Rehearsal enrollment is a test edit; final catch-up
quarantines it. Post-catch-up enrollment holds promotion until a NEW authenticated
B capture matches this exact stopped candidate generation and root binding.
The old bootstrap cannot be reused to accept a stale capture. Original source
enrollment remains false, and startup never creates or repairs tokens.

Tests exercise original-row preservation, unchanged incumbent, catch-up removal
of rehearsal identity, stale/missing B-capture hold, same-root promotion after
fixture backup, invalid identity/unverified database rejection, and closing WAL
ownership without leaving bookkeeping. These are fixtures, not a live bootstrap
or release acceptance. Actual candidate tree remains unmaterialized.

Controller bootstrap validation:38 isolated controller/scope regressions pass.
Four additional real-archive verified-index reuse tests pass. To avoid repeating
the completed20minute full-header/content audit, a new bounded checkpoint-index
provider requires hash-pinned B preservation and source binding, fresh B index/
archive verification, complete replay hash and unchanged full metadata/DB checks.
This authorizes no operational acceptance. Actual restore is the next step.
