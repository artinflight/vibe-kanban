# Project unread notices in Workspaces

Positive project Dot Chat unread summaries appear once per project in Workspaces
Needs Attention. Blue notices identify `Project · Dot Chat`, the project name and
unread count, distinct from individual purple workspace badges. Mobile shows them
only in Attention; desktop supports grouped and flat layouts. The Attention tab
counts notice destinations, not the number of messages. Project notices are not
workspace rows and are independent of workspace pagination or an empty workspace
list. Zero unread removes the notice even if an unresolved attention flag remains
in that project's chat; existing project attention indicators are unchanged.

The existing notifications query supplies project counts; existing project lists
supply names, with a project-ID fallback until names load. No count is copied onto
a workspace. Remote-host workspace panes suppress these local Dot summaries.

Clicking navigates explicitly to the project root, dropping any selected issue or
workspace before opening the chat tab/sheet. A short-lived, exact-project UI intent
is consumed only by that root destination; a stale consumer cannot steal a newer
request. An already mounted project chat receives the intent without navigating,
retaining its composer, reply selection and attention cursor. Destination switches
use the existing per-session/destination draft and reply recovery. Navigation does
not resolve flags or directly acknowledge messages; ordinary chat read behavior
continues unchanged.

## Validation

- `node --experimental-strip-types --test packages/web-core/src/shared/lib/dotProjectNotices.test.ts`
- `node scripts/dot-sidechat/test-project-notices-ui.mjs`
- `node scripts/dot-sidechat/test-project-notices-browser.mjs` with existing browser
  tooling, retained baseline CSS and mounted-SSD evidence output.

The actual sidebar, project layout, chat and notifications hook are exercised with
synthetic API data at390/1440: positive/updated/zero counts, distinct project labels,
no workspace fanout, grouped/flat/empty-workspace cases, keyboard activation, exact
project scope despite workspace selection, draft/reply recovery and unchanged
attention/manual-unread data. Browser checks include color distinction,84px notice
height and no horizontal overflow. No real conversations, authentication or live
services are modified; physical-phone and served-live acceptance are not claimed.

Local checks: notice unit/DOM/browser tests and existing routing, grouping,
notifications/manual-unread, Jump, management and neutral-presentation DOM
regressions pass; repository formatting and ops governance pass. The broader
local-web TypeScript process exhausted its existing heap allowance; that run is
incomplete, not a type-check pass. Exact-head hosted CI remains a release gate.
No production build or Rust workspace tests were run for this frontend addition.

## Coordinated release

This is a frontend-only addition atop0107f77b's routing/resize fixes and the existing
Reply/Jump/management/neutral dispatch features. No new Python/API/schema/access
requirement. Staging PR276 was notified before final source publication; Staging
owns the single hosted frontend build and activation. Reconcile both newer inputs
with its held source5fc7899be and retain live Eastern timestamps/collapsible UI,
CU/Stop, private ownership backfill and latest-data rollback contracts.

The read-only prepared receipt says the old-runtime three-row R2 boundary was not
yet consumed. This workspace has not verified a later boundary and does not alter,
replace or restart R2, build a competing package or activate any service/pointer.
Staging must use the actual boundary and its fresh live/backup gates; no new owner
numeric permission is needed. Notify the owner once the coordinated release is
actually verified live, not when source alone is ready.
