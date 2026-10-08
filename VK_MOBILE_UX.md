# Phone UI and interaction design

## Released October 8

PR224 and promotion PR226 are rebase-merged. The reviewed frontend is live without
a backend restart; see VK_MOBILE_RELEASE_20261008.md for validation and rollback.
Earlier development-only boundaries describe the original implementation phase.

Branch: `vk/eb7d-vk-native-feelin`. [PR #224](https://github.com/artinflight/vibe-kanban/pull/224) and [promotion PR #226](https://github.com/artinflight/vibe-kanban/pull/226) are merged.
The revised design replaces the initial size-focused pass after operator feedback.

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

## Style refinement (October 8)

The follow-up style pass keeps the screen structure while reducing visual bulk:

- Search uses a 40px visible surface inside a 48px interactive field. Removing
  shared padding prevents the input minimum height from growing the entire bar.
  Search icons and named clear controls improve recognition and accessibility;
  the input stays 16px and clear targets remain separate from editable text.
- Status/activity chips have 36px visible fills with 48px targets, lighter
  unselected surfaces and a distinct selected tint/outline. Controls retain
  focus and press feedback.
- Headings use 24px type and align with the 16px screen gutter. Card borders,
  radii and gaps are softer; workspace row padding and icon tiles are tighter.
  Task titles retain their 16px reading size.
- New workspace has a lighter 40px surface inside its 48px button. The floating
  task action keeps its 56px target with a narrower shape and softer shadow.

Style evidence: `/mnt/vk-storage/vk-mobile-style-20261008`. Before images copy the
previous redesigned source's saved screenshots; new captures use the same browser
harness with search sizing, clear-target separation and clear/search behavior
checks added. The harness continues exercising navigation, drafts, attachments,
keyboard geometry and desktop controls. See `acceptance/results.json` and logs.
Required formatting/governance, frontend type/lint stages and unused-i18n checking
passed. All five browser cases passed; search height measured 48px in each phone
case. Local full Rust checks remain blocked by the missing GTK libraries. The test
command was interrupted after that failure instead of waiting for unrelated
dependency jobs to finish.
All CI checks passed for preceding redesigned source `121cdccb0`; new CI applies
to the style revision after push. Physical Android and non-Chromium QA limits
remain unchanged. No model, routing or production runtime changes.

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
byte-for-byte before sharing. Current style refinement attachments:

- Task feed: `bb99d444-d0ca-4420-9c5f-217375d6c36f`.
- Workspace list: `986e6666-f08e-49b4-8f57-73b759a89523`.

The style images are retrieved PNGs verified byte-for-byte. Redesign review
attachments retained for comparison:

- Task feed: `e23c1cd9-4c9c-4a1b-a6ef-2b471d9784a2`.
- Conversation: `90c493b9-a8a0-4c13-bbf8-4f6eda6ce9be`.
- Workspace list: `9973ba9b-25b6-458c-935b-51ab1528a252`.
- Original baseline task board: `dc35a844-da5e-40b8-936a-3d40a386cd37`.

The operator subsequently authorized deployment. The frontend is now live at
`https://vibe.local`; see VK_MOBILE_RELEASE_20261008.md for the release receipt.
No temporary public preview route remains.

Chromium uses an Android user agent, touch and narrow viewports. Keyboard geometry
is explicitly simulated. Physical Samsung keyboard/browser chrome, installed PWA
and Safari/Firefox behavior remain unverified; their real-device QA is still
remaining acceptance coverage. Send/creation submissions and running-agent approval/stop
mutations are intentionally not exercised against production.
