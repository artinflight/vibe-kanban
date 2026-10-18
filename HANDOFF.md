# Storage admission pickup

Source-only draft [PR277](https://github.com/artinflight/vibe-kanban/pull/277)
continues from `af7b35ddd2cb48d6a276f6fd410820971d21a59b` on verified staging
`5b43524ea35b2eb5dd80d0881dc8445489f4442f`. Read the
[native v2 contract](VK_STORAGE_ALERT_ADMISSION.md),
[validation checkpoint](STORAGE_ADMISSION_VALIDATION.md) and [stream](STREAM.md).
The publication hold is lifted for sanitized code/tests on the existing PRs;
the host-heavy build/shared-target growth hold remains. No host Cargo, compiler,
linker or aggregate build. Use the existing hosted PR checks.

Prior native CI: 474 passed, one race assertion failed, 14 skipped and 157 not
run. This correction asserts normal recovered queued input, adds ordinary
interrupted-user-turn recovery to alert launch and tests persistence/replay.
Hosted nextest disables fail-fast to exercise the complete suite. Results on
this correction are pending. Joint T90 adapter review/integration and Staging
combined release/rollback acceptance remain distinct from native source tests.
No live dispatch, binding installation, live migration, timer, access change,
merge, deploy or restart is authorized. Preserve saved model/effort/Recommend,
genuine approval boundaries and all source/build outputs.

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
