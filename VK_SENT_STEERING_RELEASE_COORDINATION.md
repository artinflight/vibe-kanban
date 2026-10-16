# Steering frontend release coordination

Stable operational handoff for the activated steering release and a later combined
Dot notification candidate. The release-root and prepared-source copies survive
workspace cleanup. Do not use an older workspace checkout as deployment truth.

## Activated source and package

- Live URL: https://vibe.local/ ; application version **0.1.42** (unchanged).
- Exact built source: `1d074941dc4145f6827beb2c43775bab6caec20e` on
  `prep/sent-steering-live-20261016`, published on GitHub.
- Source directory: `/mnt/vk-storage/vk-sent-steering-release-20261016/source`.
- Active release: `/mnt/vk-storage/vk-sent-steering-release-20261016/release`.
- Entry: `/assets/index-CGY9AEy0.js`; CSS `/assets/index-CEkW_l7u.css`.
- Live pointer: `/home/mcp/.local/share/vibe-kanban/frontend-dist/current`.
- Authorization: Seamus's frontend-only deployment approval, reported at
  21:23 UTC and explicitly relayed by the operator for this activation.
- Activation and initial acceptance: **2026-10-16 21:49:43 UTC**.
- Receipt: `/mnt/vk-storage/vk-sent-steering-release-20261016/activation.json`.
- Scope: atomic static-pointer change only. No backend/API/sidechat/store restart,
  data restore, policy, pairing, grant or conversation change.

The package retains the exact Mobile/Dot baseline `9d76d7faf00a0997c9580cf3c8d3bd63f6440ad1`
and adds PR257's two runtime files plus its synthetic test fixture. PR257 merged
into staging as `9301e6a463a4832cc14976c7a19fa40f58567b05`.
New PR254 notifications and backend changes are **excluded**.
Production Dot mode remains enabled; fixture mode remains disabled.

## Verification and preservation

Fresh preflight rechecked source, all packaged/incumbent hashes, exact merged
runtime files, green CI, preparation results, Desktop rollback hash and runtime
identities. After switching, both public and loopback routes served the exact
new index, new entries and retained old entries. API version stayed 0.1.42;
all five monitored backend/static/gateway/Dot/notifier PIDs stayed unchanged.
The 43-project API list retained its order. No active agent was stopped.

Actual live Chromium checks pass at 393/1440px: real Dot unpaired gate remains
401, mobile tab switching preserves one panel, no horizontal overflow or page
errors, 16px mobile input and at least 44px mobile pairing button. Pairing and
message writes were blocked; no real prompt or Dot message was sent.

Post-switch tests load the actual HTTP-served static frontend (no static-file
substitution). All **nine** Send/steering cases pass at 390/412/1440px, including
sent-draft navigation/reload, failed-send recovery, retry, queue fallback and
cancellation, duplicate activation, keyboard submission and Work View landing.
All **five** Mobile/Dot viewports pass at 360/393/412/844/1440px: tab/draft
preservation, mock pairing gate, failed-send/retry with identical request body,
mobile input/tap geometry and no overflow/page errors. API/WS steering state and
Dot pairing/messages are synthetic; no real model calls or Dot messages were
sent. Live reads and real served assets were exercised.

Prior package acceptance passed nine compiled Send/steering cases, five Mobile/Dot
viewports, 21 history tests and 16 link tests, plus production build, four frontend
type checks, lint and preparation tests. Exact-head CI:
https://github.com/artinflight/vibe-kanban/actions/runs/38927199002 .
Source-map checks preserve Mobile/Dot/history/link sources; inline compatibility
scripts and old hashed assets remain included. Full package: 1,864 files.

Receipt and test root: `/mnt/vk-storage/vk-sent-steering-release-20261016`.
`activation.json`, `READINESS.json`, `release-manifest.json`,
`post-activation-browser.log`, `post-switch-steering/results.json` and
`post-switch-dot/results.json` provide the deployment/acceptance evidence.

This was browser viewport QA, not a physical S25+ test. Live project mutations,
Kanban drag/status, intentional review clearing, saved-message UI/REST/WebSocket
roundtrip, codeblock clipboard and attachment upload were not re-exercised.
The old `vk_live_regression_smoke.py` is pinned to an August release/PID/data
snapshot and is not an applicable acceptance script. Its obsolete assertions
were not treated as current release evidence. Existing retained-source checks
and read-only/live fixture checks do not claim a new full end-to-end backend QA.

## Rollback and operator action

Previous static tree remains `/mnt/vk-storage/vk-mobile-dot-route-20261016/release`.
Desktop archive: `desktop:B:/vk-backups/vk-sent-steering-release-20261016/frontend-before.tar.zst`.
SHA256: `0256874e9395f7e02a15a0b54aa07cd70675f68a6a591eaf7bc0017b53acd777`.
Upload, remote hash, readback and full physical restore verify all 1,760 previous
files (424,489,943 bytes). A private same-server atomic switch/rollback rehearsal
passed before activation. A rollback switches the static pointer only; never
restore stale application data or restart the backend for this release.

No release gate or interruption remains. Existing tabs need a normal refresh.
Old already-sent drafts cannot safely be distinguished from unsent recovery text;
clear a known sent legacy draft once if it remains, without resending. Future
confirmed immediate steering clears its persisted scratch. Failed and queued
drafts remain recoverable. No phone reboot, re-pairing or new access is required.

## Later Dot notification handoff

Owner workspace: `de2d98a3-b73f-4e70-9445-caee5cae188c`.
Branch: `vk/de2d-vk-preserve-dot`; PR254.
Owner reports immutable implementation `166b0776b` and staging reconciliation
`ab9a9cf9b` pushed and mergeable including merged PR257; 57 Python tests plus
DOM/Chromium checks pass. Integration source
`/mnt/vk-storage/vk-dot-notifications-20261016/integration/source` is based on
this exact `1d074941d` source. Owner reports both steering runtime files and
Mobile workspace routing/RightSidebar remain byte-identical. These are owner
source-test reports, not a packaged or activated notification release.

The new work adds persistent Dot unread/Needs Attention, separate violet badges
and additive Python sidechat API/store changes. None is enabled by this release.
Shared types were still finishing at the owner's handoff. Preserve this activated
Mobile+Steering baseline in the later package; do not follow a moving PR head.

Required later sequence: complete PR254 sidechat Store/browser API and connector
schema first; the browser service has a separate source pointer. Then package
the latest Mobile+Steering source with the tested notification delta and verify
backend compatibility, unread persistence/clearing and independent workspace/Dot
indicators. Preserve existing sessions, subscriptions and grants; grant no new
persistent access. Owner's `DOT_NOTIFICATION_HANDOFF.md` in PR254 covers the
backend-first rollout/rollback and pending postdeployment phone QA. Dot owner
hands off that deployment separately; it does not block this activated release.

A copy of this final note is placed at the release root and prepared source as a
post-build operational sidecar. It does not change the exact built source commit,
runtime files or packaged manifest. The source-side copy is intentionally
untracked; release identity remains the immutable built SHA above.
