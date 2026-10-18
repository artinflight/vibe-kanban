# Original branch validation receipts

Source: original feature commit `9ec3894b6`, before rebasing onto the compact
staging indexes. The dated notes below are retained as historical evidence;
current integration and deployment state is in `VK_COLLAPSIBLE_ISSUES.md`.

## STATE.md

# Collapsible issues — October 17 source preparation

Issue expansion is a UI preference, keyed by issue UUID as
`expanded["kanban-issue:<id>"]` in the existing scratch-backed preference map.
The prepared frontend defaults to expanded. Collapsed issues reveal the issue
title and hide workspace/detail content; expanded linked issues show workspace
content, with an issue-title fallback when no visible workspace exists.
Desktop and phone share the preference. Collapsed issues reserve an extra
24px of bottom padding, with a subtle theme-aware tint and accent edge.
Existing phone attention coloring retains precedence. This source has not
been deployed.
An operator-approved public lightweight branch preview targets the existing
live-data gateway
on 4720; historical Green 4511 is inactive. See the latest handoff for access
restrictions and current routing evidence.
See the current `STREAM.md` and `HANDOFF.md` entries for validation limits.


## STREAM.md

# VK::Collapsible Issues — October 17

October 18: use `pb-6` (24px) below collapsed issues on desktop and phone
as specified in operator feedback; expanded spacing stays unchanged.
Follow-up: add a soft blue collapsed background and left accent on both layouts,
while preserving stronger phone attention coloring.

A public branch preview is now running with explicit operator approval; see
the latest `HANDOFF.md` entry for the URL and runtime identity.
The active backend is reached through gateway 4720; historical 4511 is inactive.
The operator approved public preview/API publication after the initial review
rejection; Funnel 8443 now targets this frontend on 3002.
Desktop/phone browser QA also passes through the public URL with all test
writes intercepted. Preview-only
proxy Host preservation fixes backend origin validation for subscriptions and
preference writes; production routing/services remain unchanged. Browser writes
were intercepted, preserving live preferences.

Branch `vk/a7b1-vk-collapsible-i`, based on staging commit `739c2bdd9`.
Scope is frontend-only: add an accessible per-issue chevron on desktop cards
and phone task rows. Collapse reveals the issue title and hides workspace
content, description previews, PRs and relationships. Expansion restores the
workspace presentation; issues without a workspace retain their title.
Issue UUID preferences reuse the existing persisted `expanded` map, so no
backend route, schema or generated shared type changes are needed.

The chevron stops desktop mouse-up navigation and keyboard drag bubbling.
Phone controls retain a 48px target and preserve issue actions/attention.
English, French, Spanish, Japanese, Korean and both Chinese locales have labels.
Focused real-card DOM regressions cover collapse/restore, independent cards,
metadata detail hiding, title fallback and navigation in desktop/phone modes.

Validation passed: three focused DOM tests, all four frontend package type
checks, local-web/UI lint, focused container ESLint, all locale labels,
`pnpm run format`, `pnpm run ops:check` and `git diff --check`. The larger
4096MB Node heap was needed for the app type checks. No Rust tests or production
build ran. Live frontend smoke was attempted using
`pnpm run preview:light:run`; the configured Green service is inactive and
`127.0.0.1:4511/api/info` is unavailable. No preview, backend, deployment or
service restart was performed. Resume preview QA when the release owner makes
the existing backend available; do not start another backend for this change.


## HANDOFF.md

# Collapsed issue coloring — October 18

Collapsed desktop cards and phone rows now use a soft blue tint and a 3px left
accent. Existing orange phone attention treatment takes precedence, and
selection rings, issue controls and the 24px collapsed padding are preserved.
Color comes from the existing theme info token and disappears on expansion.
The approved public preview updates from this tree; no backend or production
release change is involved. Public browser QA passes at 1440px and 393px in
light and dark themes: collapsed gradients render, expanded backgrounds are
restored, and collapsed padding remains 24px. Mouse/Enter, navigation and
subscription checks pass without runtime exceptions or origin 403s; all test
writes were intercepted. Light/dark screenshots were visually reviewed.
`pnpm run format`, focused CSS/TSX formatting, container ESLint and
`git diff --check` pass. Evidence: `.vk-preview/browser-validation.json`.

# Collapsed issue spacing — October 18

The operator accepted collapse behavior and requested a little more bottom
padding on collapsed issues, then specified 24px. Desktop card content and
phone rows now apply `pb-6` only while collapsed. The existing approved public preview updates
from this worktree; expanded issue spacing is unchanged. No backend or
production deployment is involved. Public browser QA passes at 1440px and 393px:
collapsed bottom padding is 24px in each layout and expanded additional padding
is 0px. Collapse/expand, Enter, navigation and subscription checks still pass;
all test writes were intercepted. `pnpm run format`, focused UI formatting
and `git diff --check` pass. Evidence: `.vk-preview/browser-validation.json`.

# Collapsible Issues public preview — October 17

Feature commit: `4f04c88df`. A lightweight branch frontend is running under
`vk-preview-vibe-kanban-repo-37a87dee51.service` on loopback port 3002,
with a private Tailscale Serve route on port 18484. Use
`pnpm run preview:light:status` and `pnpm run preview:light:stop` from this tree.

The guide's port 4511 is stale. Current authority is
`vibe-kanban-native-review-20261015.service` on 5621, using the existing Green
XDG data. The unchanged gateway on 4720 points to the current-data/history
preservation proxy on 5640 with authoritativePort 5621. This preview targets
that gateway via `VK_PREVIEW_BACKEND_PORT=4720`; it starts no extra backend.
Private root and API probes pass (version 0.1.42). The earlier inactive-port
observation did not establish that the live application was unavailable.

The operator explicitly approved public publication of this preview and its
proxied VK API after the initial automatic-review rejection. Funnel port 8443
now targets this frontend on 3002; the preexisting file subroute is preserved.
Public preview: https://mcp-server.tail744c4.ts.net:8443/
VK Dev board: https://mcp-server.tail744c4.ts.net:8443/projects/1cf19067-4055-4432-bbc1-581919f9185d
Public root returns HTTP 200 and API reports success/version 0.1.42.
No production backend, gateway or deployed frontend was changed. This is a
branch preview against existing live VK data. Public browser QA passes at
1440px and 393px: collapse/expand, mouse/Enter, unchanged navigation, accepted
subscriptions and emitted preference saves (one desktop, two phone). No runtime
exceptions or origin 403s; test writes were intercepted. The operator's own
browser/physical-phone test is still theirs to perform.

Browser QA passes at 1440px and 393px: visible title on collapse, reduced card
height, workspace restoration, mouse/Enter activation and unchanged navigation.
The initial proxy changed Host and caused subscription 403s; preview proxy
configuration now preserves Host for backend same-origin validation on both
`/api` and `/v1`. Rechecked subscriptions have no 403s and preference-save
requests are emitted (two desktop, one phone). Application writes were all
intercepted; no live preferences were changed and durable reload persistence
was not exercised. Isolated-browser early WebSocket cancellation messages
remain, without origin failures or application exceptions. Evidence and images
are private in `.vk-preview/browser-validation.json` and adjacent PNGs.
`pnpm run local-web:lint`, `pnpm run format` and `git diff --check` pass.

# VK::Collapsible Issues — October 17 pickup

The branch adds saved per-issue collapse controls to desktop Kanban cards and
phone task rows. Collapsed issues show their title; expanding linked issues
shows the workspace content again. Issues without visible workspaces keep their
title. Reuses `UI_PREFERENCES.expanded` with `kanban-issue:<UUID>` keys.

Run the focused regression with
`VK_TEST_OUTPUT="$PWD/.vk-preview/collapse-tests" node scripts/testing/run-kanban-collapse-tests.mjs`.
The worktree resolves onto the mounted SSD. Locked frontend dependencies are
installed here; task package cache is on `/mnt/vk-storage/vk-collapsible-issues-20261017/`.
Validation passed: `pnpm run format`; focused UI/test formatting;
`pnpm run ops:check`; UI, web-core, local-web and remote-web TypeScript checks;
`pnpm run local-web:lint`; `pnpm run ui:lint`; focused ESLint on
`KanbanContainer.tsx`; all seven locale labels; and `git diff --check`.
Web-core/local-web/remote-web checks used `NODE_OPTIONS=--max-old-space-size=4096`;
the initial local-web check exhausted Node's default heap, then passed on retry.
All three focused DOM regressions pass via the command above. Rust tests,
production build, served-browser/physical-phone QA and live preference reload
were not exercised; no Rust or backend behavior changed.

Live QA is pending: the standard lightweight preview failed because the
configured Green backend on port 4511 is inactive. No backend was started or
restarted, no public preview route changed, and no live release was activated.
Feature source is committed on this branch; no PR or push yet. Review the phone feed and
scratch persistence in the standard lightweight preview once Green is available.
The DOM regression uses the shared card in desktop and mobile prop modes; it
does not prove live phone-feed rendering or persistence across reloads.


