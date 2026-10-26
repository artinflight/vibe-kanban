# October 26: PR282 published; conditional rollout not yet ready

Read [discussion repair evidence](VK_ISSUE_COMMENTS.md). PR282 targets staging,
is ready for review and has passing full CI on `a7312c35c`. VK Dev T72 remains
linked to workspace `a6f852f0-d00c-4dee-8864-1201d66ae6e1`.

The operator authorized deployment when backup/rollback/active-job gates pass.
Preserve the actual private backend and newer served frontend: isolated overlay
builds and a migration-compatible rollback are prepared under
`/mnt/vk-storage/vk-issue-comments-rollout-20261026`; inspect current receipts
before acting. Candidate builds and 73 runnable private server tests pass
(3 incident tests ignored); guard builds with 5 passing tests. Rollback compiles
and its retained source/hash are reverified. Extra DB-test compilation hit the
unchanged SSD floor; that suite, actual-data rollback rehearsal and compatible
frontend validation/build/package remain pending. No shared cache or original
was removed; safe capacity relief is required before resuming. Nightly owner604d
reports current coverage/restore gaps, and other agents remain active. No production route/service/database/frontend was switched.
S25 status now proves the existing Desktop-native Tailscale path; actual deployed
desktop/physical phone comments/reactions still need acceptance. Preserve all
jobs and private integrations. Remaining sections are historical context.

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
