# One-tap mobile Send, October 9

Owner request: Send submits on its first tap, exactly once, after today's cutover.
This is a focused frontend correction on `vk/eb7d-vk-native-feelin`, using draft
PR233 into staging. No backend, service, routing or execution settings change.

## Reproduction and identity

A fresh HTTPS read matches frontend source
`5ce84ee21be814b1519cfb2715b50f3432c3e8ba`:

- JS `index-CS-cRFJl.js`, SHA256
  `d58ddd0288832d3081bcb520bfc66d90709d52440e51be8394639c05c57db647`.
- CSS `index-Y5IFow0P.css`, SHA256
  `661669197ccc2d660f56e8e811d80807c827db7b2419f0828e3c642212986576`.
- Health returns HTTP200 and `OK`.

The test serves those immutable assets under an isolated origin. Every HTTP API
and WebSocket subscription is synthetic, including drafts, execution processes,
messages, configuration and mutations. No production request, prompt execution,
operator draft or message is involved. The browser uses touch/mobile emulation
and a controlled VisualViewport height; this does not prove physical Android IME
behavior.

With the editor focused and the simulated keyboard open, touch generates
pointerdown/up followed by compatibility mousedown. Mousedown blurs the editor;
`useMobileViewport` clears keyboard-open immediately and CSS restores the bottom
navigation. Send shifts upward 69px. Mouseup/click hit its ancestor instead of
Send, yielding zero submission requests; a second tap sends one request.

## Correction

The phone action area prevents default mouse focus transfer only when activating
an enabled button from this composer's editable text. Submission remains click
based; pointer-down alone, a cancelled gesture and dragging away cannot send.
Keyboard activation and desktop focus behavior remain available.

Navigation stays hidden after editor blur while the keyboard viewport is still
constrained, and returns on viewport expansion. No arbitrary keyboard timeout is
used. A shared synchronous ref admits one Send or active-turn correction through
scratch persistence, request and cleanup; loading state communicates the wait.
The Sending button is disabled, so another tap cannot become Stop. Failed
corrections retain text and display an error, releasing the guard for retry.
Work View launch, manifest start URL, project status defaults, selected navigation,
safe areas, conversation layout and model/routing choices remain intact.

## Validation

Functional checkpoint: `081d859a6feb079ecb78ab67e4d7932ed1cf9a4f`.

- Immutable pre-fix assets reproduce the 69px shift and two-tap send in six cases:
  existing/new/running sessions at390/412px, with Android user-agent and touch.
- All nine corrected cases pass across390/412/1440px: one first-tap request,
  disabled pending action, repeated-tap prevention, one session creation, retained
  failed draft and explicit retry, cancelled pointer gesture, keyboard activation,
  synthetic conversation reading, cold/repeated Work View landing, and navigation
  restoration after the simulated keyboard viewport expands. The first desktop
  attempt exposed an ambiguous test selector (a model dropdown also says Loading);
  an exact action label fixed the selector and all three desktop cases passed.
- Same-event concurrent-handler, pending request/cleanup, rejection and retry
  admission tests pass.
- `pnpm run format`, UI formatting, `ops:check`, legacy path guard, all four
  frontend type checks, local-web/UI lint and explicitly configured changed-file
  lint pass. The first default-heap check attempt failed at Node's heap limit;
  rerunning with `NODE_OPTIONS=--max-old-space-size=2048` passed frontend checks.
- Full `check`, `lint`, and `cargo test --workspace` were attempted with shared
  `CARGO_TARGET_DIR` and incremental compilation disabled. Rust validation is
  incomplete locally: the shared target was occupied and SSD free space fell
  below4GB. Only this task's own builds were stopped; no cleanup was performed.
  Full CI on the pushed head remains the baseline gate.

Synthetic screenshots, traces, result JSON and logs stay on the mounted SSD under
`/mnt/vk-storage/vk-mobile-send-20261009`; no private runtime evidence is published.

The reusable browser tests are `scripts/testing/mobile-send-browser.mjs` and
`scripts/testing/run-prompt-submission-browser.mjs`. Set `PLAYWRIGHT_MODULE` to
an installed Playwright module, `CHROMIUM_PATH` to its browser executable,
`VK_TEST_OUTPUT` and `TMPDIR` to a task directory on the mounted SSD. For the
full application test set `VK_TEST_BASE` to this branch's lightweight preview;
all API/WS calls are locally mocked. For before reproduction instead set
`VK_TEST_DIST` to the immutable served build and `VK_EXPECT_BUG=1`. Optional
`VK_TEST_WIDTHS`/`VK_TEST_MODES` constrain the fixture matrix. Run both scripts
with Node. The admission test checks same-event entry points before a rerender,
pending cleanup, rejection and explicit retry.

Desktop ADB currently lists no connected devices. No pairing, phone networking,
phone app state or browser profile was changed; physical S25+, Samsung Internet,
Firefox and Safari keyboard behavior remain unverified.

## Integration and release handoff

Keep the existing Dev/Staging separation. Review/integrate the focused commit on
PR233 alongside the Work View manifest/navigation follow-up. The combined live
source includes six newer consent/chat repairs absent from this older feature
branch. Apply the focused change onto that source or its reconciled staging
successor; preserve those repairs and `66e00728c` landing behavior. A read-only
patch compatibility check against `5ce84ee2` passes after accounting for its
additional first-line consent import. No owner worktree/index was changed.

This change needs a frontend build and normal staging review/QA. It does not need
a backend rebuild for these UI changes. No production bundle was built, replaced,
merged or deployed by this task. Final CI and physical phone QA must be assessed
by the release owner before promoting the new frontend; source-level/browser
validation is not a claim that the fix is live.
