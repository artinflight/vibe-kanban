# Workspace actions on status/time row — November 5, 2026

`ee435a75c` moves the accessible bookmark and three-dot controls below the title,
onto the existing status/time line, on desktop and phone. Independent opening
and action buttons avoid nested buttons and preserve action click isolation.
Titles use the full available width; phone actions retain 44px targets.

Published at 2026-11-05T10:46:08.024061+00:00, version 0.1.42, <https://vibe.local>.
Reload tabs. No source push/PR or staging/main promotion.

## Validation and preservation

The exact previously served source was verified across 1,324 inputs; only
WorkspaceSummary.tsx changed among production inputs. Reviewed test scripts were
copied separately. Bounded tsc/Vite produced 417 hashed files; VITE_DOT_SIDECHAT=0
was explicitly retained. 1,190 assets are preserved in both paired roots.

15 mounted interactions, UI type/focused lint, required format/ops, and production
build pass. Candidate and served browser each pass four 1440/393px × read/unread
cases: full-width title, both controls on metadata line, no nested buttons,
persistent save/reload/remove, section bounds, no errors/overflow. Five scrolling
layouts pass each phase. Browser tests intercept application mutations: zero
read-state/application writes or Dot polls. Screenshots inspected at both widths.
These are browser viewport checks, not physical-device QA. Full Rust workspace,
hosted baseline and provider execution were not run.

## Recovery and publication

Evidence root: `/mnt/vk-storage/vk-read-later-20261105-status-row`.
Archive: 121,107,862 bytes; SHA-256
`4ce72068d4cec269b56744b7dbcf8591cf4b702b92833687b75d28e92c25aa5b`. Full isolated extraction verified all
5,177 files before independent Desktop B readback. Existing shared backup
lane respected. No backup waiver or production data restore.

Fresh controller verified pointer ownership, source/output integrity, browser
acceptance, recovery and live health, then atomically switched the frontend in
0.012697s. Public trusted HTTPS asset hashes/API capabilities,
five service identities, backend hash and DB inode/99 migrations stayed stable.
No restart, backend/schema/generated-type change, device action or inference.

Current: `/mnt/vk-storage/vk-read-later-20261105-status-row/paired/candidate`.
Fallback: `/mnt/vk-storage/vk-read-later-20261105-status-row/paired/fallback`. Fallback requires fresh ownership/health
checks and preserves current data; do not reuse a consumed activation controller.
New JS: `index-Ux0VX78J.js`; CSS: `index-DeUaYq-8.css`.
Exact hashes and receipts are in LIVE_DEPLOYMENT.json and the evidence root:
`frontend-artifact.json`, `source-composition.json`, `preservation-after-build.json`,
`pair-receipt.json`, `activation.json`, `recovery-restore-check.json`,
`Desktop-B-recovery-verified.json`, `browser-candidate-verified/browser-results.json`,
`browser-live/browser-results.json`, both `scrolling-browser-*/results.json`, and
`live-after-verified.json`.

## Cross-device report

The reported Premiere Pro bookmark mismatch is explained by `useReadLaterStore`:
it persists `vk-read-later-v1` in browser localStorage, scoped by host/user/kind/id,
and makes no shared preference API calls. Workspace read/unread state is separate.
This layout release does not add synchronization. The sync-scope question is
pending; a shared implementation is not ready or deployed. Existing durable
preferences support order/colors, and scratch has no Read Later field; unrelated
fields must not be repurposed. Future sync needs explicit typed persistence,
local-bookmark migration, independent-context acceptance and tombstone/removal
handling. Backend publication follows the backend restart protocol.
