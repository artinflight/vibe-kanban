# Mobile Dot navigation

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

## Validation

Repository formatting, ops governance, all four frontend TypeScript checks,
and the production frontend build pass (with an 8GiB Node heap). Local-web and UI lint pass. Focused shared lint passes except for the
pre-existing RightSidebar useMemo dependency warning (also present at the base).
The required `pnpm run check`, `pnpm run lint` and `cargo test --workspace`
were attempted before publication with the shared SSD Cargo target and incremental
compilation disabled. The frontend stages passed; the Rust stages fail on this
host's missing `glib-2.0` pkg-config development library. Later aggregate stages
are not certified. No Rust, remote deployment, schema or generated types changed.
GitHub CI is still required before merge.

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
runbook. Live deployment is pending; publishing or merging this PR does not activate it. The phone browser needs its own unconsumed
pairing code entered privately by the operator at https://vibe.local; existing
desktop pairing does not authenticate the phone. This task neither generates nor
reads a real pairing code. Actual Dot roundtrip requires the existing integration's
scoped subscription; the simulated send test is not proof of external delivery.
