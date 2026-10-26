# October 26: Discussion compatibility source ready

Pick up VK_ISSUE_COMMENTS.md. VK Dev T72 (`0da02ba1-7d50-4461-9a9b-0701e341c753`)
is linked to workspace `a6f852f0-d00c-4dee-8864-1201d66ae6e1` on
`vk/a6f8-create-and-link`. Both feeds returned byte-identical SPA root HTML because
local routes were absent; explicit `/v1` wildcard isolation is required in Axum.
Prepared migration/CRUD/feed routes and local identity pass focused HTTP/storage
and real desktop/393px mobile browser acceptance. Correct linked startup requests
are captured with both feeds failing; no agent is launched. Current production
still lacks the routes. Physical S25 status is unavailable (`no_current_tls_port`).
An approved normal backend release and physical post-release acceptance remain.
Evidence: `/mnt/vk-storage/vk-issue-comments-20261026`. Other entries are history.

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
