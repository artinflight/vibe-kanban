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

## Validation and rollout

Run on mounted storage (the output directory must be on the SSD on this host):

```sh
VK_TEST_OUTPUT="$PWD/.vk-preview/link-validation/current" node scripts/testing/run-read-only-web-links-tests.mjs
```

The mounted DOM tests exercise the production Markdown synchronization and both
link plugins. All 16 pass. Against the original renderer, nine fail: bare and
inline-code URLs, angle autolinks, HTTP previews, formatted URLs, punctuation and
streamed replacements. Explicit HTTPS Markdown links already pass on the original.
Tests also cover query/fragment preservation, code examples, blocked protocols
and the editable composer. The frontend CI job includes this suite and its path
filter includes the test sources.

Additional checks passed: UI type checking and lint, shared frontend type checking
with `NODE_OPTIONS=--max-old-space-size=4096`, `pnpm run format`, UI formatting,
`pnpm run ops:check`, and `git diff --check`. The first shared frontend check
exhausted Node's default heap; the larger-heap rerun passed.

No backend code or shared generated types changed. No full Rust workspace suite,
production frontend build, real-browser/phone acceptance, preview publication or
live deployment was performed. Adoption requires the normal frontend release
workflow and a live summary-link click check; no backend restart is required.
