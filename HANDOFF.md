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

Newest follow-up: [exact-message Reply to](VK_DOT_MESSAGE_REPLIES.md) is implemented
and tested for issue/project chats, including durable links and uncertain retries.
It requires matching Dot Python/API plus frontend release; **not activated here**.
Staging owns its current timestamp execution5ab782bd and subsequent integration.
Apply only the feature diff onto its newer frontend/current Python baseline;
retain timestamps, collapsible UI, continuations, CU/Stop and latest-data rollback.

[Jump to Needs Attention](VK_DOT_ATTENTION_NAVIGATION.md) is the newest UI-only
follow-up: all-page unresolved-flag navigation, stable selection and no flag
mutation. Its handoff supersedes the timestamp-in-progress status above:
timestamps are verified live07:12:15 EDT Oct18; Reply to plus navigation still
await Staging's next integration. Current frontend/rollback pins and old r1
inputs are retained in the derived private baseline record; no new capture.
Preserve execution88a68ab1 retains exact-message acknowledgement ownership.

Newest owner request: [persistent Dot management](VK_DOT_WORKSPACE_MANAGEMENT.md)
uses an explicit local association, never dispatch/read/count inference. Only
verified T89 is provided for backfill; nothing is enabled live here. Staging owns
combined Reply+Jump+management release; Preserve retains provenance/ack contracts.

Staging compatibility follow-up: Reply/Jump panel now consumes Preserve174668ed7's
neutral derived dispatch author/body, including composer/history reply quotes.
Raw history/IDs/hash/order remain unchanged; no management inference. Real target
backfill/approval data is retained only in the private Staging handoff; tracked
examples are synthetic. Staging still owns all packaging and activation.

Priority before combined release: [Project chat routing and sizing](VK_PROJECT_DOT_CHAT_ROUTING.md)
binds the sidebar to the displayed exact workspace, restores project chat on
close/Back, retains per-session/destination drafts and pins in-flight sends.
Drag/full-width/restore keep chat state mounted. Staging's existing coordination
record was notified before packaging; no competing activation here.

Newest required addition: [project unread notices](VK_PROJECT_DOT_NOTICES.md)
adds one blue project-labeled destination to Workspaces Needs Attention, using
existing summaries without workspace fanout. Clicks explicitly select project
chat, preserving drafts/replies and flags. Routing/resize0107f77b and this source
must both be reconciled into Staging's held PR276 before the one release. Staging
was notified through its existing PR record; no package/activation here and no
claim that Nightly's actual three-row R2 boundary has been reached.
