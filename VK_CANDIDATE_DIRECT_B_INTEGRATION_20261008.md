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
