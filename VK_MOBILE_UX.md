# Phone UI and interaction design

Branch: `vk/eb7d-vk-native-feelin`. Review: [draft PR #224](https://github.com/artinflight/vibe-kanban/pull/224) into `staging`.
Frontend only; no merge or deployment. The revised design replaces the initial
size-focused pass after operator feedback.

## Screen design

Phones get distinct screens at the existing 767px breakpoint. Vibe’s orange
accent, typeface and light/dark themes remain the foundation.

- **Tasks:** a single task feed replaces stacked desktop Kanban columns. The
  project stays in the app header; a Tasks heading, persistent search and Filters
  provide the screen hierarchy. Status chips show counts and selected state.
  Each task has one title, compact ID/status metadata, an overflow action and a
  direct conversation link when a local workspace exists. The floating New task
  action remains near the thumb. Team/Personal, lifecycle and advanced filters
  remain reachable in Filters. No hover or drag is required.
- **Task detail:** the full-screen view leads with the editable title, then
  status/priority/assignee and the description. Tags and pull requests use a
  labeled disclosure rather than an empty toolbar. Linked workspaces, comments,
  relationships and sub-issues retain their existing sections and actions.
- **Workspaces:** a list replaces desktop accordion panels. Activity chips filter
  All, Attention, Running and Ready; rows show name, actual activity, available
  change/agent/preview/PR information and explicit selected state. Counts and category filtering use the complete filtered collection
  before list pagination. A single useful empty state replaces empty accordion sections. Search, New, Archive,
  host settings and list sort/filter options stay reachable.
- **Conversation:** the compact composer keeps the prompt, Options, Attach and
  Send in the primary layout. Model/permissions, session/turn controls, changes
  and additional tools remain mounted inside Options. This preserves their
  selected values while removing persistent toolbar rows. Normal collapsed
  composer height is about 115px at 390px. User prompts have a subtle tinted
  surface; agent text remains a calm reading area. Copy/edit and attachment-chip
  actions remain available without hover.
- **Navigation:** labeled bottom destinations use a selected icon pill rather
  than a large selected tile and underline. Projects and More use focus-trapped
  sheets. The workspace-list header does not repeat the last selected workspace.

Primary targets are approximately 48 CSS px; targets are scoped to controls
rather than blanket sizing for metadata. Desktop keeps its existing panels,
Kanban dragging, toolbars, compact composer and controls.

## Interaction and safety

Task detail keeps the feed mounted with its dimensions intact, retaining actual
scroll and status/filter state on Back. Workspace panes retain drafts and search
across tab changes. Sheet history is consumed before destination navigation;
Back dismisses a sheet and restores its invoking control’s focus.

The shell follows VisualViewport height/offset and safe-area insets. A
keyboard-sized reduction while editing hides bottom navigation; the editor
scrolls internally, and Send remains above the visible viewport edge. Dialogs
and sheets follow the same viewport. Pinch zoom remains browser-owned. Phone
workspace creation waits for an intentional editor tap before focusing.

A streamed-project array mirroring loop found during the original investigation
was removed; temporary optimistic ordering is retained only during persistence.
No routing policy, configured execution model/effort, defaults or backend behavior
changes. Recommend-only model routing remains intact.

## Validation

Evidence is on the mounted secondary SSD:
`/mnt/vk-storage/vk-mobile-redesign-20261008`.
Original baseline and rejected first-pass screenshots remain separately under
`/mnt/vk-storage/vk-mobile-native-20261008` for comparison.

The checked-in `scripts/testing/mobile-ux-browser.mjs` exercises the branch
frontend against the existing backend identified by the current production route
(`5511`; the historical preview-guide `4511` is frozen). Only this worktree’s
lightweight frontend is started. All application mutations are intercepted and
fulfilled locally, including drafts and attachment uploads. GET/HEAD and the
read-only workspace summaries POST may reach the backend. WebSocket subscriptions
are read-only bridged with the nominated backend Origin; client frames are never
forwarded. No prompt is submitted and no task/workspace is created or modified.

Acceptance covers 360/390/412px phones, 390px dark and 1440px desktop. It checks
project/task/workspace switching, sheet Back/focus trapping/restoration, selected
status and actual feed scroll on Back, creation reachability, real agent-message
reading/copy, multiline drafts across tabs/tools, model/effort retention, Options
and list controls, the actual Attach picker with a fulfilled file response,
separate remove/download targets, search retention, no horizontal overflow,
simulated keyboard geometry and pinch zoom. Screenshots include the new task
feed/detail, project sheet, conversation/options/keyboard, workspace list and
creation.

Reproduce with installed browser tools:

```bash
VK_TEST_OUTPUT=/mnt/vk-storage/<task>/acceptance \
VK_TEST_BASE=http://127.0.0.1:<branch-frontend-port> \
VK_TEST_BACKEND=http://127.0.0.1:<verified-existing-backend-port> \
PLAYWRIGHT_MODULE=/usr/lib/node_modules/playwright/index.mjs \
PLAYWRIGHT_WS_BUNDLE=/usr/lib/node_modules/playwright/node_modules/playwright-core/lib/utilsBundle.js \
CHROMIUM_PATH=/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell \
TMPDIR=/mnt/vk-storage/<task> \
node scripts/testing/mobile-ux-browser.mjs
```

The test expects an English local dataset, preferring VK Dev and TF::Build when
present. `VK_TEST_VIEWPORTS` can override the default cases with JSON.

### Check results

- Browser acceptance: see `acceptance/results.json` and `acceptance.log` for the
  revised layouts. The pagination/count refinement also has a focused
  `activity-acceptance/results.json` receipt at 390px and 1440px. Earlier `final/results.json` is a separate successful
  five-viewport run before expanded picker/status/list-options assertions.
- Repository format plus UI/script formatting, ops governance, self-development
  guard and legacy path guard: passed.
- Local/remote/web-core/UI TypeScript and local-web/UI lint: passed; the final
  category collection change receives an additional web-core/UI check and lint.
- Full check/lint and Rust workspace tests: host GTK dependencies
  (`glib-2.0`, `gobject-2.0`, `gio-2.0` >= 2.70) block Rust compilation. Cargo uses
  the dedicated shared SSD target with incremental compilation disabled.
- Prior first-pass frontend CI/build success is historical and does not validate
  this revised design; the updated PR’s CI is the source for new build evidence.

## Review artifacts and limits

Screenshots contain existing project/conversation data and stay outside Git.
Selected images are attached through Vibe’s normal attachment API and retrieved
byte-for-byte before sharing. Current native attachment IDs:

- Task feed: `e23c1cd9-4c9c-4a1b-a6ef-2b471d9784a2`.
- Conversation: `90c493b9-a8a0-4c13-bbf8-4f6eda6ce9be`.
- Workspace list: `9973ba9b-25b6-458c-935b-51ab1528a252`.
- Original baseline task board: `dc35a844-da5e-40b8-936a-3d40a386cd37`.

No public preview route or production frontend
assets are published. Stop the branch preview after capture.

Chromium uses an Android user agent, touch and narrow viewports. Keyboard geometry
is explicitly simulated. Physical Samsung keyboard/browser chrome, installed PWA
and Safari/Firefox behavior remain unverified; their real-device QA is still
needed before release. Send/creation submissions and running-agent approval/stop
mutations are intentionally not exercised against production.
