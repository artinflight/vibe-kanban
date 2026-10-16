# Dot reply notifications — implementation handoff

Implemented in PR [254](https://github.com/artinflight/vibe-kanban/pull/254),
against `staging`. This feature is prepared source, **not deployed**. Existing
Dot chat, all-project permissions/subscriptions and Mobile/Dot remain live as
previously recorded in [the reliability handoff](DOT_RELIABILITY_ROLLOUT.md).

## Behavior and ownership

Desktop and phone workspace rows, issue-linked workspace cards and issue cards
show separate violet **Dot unread** and **Dot · Needs Attention** indicators beside
existing coding-agent indicators. Dot activity also keeps a workspace in the
Needs Attention group when it would otherwise fall beyond collapsed history.
Coding-agent flags, review state, unread endpoints and composer are untouched.

Unread is a durable owner/issue-thread state, shared across that issue's linked
workspaces and paired devices. Opening another issue or reloading does not reset
it. Fetching/polling history never acknowledges a reply. Only a reply whose end
is actually visible in a focused, visible browser tab is acknowledged by explicit
message ID. Hidden mobile panels and replies below the scroll viewport stay
unread. New arrivals cannot be swallowed by a high-water acknowledgement.

Needs Attention is independent. Dot can label an explicit `question` or `action`
when appending its reply, or set it on an existing reply. The owner can mark a
reply as needing attention, Resolve it or Reopen it in the conversation. Reading
or sending an unrelated follow-up never resolves it. Resolution requires an
explicit action by the owner or Dot; punctuation/content heuristics are avoided.
Dot should resolve the corresponding item only after its question/action has
actually been answered/completed. Legacy replies migrate once to unread with
no guessed attention label. Retry admission retains the original annotation and
cannot reset later read/resolution state.

State lives in the existing private sidechat SQLite database (`dot_reply_state`),
not the Vibe coding-agent notification database or browser localStorage. The
additive migration retains all messages, receipts, subscriptions and grants.
Browser summaries contain issue/project IDs and counts only. The existing paired
session project scope, exact-origin and CSRF checks protect summaries and writes.
There is no new grant, pairing, credential, persistent-access policy or outbound
notification subscription. Reading/resolving creates no webhook or reply.
Local Dot metadata is disabled when viewing a remote host, preventing local
conversation counts from leaking into unrelated remote workspaces.

## Source and validation

- Store/API: `scripts/dot-sidechat/sidechat.py`, `browser_api.py`, `contracts.json`.
  New authenticated `notifications`, `seen`, `attention` browser operations;
  optional `attention` on `append_dot_reply` and scoped `set_sidechat_attention`.
- UI: `DotActivityIndicators`, `DotSidechatPanel`, `DotSidechatLive`,
  `useDotNotifications`, workspace/sidebar/issue integrations.
- `python3 -B -m unittest discover -s scripts/dot-sidechat -v`: 57 tests passed,
  including durable independent state, authorization/CSRF/origin, sibling issue
  workspaces, relinking rejection, exact-ID races and idempotent retries.
- `node scripts/dot-sidechat/test-notifications-ui.mjs` and `test-live-ui.mjs`:
  portable DOM regressions, also included in frontend CI. The legacy prototype
  HTTP fixture test requires its own disposable fixture server; it is not live
  notification acceptance.
- `node scripts/dot-sidechat/test-notifications-browser.mjs`: isolated Chromium
  acceptance at 390 and 1440 pixels using synthetic data and the prepared Sent
  Steering release stylesheet. Hidden/long replies, shared state, reload, Resolve,
  separate indicators, no horizontal overflow and touch target sizing passed.
  Screenshots/test logs remain on the SSD; no production messages or paired
  browser were used. This is component browser acceptance, not phone deployment.
- Repository formatting/governance and fresh types/lint/CI results are recorded
  with the publication. Full Rust validation depends on host GLib/GObject
  development libraries; no host dependency installation is part of this change.

Browser runner prerequisites are explicit: `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`,
`VK_TEST_OUTPUT` (mounted SSD) and optional `DOT_BASELINE_RELEASE` stylesheet.
It starts a synthetic loopback fixture and a dedicated headless browser. It does
not access the mobile owner's files, browser, pairing or device.

## Coordinated release: backend first, preserve Mobile and Sent Steering

The Sent Steering owner prepared immutable frontend source `1d074941d` in
`/mnt/vk-storage/vk-sent-steering-release-20261016/source`, containing live
Mobile/Dot baseline `9d76d7faf` plus PR257. PR257 is merged to staging at
`9301e6a46`. The owner's stable `VK_SENT_STEERING_RELEASE_COORDINATION.md` tracks
its packaging/activation status. Its pinned package **excludes this new feature**;
Dot notifications do not hold or replace that release. Do not deploy this older
preservation branch wholesale over its Mobile/Steering frontend.

1. Pin the tested notification delta and integrate it into the latest prepared or
   activated Mobile+Sent source. Recheck actual live identity before packaging;
   do not follow a moving branch or alter the other owner's candidate/pointer.
2. Back up private SQLite consistently with its existing WAL-safe procedure to
   Desktop B and verify restore/readback. Keep data and credentials out of Git.
3. Install the tested sidechat Store/browser API and connector source together,
   preserving the distinct browser service source pointer, TLS/configuration,
   paired sessions, credentials, all-project policy and both subscriptions. The
   currently installed connector and browser use different release directories;
   changing the connector's `current` pointer alone does not upgrade browser API.
   No Vibe backend restart or mobile-owner workspace modification is required.
4. Verify paired `thread` responses advertise `capabilities.notifications`,
   authenticated count/read/resolve behavior, and reply append annotation. Verify
   the connector's supported discovery advertises the additive schema/tool. Root
   metadata propagation must be observed rather than assumed from a refresh.
5. Activate the combined frontend only after that API verification. Older APIs
   advertise no notification capability, so this UI preserves ordinary chat and
   performs no unsupported seen/attention writes; notifications need the new API.
6. Validate a new real Dot reply on desktop/phone: violet unread beside any agent
   indicator; hidden panel keeps unread; visible reply clears only Dot unread;
   question/action stays attention until Resolve; sibling workspace/reload retain
   state; coding-agent unread remains. Then check Sent Steering navigation/reload
   and existing Mobile/Dot pairing/draft/send behavior in the packaged release.

Rollback the frontend to the immediately previous verified Mobile+Sent package,
retaining its assets for old tabs. The additive SQLite table can remain; do not
restore an older database over new conversations to roll back UI. Reverting
connector/browser code needs a data-safe plan: old code does not maintain this
new state table. Preserve a migration-aware implementation until reactivation,
otherwise later replies need deliberate backfill without resetting prior reads.
No activation or persistent-access change was performed by this implementation.

## Remaining acceptance and platform limitation

The earlier retained phone message has one verified direct root reply. A fresh
automatic owner-message-to-reply path and user-visible phone receipt remain
unverified separately. Root previously lacked pending-message discovery despite
other reply tools working; this UI change does not repair platform tool discovery.
The additive attention schema/tool also needs supported platform discovery before
Dot can annotate/resolve programmatically. Owner read/resolve buttons use the
paired browser API and do not depend on that tool discovery. No new refresh,
pairing, or phone UI debugging is requested by this handoff.
