# e3e1 consent-context compatibility

## Intent / WHAT / WHY

Legitimate existing connector dispatch prompts were rejected before consent
because strings were capped at 4 KiB and duplicated display values pushed the
rendered context over 8 KiB. Implement a separate bounded source candidate with
complete readable review, explicit one-shot consent and truthful validation.

Branch: `fix/e3e1-consent-context`.
Base: deployed `c3c48e6324f778ccd03a5761c2314b440e9ceac3`.
codeSha (tested): `b5e49f393a419a03631cf71ddca74d52e08b9cdc`.
Draft PR: https://github.com/artinflight/vibe-kanban/pull/239 (into staging).
No deployment, restart, native dependency, reviewer/security settings, routing,
credentials, live dispatch/retry, badge clear or local Cargo build/test.
Capture PR236 source remains `921bf86de6d04840e3cafde53c088416183652ce`.

## Changes and exact files

Runtime:
- `crates/executors/src/executors/codex/elicitation.rs`: detailed fail-closed
  validation, 60,000 Unicode characters / 240,000 UTF-8 bytes per string,
  512 KiB arguments, 640 KiB verified display, 1 MiB complete summary; depth8,
  128 nonsecret nodes, 128 display entries, 256-byte identity/key/label and
  existing 16 KiB provider-question limit retained. No consequential truncation.
  Display labels attach to exact arguments instead of repeating their values.
  Literal multiline strings remain readable; secret redaction, embedded-secret,
  bidi/control, redacted-only and display/invocation equality guards retained.
- `crates/executors/src/executors/codex/client.rs`: validation returns typed
  Cancel with `content.error.code=mcp_consent_validation`, fixed reason/message,
  numeric observed/limit, `review_requested:false`, `dispatch_allowed:false`,
  no persistence metadata; persists the same fixed diagnostic without values.
- `crates/executors/src/executors/codex/normalize_logs.rs`: truthful validation
  system warning with structured metadata; no invented operator feedback.
- `crates/services/src/services/approvals/executor_approvals.rs`: actual approval
  service shares the same bounded complete-summary budget.
- `packages/web-core/src/features/workspace-chat/ui/McpConsentCards.tsx`:
  expanded keyboard-focusable full-text scroll region, wrapping and literal
  rendering; existing request/execution binding and explicit controls retained.

Tests:
- `crates/executors/tests/mcp_consent_context.rs`: UTF-8 boundaries, observed
  3857/5820/7904/10200-byte synthetic dispatch sizes, exact 60,000-character
  prompt, duplicate display / old 8 KiB boundary, oversized arguments/display,
  credentials, mismatched display, depth and node protection.
- `crates/services/src/services/approvals/elicitation_tests.rs`: real approval
  service plus offline Python native peer; long prompt stays pending, dispatch
  only on explicit Accept, owner-decline and timeout origins, oversized request
  creates no card and returns structured validation detail without private text.
- `scripts/testing/mcp-approval-ui.test.tsx`: real mounted composer on phone and
  desktop preserves long Unicode prompt/final restriction, literal HTML, full
  content, accessible scrolling and request binding; mount sends no approval.

Workflow/docs: `.github/workflows/test.yml`, `VK_MCP_APPROVAL_BRIDGE.md`,
`STREAM.md`, `HANDOFF.md`, this handoff. Historical continuity retained.

## Hosted validation / SUCCESS evidence

**PASS** https://github.com/artinflight/vibe-kanban/actions/runs/38006166127
at exact tested `b5e49f393a419a03631cf71ddca74d52e08b9cdc`.

- `cargo test --locked -p executors --test mcp_consent_context`: 7 passed (0.09s).
- `cargo test --locked -p executors --lib elicitation::tests`: 6 passed (0.01s).
- `cargo test --locked -p executors --lib mcp_approval_card`: 2 passed (0.02s).
- `cargo test --locked -p services --lib elicitation_tests -- --test-threads=1`:
  7 passed (1.01s), with mounted UI's synthetic approval payload file.
- `node scripts/testing/run-mcp-approval-ui-tests.mjs`: 2 mounted tests passed
  (0.89s total), complete long text and no implicit consent.
- web-core/local-web/remote-web TypeScript checks passed.
- `cargo clippy --locked -p executors -p services --all-targets -- -D warnings`
  passed; workspace rustfmt, scoped Prettier and governance passed.
- Separate unchanged turn-git-preservation contract and ops job passed.

22 compiled backend tests + 2 mounted UI tests. Fixtures use in-memory SQLite,
disabled notifications, synthetic contexts, mocked UI/API transport and offline
Python peer; no real model, connector dispatch or operator review is fabricated.
Full workspace, schema, remote/platform and PR freshness/release gates were
**skipped, not passed**, in the opt-in acceptance workflow.

Previous run38005193764 passed runtime/tests/Clippy but failed only a hosted
formatter-relative-path mistake. Revised head changes only those two workflow
paths relative to that run's2596cac2. Both receipts are preserved.

## Exact review artifact and source binding

Source/docs/workflow diff excludes handoffs/runs to avoid cyclic receipt hashes:
`/mnt/vk-storage/vk-consent-context-20261009/evidence/consent-c3c48e63-to-b5e49f39-source.patch`
SHA-256: `bf554fb93f3fe9bad515a395edd17c72df1e6b9ab793dc37c877d396c2a96fc0`.
Full final patch and per-file SHA-256 manifest: sibling evidence directory,
`candidate-binding.json`. Original and final hosted logs/JSON retained there.
Only the c3-relative patch is the intended integration scope. Current Staging
lacks the deployed bridge, so do **not** merge the wider historical baseline
through this draft. Integrate the base separately or port this focused diff.
No dependency on capture PR236 is introduced by this patch.

## Remaining concrete limitation / resume

VK's typed response and diagnostic are truthful. Native Codex ignores Cancel
content and hardcodes `user cancelled MCP tool call`; returning JSON-RPC errors
would become a false Decline. **Native model-visible wording remains unresolved**
and is not represented as fixed or live. A supported native-source follow-on
must recognize bounded, schema-validated bridge validation reasons, keep
execution blocked and distinguish genuine owner decline/timeout. See
`/mnt/vk-storage/vk-consent-context-20261009/evidence/native-diagnostic-dependency.md` for the bounded proposal.
No unsupported response, consent bypass or auto-approval is used.

Next: root coordinates focused source/native review and normal integration.
Keep T18's concise complete prompts through normal review while production
remains unchanged. This draft is not merge, deployment or security-change
approval. Do not retry cancelled actions or start/stop other workspace agents.
