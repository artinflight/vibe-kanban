# Dot notification rollout — live October 16

Seamus approved deployment of the Dot chat service/connector and combined
frontend with the explained brief Dot-only interruption. Activation completed
on **2026-10-16**: Dot services at **22:37:18 UTC**, frontend at **22:38:25 UTC**.
The measured service restart/HTTP readiness interval was **1.38 seconds**.
This is not a measurement of platform catalog propagation or every client's MCP
reconnect. Vibe, the static server, gateway, notifier and workspace agents were
not restarted.

## Live identity and source

- App/API version: **0.1.42** (version number unchanged).
- Exact frontend build: `aebe6a4425ad5ee46ec45483ad181a58b81f2047`, public branch
  `prep/dot-notifications-mobile-steering-20261016`.
- Complete public equivalent frontend and Dot source:
  `7222b127c432a22efcef74860615bb75fcc2cffc`.
- [PR254](https://github.com/artinflight/vibe-kanban/pull/254) merged into `staging`
  at `28fdcfddfbdc14e7c8be018b3f01d47c5ddcf6d3`; the canonical staging reference
  was fast-forwarded. The dirty canonical development checkout was preserved.
- Exact-source [Test38976043692](https://github.com/artinflight/vibe-kanban/actions/runs/38976043692)
  passed in full before activation.
- Frontend: `/mnt/vk-storage/vk-dot-notification-rollout-20261016/release`.
- Entry JavaScript: `/assets/index-CrPmgoRY.js`.
- Entry stylesheet: `/assets/index-CnaxWhN_.css`.
- Dot release: `/mnt/vk-storage/vk-dot-sidechat-live/releases/7222b127c`.
  Connector/publisher `current` selects it. The browser service's explicit
  `notification-release.conf` override selects the same immutable source while
  retaining its TLS, origin, proxy, database and service hardening settings.

The combined source retains the deployed Mobile/Dot and Sent Steering source
from `1d074941d`. Every non-notification frontend source remains identical to
that live baseline. The eight already-live Mobile/Dot source differences were
reconciled into PR254; no active mobile-owner worktree or browser was changed.
The incumbent compatibility index differs only in its new JS/CSS entry names.
Old hashed assets remain available for existing tabs.

## Verified live behavior

The production build, preparation runner, 57 Dot tests, portable notification and
live-chat DOM tests, formatting/governance and full exact-source CI pass.
Before activation, nine packaged steering cases and five Mobile/Dot viewports
passed. The deployed source also passes the 288-pixel sidebar badge regression.

After activation, sandboxed Chromium loaded the **actual served frontend** and
used the **actual live authenticated Dot API** at 393 and 1440 pixels:

- Unread and Needs Attention badges were both visible for an issue-linked
  workspace before the reply was opened.
- A visible focused reply cleared Dot unread. Needs Attention remained visible
  after reading, navigation and reload, independently of unread.
- Resolve cleared attention; Reopen restored it. The actual server state agreed
  with the UI. There were no page errors or horizontal overflow.
- The selected workspace's real coding-agent `seen` state did not change.
  Browser guards allowed reads and the read-only summaries POST while blocking
  coding-agent and unrelated application writes.
- The test used a separate synthetic owner with ten-minute bounded access to
  one project and synthetic reply data. Only the QA page's Dot requests used
  that identity. Seamus's credentials, cookies and pairing were not inspected
  or replaced. No owner automation was triggered: zero outbound wake attempts.
  All QA sessions, grants, threads and messages were removed afterward.

All **nine** post-switch Send/steering cases passed against actual HTTP-served
assets at 390/412/1440 pixels. Confirmed sent steering stayed cleared after
navigation/reload; failed and queued drafts remained recoverable. The steering
transport was synthetic, so no live agent was prompted.

Independent final server readback confirms unchanged paired sessions and access,
exactly two existing active subscriptions, and exactly one destination for each
of all **43 projects, including 26 archived**. Automatic future-project policy
remains enabled. Existing messages and receipts were retained. No persistent
access, credential, subscription or platform-permission change was introduced.

The installed connector facade advertises all five sidechat tools, including
pending-message discovery and `set_sidechat_attention`, and the optional
`attention` argument on reply append. The new API advertises its notification
capability. Recent registered-service logs after activation showed three tool
calls with no request failures, but zero `tools/list` or `events/list` discovery
requests. This confirms the connection is serving calls; it does not prove that
the platform requested the new catalog. The supported next step is normal
platform rediscovery of this same updated service, not a credential change or
a replacement subscription route. This does not establish that every existing root/platform session
has adopted the new tool metadata; platform catalog propagation remains outside
this service's control. No identical Refresh Tools request is prescribed.

## Remaining human acceptance

**Physical S25+ UI acceptance is unverified.** The authorized ADB transport was
available, but automatic approval review rejected forwarding Chrome DevTools:
it could expose existing authenticated tabs/session material without proving a
dedicated profile boundary. That action was not retried or routed another way.
No phone networking, shared ADB server, browser tab or paired session changed.

Seamus only needs to refresh the Vibe page on the already-paired phone and send
one fresh question in any project. Confirm that its natural Dot reply arrives
in the same conversation, the violet unread clears when viewed, and attention
stays until the question is answered/resolved. Resolve/Reopen can be checked in
that conversation. No pairing or phone UI debugging is requested.

A fresh automatic root reply and human-visible receipt are not established by
synthetic QA. The earlier retained phone message still has its verified direct
root reply; this rollout neither replayed it nor wrote another reply. If a root
session cannot annotate or resolve through its tool inventory, compare its
supported discovery with the installed advertised schema; owner UI controls are
already verified against the live API.

Broader unrelated UI writes—Kanban drag/status/order edits, workspace creation,
archive/delete/menu actions, clipboard and attachment uploads—were not repeated
on production. Existing project/archive metadata and all non-notification
frontend source were preserved. Synthetic fixture results are not a physical
phone result or proof that a human read a reply.

## Backup, rollback and durable receipts

Verified Desktop backup root:
`desktop:B:/vk-backups/vk-dot-notification-rollout-20261016/`.
Complete current static tree plus consistent Dot SQLite/private config, Dot
service definitions/adapter and a safety snapshot of Vibe SQLite were uploaded,
hash checked, downloaded and fully restored for verification. A fresh consistent
Dot boundary snapshot was separately uploaded/read back and integrity checked
immediately before the service switch. Private payloads stay out of GitHub.

Previous frontend:
`/mnt/vk-storage/vk-sent-steering-release-20261016/release`.
Frontend rollback is an atomic pointer switch to that verified Mobile+Steering
release. Preserve the upgraded, backward-compatible Dot service and its new
state table when rolling back UI. **Never restore stale SQLite over current
conversations or agent state.** A service rollback requires a separate data-safe
plan; the normal UI rollback does not restart Vibe or Dot.

Private receipt root:
`/mnt/vk-storage/vk-dot-notification-rollout-20261016`.
`release-manifest.json`, `sidechat-release-manifest.json`,
`backup-verification.json`, `dot-activation.json`, `frontend-activation.json`,
`connector-discovery.json`, `final-readback.json`, `live-notifications/results.json`
and `served-steering/results.json` bind source, assets, data preservation and QA.
They contain no authority to replay a message or subscription.

Repeatable authorized live verification is versioned in
`scripts/dot-sidechat/live_qa.py`, `test-live-notification-api.mjs` and
`test-live-notifications-browser.mjs`. Supply explicit private database/release,
workspace, output, Playwright and Chromium paths via their `VK_DOT_QA_*` and
`VK_TEST_OUTPUT` environment variables. The helper's generated token/CSRF data
travels only over the controller's private fd3 pipe. Do not run setup directly,
log that pipe, use a real owner's session, or use the scripts without permission
to create and remove bounded synthetic QA data on the selected deployment.
