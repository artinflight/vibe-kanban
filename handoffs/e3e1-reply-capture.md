# e3e1 reply-capture handoff — candidate, no deployment

WHAT: Preserve durable assistant finals under MsgStore lag/large resume bursts,
and explicitly report unavailable capture rather than stale historical status.
WHY: Root coordination and exact-reply review require trustworthy current reports.
CONTEXT: deployed combined backend c3c48e6324f778ccd03a5761c2314b440e9ceac3,
kept intact; no production, Staging worktree, badge or consent-setting writes.
SUCCESS: one bounded lossless raw writer, split UTF-8 preservation, closure/failure
safety, restart visibility and isolated compiled writer/HTTP/UI regressions.

Branch: fix/e3e1-lossless-reply-capture. PR236 is draft into staging.
codeSha: 0cafd511cf1a7e2d5009599cffa5d023c82e5be8 (before this handoff).
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

Validation: initial hosted run37994262022 at5ee3486b passed utils but failed two
ApiError conversions. Corrected run37994887156 atdab918d6 passed compiled utils,
real writer/burst/restart and isolated HTTP/review tests; remaining checks were
still running when this handoff was prepared. Final hosted receipts are stored
outside the worktree under ../evidence and linked in PR236. Do not treat this
preparation note as a passing receipt. Latest UI scope/retry/type-check additions
require exact revised-commit hosted acceptance. No local Cargo build is permitted
while SSD capacity hold remains. pnpm run format and git diff --check passed.

Separate connector candidate: ../connector, fix/e3e1-incomplete-reply-status,
0ed678f5b0ee73542690518b2fecc90d8733da67, 98 Python tests passed. No new tools,
allowlist or auth changes. Explicit reads return capture_incomplete true and
completion unknown; latest lookup cannot substitute older successful status for
an unavailable newer completed report. Imported connector has no remote.

Resume: collect exact-commit hosted Test/reply-capture-acceptance receipt. Correct
scoped failures only; no local Cargo builds. Review c3-only patch and connector
candidate together, preserve all native evidence. Owner-controlled release flow
must authorize any later activation; this turn does not deploy/restart.

Limits: unavailable historic captures remain unavailable; exit zero is not proof
of a captured final. Full workspace/platform checks and physical Android QA are
not implied by scoped acceptance. No actual voice/chat playback callback is
available in the cached parent catalog, so no end-to-end automation claim.
Dispatch proposal is in VK_REPLY_CAPTURE_20261009.md; app-wide permission changes
are broader than routine dispatch and are not authorized or changed.

Capacity: local cargo target is ../.. /vk-connector-repair-20261007/cargo-target-compat
(the exact path is /mnt/vk-storage/vk-connector-repair-20261007/cargo-target-compat).
No Cargo/rustc writers remain; only debug/deps/utils-e95cc44e49995141 is released
for verified reversible Desktop B offload. No cleanup or artifact movement done.
