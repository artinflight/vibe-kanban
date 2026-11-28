# Combined deduplication/archive release — 2026-11-27

The authoritative goal is to prepare the complete release for the dedicated
external restart agent. [Takeover scope](VK_DEDUP_TAKEOVER.md) and
[archive acceptance](VK_WORKSPACE_ARCHIVAL.md) define the required outcome.
No complete combined candidate/fallback manifest exists yet. Do not substitute
the older sealed dedup-only package or claim readiness from source tests.
No production restart/cutover is authorized for this inside-Vibe agent.

## Current source

Work continues on `vk/0815-archive-release` in the separate SSD checkout named in
[HANDOFF](HANDOFF.md). It preserves staging78e472543's specialist-delegation and
run-provenance changes. Their notes remain in
[staging history](deployment-history/20261127-staging-integration/staging-HANDOFF.md).
The managed0815 worktree was unexpectedly recreated on its recorded branch;
actor/cause are unproven. Exact source writes were recovered and pushed. The
candidate now refuses ordinary recreation over populated or aliased destinations.
That safeguard is source only; production has not been changed.

Implemented archive contracts include the existing/future archive intent outbox,
immutable recovery catalog, exact retained message/settings and reserved ordinary
execution identity, native-child inventory, Linux per-workspace custody, journaled
movement and same-path restoration. Normal send/review/worktree admission and
raw/normalized history use the optional runtime. Protected readers consult the
current catalog and request the writer's recovery. Browser requests retain their
identity and show pending restoration or recovery errors.

Nightly selection now holds scoped cold custody, captures a matching SQL API
image, filters active paths and validates independent SQL/cold-reference recovery.
Messages, history-read intent, generation changes or reappearing paths invalidate
exclusions. Remote metadata work does not pin a live SQL transaction. The contract
still needs integration into the existing namespace/current-map cycle.

Normal Desktop-B adapter code uses the maintained Nightly capture/index/decoder.
Old generations retain immutable provider/index identities while using current
qualified reader inputs. Updating software does not require recapturing bodies.
Physical preparing state and its original-path journal now commit atomically.

The full81-test Python suite passes with Nightlyd419d85f4. Added real Git graph
recovery/reuse and actual cross-filesystem publication tests cover shared-history
closure and the host's distinct SSD/live-history filesystems. This code preserves
shared repositories and only exposes complete final-file writes after hashing.
The production owner/attachment/driver integration remains unfinished. Earlier source checks
passed:9 archive/revival Rust tests,2 custody tests,3 worktree-preservation tests,
3 existing owner regressions, backend compilation, generated types/check, four
frontend type checks, changed frontend lint and formatting. Local B/HTTP fixtures
are not actual B or ordinary application acceptance. Exact scope/logs are in
HANDOFF and the archive document.

## Remaining release blockers

The trusted production movement driver and complete current process/Git/native/
attachment ownership/dependency closure remain unfinished. Connect the tested
Nightly selection contract to its existing recorded namespace and current-set
acceptance, preserving its owner/cursor/retained records. Qualify actual Desktop B
recovery, both readers, ordinary desktop/mobile/history/review/settings/queues,
failure recovery and whole-population resource/performance behavior. Build and
pin the combined candidate and compatible current-data fallback, then synchronize
qualified source, CI and exact spinup/cutover instructions into staging.

Production archive configuration remains absent: no live archive migration,
retirement or Nightly exclusion is enabled. Nightly calendar remains OFF; daily
dedup remains held. Preserve Nightly tracking, pending inputs, selected settings,
all backup epochs and other owners. Never restart a consumed controller, create
a second watcher, or replace current SQL with an older snapshot.

## Accepted dedup evidence retained

Original finite conversion/catch-up is accepted. The earlier byte-saving layout
increased file count; packed qualification addresses that performance regression.
All274 prepared session groups,3,639 histories and580 packs are independently
verified. Selected files go from1,057,171 to4,219 in preparation, occupying
6,768,685,056 allocated bytes including directories. This is prepared state,
not a live file-count reduction or new net savings.

Both packed readers, exact full-EOF probes, complete original/object/metadata
closure, current SQL/software/frontend recovery and latest-data fallback have
accepted dedup-specific evidence. The paired private switch and finite publication
packages are accepted and unarmed. Their existing evidence remains valid for that
scope; it does not certify archive/revival/Nightly integration. Final current SQL
and owner identities must be refreshed at the release boundary.

[Packed evidence](VK_DEDUP_PACKED_LAYOUT.md) and
[prior detailed state](deployment-history/20261127-before-nightly-selection/STATE.md)
retain all measured stages, accepted B receipt counts, failed-attempt disposition
and source pins. Evidence root:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
`PACKED_PAIR_PACKAGE_ACCEPTED` and `PACKED_FINITE_PACKAGE_ACCEPTED` are immutable
scope evidence. No packed manifests have been published live. Post-publication
fallback must understand VKLOGCAS2 and retain the latest SQL and later writes.

Actual runtime truth remains [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json), checked
against serving processes/public routes before any action. Existing main and
protected readers and the operator's current frontend remain unchanged here.
Full historical archive: [STATE history](STATE_HISTORY_20261017.md).
