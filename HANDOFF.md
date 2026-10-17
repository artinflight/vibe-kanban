# Pickup

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
