# Exact-source P2 review disposition — 2026-10-09, NOT DEPLOYED

WHAT: Repair the two independently reviewed P2 findings against334a2a2.
WHY: healthy Completed-before-drain must recover automatically, and short-exit/
Stop cleanup must not remove capture ownership before writer first poll.
CONTEXT: same isolated worktree/branch; preserve evidence and c3-relative boundary.
SUCCESS: both source races removed, realistic compiled HTTP/writer/UI regressions
pass at the exact revised source; no wider baseline merge or live changes.

codeSha: 3af7fbda8f398117f9af7409515185fd8bd7a6ab (excludes handoffs/runs).
Branch: fix/e3e1-lossless-reply-capture. Draft PR236 remains into staging.
Base: c3c48e6324f778ccd03a5761c2314b440e9ceac3. Integrate only that bounded delta;
do not independently merge the wider PR236 combined baseline.

Finding1 — CONFIRMED / FIXED:
Completed precedes metadata Finished. API now reports capture_pending only while
an RAII capture owner is alive, including after the container map entry is gone.
Persisted pending without a live owner, or damaged/unverified capture, remains
terminal capture_error. UI re-reads authoritative finite history1000ms after each
pending response, one timer per execution; no process-status/WS-EOF inference.
Requests pause disconnected/loading, and stop on closure, terminal error, process
removal/running, scope change/unmount. Closure loads final history and clears the
loading state without manual retry; terminal errors retain explicit warnings.

Finding2 — CONFIRMED / FIXED:
Writer takes the existing MsgStore Arc directly. Receiver claim AND metadata
subscription happen synchronously before spawning; the task never re-looks-up
the map. Cleanup before its first poll cannot strand an unclaimed raw receiver.
Cancellation drops owner/receiver and releases the producer. The real metadata
Finished marker also survives UI broadcast eviction; raw EOF remains separately
required. Neither this marker nor the liveness registry is a review proof.
Existing strict closure, byte/hash, native final, revision, receipt/hold and
manual-intent guards remain unchanged. No native transcript backfill is fabricated.

Exact hosted validation SUCCESS:
https://github.com/artinflight/vibe-kanban/actions/runs/37998670795
Head: 3af7fbda8f398117f9af7409515185fd8bd7a6ab.
18 utils +13 actual writer/lifecycle +10 isolated HTTP/review =41 Rust tests;
15 UI tests; strict all-target Clippy for utils/services/local-deployment/server;
web-core/local-web/remote-web type checks; formatting/governance PASS.
New regressions: running→completed→pending→closed over real HTTP and UI; terminal
owner loss; map removed before first writer poll with Finished deliberately evicted
from the tiny UI broadcast; cancellation before first poll without stranded producer;
automatic pending retry, terminal stop and workspace switch cancellation.
One installed-MCP-only test remains ignored on the hosted runner. Ordinary PR
branch/full-workspace/platform jobs were skipped by opt-in dispatch, not passed.
Earlier green follow-up at6f499d17/run37998145590 is retained separately.
No local Cargo build was run; only formatting and lightweight Python/governance.

Connector tested code: 2e4532cf3f703b3186c22d71176aa51f81e0450f,100 Python tests
passed. It propagates active pending separately from incomplete and preserves
completion unknown with no older-report substitution. No polling/delivery callback
or receipt signal is invented in connector. Runtime/auth/allowlist/routing unchanged.

Exact patches, full file hashes and both revised hosted receipts are under:
/mnt/vk-storage/vk-reply-capture-20261009/evidence/
Use backend-p2-binding.json and connector-p2-binding.json. Both base/candidate
revisions and SHA256 bindings are recorded; earlier artifacts are historical evidence.
A later handoff-only commit does not alter compiled code or test files.

Root/Dev/Staging pickup: review this c3-only patch and connector candidate together,
apply only the bounded delta to the authorized integration source, then exercise
normal integration/promotion gates. There is no scoped source blocker after hosted
acceptance. This turn authorizes no deploy/restart, wider baseline merge or approval
change; none occurred. Source/connector candidates are NOT installed.
Historical damaged captures remain incomplete/current report unavailable/task
completion unknown. Preserve transcripts, holds and badges; no live clear occurred.

--- Earlier validated candidate/evidence (superseded by P2 revision above) ---

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
