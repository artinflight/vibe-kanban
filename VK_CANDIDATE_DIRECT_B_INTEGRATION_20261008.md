# Offline candidate/direct-B integration, October 8

## Exact scope and preservation

Independent branch `fix/candidate-direct-b-integration-20261008` extends local
candidate controller `be704f9ce1a3e858f3410d0ea2780c8a362468c7`.
All 40 deployment Python modules and the corrected routing-triage file from
PR229 head `754129c5fff55da2f5598d8c7beb4d4325587ead` match OP's source byte for
byte. Its eight reviewed source pins match the retained receipt. This checkout
needed the existing PR149-equivalent tools as a baseline; it is **not** a new
prerequisite merge or a replacement combined application release.

Root should apply only PR229's focused commits
`47d4293fe95191363eeef509d6b0e78b772ab946` and
`754129c5fff55da2f5598d8c7beb4d4325587ead` to its existing PR149-equivalent tools,
then these candidate-only changes. Do not replay this whole baseline patch onto
the already prepared combined source. PR150/153/223/225 and the phone frontend
remain the combined release scope; their fresh combined tests/binary/package
binding have not passed here. No workflow, OP source/worktree, shared checkout,
service, route, credential, security setting or incumbent data was changed.

The original 149-file B overlay remains authoritative retained evidence:
`B:/vk-backups/vk-safe-release-20261008/combined-source-overlay-20261008T193251Z.tar.gz`,
SHA256 `5b0af111571450643b47ab95f4df71018d03ff43abde82bc8571e0bdbef0821e`.
Earlier be704f9c/733371a8/1932ff47 patches, bundles and receipts remain retained.
The private partially merged application source/index is not a usable release.

## Actual contracts exercised offline

`vk_candidate_direct_b.py` consumes the unchanged actual PR229 capture/archive
formats. It verifies the published descriptor digest, exact plan/scope, entire
parent chain and complete archive streams before accepting an index. Replayed
bytes are independently hashed. Selected files stream once per contributing
archive, with EOF verification before accepting the restore. Missing members,
traversal, unsupported metadata, corruption and forged fence records fail closed.
The fixture backing archive store is explicitly local; no real B transfer or
production backup was performed this turn. Capture metadata directories retain
zero archive/snapshot payloads; the separate retained fixture store holds its
own small archive payloads and is not claimed to be zero SSD storage.

The bound supervisor checks real held kernel leases plus current source, scope,
root and capture receipts. Fixture policies/acceptance cannot be operational
proof. Rehearsal, final fenced catch-up and latest-data fallback use the same
candidate roots. Test edits and superseded state are retained in quarantine.
After snapshot normalization, acceptance is read again against current data;
stale receipts cannot authorize promotion. Cleanup always raises a blocking
error. Default operational activation and fallback methods remain unavailable:
actual VK/CU/native worker stop/launch ownership and packaged scanner/controller
acceptance must be supplied and tested by the owning release controller.

For mode0555 quarantine, the controller moves a writable ancestor below the
candidate root with its readonly descendants intact. Tests verify the retained
readonly directory's mode and inode, reconstructed current content and unchanged
root binding. Closure includes cross-subtree hardlinks and full moved subtrees.
No existing permission is relaxed, no denied child move is attempted, and no
candidate-root replacement occurs. If no writable ancestor exists below the
root, refresh blocks before moving anything. Any such real path needs an
approved preservation strategy; a denied action is not retried by another route.
A large moved ancestor increases retained quarantine capacity and must enter the
peak-space measurement. This new design has offline regression evidence, not a
new independent human/reviewer sign-off or live permission acceptance.

Built-in restoration/comparison covers current UID/GID, mode, mtime, POSIX ACLs,
user xattrs, symlinks and hardlink groups. All PAX headers stay authenticated in
the original archive. Atime is not restored by this prototype; ctime/birthtime
and original inode identities are not reproduced. Foreign ownership, privileged
modes, special files and unsupported xattrs block. The full required Linux
metadata gate cannot be asserted from these partial checks. Root needs an exact
required-metadata policy and verified lawful full-state adapter before acceptance.

`vk_candidate_package.py` wraps the unchanged PR229 package builder for a NEW
tool package. It binds the five candidate modules and packaged review receipt
alongside all eight upstream pins. Its receipt explicitly says combined backend
binary binding and operational acceptance are false. Empty archive inventories
are fixture-only. This tool bundle must never be labelled a deployable combined
application package or a whole-state restore rehearsal.

## Validation and consumed owner evidence

32 controller/scope regressions and 10 actual direct-B contract regressions
passed under Python `-O`. Coverage includes real GNU tar/zstd/SQLite capture,
ACL/xattrs/modes/links, checkpoint/delta replay, final writes, retained test edits,
latest-data fallback, a released kernel lease, corrupt archive, forged descriptor,
stale acceptance, EOF failure and default launch prohibition. A real reviewed
kernel namespace probe also passed: original absolute workspace links resolve
inside candidate roots, host writes are denied and host manager access is hidden.
Three package-binding regressions also passed, including actual packaged pin
loading and mutation rejection. The 32+10 contract cases passed again from the
fresh tool package: 51 files, five candidate modules and eight reviewed source
pins are bound. This is 45 unique regressions, not 87 distinct cases. No real
VK/CU/native process, scanner, consent acceptance or whole-state restore was
exercised. See the redacted
[offline receipt](scripts/deployment/receipts/candidate-direct-b-offline-20261008.json). Retained test failures were test-expectation errors or correctly
rejected stale evidence; they were corrected without relaxing acceptance checks.

All deployment Python files compiled without generated caches. Direct
`node scripts/check-ops-playbook.mjs` passed. The already installed nightly
rustfmt checks the exact copied triage source. `pnpm run format` was attempted
with network disabled and failed because this sparse tool checkout has no
package manifest; no dependency or toolchain install was performed. Full
application check/lint/workspace tests and combined CI remain unrun here.
The baseline diff also reports an inherited extra blank line at EOF in exact
PR149 legacy_capture_fixture.py; those upstream bytes were preserved rather
than silently changed or labelled a formatting pass.

OP session `19628b6a-1c41-49d1-8509-0ca2a3517ea2` was consumed read-only.
Its corrected [PR229](https://github.com/artinflight/vibe-kanban/pull/229)
[exact CI run 37840304123](https://github.com/artinflight/vibe-kanban/actions/runs/37840304123)
passed 399 backend tests with seven skips; remote validation still skipped the
missing deploy key. OP's 215 backup regressions, bounded live B smoke and
independent eight-source-hash review are reused, not rerun or upgraded to full
restore acceptance. The smoke observed zero local archive/snapshot bytes and
60 KiB sampled metadata, not a production-size memory/restore proof.

## Capacity and operational scope: reuse completed audit

The completed OP audit reported 87,687,933,672 logical bytes (81.67 GiB), 82.71 GiB
allocated before directory overhead; original 59 exclusions remain unchanged.
It includes 61.27 GiB histories, 2.49 GiB DBs/sidecars, 0.74 GiB attachments,
2.09 GiB Git metadata, 1.70 GiB possible build material, 0.06 GiB tools/plugins
and 13.31 GiB other unclassified material. No additional exclusion is certified.
The 74.56 GiB shared Cargo store lies outside that old scope. The existing
46-root configured-dependency proposal may add material and has no approved
scope reduction; root must reconcile it with this audit. Historical material
stays preserved on B irrespective of the final operational materialization list.

One full candidate is about 83 GiB plus directories, normalized DB buffers,
retained changed/test state and an 8 GiB working floor. OP proposed roughly
100 GiB minimum / 120 GiB Linux allocation, but full peak is unmeasured. Earlier
B free space was 317.5 GiB; proposed 96 GiB new backup plus 120 GiB allocation
would leave about 101.5 GiB before other growth. These are owner observations,
not fresh availability claims. No independent candidate/Linux storage allocation
or WSL provisioning is established here. Reusing the tested candidate removes
one second full restore; it does not remove quarantine/delta/metadata costs.

A new bounded read-only RAM check found this executor hard-capped at
3,145,728,000 bytes (3000 MiB), with a 1500 MiB high threshold. PR229 permits a
1 GiB single-DB image by default and may hold three copies: 3 GiB exceeds this
hard cap before Python, inventory and compression overhead. Host available RAM
and the incumbent's different cgroup are not candidate fit evidence. Production
capture needs a confirmed owner-environment memory budget and measured peak,
without silently expanding this executor or usage controls.

## Exact remaining gates and handoff

1. Desktop/B SSH has been verified working independently of Dot. See
   VK_RESTART_PROGRESS_20261009.md for the accepted fresh whole-state B backup,
   current source bindings and exact remaining approvals. Workflow authorization
   remains pending; no denied write, credential/route change or OAuth was retried.
2. Root binds the existing reviewed combined release to a fresh package and the
   actual native launcher, scanner, routing module, capacity guard/controller and
   supervision boundary. Confirm candidate allocation/RAM fit and account for
   the dependency proposal and readonly-ancestor quarantine peak.
3. With authoritative B available, perform fresh whole-state capture and restore
   into the independent candidate roots; authenticate all included files/DBs and
   required Linux metadata. Prepare dataset identity lawfully and regenerate its
   inode receipts after final catch-up. Obtain actual writer fencing and candidate
   consent/control/current-report acceptance before promotion of that same root.

448 unresolved names, 145 original-history ledger rows, transcript line415 and
journal/mode/link proof limitations remain explicit. The completed independent
review authenticated its bounded findings and withheld recovery-complete and
universal-zero-loss sign-off. Neither this source integration nor matched merged
functionality clears original-object/history exceptions. Cleanup remains
technically unavailable pending Seamus's human QA and separate scoped work.
No backend restart, cutover, merge, cleanup, live restore or production acceptance
occurred in this turn.

## Recorded missing links: preservation versus runtime acceptance

Fresh actual catalog inspection found575 missing virtual link targets;561 exist
on the host and14 are unavailable. Host presence is not a namespace dependency
proof. Preserve exact literals with explicit provider opt-in and manifest-bound
exceptions; do not read host targets during virtual resolution. Default validation
is strict. Operational selectors always resolve against the candidate inventory;
new dependency-closure acceptance is mandatory at every accepted stage. Metadata
restoration does not certify historical loss or current functionality.

The exception inventory counts toward the bounded metadata budget. Existing
archive/header/content authentication, hardlink metadata, archived-atime policy,
ownership/xattr restrictions, mode0555 quarantine, writer fencing and cleanup
prohibition remain enforced. No PR229 reviewed source file was edited.

## Explicit identity bootstrap after current-data reconciliation

New startup refuses a missing dataset token. Explicit CandidateController
bootstrap_identity requires a stopped restored/refreshed generation and an
authenticated standalone required DB, resolving paths only in candidate roots.
It creates the missing identity table atomically, never overwrites an existing
identity or enrolls original live state, and preserves DBinode/owner/mode.
Rehearsal identity is quarantined during fresh final catch-up. Final enrollment
changes phase to needs-bootstrap-backup; promotion remains blocked until
accept_bootstrap_capture authenticates a NEW frozen B generation with origin
bound to the SAME candidate and exact tracked post-bootstrap inventory.
This is an explicit transformation/accounting step, not startup auto-repair,
historical recovery acceptance or authorization to alter production data.

## Reuse of a verified full checkpoint index

VerifiedCheckpointProvider accepts only a hash-pinned, B-preserved full
checkpoint index and its exact verifier package/source. Its manifest must match
the recorded verifier result; operational reuse keeps the unchanged absolute
namespace and descriptor scope/generation. It freshly verifies the B index and
complete archive hashes, then replay drains the whole archive while per-file
content checks and full metadata/SQLite validation remain mandatory. This saves
a redundant full header/content-index reconstruction before the same-candidate
restore, not the restore or its acceptance. Deltas, changed captures, custom
operational readers, tampered indexes and unpreserved indexes fail closed.
Four real-archive fixture regressions passed, including canonical hardlink and
SQLite mapping, changed archive/early-consumption rejection and preservation
requirements. Operational cache use/whole restore is not yet exercised.

October 9 actual restore correction: the first MCP restore held before creating
the data tree because its blanket `-wal`/`-shm` name check matched a retained
ELF executable. The controller now requires complete authenticated archive
bytes, a native ELF header, executable regular-file metadata and no matching
base/required database before preserving such a name. SQLite/orphan/ambiguous
sidecars, links and changed content still block. Four regressions cover these
boundaries; actual retry and runtime acceptance remain pending.

The approved UID1000 B builder completed the exact c3c48e63 source/ d8bb5fb0
tree in its namespace. All 779 packaged files (325,645,508 bytes) matched hashes;
manifest SHA256 5e42276d17a512fdb712af65e7624d8ae4ced698255df114214e162caa2a51b4.
Candidate SHA256 2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f;
compatible fallback c6ebdd425e097f886cca8ae7781ddecb8b96cd96fde4e8c0f70362a5612faa91.
All 73 actual scanner contracts passed without skips. This proves packaging,
not deployment or live consent/controller acceptance.

The new read-only journal supported a successful fresh online checkpoint
63e06af56d7146dca8b2241651c90126 on B, with zero SSD archive/snapshot payload.
Capture measured about 2.4 GiB peak RAM in its 3 GiB limit. The earlier journal
gap and online changes remain explicit; a final held writer-fenced capture
and candidate catch-up are still mandatory.

MCP packaged acceptance, October 9 11:46 UTC: artifact transfer independently
verified all 779 files and the exact source/tree manifest. The actual candidate
server passed 18 private namespace startup/inspection/identity rejection cases,
including successful health and preservation of all workspace/image sentinels.
Its packaged executor passed 178 tests with eight opt-in cases ignored; the
separate offline-provider first-run success and two-worker stalled-stop cases
each passed through the actual guard/restricted supervisor. No paid inference,
production restart or live consent acceptance occurred. The exact packaged
scanner reported 8.30.1 inside the MCP boundary. All generated fixtures remain
retained.

The suffix correction has now passed authentication of the actual B executable,
and the same actual MCP tree began materialization at 11:45:37 UTC. No restored
content was excluded. Allocation, all-file/DB/metadata verification and final
catch-up acceptance remain pending; initial restoration is not a cutover.

Fresh staging is e8c450fb (main remains 22f09e24), with a workspace-first UI
change beyond the original combined release scope. The combined application
remains exactly c3c48e63; neither that unrelated UI change nor a merge is swept
into the built artifacts. PR231 currently reports a staging conflict and no
hosted checks; its 118 local candidate regressions passed from clean committed
source. PR230 Test CI remains green; its hosted artifact job still records the
namespace failure, separately from the successful approved isolated B build.
No CI status is forged or protection bypassed.

October 9 12:30 UTC: the fresh checkpoint `63e06af56d7146dca8b2241651c90126`
has passed full direct-B provider verification: 77 original roots, 76 databases,
538,717 manifest rows and authenticated archived atimes. Its 217,590,892-byte
private index is separately hash-verified on B, SHA-256
`3bfdc5d503aa3be39f8bbb354c9ffe98e2da07fcf7704677f9842133b2681431`.
All 588 recorded missing-link literals remain explicit. This online capture is
not a final fenced boundary or operational dependency acceptance. The actual
initial candidate restore remains running and has not launched a backend.

The owning controller now provides explicit recovery of **only one completed
initial restore**. It reauthenticates B, independently requires stopped ownership,
rechecks every file/DB/metadata relationship and retains the prior journal. It
rejects interrupted/later operations, changed data, live writers and source/root/
manifest mismatch. Recovery returns only `restored`, with no rehearsal/activation
acceptance. Five regression cases passed; this handoff has not been used on the
actual still-running restore owner.

The frontend scope above is superseded by Seamus's explicit inclusion instruction.
Final `66e00728` supplies twelve frontend product changes that do not overlap the
six newer consent/chat repairs already in c3c48e63. A separate frontend-only
overlay preserves both sets; the backend, guard and routing module stay pinned.
Combined frontend TypeScript checks passed for local-web/web-core/UI. Packaged
browser acceptance, actual candidate binding and routed/phone acceptance remain
pending. The standalone 66 package cannot replace the combined frontend because
it lacks those newer consent repairs.

Read-only comparison of the two authenticated indexes proves an additional
capacity requirement; see [the exact one-file exception request](VK_CATCHUP_CAPACITY_EXCEPTION_20261009.md).
No further retirement is authorized or performed. The original incident archive
and metadata have been bitwise preserved on B without converting the failed
capture into accepted recovery evidence. All historical exceptions remain open.

## October 9, 13:10 UTC correction and current receipts

The preceding no-authorization statement is superseded by the recorded 12:38
owner approval for the single pinned incident archive, and only that archive.
The independent operator consumer receipt is still absent. Approval is not
clearance; no additional retirement, permission change or live effect occurred.

The full initial materialization stopped at its final inventory comparison.
Read-only diagnosis found exactly 537,645 expected and actual names, with no
non-link metadata differences. The 225 differing rows belong to 67 hardlink
groups; every expected alias has the correct actual inode relationship. The
checker chose the first depth-first traversal name, whereas the authenticated
archive uses the lexically smallest full path. These orders differ, for example,
between `z/file` and `z-/file`. Canonicalizing full-path order corrects the
representation without changing bytes, ownership, modes, timestamps or links.
The exact restore failure and private diagnostic remain retained. No partial
restore is accepted, no journal is manufactured, and content/DB re-verification
is still required before this same candidate can be rehearsed.

The new regression restores this adversarial hardlink layout and verifies both
the exact manifest and real inode relationship. Initially 122 of 124 candidate
tests passed; two package tests correctly refused uncommitted source. They must
run again from clean committed source. `pnpm run format` was attempted and cannot
run in this sparse tooling checkout without a package manifest. No dependencies
or toolchains were installed to mask that limitation.

Final combined frontend source is PR230 head
`5ce84ee21be814b1519cfb2715b50f3432c3e8ba`, incorporating the authorized
66e00728 frontend and retaining the newer combined consent repairs. Its freshly
built package contains 923 files / 98,449,195 bytes, including 158 preserved
prior runtime assets with zero conflicting runtime hashes. The prior diagnostic
maps remain preserved at their original roots and in full B backups.
The package is independently hash-verified at
`B:/vk-backups/vk-safe-release-20261009/combined-frontend-5ce84ee2/combined-frontend-5ce84ee2.tar.zst`:
28,066,372 bytes, SHA-256
`1cf30db81af3d96abdbfa6ee09f39484d7adb2ad09b5eed74ad40889d64c352a`.
No local archive payload was staged. The older 7810706e package remains retained
and superseded. Backend/guard/routing artifacts remain pinned to c3c48e63.
See [the redacted package receipt](scripts/deployment/receipts/combined-frontend-5ce84ee2-safe.json).

Fresh Test run 37932897941 is in progress; its frontend checks have passed.
Separate artifact run 37932898022 failed on the hosted runner's
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` prerequisite.
No bypass or manufactured CI status occurred. Secure local Chromium startup
also exited with SIGTRAP before UI acceptance; its cause remains unknown.
Candidate/cutback frontend binding, mobile DOM and live consent acceptance,
final held writer fencing/catch-up, measured fallback headroom and promotion
remain unrun. PR230 and PR231 are draft and unmerged. Historical recovery
exceptions remain unchanged; these source/package receipts are not deployment.

The canonical ordering correction passed all 124 candidate tests from committed
source c15da3ff, which is pushed and independently matched to the remote branch.
Its non-fixture tool package verifies 63 files, six candidate modules and all
eight original PR229 pins. Full read-only verification of the retained actual
tree is running with that package; no controller journal has been written.
Exact PR230 Test 37932897941 subsequently completed successfully at 5ce84ee2.

A separate explicit initial-materialization verifier now supports only an empty
journal and held stopped ownership. It reauthenticates B and every actual file,
database, metadata and root identity before recording a new verification; it
does not reconstruct the failed attempt, restore files again or grant rehearsal
or activation acceptance. Authenticated archived atimes are applied only after
successful content verification. Partial/changed data, live writers, bad B
bindings and existing journals fail closed. Four focused new regressions pass;
this method has not yet been used on the real candidate. Existing completed-
journal recovery remains separately restricted and unchanged.

October 9 continued validation: all 128 candidate regressions passed from clean
committed source 80754950; ops governance passed and the exact remote branch SHA
matched. Both unchanged pinned MCP candidate and compatible fallback servers
served 163 final frontend paths with matching hashes inside private filesystem,
PID, network and manager boundaries. Coverage includes root and /workspaces HTML,
entry JS/CSS, versioned manifest and all 158 retained runtime assets. Empty
private fixtures were used; this is runtime/frontend compatibility, not launch
or path binding of the actual restored candidate. See the
[redacted two-runtime receipt](scripts/deployment/receipts/final-frontend-both-runtime-20261009.json).
The original secure-browser SIGTRAP remains unexplained. A minimal empty-profile
probe of the same browser in a private network/filesystem boundary initialized
without that signal, but timed out before DOM proof; no sandbox was disabled and
no browser acceptance is claimed. No additional archive retirement occurred.

At 13:23 UTC the retained actual MCP candidate completed corrected full
verification: all 537,645 manifest rows match, and all 76 database integrity checks
passed. Runtime was 858 seconds with a 4 GiB unit memory peak. No content was
restored again or overwritten, and no prior failed journal was manufactured.
See the [redacted actual-tree receipt](scripts/deployment/receipts/actual-initial-materialization-reverified-20261009.json).
This verifies included content, modes, ownership, mtimes, ACL/xattrs and actual
symlink/hardlink relationships against the authenticated baseline index.
Archived-atime restoration and fresh B authentication remain necessary before
controller adoption. The 589 original link exceptions and unavailable historical
inode/ctime/birthtime metadata remain explicit. This is not operational rehearsal,
current fenced data, recovery-complete acceptance or permission for promotion.

At 13:27 UTC a new held, non-activating owner began fresh B authentication and
full initial-materialization verification including archived-atime restoration.
It uses immutable tool source 5783d3eb, the same actual tree inode 10354932 and
original held lease. Unit `vk-materialization-adoption-5783d3eb.service` is in
`vk-release-preparation.slice`, outside app.slice. Its status/ownership adapter
cannot launch a candidate, fence production, switch routes or clean up. Its
ongoing state is private at
`/mnt/vk-storage/vk-runtime-backup-20261009/actual-MCP-initial-materialization-adoption-progress.json`;
no successful adoption or atime result is claimed yet.

Actual unique native allocation is 95,405,559,808 bytes / 522,757 inodes.
Available space at that measurement was 8,664,621,056 bytes: only 74,686,464 bytes
above the protected 8,589,934,592-byte reserve. Catch-up remains blocked; this is
measured allocation, not an estimate of post-retirement capacity. The operator
consumer receipt is still absent at 13:28 UTC, and the approved one-file archive
has not been retired. The helper hash still matches its published pin.

The immutable source package, verification/diagnostic receipts, final frontend
manifest, allocation and consumer helper are independently read-back verified
on B in `preparation-5783d3eb/candidate-preparation-5783d3eb.tar.zst`: 75 files,
237,497 bytes, SHA-256
`525562afd01772ac10d29a7e3665a6a82ae07bab02f3e123ae95cae2c9aff031`.
No local archive payload was staged. See the
[redacted B receipt](scripts/deployment/receipts/candidate-preparation-5783d3eb-B-20261009.json)
and [measured allocation](scripts/deployment/receipts/actual-initial-candidate-allocation-20261009.json).

Git parity receipts: application/frontend PR230 head 5ce84ee2 is published and
exact Test 37932897941 passed; tooling PR231 heads 80754950 and receipt checkpoint
5783d3eb are pushed and independently matched to the remote SHA. The original
registered f36e6f10 publication is the owner's dated read receipt, not a new
identity/recovery claim here. Unfinished isolated checkpoints are the held actual
candidate verification/adoption, final frontend runtime-path/live acceptance,
consumer clearance, final writer-fenced catch-up and latest-data fallback. No
mutable candidate payload, browser profile, cache or private transcript is being
published to GitHub. Original c15/807/578 packages, failed attempt and superseded
frontend outputs remain preserved. No restart/cutover/merge has occurred.
