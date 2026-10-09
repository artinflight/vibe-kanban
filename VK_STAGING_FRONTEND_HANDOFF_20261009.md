# Corrected frontend inclusion for VKStaging — October 9, 2026

## Owner instruction and authority

Seamus explicitly says: **“make sure the new frontend deploys with staging.”**
Include the corrected frontend in the existing VKStaging release. Owner session:
`7d6734c1-c8d0-4d55-ac27-b1f763d15a6e`; its existing execution is already running. Do not start a second
turn, interrupt its build/restore, independently switch production, replace its
pinned backend/guard/module, or weaken branch protection.

Frontend inclusion is authorized now. No additional frontend inclusion approval
is requested. The previous “permission pending” reason is superseded for this
scope. Existing protected-branch review/CI rules still apply; any remaining final
interruption authorization belongs to the owner's existing restart procedure.
Specifically, VK_BACKEND_RESTART_PROTOCOL.md's Operator Contract requires an
explicit “cut over now” after measured readiness. Do not reopen an authorization
already held by VKStaging, or treat this frontend handoff as a new restart gate.
The old task-owned activation helper remains guarded solely because its package
is obsolete and activation belongs to VKStaging.

## Exact reviewed source and CI

| PR                                                         | Current role                                                                                                                                                                                                                                                              |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [228](https://github.com/artinflight/vibe-kanban/pull/228) | Rebase-merged into staging at `c3cea2c75fef1be40ca272d6f70b087ac33a5900`; original clean source `9b53418fc7fa05e07044297bfe48bf8d01471881`. Makes root/Workspaces open the list, starts untouched mobile project feeds at To do, and highlights whole actionable cards.   |
| [232](https://github.com/artinflight/vibe-kanban/pull/232) | Open staging-to-main promotion at `e8c450fb59763180a9c66e1bedce1154f09d89ec`. All ten CI jobs passed in run37911463804. GitHub previously refused rebase merge. It does not contain PR233; do not use alternate merge methods or change protection.                       |
| [233](https://github.com/artinflight/vibe-kanban/pull/233) | Existing draft; functional frontend source `66e00728c3efb10e806976e89dd8b4a122037e18`, tree `6973b95387fbde7576301d522568ef06f6a93e78`. Workspaces selection exits `/workspaces/create` to `/workspaces`; PWA declares root start URL and uses a versioned manifest link. |

All ten jobs for functional source `66e00728c` finished successfully in
[run37927081460](https://github.com/artinflight/vibe-kanban/actions/runs/37927081460):
branch policy/freshness, changes, ops, frontend, backend schema, remote wrapper,
Clippy, backend tests and Tauri. The remote wrapper's successful result is not
proof that private deployment-key checks were exercised. Final Clippy completed
at 12:04:35 UTC. Subsequent handoff-only documentation commits do not change the
functional frontend source; their CI status is recorded separately.

## Source/base compatibility and avoiding a backend rebuild

The fork's observed main is `22f09e245332d22301d532f0ee3e8229906773ac`; observed
staging is `e8c450fb59763180a9c66e1bedce1154f09d89ec`. Between staging and functional
source `66e00728c`, product changes are only these three files:

- `packages/local-web/index.html`
- `packages/public/site.webmanifest`
- `packages/web-core/src/shared/components/ui-new/containers/NavbarContainer.tsx`

PR228's product diff plus these three files is twelve frontend files relative to
main22f09e245. Backend code, shared generated types/schemas, Cargo manifests/lock,
root package manifest and pnpm lock are unchanged between main22f09e245 and
66e00728c. Existing incumbent APIs were used in read-only acceptance. This change
requires no backend rebuild or migration. Retain the owner's independently
verified pinned executable, capacity guard and routing module; record their
existing source/hashes alongside the distinct frontend source/hash.

The isolated package contains two bounded product patches: the complete frontend
diff from main22f09e245 and the three-file follow-up from staginge8c450fb5.
At a safe preparation boundary, the owner should compare its actual combined
frontend base, preserve any newer frontend repairs (especially attention/saved
messages), and adopt the matching patch/source. Do not merge this older branch
wholesale over the owner's newer combined source. A packaged frontend can be
reused when its inputs match the intended frontend and required API/schema
contracts are compatible with the pinned backend. Otherwise reconcile only the
frontend changes and rebuild frontend assets; leave the backend artifact pinned.
A Git merge SHA alone is not proof of these behaviors being present.

Read-only comparison against the reported combined source
`e3de640de12a5ad17e6e100b6149b57cceb58120` found its entire `packages`, `shared`,
root package manifest and pnpm locks/workspace identical to main22f09e245. The
bounded complete frontend patch applies cleanly to those inputs. This establishes
compatibility with that reported source base; the owner must confirm the actual
pinned artifact/current candidate source is still this base or reconcile newer
changes. No owner checkout or artifact was modified for this check. The owner's
subsequent comparison identified six newer frontend repairs in its actual combined
release. Therefore the e3de640d comparison does not establish that standalone66
assets match the actual final candidate. Combine the non-overlapping changes and
build only the frontend, as the owner is already doing.

Use an isolated release directory under mounted SSD. Bind source, all file hashes,
entry HTML/JS/CSS, manifest and prior lazy chunks to that release. Point the actual
candidate runtime `VK_FRONTEND_DIST_DIR` at it using the owner's packaging step;
ensure candidate and compatible cutback retain the corrected UI. Do not assume
changing the general `frontend-dist/current` pointer changes a service pinned to
a different runtime path. Revalidate the packaged candidate using its real API,
without taking over its namespace, process manager or mutable data.

## Offline source handoff and frontend acceptance

Package root:
`/mnt/vk-storage/vk-mobile-launch-20261009/frontend-handoff-package`.
Read `source-handoff-manifest.json`, `base-compatibility.json`,
`reference-build-disposition.json` and `owner-delivery.json` there for patch/input
identities, validation and delivery. This directory is a verified source handoff,
not a deployable frontend release.
The detached build worktree is
`/mnt/vk-storage/vk-mobile-launch-20261009/frontend-handoff-build` at 66e00728c;
tracked source is clean, with explicitly declared dependency symlinks only.
The reference build wrote solely to the isolated package and submitted no Sentry
upload. At 12:31 UTC it was stopped after the owner confirmed that its actual
combined frontend has six newer non-overlapping MCP consent/chat repairs and is
already building the required combined assets. Deploying standalone66 assets
would omit those repairs; incomplete output is preserved and explicitly marked
not deployable. No packaged-byte acceptance is claimed for that cancelled build.
No Cargo backend build or activation is part of this handoff preparation.

The earlier frozen `/mnt/vk-storage/vk-workspaces-release-20261009/release/frontend`
contains 9b53418fc / `index-CCDYp2hT.js`, **not** the complete 66e00728c fix.
It must not be used as the latest frontend. The live version last verified at
12:26:16 UTC is main22f09e245 / `index-JMqAOzZ4.js`, JS SHA256
`71b470cb64f3dffcb6abf77cb753204b67f8a4ca97225fae9399dd9c32bb7dfa`.
This old version opens Create Workspace in both clean and warmed profiles.

Release acceptance must include all of the following:

1. Fetch actual routed HTTPS `/`, its referenced JS/CSS and versioned manifest;
   compare bytes to the adopted package manifest, not `/api/info`'s shared 0.1.42
   version. Identify the real runtime frontend path and pinned backend hash.
2. In fresh 390px and 412px phone profiles, cold `/` and `/workspaces` open WORK
   VIEW: the Workspaces list, with no standalone Create Workspace composer.
   Repeat root launch, reload and browser-process restart with a warm profile.
3. Explicit Create remains usable. From restored `/workspaces/create`, selecting
   Workspaces changes the URL to `/workspaces`; reload/reopen that URL stays in
   WORK VIEW. Selected workspace/conversation deep links remain reachable.
4. Manifest link is `/site.webmanifest?v=workspaces-home`, with `start_url: "/"`.
   Record cache/service-worker behavior and exact entry module used. Old served
   code, old cached assets and an installed icon pointing to an explicit Create
   URL are distinct cases; don't claim cache clearing fixes an unpublished build.
5. On Seamus's actual phone, identify the launch URL/icon/session and repeat
   cold and repeated opening. An already installed WebAPK/shortcut migration is
   not established by desktop Chromium profiles. Physical ADB was unavailable
   in this workspace; do not claim actual device acceptance until performed.
6. On the adopted candidate and after cutover, verify project/task/workspace
   navigation, To do default and explicit status preservation, whole-card unread/
   review attention and clearing on intentional review, saved agent messages,
   prompt composition and desktop layout. Use read-only/mock mutations for tests;
   retain the owner's full restart/regression checks and configured model/effort
   with Recommend-only routing.

The existing launch harness is `scripts/testing/mobile-launch-browser.mjs`;
set `VK_LAUNCH_EXPECT_ROOT=/workspaces`,
`VK_LAUNCH_EXPECT_TAB_ROUTE=/workspaces` and
`VK_LAUNCH_EXPECT_MANIFEST_START=/`. Playwright module/browser/backend/output
arguments and screenshots/results are recorded in the private package receipt.
Live steering was accepted at 12:20 UTC via the normal app endpoint (HTTP200,
empty queue after steer), preserving the existing executor configuration. A
12:23 read still reported the same active execution and unchanged execution count;
no new turn was requested. The owner subsequently acknowledged final66 inclusion,
reported reconciliation with its six newer frontend repairs and started a combined
frontend build while keeping executable/guard/routing artifacts pinned. Actual
release packaging, asset binding and cutover acceptance remain unverified by this
workspace. Transport receipt and runtime details stay local and are not published.

Source-preview launch acceptance previously passed 18 observations at 390/412px;
desktop1440 workflow passed. All ten functional-source CI jobs passed, including
the frontend build. The owner must perform packaged-byte acceptance against its
combined frontend and actual candidate; the obsolete reference build adds no such
evidence.

## Delivery contract

The connector's `run_session_prompt` starts a turn and is not used. The normal
app route `/api/sessions/{session_id}/queue` supports active Codex steering and
refuses a queued fallback if the active turn cannot accept it. Before sending,
verify the named execution is still running/manual, retain its exact executor
configuration, and do not overwrite queued content. A successful live-steer API
response confirms transport acceptance, not that the owner has completed adoption.
If steering is unavailable or uncertain, keep this durable handoff and let the
main root deliver it at the next safe idle; never start a duplicate turn or retry
an uncertain message blindly. `owner-delivery.json` records the actual result.
