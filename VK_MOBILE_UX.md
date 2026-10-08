# Phone interaction pass

Branch: `vk/eb7d-vk-native-feelin`. Frontend only; not deployed.
Draft review: [PR #224](https://github.com/artinflight/vibe-kanban/pull/224) into
`staging`. Source implementation commit: `098fa753f`.

## Experience

The phone shell uses a compact app header and labeled bottom destinations.
Workspaces, Chat and Changes stay directly reachable; Logs, Preview, Git,
settings and contextual actions live in a modal More sheet. Project navigation
is a scrollable bottom sheet with names, colors and attention indicators.
Sheets use the existing Radix dialog system for focus trapping, Escape,
background isolation and focus restoration. Browser/Android Back dismisses a
sheet before leaving its screen. Selecting an item consumes the sheet history
entry before navigating, avoiding an extra empty Back step.

Mobile controls have 48 CSS px minimum touch targets; bottom destinations are
64px tall. Workspace names and task workspace content wrap instead of relying
on desktop truncation. Phone cards use larger padding and rounded surfaces,
retaining Vibe's typefaces, orange accent, project/workspace colors and themes.
The card keeps review and overflow actions; priority and assignee editing remain
available in full-screen task details. The labeled native task-status selector
provides a way to move a task without dragging. Desktop dragging remains enabled.

Task details keep the board mounted with its dimensions intact, preserving its
actual scroll containers, filters and collapsed columns on return. Workspace
panes likewise retain their existing mounted state across tab changes. Route
changes select Chat for a workspace and the workspace list for the list route.
The header uses the workspace name on phones; desktop retains its branch label.
A project-array mirroring effect that looped during streamed chat updates is
replaced with temporary optimistic ordering only while a drag is persisted.

The composer separates model controls from its attachment/actions row and keeps
Send at the lower right. Its editor scrolls internally for long drafts. The shell
tracks VisualViewport height and offset, hides bottom navigation and the compact
composer stats row when an editable field and keyboard-sized viewport reduction
coincide, and reserves safe-area insets. Sheet/dialog sizing follows the same
visible viewport. Pinch zoom remains browser-owned. Workspace creation scrolls
and waits for an intentional editor tap before focusing on phones.

Message copy/edit actions appear below their content on phones without hover.
Inline attachment-chip remove/download actions use normal flow so their enlarged
targets remain separate and wrap inside narrow editors.

All layout changes use the existing 767px phone breakpoint. Model-selector
changes are accessible labels only: routing, selected model/effort, defaults,
execution and backend behavior are unchanged.

## Validation and evidence

Evidence directory: `/mnt/vk-storage/vk-mobile-native-20261008` on the mounted SSD.
The existing-production route was read to identify backend `5511`: historical
preview default `4511` is frozen. Only this worktree's frontend preview was
started; no backend, production service, routing, task/workspace data or frontend release
was changed. No public Funnel route was installed.

The checked-in `scripts/testing/mobile-ux-browser.mjs` runs against the branch
frontend. It intercepts every application write, fulfills draft/UI writes locally,
and never submits a prompt or creates a task/workspace. GET/HEAD and the read-only
workspace-summary POST may reach the nominated backend. Subscription sockets
are bridged read-only with the backend's Origin; browser frames are never
forwarded. This lets the test read actual projects, workspaces and conversation
messages without changing production settings or attention flags.
Attachment layout tests use an in-memory file and a locally fulfilled upload
response: no attachment bytes are forwarded to the backend.

Baseline screenshots: `before-board-390.png`, `before-chat-390.png`. These capture
the prior controls/layout; the baseline chat was still loading its message stream.
After screenshots cover board, projects, task details, conversation, composer with
simulated keyboard, workspace list and creation; results JSON and logs accompany
the screenshots. The baseline measured 20–29px primary controls and icon-only
phone workspace tabs.

Initial acceptance passed at 360, 390, 412 and 1440px. Phone assertions cover
project and workspace switching, sheet focus trapping/Back, task detail/Back,
restored board scroll, task creation screen reachability, reading actual agent
messages, multi-line composition, retained draft/model/effort across tabs,
workspace filter preservation, every workspace tool, Send above a simulated
keyboard, pinch-zoom handling and horizontal overflow. Desktop retains its
compact controls and panel navigation. Additional desktop navigation and dark
phone/creation checks are recorded in the final receipt below.

Reproduce using the installed browser tools (paths may differ on another host):

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

`VK_TEST_VIEWPORTS` optionally supplies JSON cases such as
`[{"width":390,"colorScheme":"dark"}]`. The default includes three narrow widths,
a desktop width and a dark phone case. The test currently expects an English
local VK dataset, selecting VK Dev and TF::Build when present.

### Final validation receipt (2026-10-08)

| Check                                                                      | Result                                                                                           |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Browser acceptance, 360/390/412px light, 1440px desktop and 390px dark     | Passed; `final-acceptance/results.json`; includes message actions and mocked attachment controls |
| Expanded desktop navigation and phone creation                             | Passed in final acceptance                                                                       |
| Configured model/effort retained and no prompt submission                  | Passed in every browser case; application writes intercepted                                     |
| `pnpm run format`, UI format and script/design-note Prettier               | Passed                                                                                           |
| `pnpm run ops:check`, legacy frontend path guard                           | Passed                                                                                           |
| Local-web, remote-web, web-core and UI TypeScript checks                   | Passed through the frontend stages of `pnpm run check`                                           |
| Local-web/UI lint and unused-i18n-key check                                | Passed                                                                                           |
| Full `pnpm run check`, `pnpm run lint`, `cargo test --workspace --offline` | Blocked at Rust GTK dependencies (`gio-2.0`/`glib-2.0` pkg-config files missing)                 |

A separate 390px run with `focus-acceptance/results.json` also passed after the
explicit opener-focus restoration change, asserting that Back returns focus to
the exact invoking navigation button.

Production builds for both local-web and remote-web, frontend type/lint/format,
i18n and legacy checks passed in the
[frontend CI job](https://github.com/artinflight/vibe-kanban/actions/runs/37781846014/job/113326731958)
for source commit `098fa753f`. The duplicate local bundle build was stopped after
that result became available: it reached chunk rendering, but host memory/I/O
pressure made it unusually slow. No local bundle-build success is claimed.

The branch's temporary frontend preview and its tailnet route were stopped after
review artifacts were captured. Screenshots are retained on the SSD, outside Git, since
they include existing project and conversation content. No preview assets are
published to the production frontend.

### Accessible review artifacts

After the operator reported that host-local file links would not open, the two
existing board screenshots were uploaded through Vibe's normal attachment API.
Both were retrieved as PNGs and verified byte-for-byte against the source files.
Only these review artifacts were written; no prompt, task/workspace change,
deployment or production service update occurred.

- Before attachment: `dc35a844-da5e-40b8-936a-3d40a386cd37` (37,337 bytes).
- After attachment: `7a951534-41c5-4b0a-8d2b-44f5339c344f` (27,631 bytes).
- Review notes: [open on GitHub](https://github.com/artinflight/vibe-kanban/blob/vk/eb7d-vk-native-feelin/VK_MOBILE_UX.md).

The before/after images are embedded as native attachments in the follow-up
conversation. Upload/retrieval receipts remain in the evidence directory.

## Limits and release boundary

Chromium with Android user-agent/touch emulation exercises real application
behavior. Software-keyboard geometry is explicitly simulated, not proof of a
physical Samsung keyboard, installed PWA, cutout, or browser chrome transition.
Only Chromium is installed; Safari/WebKit and Firefox device QA remain unexercised.
Live sends, edits, creation, attachments and mutations are deliberately not run.
Remote-host/cloud authentication behavior was not exercised.

Full Rust check, Clippy and workspace test commands cannot complete on this host:
`pkg-config` cannot find `glib-2.0`/`gio-2.0` required by Tauri. Use CI with the
repository's desktop dependencies for that baseline. No Rust source or generated
shared type changed. A merge or production publication is a separate release
operation; this task authorizes neither.
