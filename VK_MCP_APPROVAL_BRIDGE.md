# Codex MCP approval bridge

Development only, 2026-10-08. Workspace and linked issue: **VK::MCP Approval
Bridge** (`08659a8a-7908-4f92-b1e5-eee0e4e1c38c`). Branch
`vk/870d-vk-mcp-approval` has the same starting source as current fork staging
`8b562265d`. No deployment, runtime restart, recovery, permission change,
production resume or Staging-agent operation is part of this stream.
Recommend-only routing remains authoritative.

## Defect and behavior

The Codex client grouped `mcpServer/elicitation/request` with unhandled requests
and returned JSON `null`. Codex could not deserialize its typed response, fell
back to Decline and reported `user rejected MCP tool call`. The read-only
diagnostic report established this path for two attempted resumes; neither
records a human rejection or target execution. Private diagnostic logs and
identities are deliberately excluded from this public repository.

The dedicated bridge supports form-mode requests marked
`codex_approval_kind=mcp_tool_call` with an empty object schema. It publishes a
distinct request-bound consent card in the composer with its own approve/decline
controls, creates the actual Vibe approval request, and waits for the operator.
MCP requests are excluded from the generic composer's implicit selection.
Each card submits its own approval ID and execution ID, regardless of snapshot
or timeline order. Only the displayed session's running executions are included.
Connection alone is insufficient: a fresh snapshot and Ready are required after
reconnect. Pending content is carried atomically in the approval snapshot rather
than depending on delayed timeline normalization.
The protocol does not provide a corresponding MCP item ID, so the card uses an
independent UUID rather than guessing which concurrent tool item it belongs to.
Approval responses must match both approval ID and owning execution.

Only an explicit interactive approval returns
`{"action":"accept","content":{},"_meta":null}`. Command auto-approval and
noninteractive/no-op approval services cannot grant MCP consent. Request metadata
advertising persistent/session approval is never echoed or used. Plugin policies,
connector authorization and existing permission configuration remain unchanged.

| Outcome | Protocol action | Persisted origin |
| --- | --- | --- |
| Explicit approval | accept | human_approved |
| Explicit decline | decline | human_declined |
| Approval deadline | cancel | timeout |
| Request resolved/cancelled by lifecycle | cancel | request_cancelled |
| Native peer disconnect / process stop | cancel if transport available | disconnected / process_stopped |
| Stale thread/turn, unsupported form/URL, malformed request | cancel | specific bridge diagnostic |
| Missing approval service / bridge error | cancel | service_unavailable / bridge_error |

The reader remains available while approvals wait. Concurrent requests have
independent approval IDs; repeated IDs cancel pending consent and never reuse a
completed approval. Nullable provider turn IDs bind to the current turn at
admission; turn replacement/completion cancels pending requests. Peer EOF and
process stop remove pending UI state. Closing only a browser tab preserves the
pending approval for reconnect until the existing deadline; silence grants no
consent. Unsupported forms requiring user input and URL/auth flows are cancelled
because this fix supplies no form/auth UI.

The generic fallback question and monitor reason are not consent context.
`_meta.tool_title`, connector name/ID, invocation `tool_params` and verified
`tool_params_display` labels produce a bounded plain-text summary. Every
non-secret invocation parameter, including target and instructions, is visible;
secret-bearing fields are redacted; fully redacted arguments cannot produce a
consent card. This is checked recursively after sanitization: container names,
display labels, nulls, empty/blank values and redaction markers do not count as
usable invocation context. A surviving nonsecret value in a nested object or
array remains usable. Token budgets/counts remain visible. Display metadata cannot replace or disagree
with invocation values. Missing identities/arguments, inconsistent display
values, embedded credential patterns, oversized content or unsupported structure
fail closed with Cancel and `insufficient_consent_context`, before creating an
approval. Bounds are 8 KiB total, 4 KiB per string, depth 8 and 128 visited nodes, with
64 KiB maximum input arguments. Invisible direction overrides are rejected.
No consequential value is silently truncated. The card and timeline render
this summary as literal text, never Markdown/HTML/links.

Only the redacted action context is persisted for operator review; raw metadata,
provider messages, unrelated metadata, credential values and denial reasons
are not copied into bridge logs. Arbitrary free text is not a formally complete
secret detector: callers must not place credentials in action instructions.
Diagnostics contain request IDs and fixed origin labels.
Upstream Codex may still label a Cancel as `user cancelled MCP tool call`; Vibe's
persisted diagnostic records the actual bridge origin without claiming a human
decision. A genuine human Decline retains the upstream rejection behavior.

## Isolated validation

Tests use synthetic identities, an in-memory database, disabled notifications,
an offline Python app-server peer and mocked UI API transport. No model inference,
connector calls, real resume, production listener or production database is used.

```bash
export CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target
export CARGO_INCREMENTAL=0
export VK_TEST_OUTPUT=/mnt/vk-storage/vk-mcp-approval-tests
node scripts/testing/run-mcp-approval-ui-tests.mjs
VK_MCP_UI_RESPONSES="$VK_TEST_OUTPUT/mcp-ui-responses.json" cargo test -p services --lib
cargo test -p executors --lib
cargo test -p executors --test mcp_consent_context
cargo clippy -p executors -p services --all-targets -- -D warnings
pnpm run format
pnpm run ops:check
NODE_OPTIONS=--max-old-space-size=8192 pnpm run check
pnpm run lint
cargo test --workspace
```

The mounted real SessionChatBox, McpConsentCards, approval selector and WebSocket
patch hook use only a mocked transport/API boundary. They exercise concurrent A/B,
reversed snapshots, reconnect before Ready, cancellation, delayed consent context,
expiry, execution filtering and literal text. No response is emitted at render;
explicit per-card approve/decline payloads are consumed by the service fixture. The peer's
synthetic dispatch gate remains closed while pending and opens only for Accept.
Regression coverage includes the Reporting-resume empty-form shape and RPC ID 0,
typed result decoding, denial, actual deadline expiry, cancellation, EOF/stop,
unsupported/malformed input, concurrent/repeated requests, cross-execution and
cross-connection isolation, nullable/stale turns and metadata redaction. Actual
upstream generic `Allow this app to run tool "run_session_prompt"?` and
`Tool call needs your approval. Reason: ...` shapes have distinct synthetic
session targets in metadata; incomplete context produces Cancel without a card.

Validation receipts and draft PR/CI status are recorded in HANDOFF.md. Full host
workspace tests/lint require missing GLib development libraries; do not install
system packages or change the runtime as part of this task. Actions publication
was inspected: PR checks target staging; deploy workflows require main pushes or
explicit dispatch. This draft is not release approval. Live activation and a
genuine connector/operator round trip remain outside this task and require a
separately authorized release after review and passing applicable CI.

## Installed launch protocol verification (2026-10-08)

Read the configured `VK_CODEX_BASE_COMMAND` wrapper and its delegated executable,
then generate schemas offline through that wrapper:

```bash
node scripts/testing/check-codex-mcp-runtime-schema.mjs <configured-launcher> <mounted-output-directory>
```

This workspace's configured wrapper delegates to **codex-cli 0.159.2**. The
unqualified shell launcher delegates to 0.153.4 and is not the configured
executor. The generated 0.159.2 request schema SHA-256 is
`5cbeb6bc702d2efa076da4c1dfb00672c970c1bad747031eb880b9ab907815c0`;
response schema SHA-256 is
`792a012fdfe53ac211575a6c37ffbd492be848d15cb313d1bb4b534ade1f54ac`.
The supported form envelope, nullable turn, action enum and optional content/meta
agree with the pinned protocol's one-shot response. This verifies the installed
launch path, not merely Cargo's rust-v0.116.0 dependency. Newer `openai/form` and
`openaiForm`, URL flows and nonempty schemas remain unsupported and fail closed.
Metadata is schemaless upstream; the bridge validates the supported fields.
No live session or connector execution was started for this verification.
