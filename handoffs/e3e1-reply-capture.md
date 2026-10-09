# e3e1 reply-capture handoff — candidate, no deployment

WHAT: Preserve durable assistant finals under MsgStore lag/large resume bursts,
and explicitly report unavailable capture rather than stale historical status.
WHY: Root coordination and exact-reply review require trustworthy current reports.
CONTEXT: deployed combined backend c3c48e6324f778ccd03a5761c2314b440e9ceac3,
kept intact; no production, Staging worktree, badge or consent-setting writes.
SUCCESS: one bounded lossless raw writer, split UTF-8 preservation, closure/failure
safety, restart visibility and isolated compiled writer/HTTP/UI regressions.

Branch: fix/e3e1-lossless-reply-capture. PR236 is draft into staging.
codeSha: 334a2a2af608cd9a83eb721397a4ca7b8e87c9ee (excludes handoffs/runs).
Base: c3c48e6324f778ccd03a5761c2314b440e9ceac3. PR diff also carries unmerged
combined baseline; do NOT independently deploy or merge that wider baseline.
Root/Dev/Staging must apply/review only the c3-relative bounded patch.

Changes: crates/utils/src/{msg_store,execution_logs}.rs and Cargo.toml;
crates/{services,local-deployment}/src/.../container.rs;
crates/services/src/services/execution_process.rs;
crates/server/src/routes/execution_processes/log_history.rs;
crates/server/src/routes/workspaces/report_review_tests.rs;
crates/server/tests/report_review_integration.rs;
packages/web-core/src/features/workspace-chat/{model/historyPage.ts,
model/hooks/useConversationHistory.ts,ui/ConversationListContainer.tsx};
scripts/testing/long-thread-history.test.tsx; .github/workflows/test.yml;
STATE.md, STREAM.md, HANDOFF.md, VK_REPLY_CAPTURE_20261009.md and this handoff.

Raw queue is bounded (128 chunks) and backpressures the producer independently of
lossy UI delivery. Single storage-writer registration precedes exit monitoring;
raw EOF and metadata Finished both drain before closure. Split UTF-8 is carried,
not replaced. Pending/closed capture state survives writer interruption; independent
byte/hash/final/receipt/intent guards remain authoritative. Completed capture that
is pending, damaged, missing or unverified returns explicit capture_error.
UI cannot apply an abandoned workspace response to another scope; retry recovery
requires a new authoritative result. No native transcript backfill is fabricated.

Validation completed 2026-10-09T21:59Z: hosted run37996012426 is SUCCESS at
334a2a2af608cd9a83eb721397a4ca7b8e87c9ee:
https://github.com/artinflight/vibe-kanban/actions/runs/37996012426
18 utils tests (queue burst/lag, metadata concurrency, UTF-8, loss/error guards),
11 real writer/lifecycle tests (20 MB resume + Unicode final, exact bytes/hash,
restart/pending status and failed raw producer), 8 isolated HTTP/review tests,
11 UI tests (newer unavailable report, authoritative retry and abandoned-scope
response), strict Clippy all targets for utils/services/local-deployment/server,
web-core/local-web/remote-web type checks, Rust formatting and governance PASS.
One installed-MCP connector acceptance test is deliberately ignored on the hosted
runner; no actual voice playback/delivery signal is invented or tested here.
The ordinary PR gates/full-workspace/remote/platform jobs were skipped by opt-in
workflow_dispatch, NOT passed. This does not certify promotion/deployment.
Earlier failures are retained: run37994262022 API conversions;
run37994887156 nested-if lint; run37995427513 incorrectly ordered UI fixture.
All corrected, exact revised code compiled and tested. No local Cargo builds.

Exact tested c3-only patch and all file SHA-256 bindings:
../evidence/backend-c3c48e63-to-334a2a2a.patch
SHA256 e929b2bcc4635b5101dc8794682e1928bfd177b17c25534c6c3fdd237f16a232
../evidence/backend-binding.json plus run37996012426 JSON/log receipts.
The later handoff-only commit does not alter compiled runtime or test files.

Separate connector candidate: ../connector, fix/e3e1-incomplete-reply-status,
tested code0ed678f5b0ee73542690518b2fecc90d8733da67, handoff HEAD
fde38ec45f0e87f6d872d3c49eff9d40f716a411, 98 Python tests passed. No new tools,
allowlist or auth changes. Explicit reads return capture_incomplete true and
completion unknown; latest lookup cannot substitute older successful status for
an unavailable newer completed report. Imported connector has no remote.

Resume: exact-commit hosted acceptance is complete with no scoped source blocker.
Review c3-only patch and connector
candidate together, preserve all native evidence. Owner-controlled release flow
must authorize any later activation; this turn does not deploy/restart.

Limits: unavailable historic captures remain unavailable; exit zero is not proof
of a captured final. Full workspace/platform checks and physical Android QA are
not implied by scoped acceptance. No actual voice/chat playback callback is
available in the cached parent catalog, so no end-to-end automation claim.
Dispatch proposal is in VK_REPLY_CAPTURE_20261009.md; app-wide permission changes
are broader than routine dispatch and are not authorized or changed.

Capacity: exact local Cargo target is
/mnt/vk-storage/vk-connector-repair-20261007/cargo-target-compat.
No Cargo/rustc writers remain; only debug/deps/utils-e95cc44e49995141 is released
for verified reversible Desktop B offload. No cleanup or artifact movement done.

Fresh incident evidence: files for executions3bd4815a-3aaf-405e-acb3-c9d68a21bb77,
95d4f979-264d-4304-92b3-c0a278b53d93 and3c466517-b1bd-4d0e-b710-2dcfb46f0abe
still end mid-native JSON. Explicit result: capture incomplete; captured current
report unavailable; task_completion unknown. Native transcripts are preserved
separately. No older report substitution, fabricated backfill or badge clear.
