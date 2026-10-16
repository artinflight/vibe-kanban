# Sent steering message returns as a draft

Issue: [Sent turn-steering message reappears in composer after navigation](https://vibe.local/projects/e2645d00-9bc6-4136-8d6e-0c2fcf032d77/issues/e662a94d-0fff-428b-9f43-9d771ebcc8e1).
Created in the local vibe-kanban project and linked to workspace
`54f815cd-930d-42e3-9fb5-a39d214bcf86`; the persisted workspace task ID was verified.
GitHub issues are disabled for `artinflight/vibe-kanban`.

PR: [#257 — Stop sent steering messages reappearing as drafts](https://github.com/artinflight/vibe-kanban/pull/257), merged into `staging` at `9301e6a46`.
Source fix: `ca9911225`, pushed and verified on GitHub.

## Current release status

The fix is merged and live after Seamus's frontend-only approval. Acceptance
completed at 2026-10-16 21:49:43 UTC, version 0.1.42, built source
`1d074941dc4145f6827beb2c43775bab6caec20e`, entry `/assets/index-CGY9AEy0.js`.
No service restarted. Existing Mobile/Dot is preserved; new PR254 notifications
remain excluded. Read [the coordination note](VK_SENT_STEERING_RELEASE_COORDINATION.md)
for final post-switch results, immutable source and rollback paths.
The older local limitations below are historical; hosted CI, successful
production packaging and live acceptance close those release gates.

## Cause and correction

The active-turn handler saves a `DRAFT_FOLLOW_UP` recovery scratch before its
queue/steering request. It previously cleared only the local composer on success.
`useSessionMessageEditor` hydrates the surviving scratch when the view remounts,
which makes an already-delivered message appear unsent.

The queue interaction hook now returns the API result. When it confirms immediate
delivery (`status: empty`), the handler awaits `clearDraft()` within the existing
submission guard. Rejected delivery and `status: queued` retain the recovery draft.
Queued message display and explicit cancellation still read queue state. Backend
queue consumption clears the scratch only after the queued run starts, preserving
recovery if dispatch fails or a non-durable queue is lost on restart.
No backend, schema, generated type or queue delivery semantics change.

## Original source validation (historical)

Passed:

- `pnpm run format` and `pnpm run ops:check`.
- `NODE_OPTIONS=--max-old-space-size=8192 pnpm run web-core:check`.
- `NODE_OPTIONS=--max-old-space-size=8192 pnpm run local-web:check`.
- `pnpm run local-web:lint` and direct ESLint of the modified shared composer
  using the local-web `.eslintrc.cjs`.
- Prettier checks of the composer and browser fixture; `git diff --check`.
- Final synthetic source browser regression at 390, 412 and 1440 pixels: immediate
  steering clears persisted draft, navigation and reload keep it empty, failed
  delivery restores the draft after navigation, explicit retry succeeds, queued
  fallback retains its recovery scratch, and cancellation restores queued text.
  Duplicate activation, pointer cancellation and keyboard submission also pass.
  Results: `.vk-preview/steering-test/after/results.json`.

The prior frontend release reproduces the exact bug under the updated fixture:
after navigation the editor contains `One tap fixture` instead of an empty value.
The first build and local-web type-check attempts exhausted Node's default heap;
both type checks pass with an 8 GiB heap. The build retry transformed 12,841
modules but reached roughly 3.7 GiB swapped under the task memory limit during
packaging. It was stopped to avoid prolonged memory pressure. Production bundle
validation is unverified. Browser testing uses the lightweight branch Vite
frontend with all API/WebSocket traffic intercepted by synthetic fixtures.

The existing duplicate-send timing assertion required a deterministic first
response gate under build load; the fixture now explicitly releases that response
only after verifying repeated activation cannot submit again.
The regression extends `scripts/testing/mobile-send-browser.mjs` with persistent
HTTP/WebSocket scratch fixtures, navigation/reload, failed-send recovery and queue
fallback/cancellation. All browser API/WS requests are synthetic and no inference
or production data writes occur during tests.

Reproduction command (prior immutable release):

```sh
VK_TEST_OUTPUT="$PWD/.vk-preview/steering-test/before" \
VK_TEST_DIST=/mnt/vk-storage/vk-clickable-links-20261016/release \
VK_TEST_WIDTHS='[1440]' VK_TEST_MODES='["running"]' \
PLAYWRIGHT_MODULE=/mnt/vk-storage/codexusage-capacity/format/node_modules/playwright-core/index.mjs \
CHROMIUM_PATH=/opt/playwright-browsers/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell \
node scripts/testing/mobile-send-browser.mjs
```

Source smoke uses the same runner with `VK_TEST_BASE=http://127.0.0.1:3039`,
without `VK_TEST_DIST` or a widths override, with `VK_TEST_MODES='["running"]'`,
and output `after`. This exercises 390, 412 and 1440 pixel layouts.
This temporary frontend is only for automated tests and is stopped afterward.

## Rollout

Authorized static-only activation and fresh hash/PID/API/browser acceptance are
complete. Receipt: `/mnt/vk-storage/vk-sent-steering-release-20261016/activation.json`.
The full prepared package and Desktop rollback were verified before switching.
Existing tabs need refresh. A known already-sent older draft may need one clear;
no bulk migration or message resend is required. Notification deployment remains
separate and backend-first. See the coordination note for final test details.
