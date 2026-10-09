# e3e1 consent-context compatibility

Intent: support existing bounded connector dispatch prompts with complete
readable one-shot consent and truthful structured validation failures.
Branch: `fix/e3e1-consent-context`. Base: deployed `c3c48e6324f778ccd03a5761c2314b440e9ceac3`.
codeSha: pending initial source commit (final receipt will bind tested SHA).

Changes: 60,000 Unicode characters / 240,000 UTF-8 bytes per string;
512 KiB arguments, 640 KiB verified display, 1 MiB rendered summary; retained
128 nodes/depth8/credential/bidi/display-equality checks. Display labels attach
to exact arguments rather than duplicating content. Multiline strings remain
complete literal paragraphs. Accessible expanded scrolling card; no implicit
consent. Fixed structured fail-closed validation detail is returned, persisted
and normalized without argument values or fabricated owner decisions.

Files: codex/{elicitation,client,normalize_logs}.rs; mcp_consent_context.rs;
services/approvals/{elicitation_tests,executor_approvals}.rs; McpConsentCards.tsx;
mcp-approval-ui.test.tsx; .github/workflows/test.yml; VK_MCP_APPROVAL_BRIDGE.md;
STREAM.md; HANDOFF.md; this handoff. Historical continuity retained.

Commands/results: read-only deployed connector limit/source verification;
fetched current fork/main and fork/staging; isolated git worktree from deployed
bridge base; scoped rustfmt and Prettier; git diff --check. Hosted compiled,
strict Clippy, real approval-service/offline-peer and mounted UI acceptance
pending. No local Cargo invocation or local builds/tests.

Decision: current Staging lacks deployed bridge, so integration needs the base
or port of only the c3-relative patch. Draft must not merge its wider base as a
shortcut. Capture PR236 and all runtime/configuration/state remain unchanged.

Known limitation: native Codex ignores Cancel content and hardcodes generic
'user cancelled'. JSON-RPC errors become a false Decline. This candidate's
response and Vibe timeline are truthful, but upstream model-visible wording
requires a reviewed native patch; no native binary/dependency change here.

Resume: inspect latest hosted acceptance and exact patch/hash receipt; correct
only scoped source/test failures. No deployment, restarts, reviewer settings,
cancelled-call retries, live dispatch or badge clearing authorized in this task.
