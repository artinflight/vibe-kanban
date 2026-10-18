# Project unread notices in Workspaces

Positive project Dot Chat unread summaries appear once per project in Workspaces
Needs Attention. Compact unboxed rows identify the project name and
`Project · Dot Chat`, with a small blue unread badge distinct from purple workspace
badges. The row itself has no blue fill or outline. Mobile shows them
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
attention/manual-unread data. Browser checks include color confined to the badge, compact two-line notice
height and no horizontal overflow. No real conversations, authentication or live
services are modified; physical-phone and served-live acceptance are not claimed.

Local checks: notice unit/DOM/browser tests and existing routing, grouping,
notifications/manual-unread, Jump, management and neutral-presentation DOM
regressions pass; repository formatting and ops governance pass. The broader
local-web TypeScript process exhausted its existing heap allowance; that run is
incomplete, not a type-check pass. Exact-head hosted CI remains a release gate.
No production build or Rust workspace tests were run for this frontend addition.

## Coordinated release

This visual correction is frontend-only and starts from the current combined
live source, retaining routing/resize, Reply/Jump, management, neutral dispatch,
selective acknowledgements, Eastern timestamps, collapsible UI and CU/Stop.
No new Python/API/schema/access requirement. Staging's existing PR276 record was
notified before preparation; no competing combined activation or service restart.

Staging subsequently verified the combined source366cfd243 live at09:35 EDT.
The owner's visual correction is based on that exact current entry and changes
only this presentation component. A source-derived component drop-in preserves
all other compiled bytes and incumbent assets, with the previous immutable root
retained for rollback. Fresh drift checks and actual served390/1440 acceptance
are required; no Python, service, database or running-agent change is needed.
