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
