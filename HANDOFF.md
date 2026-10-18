# Final storage client validation pickup

Supporting draft [PR277](https://github.com/artinflight/vibe-kanban/pull/277)
now pins Operations PR215 client `5c2ee7f5f561a943d123fcc09d5ee8098cbeab20`.
Source/test snapshot includes the 76 published Python tests and exact twelve-file
provenance; hosted CI runs them before the real native HTTP/DB/queue integration.
The previous native59e64543/clienta345ca8 pair passed633main +onepaired +15
scheduling-enabled tests. Its result remains historical; final5c exact-pair
hosted acceptance is pending. Native wire/implementation/fixture is unchanged.
Read [contract](VK_STORAGE_ALERT_ADMISSION.md), [validation](STORAGE_ADMISSION_VALIDATION.md)
and the final result on PR277/existing private T90/Staging handoffs.

Actual nominated Staging source is PR276/366cfd243. Native-crates and additive
workflow patches passed temporary-index applicability checks; only workflow
and continuity paths overlap. Preserve the release and reconcile additively;
combined copied-data/queue/resource/budget/approval/private-route and forward/
latest-data rollback acceptance remain Staging-owned. No bundle overlay.

Publication is limited to sanitized code/tests on existing PR215/277. Host
Cargo/compiler/linker/aggregate-build/shared-target hold remains; use normal
hosted PR checks. No live backend, migration, binding, timer, access, dispatch,
merge, deploy or restart. Preserve saved config/Recommend and all existing work.

The following prior pickup is retained as release context.

# Pickup

Current bounded follow-up: [compact durable job outcomes](USAGE_JOB_OUTCOMES.md).
PR266 is merged; preserve its archives/reuse and the newer release coordination.

1. Read [STATE](STATE.md) for active protections and the topic map, then
   [STREAM](STREAM.md) for this branch. Do not load historical archives by default.
2. Read [USAGE_EFFICIENCY](USAGE_EFFICIENCY.md) for exact measured results,
   commands and outstanding integration. Preserve owners' existing changes.
3. Reuse the existing fingerprinted Preparation runner: prerequisites before
   build, immutable source/tool/config/artifact identity, one cache owner,
   and fresh volatile acceptance on every run. A cache hit never authorizes
   deployment or skips current owner/data/queue/QA checks.
4. Staging owns release and actual native queue start/drain readback. Nightly
   workspace604d owns the sole B backup/package/schedule; its counted capacity
   phase is not a backup. Neither is replaced by this efficiency branch.
5. No restart, schedule activation, cleanup, privilege change or extra worker
   is authorized here. Observe fresh resource admission and leave a user lane.

All former pickup text is preserved exactly in
[HANDOFF history](HANDOFF_HISTORY_20261017.md). Locate relevant dated sections
with `python3 scripts/continuity/pickup.py find QUERY` rather than reading the
whole archive. The [archive manifest](CONTINUITY_ARCHIVE.json) records the
original source commit, byte counts, hashes and every heading/line locator.
Archives contain historical contradictory checkpoints: use current validated
owner evidence, never a stale heading that says "current".

Current release coordination, newer Sidebar adoption and remaining private gates:
[October 17 release status](VK_RELEASE_COORDINATION_20261017.md).

Collapsible issue behavior and approved frontend release: [topic evidence](VK_COLLAPSIBLE_ISSUES.md).
