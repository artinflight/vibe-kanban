# Pickup — combined archive/revival release is not yet ready

Authoritative goal: get the combined dedup/packed-reader/archive/revival/Nightly
release ready for the dedicated external restart agent. The native controller's
label `clear` is stale; the user's later goal and five durable requirements govern.
No requirement is fully closed. Do not create another goal or continuation loop.

Continue on `vk/0815-archive-release`, based on staging
`78e472543b950a15a260e2d6af249bd5bef671d2`, in:
`/mnt/vk-storage/vk-archive-release-20261127/source`.
Use operator remote `fork`, not upstream `origin`. Preserve the canonical staging
worktree's unrelated dirty Antigravity/UI work. PR291 merged earlier source only.

The managed0815 checkout was recreated on recorded branchd8bd57f5c at22:28:56Z,
removing this turn's uncommitted edits. Actor/cause remain unproven. Committed
154952af0 stayed safe; exact recorded source writes were recovered into the
separate checkout above. Do not reset other worktrees to continue.

## Implemented and tested source

[Archive implementation/acceptance](VK_WORKSPACE_ARCHIVAL.md) describes the intent
outbox, immutable recovery catalog, exact input/reserved dispatch, native child
inventory, kernel custody, journaled movement and maintained normal-B adapter.
The backend now connects ordinary send/review/worktree admission and raw/normalized
history to restoration. Protected readers use the current catalog read-only and
request the writer's restoration. Concurrent readers share one restoration.
The browser retains request identity and displays saved-message/recovery status.
Ordinary recreation preserves populated/aliased worktrees on branch mismatch.

The full67-test Python suite and12 final focused selection tests pass with
Nightly source d419d85f4. Nine archive/revival Rust tests,
two kernel-custody tests, three worktree-preservation tests and three existing
owner regressions pass. Backend compilation, generated types/check, all four
frontend type checks, changed frontend lint and formatting pass. TypeScript used
a bounded1536MiB heap after default heap exhaustion; production settings stayed
unchanged. Logs: adjacent `source-recovery/`. Local transport/HTTP/driver fixtures
are not actual Desktop B or ordinary application acceptance.

The new `nightly_selection.py` contract holds scoped cold custody, captures a
matching current SQL image, filters active paths and validates independent
SQL/cold-reference recovery. Message/read intent invalidates exclusions. B
metadata work does not pin a live SQL transaction. Physical preparation now
commits its path journal atomically. Normal B restores old generations using
current qualified reader inputs while preserving immutable provider/index identity.
New logs: `archive-nightly-tests.log`, `selection-final-tests.log`, `format-nightly.log`.

## Remaining outcomes

The immediate implementation gap is the source-pinned physical driver with actual
serving-reader, native/process, Git and attachment dependency ownership. Reuse the
checked lifecycle/custody/B adapter. Then wire the tested Nightly selection contract into the actual recorded namespace/current-map cycle,
actual B/current-SQL/software/frontend recovery, combined candidate/fallback and
ordinary paired-reader/API/desktop/mobile validation, and qualified staging handoff.
[Full takeover scope](VK_DEDUP_TAKEOVER.md) remains IN PROGRESS; no deployable
combined candidate/fallback manifest exists yet. Do not substitute the older
sealed dedup-only package or treat source tests as cutover readiness.

Production archive configuration remains absent. No live migration, workspace
retirement, Nightly schedule activation or service action occurred. Actual
spinup/cutover belongs to the external managing agent. Preserve current data,
inputs/settings/owners, backup epochs and the existing Nightly tracking/cursor.
Recheck mounted SSD resources; earlier low-capacity readings are historical.

Read-only current inventory found1,296 workspaces/1,051 archived;1,011 have no
metadata hold, of which634 have no local worktree and377 have one. This is not
eligibility or movement proof: current process/Git/dependency and existing-history
ownership remain required. Do not recapture/move the population from these counts.

## Accepted dedup evidence to retain

Original conversion/catch-up is accepted. Packed311 plans/3,639 histories are
prepared, not published live. PACKED_PAIR_PACKAGE_ACCEPTED and
PACKED_FINITE_PACKAGE_ACCEPTED retain valid private switch/fallback and actual B
proof; read [packed evidence](VK_DEDUP_PACKED_LAYOUT.md) and
[prior handoff](deployment-history/20261125-before-workspace-archival/HANDOFF.md).
Evidence root: `/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
Do not edit accepted source pins, replay consumed controllers or duplicate
WakeWatch. Daily dedup remains held; Nightly calendar stays off. After publication,
fallback must understand VKLOGCAS2 and use latest SQL, never overwrite later writes.
Historical73,893,642,640B savings exclude later staging and are not current net relief.

Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
