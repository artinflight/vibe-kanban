# Safe restart progress — October 9

Resumed e3de640d under explicit restart/cutover authorization. Existing Desktop
SSH works independently of Dot; initial B free340917653504bytes. Earlier claim
that Dot offline implied SSH offline was incorrect. No credentials/routes/security
permissions changed; no denied GitHub write retried.

All PR150/153/223/225/229 heads were checked live read-only and still match
authorized pins. The original149-file B overlay was read back and matches
SHA2565b0af111571450643b47ab95f4df71018d03ff43abde82bc8571e0bdbef0821e.
GitHub grant checked read-only has admin:repo_hook,gist,read:org,repo,user, lacks
workflow. Publishing .github/workflows/test.yml and scheduled-goal-artifacts.yml
remains blocked. Specific approval requested asynchronously; no OAuth initiated.

B Linux environment: WSL2.4.12/kernel5.15.167.4 already installed, no previous
distros. Imported VK-Candidate-20261009 to
B:/vk-backups/vk-safe-release-20261009/linux-candidate/distribution using official
Ubuntu24.04 minimal20261008 image, SHA256
e322e57b71859d444258e18118e48550c243b68cb28befca629ea2573ef47ee6.
Windows features, host ACLs and credentials unchanged. Default guest RAMabout47GiB,
DesktopphysicalRAM102952357888bytes. New120GiB opaque candidate-data.ext4 created
on B and formatted ext4, mounted guest /mnt/vk-storage (/dev/loop0 rw,noatime).
119767867392availablebytes after filesystem reservation. Sparse allocation was set
on this new container only, without deleting original data or changing ACLs.
Guest-only Git,zstd,ACL/xattr,bubblewrap and compiler tools installed. No VK/CU
application started, no production fence/restart/cutover/cleanup occurred.

Capture RAM: actual largest plannedDB memory_snapshot/BytesIO measured
790982656snapshotbytes,1546690560peakRSS,19.46seconds; no SSDpayload. Full capture
peakcgroup1573625856bytes, noOOM. However full77-root capture failed closed at1GiB
bound on added Green logs_2.sqlite4734447616bytes. Original69 snapshot DBs fit;
adding current logging DBs exposed this concrete extra dependency. Preserve failed
checkpoint directory and remote partial. Next: consistent SQLite backup API
directly to B using existing SSH/SFTP/FUSE if available; do not raise RAM bound
or silently omit the database. Current logging/current-state scope supplement
needs explicit bound accounting and full verification before acceptance.

Fresh plan: /mnt/vk-storage/vk-runtime-backup-20261009/backup-plan.json retainsall66
original source roots, adds11configuredruntime dependencies and removes6old
logging DB/sidecar exclusions;71explicitDBs. Journal isrunning with55719watches,
readytrue,noerrors initially. Private capture log and scope accounting stay
outsideGit. No proposed historical B-only reduction applied. Shared build caches
outsideoldscope require explicit cold/runtime dependency acceptance; not retired.

Prepared source preservation:62,110,543byte Gitpack streamed directly to B:
B:/vk-backups/vk-safe-release-20261009/combined-source-inputs/inputs.pack
SHA25698b205774e4871116f8f301709aead78969a0005bdc3543dc4d2389696253e55.
First receive receipt failed because Desktop Python lacks hashlib.file_digest;
file retained, verified read-only with compatible hashing, no resend. Scoped
source refs/shallow boundaries preserved besidepack. Git index-pack/object
identity validation is pending before building from it. Do not treat this
transfer as combined-source CI or an accepted full backup.

All448name/145originalhistory/transcript415/journal/mode/link exceptions remain.
No recovery-complete or universal-zero-loss sign-off, no cleanup before humanQA.

## Subsequent independent preparation

The Git pack passed strict index-pack and connectivity verification for all seven
pinned commits, with its original shallow boundary retained. Candidate source was
created from preserved staging5a887abf8 and all149 overlay file hashes verified.
Focused PR229 patch application correctly failed against differing prerequisites
and tests; no partial patch was applied. The original overlay contains no deployment
tools. Exact reviewed e3 tools are therefore bound separately. Two triage test
conflicts were resolved by three-way integration, retaining PR150 repository-context
logic and both budget-exhaustion regressions. Integrated triage SHA256
589f00d0ea332e78c993f877eafdcb7002062a10e5e226ea852134127a43c114;
combined Rust/application validation remains unrun.

The 4.4GiB logger was consistently backed up with SQLite's backup API directly onto
B. Independent Windows full hash/integrity readback passed:4734447616bytes,
SHA25639282baccbf4259cac579cab62d1fbb10deb6a8da8939ed3fe9a4dfcd2d7920e,
480.09seconds,339894272peakPythonRSS. Initial separate-mount fixture was invalid
because exec lifecycle removed the mount before use; its286720byte local fixture
is retained and excluded. A corrected same-invocation probe authenticated mount
identity and physical Windows B hash. No actual logger payload was staged on SSD.

New isolated vk_b_disk_snapshot.py and vk_b_disk_capture.py extend online capture
without editing OP's original eight pinned files or reducing source scope. Six
snapshot and three archive regressions pass under -O, including WAL/row identity,
wrong mounts, scope, existing-output protection and rejected/corrupt readback.
The whole77-root/71explicitDB capture is running in session1995 with original
journal56922. It has verified a new4734447616byte B logger snapshot with SHA256
03642855b12ed608ed8d62e2bbcc8b38177b25575ac4c91e95ce1f567311b450.
No accepted whole-state result exists yet. Large fenced snapshots remain explicitly
blocked; this extension cannot authorize final catch-up/cutover.

WSL mount lifecycle observation: mounts did not survive an idle guest restart.
Isolated source/tools were created in the B-backed guest VHD, not the120GiB data
image. Data image is now held at /mnt/vk-candidate-data by a scoped no-writer guest
observer (session33363), verified ext4/noatime,119767863296availablebytes. Every
future restore/test/promotion must reauthenticate this mount and UUID; presence
of a directory is insufficient. No source files were hidden/moved to achieve it.
Guest bubblewrap namespace prerequisite passed. Node24.13.1,pnpm10.13.1 and exact
Rustnightly2025-12-04/rustfmt installed on B with publisher hashes; not application
validation or a release package.

The actual retained Gitleaks8.30.1 binary matches retained official archive,
SHA25688f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509.
Its UID1000 test invocation did not start: scripts/preservation was inaccessible
inside the new root-owned0700 source directory. Do not rerun as root or bypass
this boundary. Specific approval to assign only new isolated source/test-output
ownership to UID/GID1000 is pending. No live/backup/quarantine ownership changed.

A real five-path metadata fixture on the B-backed ext4 volume failed initially:
GNU tar recorded conflicting atimes for a hardlinked inode. Failed material and
archive remain retained. A new fixture with --atime-preserve=system plus explicit
archived-atime restoration passed owner/mode/ACL/binary user-xattr/mtime/atime,
symlink and hardlink checks. Original inode/ctime/birthtime are not reproduced.
This is platform fixture proof, not full-state metadata acceptance. Future capture
extension now uses atime-read preservation; the exact older running driver was
preserved separately on B and its hash recorded before that change. The running
capture does NOT acquire the newer metadata fix retroactively.

Workflow approval and source/test ownership approval remain pending. No denied
GitHub write retried, no credentials/security settings expanded, no production
writer fence/restart/cutover/cleanup occurred. All recovery exceptions remain.

## Second measured production-size bound and correction

Session1995 ended unsuccessfully: the generated source path inventory exceeded
64MiB. Its local paths.nul67108839bytes and B partial archive979369984bytes remain
retained; no accepted whole-state head was published. The extension's next version
keeps local per-file64MiB and total256MiB bounds unchanged, puts the generated
inventory on the exact verified B mount with an explicit256MiB B-only limit,
records count/bytes/SHA256 in the archived manifest, and verifies the same digest
before and after GNU tar reads it. No additional source exclusion or RAM-limit
increase was introduced. Four archive regressions now pass, including a private
inventory exceeding a64KiB simulated local bound while no local list is created;
six snapshot regressions pass, for10new tests. The original45were not repeated.
All eight original PR229 source hashes still match.

Fresh corrected full capture session63638 is running from
/mnt/vk-storage/vk-runtime-backup-20261009/run_b_inventory_capture.py;
B destination vk-safe-release-20261009/whole-state-b-inventory. This is a new
attempt, not concatenation/resumption of a failed partial. Current journal has no
coverage errors. Source plan remains exactly77roots and71explicit databases.
Whole-state, full-restored metadata and final-fenced acceptance remain unproven.

New source validation: Python parsing and10regressions pass; ops governance passes.
pnpm run format was attempted and fails because this sparse tool checkout has no
package manifest. Combined check/lint/workspace tests, scanner tests and real
runtime/consent/controller acceptance remain unrun. GitHub scope approval still
pending; no write retried. Source/test ownership approval still pending; denied
UID1000 scanner invocation not rerun by a privileged/alternate route.

Incumbent refreshed read-only: service active/running,PID3027197; API/info returned
HTTP200/success true/version0.1.42. This is incumbent health, not candidate readiness
or completed restart. No original production/shared paths were overwritten.

## Final-boundary preparation without operational effects

A separate explicit fenced_snapshot helper now streams bit-exact stopped SQLite
files to the exact B mount without source SQLite opens/WAL bookkeeping or a RAM
image. It requires positive stopped-writer/held-lease fields, no source sidecars,
unchanged source generation/metadata and independently verified private immutable
B integrity/hash readback. The capture extension admits that explicit factory
for all private DBs, avoiding the old multiple-image RAM path; missing checkpoint
or mismatched fence/readback blocks. Nine snapshot and five capture regressions
pass under -O (14new cases total), including exact final source bytes, retained
held kernel fixture lease and rejected remaining WAL/unverified writers.
These are owned fixtures: no real stop/checkpoint/fence or frozen B capture ran.
The actual production supervisor remains unbound/default-blocked; no fixture
receipt can authorize activation. This future source is not retroactively adopted
by current session63638, which uses the previously preserved842999b2 code.

Startup review also found the inherited legacy attachment migration contains
removal calls and the expected marker was not found at the checked green data
location. Its actual source/asset mapping and compiled startup cleanup prohibition
must be verified/corrected before production activation; do not fabricate a marker
or waive human-QA cleanup gating. Current incumbent remains protected/running.

## Existing workflow helper correction

Session63638 failed closed after writing a25001197568byte B partial: the updater
socket warning was not accepted by the low-level driver invocation. The generated
path inventory67733483bytes is fully on B, demonstrating the B-inventory correction.
Seven retained warnings were inspected: one exact Codex daemon-updater.sock and
six generated tmp/arg0/codex-arg0sng2DK members deleted during capture.

This was an invocation omission: unchanged reviewed vk_runtime_ephemeral.install
already supplies narrow socket/generated-wrapper lifecycle handling. Its exact
source hash is b61bd00ab4ebf7be5841c973a17fe113e3884325e3ececfeef5b25fee27d889f.
Applying it read-only to the retained warning log plus capture-start journal
sequence accepts all seven warnings; coverage errors remain empty. No blanket
socket or temp-directory exclusion is needed. The existing socket's live listener
is UID1000 codex PID3211750 from installed daemon release0.162.0. Its IPC content
is not persistent file content; existing workflow retains warning accounting.
No old partial is accepted/resumed, and no data or endpoint is deleted here.
Future full invocation must install that existing helper before capture.

## Current full capture and index preflight

Correct workflow invocation is running as session79354:
run_workflow_complete_capture.py, B destination whole-state-workflow-complete,
local metadata workflow-complete-backups. It installs the unchanged runtime
lifecycle helper before the capture function imports its warning validator.
Source plan/journal/roots remain unchanged; previous25GB partial stays unaccepted.

Read-only analysis of the already generated B inventory counted537532paths,
67733483bytes. Even an empty-value JSON object for these names is70421143bytes,
which exceeds the existing candidate64MiB index budget before file metadata.
The provider now retains its64MiB default and admits an explicit finite budget
of at most256MiB, counts JSON incrementally without another full encoding buffer,
and checks the canonical hardlink-expanded result too. Budget/actual encoding
size are bound into the proof. Two new regressions pass for unchanged defaults,
invalid/unbounded budgets, accepted explicit budgets and fail-closed overflow.
The full production index size and its actual memory fit still need measurement
from the accepted archive; no larger operational budget is silently selected.

## Compiled startup cleanup prohibition, isolated correction

Prepared an exact four-file application patch against the preserved149-file
overlay, not the failed merge index. It disables automatic legacy attachment
migration before any marker/filesystem work and automatic orphan attachment
deletion in the local deployment constructor. Compiled constants are false;
no environment/marker can enable either path in this recovery release. Build-info
exposes both flags. Existing legacy cache read fallback remains unchanged.

The real-server sandbox regression now requires both compiled flags false,
seeds a legacy cache sentinel, and tests startup with DISABLE_ATTACHMENT_CLEANUP
unset. It checks retained legacy content/metadata without rejecting normal
creation of unrelated new cache entries. Patch syntax and exact nightly Rust
formatting pass; combined compilation and packaged execution remain unrun.

Patch/receipt are preserved in
B:/vk-backups/vk-safe-release-20261009/attachment-startup-gate; its exact inputs
and resulting file hashes are bound before the private candidate source changes.
This does not change the incumbent, original backups, or cleanup authorization.
Later cleanup requires human QA and a separately reviewed release; no runtime
override is introduced.

## Fresh whole-state backup accepted (online baseline)

Session79354 completed successfully. All77roots remain included;71explicit
SQLite selectors plus discovery produced76databases,537739inventory entries.
B archive checkpoint--b6977449efc74320bf5fbbe432ae06ef.tar.zst is25006383044bytes,
SHA256735e211552c315f9f9be78eda9f28d175f2406847032f5df6a5d2307d8362ef5.
Physical B readback, complete archived manifest and all snapshot hashes passed.
Recovery descriptor SHA256514c96fe5da800b620427ca25da39e8120a2eb7729eef2afba118e70f6645152
is published and independently verified beside it at
B:/vk-backups/vk-safe-release-20261009/whole-state-workflow-complete.

Preparation2204.99seconds; measured Python peak1468526592bytes. Local archive
and snapshot payload zero; local capture metadata28978bytes. Two narrowly
accepted online runtime warnings remain in private evidence. Frozen boundary
is false: final held-writer catch-up is still mandatory, and live writes were
not stopped for this baseline. Journal instance/coverage remained healthy.

The read-only Desktop catalog inspection now authenticates this accepted
descriptor/archive and hashes every included regular member, counts numeric
ownership/PAX timestamp/xattr coverage and measures actual restore bytes/index
size. It will retain a private B catalog and publish only a redacted summary.
Full candidate restoration and full Linux metadata/application acceptance remain
unrun. No old partial, historical loss exception or recovery sign-off is changed.

## Exact offline application source binding

Candidate149-file overlay plus bounded PR229 triage integration and compiled
startup cleanup prohibition is committed locally on B as
f8fd50327331d43f672966a53da90a5f2b13b685, tree
e1a17ed26470e221a7ee0a995b4f1b7d10a49dc8, branch
candidate/safe-restart-20261009. No unrelated path was staged. This is a local
source binding, not a tested release or GitHub publication. The original
149-file overlay remains unchanged.

B incremental source pack1586305bytes, SHA256
3e416e633a677d00f8cd0ccc765bf552f3b667934bdab8cdf7bc05173dcc8ec6,
is preserved beside attachment-startup-gate receipts. It requires the retained
initial98b20577 pack and original shallow/ref boundary. No workspace was
recreated to recover a missing original object.

Both specific approval questions remain pending: workflow grant for publication
and ownership of only newly generated candidate source/test-output toUID/GID1000.
Source remains root0700. Denied tests were not retried as root or by another
route. Actual controller/supervisor activation and compatible latest-data fallback
remain unbound/default-blocked; fixtures cannot replace these acceptance gates.
No fencing/restart/cutover/merge/cleanup or original live metadata change occurred.

## Full-file catalog bound correction

The first independent Desktop catalog stopped at its explicit256MiB private
metadata-file limit. Its partial catalog and exact script are retained on B; it
is not full-file or metadata acceptance. The already accepted whole-state backup
remains verified and unchanged. New inspection uses64MiB disk chunks, a finite
1GiB total output limit and8GiB B reserve. It authenticates the exact published
descriptor514c96fe and archive735e2115 before inspection and again at completion,
and retains full member/snapshot coverage requirements. No candidate index or
RAM limit is raised and no member is omitted. Session78183 is running this
read-only corrective inspection; no restore or operational effect was started.

## Independent full-member inspection completed

Corrective session78183 passed. Descriptor514c96fe/archive735e2115 independently
matched the authoritative capture receipts. All462503regular members were
hashed;76snapshot hashes matched. Retained55725directories,4501symlinks,14889
hardlinks;537618archive entries after snapshot/sidecar handling. All recorded
owners areUID/GID1000; no archived special modes or extended-attribute headers
were observed; zero members lack archived atime. This authenticates archive
content/header evidence, not restoration of those metadata into the candidate.

Regular payload93864377002bytes (87.42GiB). Candidate111.54GiB usable leaves
24.12GiB before actual filesystem overhead/quarantine/final catch-up;8GiB working
reserve must remain. Do not claim measured restored peak from logical bytes.
Private catalog269021663bytes is five hash-bound chunks, each<=64MiB, on B.
Inspection515.81seconds/823173120peakRSS. Original failed256MiB catalog retained.
Safe summary is scripts/deployment/receipts/fresh-backup-full-file-20261009.json.

A new read-only namespace preflight found27unarchived context parent directories,
no missing hardlink targets and no special-mode members. Current provider's exact
parent validation therefore still blocks full-root materialization. These parent
directories need explicit, source-plan-bound namespace scaffolding; they must not
be represented as recovered source metadata or used to fill missing data inside
an included root. No original evidence was changed. The catalog-derived core
index estimate171576375bytes precedes canonical hardlink expansion and tar base
mtime fallback; it is not final provider acceptance. The256MiB provider limit
remains unchanged. Raw parent names/catalog stay private on B.

Exact remaining gates: the held workflow grant and new-source/test ownership
correction; reviewed context-parent/atime restoration binding; measured full
restore/peak capacity; combined application/scanner/package tests; actual native
controller/consent/current-report acceptance; compatible latest-data fallback
and final held-writer catch-up. No restart/cutover or historical sign-off occurred.
