# Workspace project filter publication — 2026-10-31

The operator approved the mobile project dropdown and compact desktop bubbles,
then authorized PR integration, rebase merge and deployment. Public frontend
activation completed at **13:07:50 UTC**; read-only verification passed at
**13:08:41 UTC**. Version is **0.1.42**; use source/hash identities below.

## Source and integration

[PR #286](https://github.com/artinflight/vibe-kanban/pull/286) targets staging with
the requested rebase method. The PR merge event records integration and rebased
IDs; main promotion is separate. Application source head
`d83e7587a13184126f9935cf692e010520354362` contains the mobile dropdown,
direct mobile sort/filter controls, and desktop 28 px abbreviation/color bubbles.
The shared appearance helpers preserve saved project customizations and full
accessible names. Both controls share existing filtering and persistence.

The live frontend already contained unread/review/reselect fixes that were absent
from staging. Deployment source `02a9a993d8d9118ca703a22baa15efcf0c7cc4c9`
combines those live fixes at `b990b5939642b1ac7e744a9290840a731fa3f550`
with the filter changes. All 11 existing live package files and all 15 changed
filter package files match their respective sources exactly. The composition is
pushed on `deploy/workspace-filters-20261031-311d`; those other-stream changes
are not added to staging by the filter PR. Original source receipts remain intact.

## Production and recovery

- URL: <https://vibe.local/workspaces>.
- Public JS: `/assets/index-Bgdr6hzC.js`; CSS: `/assets/index-DL7rKLPs.css`.
- Receipt root: `/mnt/vk-storage/vk-mobile-filters-20261031-311d`.
- Public frontend: `paired/candidate` under that root; fallback: `paired/fallback`.
- Previous frontend: the October 31 unread/reselect paired candidate.
- Package contains 417 new build files and retains 612 hashed assets across both
  versions. Previous JS/CSS also passed independent public hash readback.
- Source bundle and paired recovery archive (46,612,803 bytes together) were
  mirrored to Desktop B and independently reopened before activation. Exact
  descriptors and readback evidence are in `Desktop-B-recovery-verified.json`.
- The frontend pointer changed atomically in 0.033 seconds. All five service PIDs
  and invocation IDs stayed unchanged. Backend source remains `9a4179e8b`,
  executable SHA256 `137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
  Database device/inode and 99 migrations stayed unchanged. No backend restart,
  database restore, route replacement or provider inference occurred.

An immediate frontend-only cutback can use the paired fallback after fresh
ownership/pointer checks. Preserve all assets and current data. This receipt does
not authorize future service restarts or replay a consumed activation controller.
Backend/history-proxy direct frontend roots retain their October 30 assets;
the public gateway/static frontend uses this release.

## Validation and limits

Production-candidate browser acceptance passed at 360, 412, 767, 768 and 1440 px:
actual filtered rows, multi-select, No project, reset, local save/reload, shared
dialog state, responsive resizing, keyboard focus, 300 px sidebar scrolling,
compact dimensions and saved abbreviation/color parity with the left menu.
The harness waits for stable named items, menu animations and preference hydration.
Existing review-flag acceptance passed at 393/1440 px. All application mutations
were intercepted into disposable fixtures.

Public browser acceptance at 412/1440 px used normal production WebSockets, showed
54 workspace cards in each viewport and no page errors. `after-live.json` confirms
public/backend capability routes, exact public asset hashes and unchanged backend
and database identities. `final-verification.json` also confirms old public assets.

All four frontend TypeScript checks, frontend ESLint, root formatting, explicit
UI/test Prettier, ops governance and unused-i18n checks passed. Application-head
hosted frontend checks and deployment artifact build passed. Final-head GitHub
checks are required before merge and are recorded by PR #286.

Local `pnpm run check`, `pnpm run lint` and `cargo test --workspace` cannot finish:
the host's offline Cargo registry cannot resolve serde. No physical-phone UI QA
or new native-provider execution was performed. The inherited nested filter
dialog Escape/pointer-lock issue is outside this direct-selector change.
