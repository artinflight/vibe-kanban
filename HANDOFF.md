# Preserve Dot: selective notification acknowledgement candidate

Read [the source-only protocol and approval boundary](DOT_SELECTIVE_NOTIFICATION_ACK.md).
Implementation/test only: no live state was opened by fixture acceptance, no
credentials/authentication/grants, service restart, cleanup write or agent launch.
Preserve live T63 sidechat hash `dd184669` and PR268 newer source `2a29ae93a`.
The new module protects manual unread, unresolved attention, genuine conversation,
sibling workspaces and newer/unselected messages. Inventory uses a read-only
existing store; acknowledgement is exact-ID/state-token fenced in one transaction.
Tests: 98 full regressions + two preparation checks, plus 14 focused cases and
fixture dispatch against deployed Store/adapter. Format stops at missing Prettier
after Rust formatting; no compiler or browser used. New persistent Dot read-state
permission and connector-only adoption need separate authorization. Preparation
must preserve fresh complete live source; never copy this whole stacked branch.

Existing shared handoff follows unchanged.

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
