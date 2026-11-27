# Workspace archival, revival and Nightly separation

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
- `nightly_selection.py`: scoped cold-generation custody, coherent SQLite API
  image, active-path filtering and independent SQL/cold-reference recovery
  validation. Exclusions invalidate on retained messages, history-read intent,
  generation changes or reappearing local paths. The external owner contract
  supplies required SQL/catalog/shared sources; a backup cannot choose its own
  minimum scope. This contract is not yet wired into the installed Nightly cycle.

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

The trusted physical driver, complete production ownership/Git/attachment closure
and Nightly consumer remain unfinished. Runtime configuration stays absent in
production until those dependencies and the combined release are qualified.
Native metadata snapshots alone do not establish process or dependency custody.
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

The full67-test Python suite passes with the actual maintained Nightly modules supplied.
After moving remote checks outside live SQL transactions, all12 focused Nightly
selection tests pass, including a concurrent SQL commit during B metadata reopen. Coverage
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
