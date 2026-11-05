# Clickable links in agent summaries

October 16 follow-up: the OP::3D Print Issues counterexample was an unpublished
filesystem link. The newer live frontend retained this web-link repair.
[VK_ARTIFACT_LINKS.md](VK_ARTIFACT_LINKS.md) documents the installed native
publisher, shared first-response instruction and sandboxed HTML report viewer
that address generated-file delivery. Earlier web-only rollout evidence below
does not establish filesystem-link support.

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

## Live repair

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

Before activation, frontend discovery on October 16 found `/assets/index-Djfpggqs.js` served
through `vk-frontend-static.service` and `vk-standby-gateway.service`; the backend
is `vibe-kanban-native-review-20261015.service`. The historical green service and
port 4511 are inactive. All mapped sources reachable from that incumbent entrypoint
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
regressions pass. The final preservation production build passed, and its frontend
inputs are identical to the merged staging source.

[PR #251](https://github.com/artinflight/vibe-kanban/pull/251) merged into staging
at `cb613654ad911ffa976ee53ea125a1dd67bd2bbe` after exact integrated-head
[Test run38885247672](https://github.com/artinflight/vibe-kanban/actions/runs/38885247672)
passed. Its standard frontend, backend and applicable desktop checks passed;
the unrelated old-release source fence was skipped on normal PR validation.
No backend code or generated shared types were changed by this repair.

## Live activation and rollback

The operator explicitly authorized the verified Desktop B frontend rollback in
place of a fresh full mutable-state backup. The legacy helper would stage65 GB
of live sessions with only22 GB free on SSD; Desktop B had about25 GB free.
This exception covers the frontend pointer switch only. No full backup is claimed.

Before activation, current fork/staging was freshly fetched and matched the
merged source. All 1,446 release files passed SHA256/size checks; all 1,342
incumbent files still matched the rollback manifest. The Desktop archive hash
was freshly rechecked. The archive is
`desktop:B:/vk-backups/vk-clickable-links-20261016/frontend.tar.zst`, SHA256
`55932328398d219a521ec826fbffca892e8b78fa723a34accae6a0e4dc0f9fb5`.
Physical restore/readback had verified every file.

At 2026-10-16 10:30:36 UTC, the current frontend symlink was atomically switched
to `/mnt/vk-storage/vk-clickable-links-20261016/release`. Both the live gateway
and static server serve the exact packaged index and entry assets:
`/assets/index-DX_bn9dg.js`, index SHA256
`1d350a0c5f09a7f082517571d590c134ad2b8a94ef9a39233363da74b88758c3`.
The old entry asset remains available for existing tabs. The API still reports
version0.1.42. Backend PID3927146, static PID3368 and gateway PID602359 remained
unchanged. No restart, data migration, route or access-policy change occurred.

Sandboxed Chromium loaded the actual live app at 1440px and 393px without page
errors. All mutating API requests were blocked. In this task's read-only editor,
synthetic text held only in browser memory produced three first-render links
(bare HTTPS, URL-only inline code and HTTP), each opening a real intercepted
new tab; a streamed replacement also stayed clickable. No conversation history
was changed. The earlier production-editor fixture additionally covers explicit
Markdown and fenced-code exclusion. Temporary browsers were closed afterward.

The old frontend remains at
`/mnt/vk-storage/vk-safe-release-20261009/frontend66-over-c3/packages/local-web/dist-v6`.
Rollback atomically restores the current pointer to that directory without
restarting services or restoring application data. Immutable old assets were
retained in the new package. Durable manifests and activation/browser receipts
are under `/mnt/vk-storage/vk-clickable-links-20261016/`, outside the task
worktree. Refresh an existing VK tab to load the renderer. No public preview
was generated; production is [Open VK](https://vibe.local/).
