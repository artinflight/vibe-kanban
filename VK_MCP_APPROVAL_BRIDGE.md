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
distinct approval card with the server-provided consent message and one-call
scope, creates the actual Vibe approval request, and waits for the operator.
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

Raw elicitation metadata, URLs, form contents, tool arguments and denial reasons
are not copied into bridge logs. The consent message is retained because the
operator must review it. Diagnostics contain request IDs and fixed origin labels.
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
cargo clippy -p executors -p services --all-targets -- -D warnings
pnpm run format
pnpm run ops:check
NODE_OPTIONS=--max-old-space-size=8192 pnpm run check
pnpm run lint
cargo test --workspace
```

The real UI mutation hook emits no response at render and generates explicit
approve/decline payloads consumed by the service round-trip fixture. The peer's
synthetic dispatch gate remains closed while pending and opens only for Accept.
Regression coverage includes the Reporting-resume empty-form shape and RPC ID 0,
typed result decoding, denial, actual deadline expiry, cancellation, EOF/stop,
unsupported/malformed input, concurrent/repeated requests, cross-execution and
cross-connection isolation, nullable/stale turns and metadata redaction.

Validation receipts and draft PR/CI status are recorded in HANDOFF.md. Full host
workspace tests/lint require missing GLib development libraries; do not install
system packages or change the runtime as part of this task. Actions publication
was inspected: PR checks target staging; deploy workflows require main pushes or
explicit dispatch. This draft is not release approval. Live activation and a
genuine connector/operator round trip remain outside this task and require a
separately authorized release after review and passing applicable CI.
