# Combined archive/revival release — November 28, 2026

The release is **not yet qualified for cutover**. The goal is the complete
source-pinned dedup/packed-reader/archive/revival/Nightly release for the dedicated
external managing agent. Source implementation or a successful build does not
satisfy that goal. [Scope](VK_DEDUP_TAKEOVER.md),
[archive acceptance](VK_WORKSPACE_ARCHIVAL.md), and [pickup](HANDOFF.md).

## Live state

Production remains unchanged. On November28 the writer service
`vibe-kanban-native-review-20261015.service` remained active at PID70372,
invocation81dd8bb21f894aa1bd286f8f0029b770. The protected reader service
`vk-chat-history-readonly-20261010.service` remained active with wrapperPID2573723,
invocation9c0b08030aa445318309e41dff070786. These observations are historical;
reconcile actual identities again before any deployment. Public frontend remains
`/mnt/vk-storage/vk-codex-menu-20261120/release/paired/candidate`.

Production archive configuration and the new process inspector are absent.
No live migration, archival retirement, schedule activation or restart occurred.
Nightly remains OFF. Backend spinup/cutover belongs to the external managing agent.
Preserve pending inputs, selected settings, backup epochs and other owners.

## Candidate source and evidence

The source implements archive intent, immutable recovery generations, exact
retained messages/settings, one reserved execution, kernel custody, native/Git/
attachment ownership, lossless movement/revival and both history reader paths.
The finite driver now checks the actual serving pair, source/config bindings,
resources and privileged process-clearance receipts before physical changes.
A root-owned metadata-only inspector package is prepared but not installed.

The maintained Nightly owner is contained at `scripts/nightly-owner/`, with
upstream d419d85f4 provenance. Its ordinary service, current-map acceptance and
independent current-SQL reader now support cold references. Pending revival
cannot masquerade as empty active history. No second backlog converter is added.

119 archive integration tests passed against the contained Nightly source.
Changed Nightly service/consumer suites passed14 each; composed restore passed7.
These are source/local-transport evidence, not actual Desktop B acceptance.
The offline backend build succeeded in17m11s. The frontend build succeeded with
a bounded3072MiB heap; optional Sentry map upload lacked authentication.

The actual live frontend had source patches absent from staging. Clean three-way
reconciliation preserves those shipped menu/read-later/sidebar/preservation
features plus archive UI. The 1,327-input preservation gate passes with only nine
reviewed archive/staging differences. Do not replace this with a blanket allowlist.

## Remaining qualification

Install and exercise the scoped inspector through the external manager; qualify
real paired readers, automatic archival/message revival, actual Desktop B and
current SQL/software/frontend recovery, compatible current-data fallback,
ordinary UI/queues/settings, resources/performance and Nightly current-map cycle.
Then finish CI/staging and the executable combined handoff. No complete qualified
combined candidate/fallback manifest exists yet. Do not substitute the older
sealed dedup-only package or restart consumed controllers.

Original finite dedup and catch-up acceptance is retained under
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.
311 packed plans/3,639 histories/580 packs were prepared, not published live.
[Previous continuity](deployment-history/20261128-before-runtime-integration/STATE.md).

[Full historical archive](STATE_HISTORY_20261017.md).
