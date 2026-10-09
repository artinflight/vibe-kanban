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

## Owner update reconciled: stored workflow grant and MCP architecture

Read-only GitHub user headers on2026-10-09T04:31:13Z identify artinflight and
include workflow; Last-Modified2026-10-09T01:03:19Z matches the owner's completed
refresh. No new authorization flow, credential change or denied-write bypass.
The old workflow hold above is superseded. Scoped combined source is published
as draftPR230 https://github.com/artinflight/vibe-kanban/pull/230. Retained source
f8fd50327331d43f672966a53da90a5f2b13b685 was imported from the authenticated B
incremental pack, strict-verified and published with exactly149 changed paths
against unchanged staging5a887abf8bbedfbfb01ce7f8898fed07102fa1e3. All five input
PR heads still match authorized pins. An actual Gitleaks8.30.1 sanitized-environment
scan of the4494189byte publication diff passed with allow-comments disabled.
No raw private transcript or credential was published.

Initial combined CI37883617292 exposed one frontend formatting failure in
SessionChatBox.tsx. Applied exact locked Prettier3.6.1 transform using the repo
config, checked idempotent formatting and restricted the correction to that file.
Pushed descendant fe94c13738c4f4e2588f0ac43ee9efd1e2227524, remote ref verified;
treefeba17ebb2213c7462fbc56c8312e3181af1a180. New TestCI37883846489 and scheduled
artifactCI37883846490 started for that exact SHA; final combined acceptance is
pending, not inferred from individual CI. Initial combined scanner contract
ran73tests including14real-scanner cases successfully; this does not bind a
future deployment package or opt production into preservation automatically.

Owner architecture correction: production stays on MCP. The existing Desktop
B-backed WSL distribution/120GiB ext4 container is preserved verification/storage
material, not an approved eventual production candidate. No VK process was run
there. The intended single eventual MCP candidate must itself be the restore
rehearsal and later promotion target; do not create a separate rehearsal or
silently migrate production to Desktop. The source/test-output UID/GID1000
ownership request remains unanswered and no ownership/permission change or
retry of its denied non-root invocation occurred.

Targeted mount observation (not another whole-scope audit): MCP secondary SSD is
mounted ext4,335163392bytes available at04:17; no candidate data allocation there.
System disk free42.6GB is not an approved backup/bulk-staging location. Existing
accepted B catalog proves93864377002logical regular-file bytes, before filesystem,
catch-up/quarantine/build reserve. OP scope/capacity evidence is retained; no
historical-scope reduction has been applied. The allocated Desktop volume is
not MCP storage and Windows B SSHFS is not proof of native Linux metadata or
suitable production SQLite storage. An MCP native Linux candidate volume with
sufficient measured restore/catch-up capacity is the concrete operational
prerequisite. No deletion of retained data is proposed to create that space.

Implemented optional authenticated-plan namespace scaffolding: registration
binds the canonical plan and scope digests, and only missing strict ancestors
outside every declared source root may be generated. Archive metadata wins,
missing directories within source roots fail closed, generated context has
explicit0700/currentUID/currentGID/mtime0 defaults and is not described as recovered
historical metadata. The default provider still rejects missing parents without
this policy. Seven tests pass including an actual sparse direct-B fixture archive,
wrong plan/scope/prefix, non-directory parents and missing source directories;
two metadata-bound regressions pass. Candidate package includes the new module.
No OP eight source pins or index/memory bounds were changed.

Read-only planning against all five authenticated private B catalog chunks
confirmed all27missing parents are strict outside-source ancestors; zero are
inside a declared source root and zero are unrelated. This is planning proof,
not materialization or full metadata acceptance. First planning invocation
correctly rejected a file-SHA/canonical-plan-SHA mixup, retained; corrected run
bound descriptor plan1da86062af8e708457654a9e31c3057dc3f249ee4498ef474d5cb0a62c96c1cb
instead of plan-file SHA4a7abb5628f381d943acb51e2ffc00c250e11bfb0b71b29a1ff78c1df4865b0c.
Only redacted planning receipt is tracked. Own generated bytecode was checked
for open consumers and moved without deletion/permission changes to retained
candidate-bytecode-ca74104d outside source for honest clean-source packaging.
First package regressions blocked as intended on uncommitted source; rerun
requires the committed source and does not weaken the clean-source check.

At04:30 incumbent service remains active/running PID3027197; /api/info HTTP200
success true. Protected incumbent/fallback, online whole-state B baseline,
journal and every historical recovery exception remain. No writer fence,
restart, route switch, deployment, merge or cleanup occurred. Atime/full restored
metadata, actual MCP candidate capacity, final fenced catch-up, latest-data
fallback, fresh package/controller binding and live consent acceptance remain
release gates. Cleanup stays technically unavailable pending human QA.

## Fresh combined CI correction and remaining metadata preparation

PR230's first formatting correction passed frontend format checks and exposed
an actual combined test-harness dependency: the merged phone layout calls
window.matchMedia, absent from PR225's simulated browser. Added the real browser
API shape to that fixture and expanded all mounted consent/snapshot/lifecycle
race scenarios to both desktop and phone layouts, explicitly asserting the
actual layout branch. No test was removed/skipped and no production UI logic
changed. Pushed a22a93f1bd07c9e3aaa0d94598611221b86b4dee, exact remote verified;
tree915a40de3394c628fa827b6f041bcae6c591d187. TestCI37885126071 and artifactCI
37885126054 are running for that head. Superseded first source runs/receipts/logs
are retained; obsolete f8CI was explicitly cancelled to release the pending
current run. CI passing/readiness is not asserted before completion.

Isolated tooling is now independently published as draftPR231
https://github.com/artinflight/vibe-kanban/pull/231, head2104d175f82b6db4ca010a4aa97a5ea9d2d288ea
at initial publication, remote verified. It remains a distinct PR149-equivalent
candidate/direct-B concern, based on the existing integration work. PR149 and
OP worktree/code were not overwritten; combined application PR230 stays separate.
All8exact PR229 source pins are unchanged. Committed-source candidate package
regressions now pass3/3, with6required modules including namespace scaffolding.
Ten direct-B/catch-up/latest-data fallback contracts also pass. These checks
remain fixtures, not actual production adapter or live consent acceptance.

Corrected the remaining archive-atime restoration gap in accessible isolated
controller code: an explicit archive timestamp policy binds every PAX atime
as exact nonnegative nanoseconds, rejects missing/ambiguous timestamps and
contradictory hardlink inode metadata, includes the timestamp index in the
unchanged finite metadata budget, and reapplies/verifies timestamps after the
last content traversal using lstat only. Operational (non-fixture) restore now
requires that policy; it cannot silently inherit the old unsupported-atime
path. GNU tar hardlink aliases omit repeated xattr headers, so they inherit the
authenticated target inode's attributes; explicitly conflicting alias attributes
still block. A first overly strict equality attempt correctly failed fixture
coverage on that omission, was diagnosed from the retained synthetic archive,
and corrected without changing OP's original source or source attributes.

Five new -O regressions pass: exact timestamp parsing/ambiguity rejection,
non-fixture policy enforcement before materialization, hardlink metadata
contradiction rejection, actual private file/directory/hardlink/symlink timestamp
restoration with protected canary metadata unchanged, and tampered/incomplete
atime-map rejection before any timestamp write. Existing10direct-B contracts,
7scaffold tests and2metadata-bound tests were rerun successfully after this
change. This verifies restoration of authenticated archive headers; it does
not invent original source atimes for normalized DB snapshots or original
inode/ctime/birthtime identities.

A targeted read-only metadata pass over the five already authenticated B catalog
chunks checked all14889hardlink relationships: zero mode/owner, atime or mtime
conflicts, zero hardlink comparisons lacking catalog mtime, zero missing/invalid
archived atimes. There are6038othercatalogmembers without the retained base mtime
field; the original authenticated tar headers remain authoritative and the
actual provider reads their base mtime, so this catalog-only planning pass does
not assert full mtime acceptance for them. Safe receipt is tracked, fullprivate
catalog remains on B. No second full content/backup/storage audit, restore,
permission change, live write, cleanup or release acceptance occurred.

Concrete next operational prerequisite remains MCP native Linux candidate
capacity. Current free space cannot hold the required candidate; the Desktop
120GiB container is not a substitute for MCP-local production storage. Use the
same eventual MCP generation for restore, rehearsal, final caught-up promotion
and latest-data fallback. Existing B backup/evidence and stable incumbent stay
protected. UID/GID1000 permission correction for only the newly generated B
source/test-output remains unanswered and held. After capacity/source-bound
candidate gates and live consent pass, perform the separately bounded writer
drain/final backup/catch-up/acceptance/cutover; cleanup remains technically
unavailable until human QA and a separately reviewed enablement.

## Final-boundary source progress: invocation regression and compact time index

Current combined application PR230 head is7708037a4646b385e363ff734177053c657b7f4f,
treecec692bc2758f8d49a892d8782e6f6b59d00b6d7, remote ref verified. At predecessor
a22a93f1 the frontend (including both consent layouts), clippy, schema, Tauri,
scanner73-test contract, governance and freshness checks passed. Backend reported
463passed,1failed,10skipped and8notrun after fail-fast: the original generic
invocation test still listed the intentionally supported single
--capacity-build-info alias as invalid, despite the dedicated exact-alias
regression accepting it. Corrected that stale test expectation and expanded
mixed/duplicate/serve argument rejections. Startup parser/serve behavior unchanged.
Both exact invocation tests pass with installednightly2025-12-04 via standalone
rustc test compilation, without production/native state access or fixture deletion.
Fresh exact-head TestCI37886243350 and artifactCI37886243480 are running; final
source/package acceptance still awaits these results. No failed check was waived.

Archived-atime receipts now use a compact vector aligned with sorted authenticated
manifest names; its digest binds the manifest digest, ordering and all values.
This avoids encoding537618privatepathnames twice, retaining the default64MiB/
explicit256MiB ceiling and counting timestamp bytes in that same budget. Restored
core inventory remains exact; timestamps are verified separately after content
reads, with reordered vectors, changed manifests, incomplete vectors or changed
values rejected before metadata writes. Five timestamp regressions and the
10direct-B/2bound tests pass after this source change. Full actual provider index
bytes/RAM and restored filesystem allocation remain measured candidate gates,
not inferred from the planning index estimate.

Published-source-f5713ad7 B preservation was independently hash-read back: tool
incremental pack181897bytes SHAb597abb20ba74db675c223be6956e086b029f13fa45968404b0c3d3ea0820ce1;
then-current appa22 incremental pack20879bytes SHA4f239eba65fea59dc068944870db74bb86f5f6b3f0c4f828f3c3dd97e4907030;
e3-to-f571 patch133936bytes SHA7a4d2a1c47b4f94a1e681790aab6a5d6447abac2bf467b33350c9157d7ff2912.
They require the retained original Git input packs; originals and previous receipts
are preserved. Later local source/remote commits are additive, not replacements.

Capacity wording:87.42GiB is the regular-file lower bound for materializing the
entire current unreduced77-root preservation plan, not a claim that every historical
file is needed to start VK. The operational candidate must cover the established
configured dependency closure and explicitly account for any B-only historical
material; no such reduction has been applied or silently accepted. The existing
B volume is physically on Desktop. Keeping production on MCP therefore needs
MCP-accessible native Linux storage and a measured candidate/catch-up reserve;
current335MBfree does not solve that. In particular the accepted current Green
logging database snapshot alone is4734447616bytes, before attachments, agent
history, active DBs, release artifacts and reserve. The active VK DB itself is
91684864bytes by a read-only stat; a DB-only copy is not full state/rehearsal.
Do not consume system-disk bulk space, delete preserved data, or switch production
to Desktop to bypass this capacity requirement.

Unrun operational outcomes: same MCP candidate full included-file/DB restore,
actual Linux metadata/ownership/link/ACL/xattr/time acceptance, measured restore
and catch-up peak/RAM, actual package/supervisor/controller/prerequisite binding,
real consent acceptance, safe active-session drain/held writers, final fresh B
boundary and catch-up, latest-data compatible fallback rehearsal and live health
cutover. Historical448/145/transcript415/journal/mode/link exceptions remain
explicit and are not automatically operational data-loss acceptance. Stable
incumbent/fallback and all B evidence remain protected. No permission change,
credential/access expansion, new auth flow, production restart/cutover or cleanup.

## Verified publication, combined CI and actual candidate blocker (05:31 UTC)

Stored MCP artinflight workflow grant is verified; no new auth flow or repeat
approval is needed. Existing SSH desktop and physical B path checked successfully
again. Incumbent Green service remains active/running PID3027197 and /api/info
responds successfully. These facts do not authorize any pending ownership change.

PR230 combined source at7708037a passed exact Test37886243350:472 backend tests
passed,10 skipped; real scanner73 contracts passed, plus frontend desktop/phone
consent lifecycle fixtures, formatting/type/lint checks, schema/clippy/Tauri and
ops/branch checks. Remote private dependency validation is still skipped because
its deploy key is absent; its green job is not evidence those checks ran.
Artifact37886243480 compiled candidate/rollback binaries but failed its mandatory
routing-module verification. Diagnostic commit04c998c8 preserved every check and
made the failure observable early: artifact37888782559 reports exactly
"Routing module prerequisite missing: bwrap". Current PR230 headc3c48e6324f778ccd03a5761c2314b440e9ceac3,
treed8bb5fb0678e7e7ce0951bc2dc8aa95a61ecf99a installs only the required bubblewrap
dependency on the isolated hosted builder; no host security policy is changed.
Both source revisions retain exactly149changed paths against the pinned staging
baseline; original overlay/packs/receipts are retained. Fresh exact-head
Test37888935110 and artifacts37888935082 are pending/running, not accepted yet.

Exact read-only namespace preflight succeeds on MCP with existing bwrap. Bounded
regressions prove a missing dependency blocks before process spawn and a namespace
denial fails closed. A repeat execution of the local publication scanner at
/mnt/vk-storage/vk-runtime-backup-20261009/gitleaks-publication was denied: mode0605,
owned mcp, owner execute absent. No chmod/chown, alternate executor or credential
route was attempted. Existing successful original publication scan and exact
real-scanner CI evidence remain; current-source CI is separately required.

Source metadata review confirms DB archive headers originate from gettarinfo(raw)
and source xattrs, with exact source_metadata_before atime/mtime for direct B
snapshots when supplied. The temporary B snapshot inode is not substituted for
source owner/mode metadata. This is source review, not full restored Linux
metadata acceptance or proof of all historical original atimes/ctime/inodes.

Production architecture remains MCP. The accepted design is ONE independent MCP
candidate generation restored, tested, caught up and later promoted with those
same roots; compatible fallback must use latest candidate data. The existing
120GiB B-backed ext4 environment is located on Desktop and is NOT the eventual
MCP cutover instance or permission to migrate production. No second full restore
or new environment provisioning is started. Pending UID/GID1000 change for only
new Desktop guest source/test-output is unanswered and held.

Targeted retained-catalog accounting, without a repeat OP storage audit, gives
active Green agent home10081079316bytes and current XDG30567395733bytes regular
payload; these entire included roots still contain unclassified historical
subtrees. Adding the accepted4734447616byte current Green logger snapshot gives
45382922665bytes before other DBs, attachments, native tools and restore/catch-up
reserve. This is a lower bound for THESE CURRENTLY INCLUDED roots, not a proven
minimal operational subset. Full unreduced preservation payload is93864377002bytes
(87.42GiB). Historical material remains authenticated on B; no intra-root scope
reduction has been authorized/applied or silently claimed safe.

Current MCP secondary ext4 free275693568bytes, system free42568028160bytes.
No MCP candidate volume is allocated/restored. System bulk staging is prohibited,
and the full included active-root lower bound alone exceeds its free bytes.
The smallest external prerequisite is MCP-accessible native Linux candidate
storage with capacity for the approved operational dependency closure plus a
measured restore/catch-up/quarantine/package reserve. Operator must provide or
approve that storage attachment/allocation; neither Desktop SSH file access nor
its ext4 image alone supplies MCP native production storage. Do not delete
protected data, remotely loop-mount through SSHFS, change permissions/security,
or silently reclassify current data to evade this requirement.

After that prerequisite and fresh package binding: restore the SAME MCP candidate,
validate every included file/DB and full Linux metadata, bind actual namespace/
application/supervisor/scanner/controller prerequisites, validate live consent
and current delivered-report receipts, drain active sessions safely, hold all
writers, produce a fresh B boundary/catch-up preserving test edits and newer live
writes, rehearse latest-data fallback and promote only if actual acceptance passes.
No production stop/fence/restart/cutover/merge/cleanup has occurred. Cleanup remains
technically unavailable pending human QA and a separately reviewed implementation.
Historical448/145/transcript415/journal/mode/link exceptions remain explicit.

Artifact37888935082 finished failed on exactc3c48e63. Dependency installation
passed, then mandatory namespace preflight reported exactly:
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`.
No artifacts uploaded. No runner security-policy change, namespace bypass,
privileged rerun or alternate builder route was attempted. The existing MCP
namespace preflight passes, but local build/candidate capacity remains missing.
Independent prerequisites are now specific: a permitted isolated builder with
required namespace support (or operator-approved build capacity on the existing
MCP sandbox), plus MCP-native same-candidate restore/catch-up storage. No repeated
GitHub authentication is required. Pending ownership request remains unanswered.

Additive B preservation independently hash-read back at
B:/vk-backups/vk-safe-release-20261009/published-source-1285ddc3:
combined-app-c3c48e63.incremental.pack17187bytes SHAa4d123836cbcf334b0b8e6d08c584ce1e4740d6fdde37c6545a1550e02dc783d;
candidate-tools-1285ddc3.incremental.pack43938bytes SHAb4ac9498a7e70687d957a94c9401e34d0fcfb0697665b813636110d514bccc36;
candidate-tools-e3-to-1285.patch150181bytes SHA5a4684b8baf2b33f902bf4375da860a3ef42da4891774b4e8185f9449921b023.
Original input packs, f571/a22 delta packs, original149overlay and all earlier
receipts are required and retained. Safe current tracking, grant and bounded
scope/failure receipts are included; eight files matched physical B SHA/size.
Source commits1285ddc3191a10b27d90f1478565b9c8b861e93b and
c3c48e6324f778ccd03a5761c2314b440e9ceac3 remotely verified. Receipt-only later
tracking commits do not claim a newer operational source or candidate acceptance.

Fresh exact-head Test37888935110 is GREEN at
c3c48e6324f778ccd03a5761c2314b440e9ceac3:472backend tests passed,10skipped,
real scanner73contracts passed, desktop/phone consent fixtures and frontend,
schema, clippy, Tauri, governance/freshness all passed. Private remote checks
remain skipped for missing deploy key. Artifact37888935082 remains failed on
required namespace support; no fresh deployable package or live acceptance is
claimed. Current CI receipt records both outcomes, not a blended green result.

## Read-only exact operator decisions

See VK_RESTART_OPERATOR_DECISIONS_20261009.md and receipts/operator-decisions-readonly-20261009.json for measured current reference-backed scope, exact conditional local duplicate/generated reclaim paths, the already-realized64.43GiB retirement, proposed120GiB MCP native mount and narrowly scoped existing B guest builder ownership decision. No exact operational minimum or peak is invented; no scope, permissions, service, backup or cleanup changed. Source/artifact/metadata/fencing/live acceptance gates remain.

## Native/cache capacity follow-up

Read-only shared cache assessment supersedes the premature new-device proposal. No120GiB unallocated native device exists; application/symbol outputs, all dependency/fingerprint provenance and21missing-source outputs retained;71.63GiB generated-file proposal plus27.73GiB conditional candidates could yield approximately99.58GiB on existing ext4. Exact identities/QA/privileged-use clearance/writer boundary remain required. No retirement or mount/access/source-scope change. See the appended operator decisions and native-cache-capacity-readonly receipt; private frozen manifest remains unpublished.

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

## Approved retirement complete; observed Desktop outage holds restore

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

## October 9, 14:40 approval and recovered preparation owner

Seamus explicitly approved the brief service interruption/switchover at
2026-10-09T14:40:34.401901Z, direct reply Sentinel_dd64f5923b088191aeef2ff5dc5b82fd
to Sentinel_145c5d8131e881919b612786bda470c3. The relay is restricted to existing
execution d9f07b0f-b92d-4b17-a60a-f1cfdf0782bb. This resolves the parent
service-impact hold; no renewed interruption approval is required. Final writer
fencing, acceptance, protected latest-data fallback and exact cleanup checks
remain prerequisites. General post-cutover cleanup remains unavailable before
Seamus human QA.

The completion-output/lifecycle repair is published at 097e1bfac31e1fd31c3469096cc8d0c050b6077d,
with 137 focused tests passing. The same restored MCP candidate was recovered
under non-activating owner PID500933/start757986989 and unit
vk-preparation-owner-097e1bfa.service. Fresh authenticated peer/lease probes
verified source/root/process identity and survival of a disconnected status
client. The original completed materialization journal remains byte-identical;
0002-initial-owner-recovered.json was appended. No repeated restore occurred.
All76 SQLite checks, the full537645-row baseline and archived atimes pass.
The safe probe receipt is scripts/deployment/receipts/recovered-preparation-owner-20261009.json.
Its live result is a dated observation, not a durable liveness promise: persisted
progress always records controller_retained_alive:false and requires a new probe.
Operational activation is unavailable in this preparation owner.

The existing Homelab CA from Desktop's public root stores authenticates routed
HTTPS with hostname/chain validation using only a request-scoped in-memory root.
No TLS bypass, global trust or security setting was changed. Routed assets remain
the old October8 frontend; corrected source5ce84ee2 is not yet live.

The authenticated13:35 independent root consumer receipt passed for the approved
single incident archive. No archive was removed. A fresh instance of the same
read-only operator check was requested for the current retirement boundary,
preserving the original receipt. The manual step is required because MCP-user
access cannot inspect all protected process descriptors/maps, and denied sudo
authentication is not bypassed. Future preflight can use a one-shot hash-pinned
read-only operator receipt; broad or persistent privileges are not proposed.

Remaining critical path: exact approved archive retirement and measured space;
strict initial-only controller handoff to the actual application adapter; same-root
application rehearsal including Linux metadata, module/scanner/controller, consent,
frontend and usage controls; fresh final held-writer catch-up; same-root promotion
and latest-data fallback. None of these is certified by source/fixture success.
Historical448/145/transcript415/journal/mode/link exceptions remain unchanged.

Initial-only handoff source now accepts a hash-pinned contiguous chain consisting
solely of the initial completed journal and initial-owner-recovered journals.
It checks every chain link, scope/root/capture/manifest, explicit latest source,
false rehearsal/activation claims, independently stopped ownership and actual
B/tree verification. New fixtures cover preservation, missing/changed pins,
later operations, false links, live writers and changed data. This is not a
reconstruction of interrupted operations or operational acceptance. Actual
PID500933 remains unchanged; no ownership transfer has been performed.
The59 controller tests passed; package tests correctly refused the uncommitted
working source, so the complete suite is rerun from the immutable checkpoint.

## 15:02 actual-root read-only namespace acceptance

All142 focused candidate tests pass from immutable source868999dd, remotely
verified on PR231. The sparse tooling checkout has no package.json, so
pnpm run format cannot run there; no backend/frontend source rebuild was done.

The actual MCP candidate's virtual database/workspace/Codex-home/controller/token
selectors were inspected inside a read-only filesystem/PID/network namespace.
All five resolve to the independently restored candidate inodes; the absolute
/home/mcp/code/worktrees alias resolves inside its own /mnt/vk-storage/worktrees.
Host manager sockets and incumbent TCP are hidden. Both pinned candidate/fallback
binary hashes and the final5ce84ee2 frontend HTML are visible read-only.
See scripts/deployment/receipts/actual-candidate-readonly-namespace-20261009.json
and its retained reproducible helper. This is actual-root mapping proof only,
not a launched application, writable-worker boundary, live consent or cutover.
The first probe correctly failed because /opt was read-only and the new target
did not exist. Using existing private /run tmpfs corrected the mount declaration;
no host permission, security setting or denied identity/route was changed.

At15:01:48UTC, native archive and B copy both hash e994567e..., with exact native
inode/size/owner/mode/link/mtime/ctime and archived atime unchanged. The retained
B metadata bundle hashes c783bbc9.... The one archive is outside all77capture
roots. The readback receipt is scripts/deployment/receipts/
excluded-incident-archive-fresh-readback-20261009.json. No file was deleted.

The read-only operator check requested at14:50 writes a NEW private receipt
excluded-incident-archive-operator-consumer-clearance-1450.private.json, retaining
the authenticated13:35 receipt. It remains pending as of this observation.
A stale successful consumer observation cannot prove current protected-process
absence at retirement. No sudo retry or alternate privileged route is attempted.
The current native reserve and operational acceptance gates remain held.

## 15:05 held state and immutable handoff checkpoint

The new nonfixture controller package actual-candidate-controller-package-f37b9987
verifies65files,7candidate modules and all8exact reviewed PR229pins. Its source is
f37b99875dbfa08410e029735331e383c41bde37. Both existing initial-only journals are
hash-pinned for eventual supported ownership transfer. A fresh live probe again
verified the original preparation owner PID500933/start757986989 holding the same
lease; no transfer, restore, application start, writer fence or cutover occurred.
See scripts/deployment/receipts/prepared-initial-only-handoff-20261009.json.

Native available at that measurement was8,581,804,032bytes, below the retained
8,589,934,592-byte reserve by8,130,560bytes. This is observed host growth, not
reclaim capacity. No bulk candidate operation may start until the separately
approved single-archive retirement actually supplies measured headroom. The
requested fresh operator receipt remains absent; the13:35authenticated receipt
is unchanged, passing, and preserved. Interruption approval is resolved.

Green PID3027197 is active with cgroup frozen0. Protected previous PID1369037
is active and systemd/cgroup frozen1, freshly checked. Preparation PID500933
is running, its kernel FLOCK is present. Former compiler-cache lock holder
PID165545 has exited and its locks are no longer held; do not rely on old cache
fence receipts for any future cache mutation. No further cache deletion is in
scope. Future single-archive retirement still requires its own fresh consumer,
identity/dependency and held-boundary checks; it does not expand the old allowlist.
All remaining application/rehearsal/consent/current-receipt/catch-up/latest-data
fallback/live acceptance requirements remain unfulfilled, not waived.


## 16:19 consumer-boundary sequencing repair (no retirement/cutover)

Owner approvals remain valid: exact one-file retirement, Sentinel_3c972054e9688191900e38417fd55e00
at12:38:25UTC, and brief service interruption, Sentinel_dd64f5923b088191aeef2ff5dc5b82fd
at14:40:34UTC. These are conditional on the existing safety gates; no new privilege
installation, broader cleanup or recovery acceptance is authorized.

The new15:35:17UTC operator receipt was authenticated against the unchanged helper,
preservation manifest, exact inode and Seamus's15:35:23UTC completion. It records
root inspection with no matches or denied inspections. Its SHA256 is
443032f47a9abaed509d12beba4daa736e2f75aebf5e99d0a5fc60022709d894.
It proves that dated inspection, not consumers after it. The real one-file retry
started but stopped BEFORE unlink on a safety check; this was not a further
approval rejection. It left the archive and every protected copy unchanged.

That retry incorrectly performed expensive native/B hashes and SSH operations
AFTER accepting the root receipt. Protected SSH/SFTP PIDs1632206/1632291/1632292
were born15:42:48UTC; the15:35 receipt cannot cover them. We do not infer their
creator or archive use from those observations. Kernel workers also appeared;
comm names alone are not proof of consumer absence. The failed attempt and safe
held-state record remain in vk-runtime-backup-20261009; none was overwritten.
The superseded1545 snapshot request is withdrawn until preparation ordering is
correct. Repeated manual snapshots followed by SSH orchestration are not a fix.

A one-file unprivileged prepare-first continuation is retained in
scripts/deployment/receipts/retire-approved-single-incident-archive-prepare-first-20261009.py.
It completes exact native/B/archive-metadata hashes and all SSH children before
waiting for NEW independently authenticated manual clearance. It closes the
archive FD before the unchanged root helper: the helper has no holder exemption.
It preserves the live candidate owner, freezes local dependency identities and
blocks later Python-managed fork/exec/process/TCP/unrelated Unix channels.
After clearance it performs only bounded in-process receipt, process-reference,
visible-path/inode, dependency, owner and exclusive-lease checks, then the exact
approved one-file continuation. Newly uninspectable processes and process
birth/reuse during the final local inspection block continuation. It requires
Staging to authenticate the actual operator action; a file merely claiming
euid:0 or an arbitrary confirmation string is not independently sufficient.
Completion logging uses the existing nonfatal notifier after durable results.

Three isolated regressions exercised real preparation children and rejected
post-clearance subprocess, fork/shell, TCP and unrelated Unix-channel attempts.
They do not fabricate operational root visibility or deletion acceptance.
The first prepared resident2084790 reached the wait after successful native/B
hashes at16:19. It was stopped ONLY before clearance/unlink to add final local
process-inventory/visible-parent checks and nonfatal completion logging. No
operator was asked to run a scan for that preliminary resident. The corrected
resident must reach readiness before the final manual helper is requested.

This is managed-owner protection plus approved consumer clearance, not an atomic
global open fence. An already-existing unrelated process can open a file after a
read-only scan. We do not claim otherwise or invent an unattainable prerequisite.
No approved gate is waived; no root scanner, sudoers rule or persistent privilege
was installed. Existing manual operator authentication remains the supported
privileged inspection route; denied MCP-user access is not bypassed.

Findings were delivered by active-turn steering to the EXISTING source-only
checker session6330face-7cfb-43d8-89ff-2906f64ef64a/execution2f8ab9fa-4eaa-40a3-8f74-471c71f1d789.
No new execution was started and none of its files were edited. It is correcting
the redundant post-scan verify_gates callback and removing the invented global
consumer-fence requirement, with real process-event regressions. Its new
privileged ABI remains source-only and uninstalled; no deployment dependency is
created from that proposal.

At16:11:57 the actual archive still had dev2065/inode7340415/23441521918bytes and
all pinned owner/mode/link/mtime/ctime values. Preparation owner500933/start757986989
still held its kernel lease in restored phase, activation/cleanup unavailable.
Full initial restore, original journals, B evidence, incumbent and fallback remain
protected. No further restore, candidate start, writer stop, merge, route switch
or cutover occurred. The actual application rehearsal, final fenced B catch-up,
consent/frontend/controller acceptance and latest-data fallback remain open.
The448/145/transcript415/journal/mode/link exceptions are unchanged.


## Follow-up: thread coverage and late-expiry correction

The16:21 independent review found process-leader-only coverage and an age check
before proof-file fsync. Neither is treated as a valid operational success.
The final one-off root reader now enumerates every observed /proc/PID/task/TID,
checks exe/cwd/root/fd/maps, records PID/TID starts and reports newly uninspected
tasks after traversal. No observed task is exempted by process name. The resident
uses that same inspector unprivileged and requires each protected denied task's
exact identity to appear in the independently authenticated root witness.
Neither scan claims a global future-open barrier. The original helper and all
old receipts remain untouched; old leader-only receipts cannot satisfy schema2.

This is a temporary correction to the exact manual read-only inspection already
required for the one approved archive, not installation/adoption of PR234's ABI.
It has no arguments, no subprocess/service/security operations, reads only the
fixed preservation manifest/target metadata and /proc, and cannot remove data.
Source: scripts/deployment/receipts/excluded-incident-archive-consumer-check-threads-readonly.py.
SHA256 e176f8397319fb34306c6892178c5dfae9d37b127cba7bbdb1c31ffea22ae47a.
The actual protected-process run remains unperformed pending operator authentication.

The continuation checks receipt age again AFTER proof-file fsync, immediately
before unlink. A regression delays a real fixture-file fsync across expiry and
verifies the fixture archive remains. Additional fixtures detect an archive FD
owned only by a nonleader task and explicitly report a new task during traversal.
All six focused regressions pass; they do not certify protected host visibility.
Ops governance passed. pnpm run format was attempted but cannot run because the
isolated sparse tooling checkout has no package.json. No unrelated build ran.

The successful16:19 native/B hashing is retained in
scripts/deployment/receipts/single-incident-preparation-completed-1619.safe.json.
It is explicitly parent-attested from resident2084790/tool-output8d1e52, not a
new independent root receipt or a claim of newly rehashed B bytes. The corrected
resident reuses those exact verified hashes only while the exact original native
inode/size/owner/mode/link/mtime/ctime and pinned local dependencies still match.
This avoids repeating valid bulk work; no backup or payload was created.

Corrected resident2255906 (tool session93793) has reached the sealed wait with
its archive FD closed; all B/network/process-spawning preparation is complete.
It waits for a NEW schema2 operator receipt at excluded-incident-archive-operator-
consumer-clearance-after-preparation.private.json and actual authenticated
operator completion/digest from the existing Staging execution. Do not feed it
an invented confirmation or an old receipt. No further SSH/hash or general gate
callback may run after final clearance. If it exits, persisted readiness is not
live ownership and must not be used to authorize retirement.

Exact next operator command, only after parent confirms this resident remains
ready and all orchestration is prepared, in the EXISTING MCP terminal:

```bash
(umask 077; set -o noclobber; sudo /usr/bin/python3 -I -S -B /mnt/vk-storage/vk-runtime-backup-20261009/excluded-incident-archive-consumer-check-threads-readonly.py > /mnt/vk-storage/vk-runtime-backup-20261009/excluded-incident-archive-operator-consumer-clearance-after-preparation.private.json)
```

This creates no installation or persistent grant; operator authentication is
necessary because MCP-user access cannot inspect protected thread descriptors.
No existing evidence file may be overwritten. After actual operator completion,
Staging authenticates the new receipt and sends only its digest/completion ID to
the same resident. Its bounded in-process checks remain fail-closed. All later
application/rehearsal/catch-up/promotion/fallback gates are still separately required.


## 17:51 administrator handoff verified; installation entrypoint not invoked

Seamus's17:51:33 completion, Sentinel_7584cfaa11d481919cda44916f8856a7,
authorizes no assumption of successful installation. The exact124669-byte
installer matches SHA6d7db4427a7fed2e056ca28ca71057b99a7cc6cb719c74b99a25b7b778c6a6e3;
its embedded29af1c33 plan and all8source/2binary payload pins verify.

Read-only MCP sudo journal evidence authenticates the advertised path/hash/plan/
flags at17:51:23.867218UTC, with root session opened17:51:23.869090 and closed
17:51:23.937097. No password, credential, full bootstrap argv or private transcript
was printed or published. Sudo wraps arguments containing spaces in quotes; that
logger framing was decoded before parsing the bootstrap, not mistaken for an
operator quoting error. The actual logged exec globals are {"name":"main"},
where the documented bootstrap requires {"__name__":"__main__"}. A harmless
isolated reproduction confirms the former does not invoke the main guard and
the latter does. The installer entrypoint was never invoked. We do not infer
whether rendering/copying changed the text or blame the operator.

Both fixed launchers, both libexec payloads, both policies, the sudoers include
and managed anchor are ENOENT. The SSD UUID remains the approved26e4cac1-f2cf-
485b-b1bc-d1be197a747e. No root installer is running. This is not a denied sudo
or an absence of operator authentication: root authentication succeeded, but
installation effects are absent. No SDK sudo retry or alternative privilege
route was attempted. Neither installed profile's real acceptance has run.

Root owns the corrected already-approved administrator handoff. No new scope,
grant or installation approval is required; the identical payload/plan remains
valid. Staging has not asked for another manual consumer snapshot or root command.
Current blocker: the authorized installer must actually call its main entrypoint
through the existing operator-controlled administrator route, followed by exact
installed metadata and both automatic read-only acceptance checks. Do not silently
reinterpret the17:51 completion as installation/acceptance.

For later integration, four immutable unprivileged adapter/acceptance/owner
modules from publishedPR234 a875ccfe2d7ac094a93422cacd2a24d9a0f7803e are compiled
and hash-bound in inspection-adapter-source-a875ccfe under vk-runtime-backup-20261009.
This is source preparation only, not operational adoption. OP's worktree/index
is untouched. Its finishing execution had completed before active-turn steering
was attempted; the endpoint returned409, and no new execution was queued.

Obsolete manual resident2255906 has already exited; no action or cause is inferred.
Its successful16:19 native/B preparation and all prior evidence remain retained.
Fresh peer/kernel-lease probing verifies preparation500933/start757986989 still
restored, activation/cleanup unavailable. Archive dev2065/inode7340415/23441521918
and pinned metadata remain unchanged. No archive deletion, service stop, writer
fence, restore, routing switch or cutover occurred. Remaining operational gates
and historical448/145/transcript415/journal/mode/link exceptions remain explicit.
See scripts/deployment/receipts/two-profile-installation-not-established-20261009.json.

The former manual snapshot command and waiting-resident instructions above
are superseded. Do not rerun that command or resume that exited resident.
At18:15:39UTC all8installation targets remain absent. The smallest correction
is to invoke the exact reviewed installer main entrypoint through the same
operator-controlled administrator handoff; no new permission or broader payload
is needed. Root coordinates that correction. Both real automatic profile
acceptances must then pass before integration or the approved one-file retirement.
