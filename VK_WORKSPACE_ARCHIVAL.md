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

## Source implemented in this change

`20261125000000_workspace_archive_requests.sql` adds an archival-intent outbox.
It seeds existing archived workspaces and records future archive/unarchive
transitions in the same SQL transaction as the flag change. A no-op archive
does not duplicate work. Revival/rearchive increments the request generation,
so a mover can reject obsolete copy results. This is an intent queue only:
it dispatches no job, moves no files and grants no backup exclusion.

`scripts/workspace-archive/inventory.py` reads one coherent application SQL
snapshot and a separate native-history metadata snapshot. It resolves workspace
and session ownership without transcript reads or a recursive payload scan.
It identifies pinned/running/input/lease holds and shared or unresolved native
history/worktree ownership. The snapshots are not an atomic cross-database
custody boundary; actual writers and sources must be checked at action time.

Read-only production inspection on November25 found 1,296 workspaces:
1,052 archived and244 active. 1,016 passed the implemented metadata filters.
These are candidates for further qualification, not movement clearance.
No live SQL migration, archive dispatch, payload movement, Nightly change,
backend restart or sealed-package modification was performed.

## Remaining implementation and acceptance

The mover, verified archive catalog, send-triggered restoration, cold-history
read path and Nightly consumer are **not implemented by the outbox**. They must
be connected before the feature is called ready or any live source is retired.
The existing backend still only sets the archived flag/runs repository scripts.

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

Eleven fixture tests cover SQL transaction rollback, initial backlog seeding,
future archives, no-op idempotence, revival/rearchive generation changes, owner
deletion, active/pinned/running protection, pending inputs/leases, shared or
unresolved native/worktree ownership, and missing-schema failure. These tests
do not certify transport, restoration, UI or production deployment.

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/workspace-archive -v`.
The inventory CLI is read-only. Its output explicitly denies movement and
backup-exclusion authority; it is not a deletion allowlist.


Ops and whitespace checks pass. Rust formatting passes. Full
`pnpm run format` stops at the existing missing Prettier executable.
No backend build or production migration was run for this source-only step.
