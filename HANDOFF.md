# Pickup: finish real qualification, then hand off to the external manager

**Not cutover-ready.** Authoritative goal: complete the combined dedup/packed-reader/
archive/revival/Nightly release, not another source milestone. Five fixed outcomes
remain: archive lifecycle; revival/history; Nightly selection; combined candidate;
qualified staging/cutover handoff. Do not create a new goal or continuation loop.

## Working source and authorization

Use `/mnt/vk-storage/vk-archive-release-20261127/source`, branch
`vk/0815-archive-release`, operator remote `fork` (artinflight/vibe-kanban).
The user explicitly approved this task's source/tests/docs publication to that
public repository. Keep private histories/SQL/config/credentials/evidence outside
Git. `origin` is upstream: do not push there. Preserve unrelated dirty canonical
staging work. The managed0815 checkout was unexpectedly recreated; use this SSD
checkout and preserve committed work. The earlier narrative is linked below.

Native goal bookkeeping remains the old `clear` goal in paused state. Checkpoint
calls report no active goal. The publication hold was already resolved by Yes;
do not ask again or invent completion to repair that bookkeeping.

## What is implemented

`scripts/workspace-archive` contains the tested catalog, lifecycle, kernel custody,
current SQL/native/Git/attachment ownership, normal-B capture/recovery, finite
controller, physical driver and actual serving-pair/config/resource guards.
New messages invalidate byte-stream archive preparation before retirement.
Backend/frontend source retains exact messages/settings, reserves one ordinary
execution, restores send/review/worktree/history access, protects populated
worktrees, and coordinates writer plus protected reader. Cross-filesystem restore
publishes complete create-only files and journals interrupted publication.

`scripts/nightly-owner` contains exact maintained d419d85f4 source and tests plus
archive integration. UPSTREAM_SOURCE.json pins the original files. The optional
service bridge opens qualified shared cold custody before the normal capture
lane. Its current-map finalizer requires cold payload absence and active SQL/shared
coverage. The ordinary independent SQL decoder validates the exact cold catalog.
Pending/incomplete revival holds a new backup; old backups and tracking remain.
No second conversion workflow or recurring schedule was introduced.

The actual live frontend snapshot had menu/read-later/sidebar/preservation patches
not present in staging. A clean three-way merge against dbcbfbe4e preserved them
and the new archive UI. The preservation gate compares1,327 pinned live inputs and
passes with only nine reviewed archive/staging differences. Preserve that merge.

## Current external dependency

Ordinary same-user process inspection cannot read some host manager/browser
processes. Existing sudo helpers are explicitly scoped to other artifact roots.
Do not bypass their policy, exempt inaccessible tasks, or change security settings.

Prepared, NOT installed:
`/mnt/vk-storage/vk-archive-release-20261127/inspector-package-v1`.
ManifestSHA256 `d94163bfc902e4c1a445e6bfa9f11e096016644f56b1223f8006bbfa89cf5e22`.
The root-owned metadata-only helper inspects current task/file metadata under
inode-bound scopes. Requests require exact live owner/custody/nonce. It cannot
read payload contents or mutate/restart anything. `install_inspector.py` grants
only its SHA-pinned fixed no-arguments launcher and preserves differing existing
files. The external managing agent must install it; this workspace lacks that
root capability. A user question is pending for that installation.

`INSPECTOR_MANAGER_HANDOFF.txt` in the private release root was published as
attachmentf5a55e6b-940f-49c9-8099-6f777d166037. This is one prerequisite, not the final
spinup/cutover handoff. Package scopes currently cover app/native histories,
SSD worktrees, this repo's private Git administration and qualification inputs.
Other repository administration must be explicitly qualified before retirement.

## Validation and artifacts

Private evidence: `/mnt/vk-storage/vk-archive-release-20261127/source-recovery/`.
- `combined-nightly-archive-tests.log`:119 passed in93.322s, no skips.
- `nightly-service-tests.log`:14 passed; `nightly-consumer-tests.log`:14 passed.
- `nightly-composed-integration-tests.log`:7 normal composed restore and14 service
  tests passed before the later service bridge; final service tests are above.
- `combined-driver-build.log`:offline shared-target backend build completed in17m11s,
  Rust source pinb2330ee1ff9d7640197f95d2a336d8cdb72d4aba. Qualification copy is sealed at `qualification-artifacts-v1/reader-server`,
  SHA77f5ea94cd09dbab63633c77e8a7484295068a2b1eda1ab80b1c11308587cd9c.
  Actual build-info confirms archive custody/packed reader protocols. It requires
  the separately sealed frontend; it is not cutover-qualified.
- `combined-frontend-preserved-build.log`:frontend build completed in2m15s with
  bounded3072MiB heap. Optional Sentry map upload lacked authentication.
- `frontend-preservation-reviewed.json`:all1,327 live source pins checked; pass.

Earlier narrow Rust, generated-types, frontend check/lint and recovery results
remain in the previous handoff. Final format and ops checks passed; continuity is within the pickup budget.
The preserved live model menu passed3 tests and preservation reconciliation passed18.
These fixtures/builds are not real Desktop B or combined serving acceptance.

## Next meaningful work

After the scoped helper is installed, test real process visibility under custody.
Seal a source-pinned candidate plus compatible current-data fallback and current
private driver/runtime/Nightly configs. Qualify real isolated writer/protected
readers and B archive/restoration, automatic message revival, ordinary desktop/
mobile/history/review/settings/queues, failure recovery and resource/performance.
Retain current SQL/native/config/frontend/shared dependency recovery. Never
restore old SQL over newer writes. Finish CI/staging and one unambiguous executable
external-manager spinup/cutover handoff. No production restart/cutover here.

Accepted finite dedup/catch-up evidence remains in
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
Packed311 plans/3,639 histories/580 packs are prepared, not livepublished. The old
sealed dedup-only activation is unarmed and must not be replayed. Production
archive config is absent and Nightly remains OFF. Preserve current owner/cursor,
pending inputs, selected settings and all backup epochs.

[Prior detailed pickup](deployment-history/20261128-before-runtime-integration/HANDOFF.md).

[Full historical archive](HANDOFF_HISTORY_20261017.md).
