# Current pickup — archive separation added before managed restart

The operator now requests archive separation, automatic movement during normal
archive actions, automatic revival on message, and active-workspace Nightly
payloads. This supersedes the previous deferred-archive exclusion for this scope.
Nightly schedule activation remains off. Actual backend restart belongs to an
external managing agent; do not perform it from this Vibe workspace.
[Required behavior/current implementation](VK_WORKSPACE_ARCHIVAL.md).

Source changes in this turn:
- New migration records archive/unarchive intent transactionally, seeds existing
  archived owners, and increments generations only on state changes.
- Read-only inventory binds workspace/session/native history metadata and
  protects pinned/running/shared/unresolved owners, drafts, queues and leases.
- Eleven fixture tests pass. Current inspection:1,052 archived,244 active,
  1,016 metadata candidates. No candidate is retirement/backup-exclusion proof.

Not done: mover, verified cold catalog, automatic revival/dispatch reconciliation,
both cold-history readers, Nightly consumer and combined qualification. No live
migration, transfer/retirement, Nightly change, restart or activation occurred.
Do not use the intent queue as an accepted archive catalog. Keep private content
out of Git; bulk staging requires mounted SSD, archive payloads canonical B.
Next: implement the mover/restore integration with per-workspace custody and
normal input admission, test failures/concurrent sends, qualify actual B restore
and Nightly selection, then prepare the combined candidate for external restart.

Dedup continuity:
Read dedicated WakeWatch CONTEXT.md and STATE. No active native goal or script
continuation. Preserve existing monitoring/owners/receipts; no duplicate workers,
new watchers, uncertain replay or model polling. All original conversion/catch-up
accepted. Packed311plans/3,639histories are prepared, not published live.
Evidence root:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.

PACKED_PAIR_PACKAGE_ACCEPTED accepts the corrected five-stage private paired
switch/fallback with latest-copy SQL preserved; actual B triples verified.
PACKED_FINITE_PACKAGE_ACCEPTED accepts all three finite-package stages and188pins,
with actual B recovery and no publication dispatch. Preserve this valid historical
evidence; do not replay accepted jobs or mutate sealed packages.

Existing packed-reader-cutover-v1 and packed-reader-activation-v1 remain UNARMED.
Their exact hashes/launch details and full accepted evidence are preserved in
[previous handoff](deployment-history/20261125-before-workspace-archival/HANDOFF.md).
Those packages do not contain new archive/revival changes. Do not silently arm
them as a combined release. Any actual restart needs the external managing agent
and current authorization, current owner/input/settings checks and compatible
fallback. Original software is fallback only before VKLOGCAS2 publication.

After compatible reader deployment: bind actual POST_ACTIVATION readers, perform
one exact finite publication under existing custody/recovery, qualify daily
forward conversion before releasing its saved hold, and finish ordinary public
desktop/mobile/history/review/settings/queues/monitoring checks. Measure current
allocated space/file-count/performance/growth including all SSD staging and B.
The historical73,893,642,640B recovered predates new staging; it is not current
exclusive filesystem relief. Full deduplication remains unfinished.

Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
