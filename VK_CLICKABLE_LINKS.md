# Clickable links in agent summaries

The chat renderer can reproduce the reported first-response failure without any
agent or network call. Assistant messages in `DisplayConversationEntry` use the
read-only `WYSIWYGEditor`, backed by Lexical's Markdown transformers. Those
transformers recognize `[label](https://...)`, but leave bare URLs, angle-bracket
autolinks and URLs in inline code as text. `ReadOnlyLinkPlugin` also previously
removed the `href` from every HTTP link, including local preview addresses.

This explains how a follow-up that rewrites an address as an HTTPS Markdown link
can suddenly become clickable. The agent-summary instructions already requested
Markdown links for PR and preview fields; instructions alone did not cover the
renderer gap. This investigation reproduces that mechanism, rather than claiming
an audit of every historical agent reply.

## Prepared repair

`ReadOnlyWebLinkPlugin` registers a display-only text transform before Markdown
synchronization. It creates real links for HTTP(S) URLs in prose and URL-only
inline code, handles angle brackets and surrounding punctuation, and preserves
balanced parentheses within paths. It runs on the first render and subsequent
streamed replacements, including existing saved conversations when displayed.
It does not alter persisted conversation logs or the editable composer.

`ReadOnlyLinkPlugin` accepts valid HTTP and HTTPS URLs and applies the same
`target="_blank"` and `rel="noopener noreferrer"` handling to explicit Markdown
and automatically detected links. Unsafe/custom schemes and relative/file paths
remain disabled. Fenced code and inline commands remain ordinary code.

Agents should still use descriptive Markdown links, such as
`Preview URL:: Updated [Open preview](https://host.example/)`, on their first
summary. Avoid wrapping a navigable link in backticks or a code fence. Renderer
support is the fallback when an agent supplies a plain web address.

This change concerns clickability, not whether a target is reachable from the
operator's device. It does not publish local files, invent public preview URLs,
or change file-navigation behavior.

## Live frontend preservation

Active frontend discovery on October 16 found `/assets/index-Djfpggqs.js` served
through `vk-frontend-static.service` and `vk-standby-gateway.service`; the backend
is `vibe-kanban-native-review-20261015.service`. The historical green service and
port 4511 are inactive. All mapped sources reachable from the live entrypoint
match this branch except the link-rendering changes and one live-only
`useConversationHistory.ts` fallback. Old immutable chunks remain in the live
asset directory, so auditing every `.map` there mixes obsolete source versions;
only the current entrypoint and reachable imports establish the live baseline.

The branch now preserves that exact live fallback: an unavailable newest turn
keeps its warning and empty execution placeholder while older authoritative
history remains reachable. A regression covers the older history, warning,
original execution identity, no request loop and successful retry. The existing
history suite was aligned with the already-live behavior and added to frontend
CI; this is release preservation, not a new history feature.

## Validation and rollout

Run on mounted storage (the output directory must be on the SSD on this host):

```sh
VK_TEST_OUTPUT="$PWD/.vk-preview/link-validation/current" node scripts/testing/run-read-only-web-links-tests.mjs
```

The mounted DOM tests exercise the production Markdown synchronization and both
link plugins. All 16 link tests pass. Against the original renderer, nine fail: bare and
inline-code URLs, angle autolinks, HTTP previews, formatted URLs, punctuation and
streamed replacements. Explicit HTTPS Markdown links already pass on the original.
Tests also cover query/fragment preservation, code examples, blocked protocols
and the editable composer. The frontend CI job includes this suite and its path
filter includes the test sources.

Additional checks passed: UI type checking and lint, shared frontend type checking
with `NODE_OPTIONS=--max-old-space-size=4096`, `pnpm run format`, UI formatting,
`pnpm run ops:check`, and `git diff --check`. The first shared frontend check
exhausted Node's default heap; the larger-heap rerun passed.

The actual production `WYSIWYGEditor` also passed sandboxed Chromium tests at
1440px and 393px: first-render bare/inline-code/HTTP links open a real new tab;
streamed replacements stay clickable and fenced code stays inert. Synthetic
navigation targets were intercepted; no live data was written. All 21 history
regressions pass. The production frontend build passed at the initial link-fix
commit; the final preservation source requires its own release build.

No backend code or generated shared types changed. Source is pushed. Staging PR,
final artifact/CI acceptance and live activation are being completed. The normal
full hosted workflow includes a separate combined-capture-consent source fence
pinned to an older release: it rejects this branch as outside that unrelated
source scope. Its failure must not be reported as a green full workflow. Normal
PR validation skips that release-specific job. No backend restart is needed.
