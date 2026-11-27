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

The normal-B adapter uses the maintained Nightly source closure, currently tested
against d419d85f4f5652a36f9372feaa889d59e4ee8079. Its source/configuration must be
included and pinned in the combined release; a mutable external checkout is not
release qualification. Connection/source/lease changes require reconciled owner
bindings, not accepting executable settings from a backup record.

There is no production movement CLI. The required production authority and
ordinary backend/history integration are still absent. These libraries therefore
cannot retire live workspaces merely because an archive flag was set.

## Remaining implementation and acceptance

The production ownership/dependency authority, backend custody and send-triggered
restoration, both cold-history readers and Nightly consumer still need integration.
The existing backend only sets the archived flag/runs repository scripts. Native
metadata snapshots alone do not establish process, Git or attachment custody.

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

## Validation

All52 tests pass with the actual maintained Nightly modules supplied. Coverage
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
Nightly commit must accompany results. Actual B restore, production owner and
both reader/API/UI tests remain outstanding.

Ops and whitespace checks pass. Rust formatting passes; full `pnpm run format`
stops at the existing missing Prettier executable. No live migration, retirement,
backend restart or Nightly activation occurred. November27 SSD free space was
2,910,162,944B, below the existing3GiB production qualification reserve; never
weaken the reserve or remove required recovery evidence to pass admission.
