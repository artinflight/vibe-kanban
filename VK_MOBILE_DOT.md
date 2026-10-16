# Mobile Dot navigation

## Live phone QA deployment — October 16

The operator's later explicit deployment request authorized this frontend-only
phone QA rollout. It is live at [Vibe](https://vibe.local/) from 15:41 UTC.
The earlier publication/correction statements below describe their original
scope; this separate deployment is now complete. PRs #254 and #255 remain draft
and unmerged. No backend/API/connector install, service restart, grant or pairing
change was performed.

- Clean build source: `5ffaa3b4687d342e940fa80b4b963b8efc6d06e0`; real Dot enabled,
  fixture mode disabled. [Exact-source CI passed](https://github.com/artinflight/vibe-kanban/actions/runs/38923258466).
- Live release: `/mnt/vk-storage/vk-mobile-dot-deploy-20261016/release`.
  Entry assets: `/assets/index-DTWehWC4.js`, `/assets/index-CEkW_l7u.css`.
  Index SHA256: `e4bba4efc4f87db77b9ec1bd83575ef60a296bee21ed3e61f146e3b1e86308b6`.
- A separately bounded build job completed successfully after the first build
  hit the agent's soft memory limit. Production services were untouched.
- Packaged browser tests passed at 360/393/412/844/1440px with simulated
  pairing/send/retry. Actual live browsers at 393/1440px verified the real 401
  pairing gate, phone Dot/Git switching, one panel, touch sizing and no page errors.
- All five monitored runtime PIDs and project count/order (43) stayed unchanged.
  All 1,551 incumbent files were hash-checked; old entry assets remain served,
  and inline compatibility scripts are unchanged.

Rollback covers the static frontend tree and compatibility sidecars, not live
application databases or session stores. The Desktop archive is
`desktop:B:/vk-backups/vk-mobile-dot-20261016/frontend-before.tar.zst`, SHA256
`a7b200a6b6e8d7d8dd34b9cf278f1f1d60236eb9e89a3812ee2649d1b718fc22`.
Desktop upload/hash/readback and full restore verified 1,551 files totaling 342,928,569 bytes.
The preceding frontend remains at
`/mnt/vk-storage/vk-dot-sidechat-live/frontend-releases/975f62c7c`;
a frontend rollback atomically restores the current pointer to that directory,
without restarting services or restoring application data. Retention/latest
backup pointers were not changed.

Private deployment manifests, validation screenshots and executed tooling are
under `/mnt/vk-storage/vk-mobile-dot-deploy-20261016/`. The read-only smoke did not
exercise archive/menu/default-repo flows, attention clearing, drag/status writes,
queue updates, codeblock copy, attachment writes, sub-agent state semantics or
saved-message REST/WebSocket/picker behavior. Those source areas and incumbent
assets were retained; no broader interactive regression pass is claimed.

**Seamus's next check:** refresh Vibe on the S25+, open an issue-linked workspace,
and tap **Dot** beside **Chat**. The phone needs its own private pairing code if
it is not already paired. Physical keyboard and actual phone message/reply
acceptance remain pending. The desktop reply proof and root-connector boundary
are unchanged by this frontend deployment.

Published as [draft PR #255](https://github.com/artinflight/vibe-kanban/pull/255)
against `staging`, stacked on [preservation PR #254](https://github.com/artinflight/vibe-kanban/pull/254).
The PR records the mobile-only comparison, merge order, host validation limit,
and pending phone keyboard/phone roundtrip/deployment acceptance. The
mobile issue is [T60](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d/issues/c961527e-f090-4eac-9483-2480d016a552).
Publication alone did not activate the tab; the separately authorized rollout is recorded above.

The local workspace navigation includes a **Dot** button beside **Chat** when
`VITE_DOT_SIDECHAT=1` (or the isolated fixture flag) is enabled. Dot gets the full
mobile content area. Git/details retains its existing tools and Notes. Desktop
keeps the resizable sidebar. The remote frontend and builds without the flag
retain their existing navigation.

This mobile follow-up is stacked on [preservation PR #254](https://github.com/artinflight/vibe-kanban/pull/254),
branch `vk/de2d-vk-preserve-dot`, pinned at
`14fca343bc1f466cb369524570a199271082208c`. That shared baseline owns the original
API, sidebar UI and responsive CSS. The original mobile commit `6a3af844c` was
replayed onto that history before publication; its frontend files remain byte
identical. The preservation branch and workspace were not modified.

Review the mobile-only delta from the pinned preservation commit to this branch.
Both PRs target `staging`, so GitHub's aggregate diff includes the shared baseline
until #254 is integrated. Merge the preservation work first, then rebase this
follow-up onto the resulting staging commit before merging it. Do not use the
mobile PR as a second independent publication of the API/UI baseline. Its changes
are the labeled Dot navigation, full-screen mounting, shared wrapper/flag, browser
acceptance harness and mobile notes. It does not change connector/API behavior.

The mobile panel remains mounted when switching tabs, preserving drafts and
pending requests. It resets when the workspace changes. Inputs use 16px text,
controls have 44px touch targets, long context labels wrap, and the chat can
scroll when the keyboard reduces the available height. Existing pairing, project
scope, CSRF, receipt and retry behavior is retained.

## Desktop success and remaining connector/phone checks

Seamus confirms that the first desktop Dot chat request/reply test succeeded on
October 16, witnessed in his screenshot. It used the integration task's available
connector. This is a successful desktop reply test; the mobile browser harness
below still uses simulated pairing and sends.

Direct root Dot connector access remains unverified because root Dot still lacks
the new tools. A real phone roundtrip and physical S25+ software-keyboard
acceptance also remain unverified, pending Seamus making the phone available.
No private conversation identifiers, receipt identifiers or screenshot contents
are included in this correction. Publishing it does not authorize deployment.

## Validation

Repository formatting, ops governance, all four frontend TypeScript checks,
and the production frontend build pass (with an 8GiB Node heap). Local-web and UI lint pass. Focused shared lint passes except for the
pre-existing RightSidebar useMemo dependency warning (also present at the base).
The required `pnpm run check`, `pnpm run lint` and `cargo test --workspace`
were attempted before publication with the shared SSD Cargo target and incremental
compilation disabled. The frontend stages passed; the Rust stages fail on this
host's missing `glib-2.0` pkg-config development library. Later aggregate stages
are not certified. No Rust, remote deployment, schema or generated types changed.
GitHub CI passed for the pre-correction heads of both
[preservation #254](https://github.com/artinflight/vibe-kanban/actions/runs/38911578393)
and [mobile #255](https://github.com/artinflight/vibe-kanban/actions/runs/38914513436).
The mobile run validated `9b5625be5`. Later commits require their own checks;
passing CI does not establish phone or connector-route acceptance.

`scripts/testing/mobile-dot-browser.mjs` exercises the real branch frontend at
360/393/412px, 844px landscape and 1440px desktop. It simulates browser pairing,
long labels/history and a failed send/retry. It checks direct navigation, draft
retention, a single mobile chat instance, request identity reuse, input/control
sizes, and no horizontal overflow. All Dot responses are intercepted and other
application writes are blocked. No real pairing or prompt delivery is claimed.

Run with `VK_TEST_OUTPUT` on mounted SSD. The default base is localhost:3002;
override `VK_TEST_BASE` and optionally `VK_TEST_BACKEND` for a device tunnel.
`PLAYWRIGHT_MODULE` selects the installed Playwright module. `VK_TEST_CDP` opts
into a physical Chrome connection; the test uses only its own page and leaves
the shared browser running. Keep the phone unlocked with Chrome foregrounded.

Evidence: `/mnt/vk-storage/vk-mobile-dot-20261016/`.

## Release and phone acceptance

The preview uses the existing live gateway on port4720. Port4511 in the older
preview guide is no longer active. This does not create or restart a backend.
The current live frontend remains the release recorded in
`/mnt/vk-storage/vk-dot-sidechat-live/frontend-activation.json`.

The physical S25+ is reachable through the documented Desktop ADB server and
reports SM-S936W, 1440x3120, density560. Its screen slept during the first Chrome
attempt, so actual keyboard acceptance remains pending. Do not describe the
browser-size checks as physical phone acceptance.

Before activation, complete a clean source-bound frontend package, preserve and
verify incumbent immutable files, and follow the frontend activation/rollback
runbook. The frontend is now deployed for phone QA as recorded above; publishing or merging a PR alone does not activate it. The phone browser needs its own unconsumed
pairing code entered privately by the operator at https://vibe.local; existing
desktop pairing does not authenticate the phone. This task neither generates nor
reads a real pairing code. The successful desktop reply used the integration
task's available connector. Direct root Dot access and a real phone roundtrip
remain unverified; the simulated mobile send test does not establish either.
The later explicit deployment request authorized the rollout recorded above; this correction alone did not authorize it.
