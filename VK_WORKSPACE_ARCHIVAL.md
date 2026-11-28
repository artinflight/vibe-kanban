# Workspace archival, revival and Nightly separation

## November 28 integration checkpoint — still not qualified for cutover

The finite production `driver.py`, serving-pair/config/resource qualification,
normal-B provider factory, and metadata-only process-inspector client now exist.
Archive streaming checks newly committed inputs and yields before retirement.
A source-only root inspector and create-only installer are prepared; no sudo
policy/helper has been installed. The external manager must install the reviewed
capability before actual host process-clearance qualification can run. Existing
inspectors cannot cover this scope. No security setting or service was changed.

The exact maintained Nightly source at d419d85f4 is now contained under
`scripts/nightly-owner/` with an upstream file-hash inventory. Its ordinary service,
current-map finalizer and independent SQL consumer have optional archive integration.
Shared cold custody and current catalog references are checked before acceptance;
current SQL/shared sources remain mandatory. A pending revival now blocks a new
backup until its absent bytes are restored instead of being mistaken for empty
active work. Current-map removal still follows the existing journal; there is no
second archive converter, source sweep, schedule, controller or new body codec.

The 119-test combined archive suite passed with this contained Nightly source.
The changed Nightly consumer and service suites each passed 14 tests; normal
composed restore passed 7. These are source/local-transport evidence, not actual
Desktop B or whole-release acceptance. The offline shared-target backend build
completed. Its source pin is b2330ee1f; later script/frontend integration is recorded
separately and must be sealed together in the final release manifest.

The actual public frontend snapshot contained shipped changes absent from staging,
including GPT-6.2 menu behavior and read-later/sidebar/preservation UI. A clean
three-way reconciliation preserved those live changes plus the new archive UI.
The preservation gate now passes all 1,327 pinned live inputs with only nine
reviewed archive/staging differences. The candidate frontend build passed. Complete
runtime/fallback/B restore/UI qualification remains open. Initial frontend build
exceeded a 1536MiB heap; the preserved build uses a bounded 3072MiB heap.

Private source/build/test evidence and the exact inspector installation manifest
are under `/mnt/vk-storage/vk-archive-release-20261127/`. The inspector handoff is
one installation prerequisite, not a cutover-ready release or restart approval.
Actual paired-reader tests, Desktop B restoration, compatible current-data
fallback, resource/performance proof, current Nightly configuration, CI/staging
publication and the executable combined handoff remain unfinished. Nightly stays
OFF and production restart/cutover remains exclusively with the external manager.


## Operator decision — 2026-11-25

Archive separation is now authorized preparation work, including automatic
movement on future archive actions and automatic revival when the user sends a
message. This supersedes the earlier exclusion of deferred workspace archival
for this concern. Nightly schedule activation and a backend restart remain
separate. The actual backend restart belongs to the external managing agent,
not an agent running inside Vibe.

Prepare and qualify the combined behavior before the managed restart. Physical
retirement of live workspace payloads can begin only after compatible revival
and history readers are actually serving. The sealed, unarmed dedup-only
activation package is not evidence that this additional feature is included.
Do not modify its source pins or silently activate it as the combined release.

## Required behavior

- The normal Archive action records durable intent. The existing archived
  population uses the same process once; future archive actions need no repeated
  operator cleanup project. Repeated unchanged requests are idempotent.
- Archive payloads go to canonical Desktop B storage with the complete recovery
  dependency set, Linux metadata and verified normal restoration. Preserve
  shared immutable content through existing catalog locators where possible.
  Local retirement follows verified recovery, current ownership and reader
  acceptance; an archived flag, age or copied filename does not qualify it.
- Preserve workspace/session/native identities, original history, code and Git
  state, attachments, settings, queued inputs, approvals and accepted backup
  epochs. Running, pinned, dirty, shared or unresolved data remains protected.
  A metadata inventory is not live custody. Native child threads and shared
  provider/Git/attachment dependencies must be accounted for explicitly.
- Sending to a cold workspace durably retains the exact message and selected
  settings, restores and verifies the workspace, then resumes through ordinary
  admission. Do not create a fresh agent that loses context. Interrupted or
  uncertain dispatch is reconciled using its existing identity, never replayed
  blindly. Desktop offline leaves input recoverable and reports restore status.
  Concurrent sends and archive requests must not lose input or dispatch twice.
- Archival also preserves a discoverable catalog and usable history UI.
  Both serving readers must support the cold-history state; missing local files
  must not become an empty conversation or a recreated empty workspace.
- Nightly backs up active workspace payloads and the current SQL/catalog/shared
  recovery dependencies. Cold payloads remain separately restorable on B and
  are referenced, not recopied each night. Exclude only a verified, current cold
  generation. A restore/new message invalidates exclusion until its current
  active data is included. Do not enable a Nightly that silently skips
  unverified archived work or recaptures the undeduplicated backlog.

## Source implemented (not deployed)

The intent outbox seeds existing archived workspaces and records subsequent
archive/unarchive transitions in the same transaction. Current physical state,
immutable recovery generations, exact revival inputs and operation journals are
separate. A UI flag or incomplete physical transaction never grants exclusion.

`scripts/workspace-archive/` now contains:

- `inventory.py`: coherent application/native metadata inventory, including
  transitive child ownership. Open, shared, conflicting, cyclic or unresolved
  native child records remain protected. This is not process custody.
- `catalog.py`: short transactional generation transitions, immutable recovery
  epochs, exact input retention and single reserved ordinary execution identity.
- `custody.py`: permanent per-workspace Linux flock inodes; readers share custody,
  movement/restoration requires exclusive custody, unrelated workspaces proceed.
- `payloads.py`: stable byte/metadata manifests, bounded independent restoration,
  create-only publication and exact-member retirement with no generic tree delete.
- `lifecycle.py`: copy intent, independent restore, journaled source retirement,
  interrupted-operation reconciliation and same-path revival. Partial staging is
  retained and counted by resource admission. New destinations are not overwritten.
- `normal_b.py`: existing Nightly native B object capture, immutable selected
  indexes, control checkpoints and normal decoder. Source pins, existing leases
  and operator connection settings remain required. No new backup transport.
- `git_dependency.py` / `shared_dependency.py`: real clean-worktree and private
  administrative identity checks, independently restored shared Git graphs and
  reuse of verified commit/tag coverage across workspaces. Shared repositories
  stay in place; unrelated branch changes do not recapture an already covered
  graph. New workspace commits get a new immutable point. Dirty/untracked work,
  unfinished Git operations, filters and unqualified external/submodule objects
  are protected. Durably removed worktrees still retain their shared branch
  recovery graph; their absence does not erase that dependency.
- `ownership.py` / `process_use.py`: exact current application/native/repository
  bindings, overlap and dirty-work protection, and process cwd/open/mapped-file
  checks. Custom outer-workspace files and external aliases remain protected.
  This is a read-only ownership contract, not privileged host clearance.
- `shared_files.py`: immutable normal-B points for shared attachments, verified
  independently before reuse; missing-file recovery preserves later uploads and
  refuses to overwrite changed shared files. Shared attachment roots stay live.
- `controller.py` / `authority.py`: one finite operation reconciles the current
  journal, composes ownership and shared recovery, and verifies dependencies
  before retained input becomes ready. Lost capture receipts reuse the same
  operation. No daemon, dispatch loop, service change or replacement controller
  is created. The source-pinned Host/factory now exists; installed process clearance and live qualification remain open.
- `nightly_selection.py`: scoped cold-generation custody, coherent SQLite API
  image, active-path filtering and independent SQL/cold-reference recovery
  validation. Exclusions invalidate on retained messages, history-read intent,
  generation changes or reappearing local paths. The external owner contract
  supplies required SQL/catalog/shared sources; a backup cannot choose its own
  minimum scope. The maintained service/finalizer/consumer source now uses this contract; installation and actual cycle qualification remain open.

The normal-B adapter uses the maintained Nightly source closure, currently tested
against d419d85f4f5652a36f9372feaa889d59e4ee8079. Its source/configuration must be
included and pinned in the combined release; a mutable external checkout is not
release qualification. Connection/source/lease changes require reconciled owner
bindings, not accepting executable settings from a backup record.

The backend now retains exact inputs before recovery and binds ordinary dispatch
to one reserved execution ID. Request UUIDs survive uncertain browser responses.
Only the matching execution receipt resolves an interrupted dispatch. A saved
message remains visible while restoring or held; unreserved messages can be cancelled.
Normal follow-up and stale queue UI submissions share this admission contract.

`utils::workspace_custody` shares the Python kernel lock protocol. Full raw and
normalized history streams retain custody through lazy reads; launch/worktree and
review paths acquire it before global admission. The writer's optional pinned
runtime invokes a physical driver outside global admission. Protected readers
consult its current catalog read-only and request restoration over the existing
loopback writer route. Both roles recheck cold state under shared custody.
`workspaceArchiveCustodyProtocol` in build-info supports qualification against
actual binaries; its presence alone is not evidence of a deployed configuration.

Ordinary worktree recovery also refuses populated or aliased destinations when
Git registration/branch identity differs. It no longer treats that discrepancy
as authorization to erase local source. New absent worktrees can still be created.

## Remaining implementation and acceptance

The finite controller, authority composition and shared Git/attachment contracts
are implemented and fixture-tested. The source-pinned Host/factory and Nightly consumer source are integrated.
Installed process clearance and actual whole-cycle qualification remain unfinished. Runtime configuration stays absent in
production until those dependencies and the combined release are qualified.
Native metadata snapshots alone do not establish process or dependency custody.
On November 28, ordinary `/proc` inspection was denied for the user service
manager and some sandboxed processes. `process_use.py` refuses to call that clear.
The installed digest-approved `vk-process-inspect-v1` accepts only its managed
artifact scope; `vk-historical-archive-inspect-v1` accepts one fixed old backup.
Neither provides workspace-path clearance. Do not reuse those sudo permissions
outside their root-owned policies, exempt unreadable processes by name, or change
host security settings to make a test pass. The production qualification must
resolve bounded workspace process inspection and test it in the actual host
context. Fixture process lists in tests are explicitly not that proof.
The selection contract must be connected to Nightly's recorded namespace/current
map and normal current-set acceptance; importing the helper alone is insufficient.
The existing Nightly source owner, cursor, retained STOP/STARTED and schedule stay
unchanged. Metadata reopening currently uses bounded serial normal contexts;
whole-population performance still needs qualification with the final owner.

Use the maintained Desktop backup transport/catalog instead of another backup
service. Keep bulk staging on mounted SSD. Hold only the exact workspace's
custody across transfer; do not hold global admission or the shared backup lock
for the entire archived population. Preserve existing dedup owners/receipts.
A revived workspace's new archive generation must retain earlier recovery
points rather than overwrite an accepted archive.

Acceptance must include actual B restore, both history readers, ordinary
send/review/settings, offline B, failed/corrupt transfer, interrupted copy and
restore, concurrent sends, stale-generation rejection, source-change detection,
and a repeat archive with no duplicate capture. Nightly must demonstrate active
payload selection with complete SQL/catalog/shared closure and cold restore.
Qualify the combined candidate and compatible fallback before handing the
restart to the outside managing agent.

## Recovery and selection refinements

Actual host inspection confirmed that native/application histories and the common
Git repository are on a different filesystem from the SSD. Restore publication
therefore cannot rely on rename alone. Cross-filesystem recovery now retains
verified backup staging on SSD and writes final active-file inodes anonymously
on their destination filesystem. Only a complete hashed/metadata-applied/fsynced
inode becomes visible, through a create-only link. Exact publication intent is
journaled before directory creation. Directory construction and complete members
resume after interruption; mismatched members/unknown entries remain protected.
A final-destination resource admission is required in addition to SSD staging
admission. No system-disk backup copy is created. Verified publication is durable
before temporary-source retirement, allowing interrupted retirement to resume.
These changes are tested source, not deployed filesystem movement.

Physical preparation state and its original-path journal now commit in one SQL
transaction. Failure of the journal write leaves no orphaned `preparing` state.
A crash after intent can resume the same operation without another capture.

Normal B recovery reopens the immutable bundle and every selected index. An
archive retains its original provider/selected-index identity while using the
current qualified executable, connection and resource inputs. Old backup metadata
cannot select commands. New reader settings create new immutable control files,
preserving earlier files and epochs; ordinary software upgrades do not require
recapturing old bodies. Changing the logical provider remains refused.

Nightly selection performs remote metadata checks outside live SQL transactions.
Its SQL API image is bounded by explicit capacity/reserve admission and verified
against the exact cold references. Shared workspace locks prevent physical moves;
new user input still commits and invalidates the selection immediately. The normal
recovery validator requires the externally specified active/shared scope and
checks the independently restored SQL against each referenced cold generation.
These are source contracts, not an activated Nightly or actual-B acceptance.

## Validation

The preceding 105-test source milestone passed (49.251 seconds); the November28
combined suite now passes119 tests (93.322 seconds) with the actual maintained Nightly modules
supplied. This includes 12 Nightly selection checks, 8 real-Git dependency checks,
6 cross-filesystem recovery checks, 7 ownership checks, 6 finite-controller checks,
6 shared-attachment checks and 4 composed authority/revival checks. The composed
checks use actual Git/SQLite/filesystem data, exact retained inputs and shared
attachment recovery; host and B connections are fixtures. They do not certify
production service identities, privileged process visibility or actual Desktop B.
Final run evidence is recorded in HANDOFF. The cross-filesystem checks use small
disposable /tmp and /dev/shm fixtures on distinct devices; they are not production
or actual Desktop B acceptance. Concurrent SQL commits during B metadata reopen,
anonymous-file interruption, copy-intent interruption, interrupted staging
retirement, target capacity refusal and foreign data protection all pass. Coverage
includes SQL intent/generation/input concurrency, native descendants, shared
custody, exact bytes/Linux metadata/symlinks/empty files, interrupted copy and
root renames, offline/corrupt recovery, messages during retirement, newer local
destination protection and retained partial staging. Adapter contract tests use
Nightly's real capture/index/decoder across128-member boundaries, Unicode paths,
empty files and repeated body reuse. Their native connections and remote lease
verification are local fixtures, explicitly not actual Desktop B evidence.

Run:

```sh
NIGHTLY_SOURCE_DIR=/path/to/qualified/nightly/scripts/deployment \
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/workspace-archive -v
```

Without that dependency path, two transport-contract tests are explicitly skipped;
that result is insufficient combined qualification. Source identity and the exact
Nightly commit must accompany results. Actual B restore, production ownership and the full ordinary paired-reader/API/UI
rehearsal remain outstanding. Writer/protected-reader runtime tests use disposable
SQLite and a local HTTP/driver fixture, not the deployed application or actual B.

Ops, whitespace, full `pnpm run format` and backend compilation pass. Additional
Rust unit checks pass: 9 archive/revival, 2 kernel-custody and 3 worktree preservation,
plus 3 existing workspace-owner regressions. Generated types/check, all four frontend
type checks and changed frontend lint pass. TypeScript needed a 1536MiB heap; its
default heap exhausted before checking completed. No live migration, retirement,
backend restart or Nightly activation occurred. The early November27 SSD readback
of 2,910,162,944B predates concurrent cleanup and this build; it is not current
capacity. Recheck resource admission; never
weaken the reserve or remove required recovery evidence to pass admission.
