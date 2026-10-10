> Latest owner instruction: corrected frontend inclusion with existing VKStaging
> is explicitly authorized. Read VK_STAGING_FRONTEND_HANDOFF_20261009.md; final
> functional source66e00728c has all ten CI jobs green. The old activation guard
> protects against a stale package and independent deployment, not an assumed
> unresolved frontend permission. Existing owner release/cutover rules still apply.

# Mobile opening-screen investigation — October 9, 2026

Seamus reports that mobile still opens directly to Create Workspace and expects
WORK VIEW (the Workspaces list). This report is reproduced against the actual
served frontend. It does not establish failure of the unpublished workspace-first
fix. The operator's actual entry URL, installed shortcut/PWA and browser session
remain unknown; no operator profile or credentials were inspected.

## Served version versus fixes

Read-only HTTPS snapshots at 11:30:53 and 11:56:45 UTC agree byte-for-byte:

| Version                                                                           | Entry module                   | Root launch      | Workspaces from restored Create, then reload |
| --------------------------------------------------------------------------------- | ------------------------------ | ---------------- | -------------------------------------------- |
| Live October 8, main `22f09e245332d22301d532f0ee3e8229906773ac`                   | `/assets/index-JMqAOzZ4.js`    | Create Workspace | Returns to Create Workspace                  |
| Isolated PR228 candidate, clean source `9b53418fc7fa05e07044297bfe48bf8d01471881` | `/assets/index-CCDYp2hT.js`    | Workspaces list  | Returns to Create Workspace                  |
| This PR233 follow-up, source preview                                              | `/src/app/entry/Bootstrap.tsx` | Workspaces list  | Stays at `/workspaces`, showing the list     |

The served JavaScript SHA256 is
`71b470cb64f3dffcb6abf77cb753204b67f8a4ca97225fae9399dd9c32bb7dfa`;
CSS `/assets/index-CQFlZPbR.css` is
`371ade02267e207abce0f803c4bc38b5e09ee87ebae056c7980269fe88db8290`;
HTML is `ab7c3637e64b3bafe1db5ec85f33d132e5c92609a80fd93a08cf83ed277d0f34`.
These match the October 8 release manifest. Runtime frontend resolves to
`/mnt/vk-storage/vk-mobile-release-20261008/release/frontend`.
The read-only backend observation remains Green PID3027197, API version 0.1.42.
The API version alone does not identify the frontend. These snapshots are dated
observations, not a claim about later VKStaging operations.

PR228 is rebase-merged into staging as `c3cea2c75`; staging `e8c450fb5` has the same
application tree as clean source `9b53418fc`. Promotion PR232 remains open with
passing CI. Its previously refused rebase merge was not retried by an alternate
method. No branch protection, protected ref, production pointer, service, data,
model/effort or Recommend-only routing was changed by this investigation.

## Launch, session and cache diagnosis

The live root and `/workspaces` both redirect to `/workspaces/create`. This occurs
in clean task-owned Chromium profiles and after browser-process restart. Warm
launches demonstrably reuse the old hashed JS/CSS from disk cache, yet the same
entry version and behavior occur on cold launches. Controlled profiles have no
service-worker controller, registrations or CacheStorage entries. The existing
notification worker has no fetch/cache handler. Old served code is sufficient to
explain this reproduction; clearing Seamus's cache is not a demonstrated fix.

PR228 correctly changes root launch and `/workspaces` into the list. A separate
existing edge remained: on `/workspaces/create`, the mobile Workspaces tab changed
an in-memory panel without changing the URL. After reload, the create-route
layout effect selected chat again. The mobile tab is memory-only, not a persisted
localStorage preference. This follow-up navigates that tab to `/workspaces` so its
selection survives reload and subsequent restoration of that URL. Explicit Create
Workspace links still open creation; selected-workspace/session deep links and
creation drafts retain their existing behavior.

The served manifest has no `start_url`, and both it and hashed assets have
`public, max-age=31536000, immutable`; HTML has `no-store`. Under the
[Web App Manifest specification](https://www.w3.org/TR/appmanifest/#start_url-member),
a missing start URL falls back to the document URL. An existing installed entry
could therefore retain a creation URL; this is an inference, not an observation
of Seamus's icon. The follow-up declares `start_url: "/"` and versions the local
HTML manifest link as `/site.webmanifest?v=workspaces-home` to request the new
manifest after deployment. Root still respects onboarding before Workspaces.
Existing installed shortcut/WebAPK migration has not been proven. A deliberately
opened `/workspaces/create` URL continues to show Create Workspace.

## Validation and evidence

`scripts/testing/mobile-launch-browser.mjs` performs nine checks at each of 390px
and 412px: fresh root, reload, repeated root, Workspaces link, explicit creation,
browser-process restart restoring creation URL, Workspaces selection, reload
after selection, and restarted root. All 18 observations passed for each of live,
frozen PR228 bundle and this source follow-up, with version-specific expectations.
Before/after screenshots, exact module hashes and cache observations are recorded.
The new manifest/start URL is asserted on the follow-up. Cache reuse is recorded
on the built live/frozen versions; Vite source-preview caching is not equivalent
to production asset caching.

The existing workflow harness passed at 1440px against the follow-up: landing,
project/task/workspace navigation and Back, saved state, message reading, prompt
composition without submission and preserved desktop layout. Both harnesses
intercept `/api` and `/v1` mutations, allow only read-only summaries, and forward
server subscription messages without forwarding browser WebSocket frames. No
prompt or inference was submitted.

All four frontend type checks, local-web/UI lint, focused Navbar ESLint, repository
formatting and launch-script syntax passed. The initial default-heap TypeScript
attempt exhausted Node memory; the 4 GiB retry passed. Aggregate backend checks,
Clippy and Rust tests did not complete: the shared Cargo target is owned by
VKStaging's active build. Only this task's waiting validation processes were
stopped; no owner process was interrupted. New-head full CI must establish the
remaining baseline. There is no production build of the follow-up yet.

An initial validation incorrectly created a per-worktree Cargo target before the
shared target was set. It was stopped, checked for consumers, and moved intact to
this task's SSD evidence directory, without deletion. Subsequent Cargo commands
use `/mnt/vk-storage/cargo-target` and `CARGO_INCREMENTAL=0`.

Physical S25+ acceptance was attempted through the documented Desktop ADB forward;
the Desktop ADB endpoint was unavailable. No shared ADB server, networking or phone
state was changed. Actual installed-PWA behavior, Android keyboard/browser chrome,
Safari/Firefox and production writes remain unverified.

Private screenshots, task-owned profiles, logs and JSON snapshots are under
`/mnt/vk-storage/vk-mobile-launch-20261009/{live,frozen-candidate,followup,desktop}`
and adjacent evidence files. They are not committed or uploaded.

## Smallest remaining release action

VKStaging owns active build/restart coordination. It must adopt this PR233 launch
follow-up alongside PR228 in the approved release source, rebuild the frontend,
and bind its artifact hashes to the reviewed source before activation. The frozen
`9b53418fc` candidate does not contain the tab-route or manifest changes and must
not be presented as this complete follow-up.

The earlier task-owned activation helper now checks
`/mnt/vk-storage/vk-workspaces-release-20261009/release-coordination-hold.json`
and refuses activation while that explicit operator hold is active. No activation
was attempted. PR232 remains pending; there is no authorization to bypass its
required approval or merge-method restriction. After the owner completes the
approved release, verify actual served hashes, Seamus's entry URL/icon, and cold
and repeated mobile launch. No further redesign is required for this scope.
