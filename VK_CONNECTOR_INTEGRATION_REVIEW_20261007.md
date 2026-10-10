# Connector Integration Review: Release Blocked

## Scope And Provenance

Review target is connector backend candidate
`13a3458eb2dc4f8660b756aab8593ac0d4a7dcd5`, not its older patches. All eight
base and applied source hashes were checked against `backend/source-binding.json`
in `/mnt/vk-storage/vibe-dot-connector-maintenance`. Connector runtime
`5e4c74998de6c490781e0698135040a835944528` was deployed independently; its 94
Python tests do not establish Rust or production acceptance.

Applied only to isolated branch `release/overnight-autoswitch-20261007`, based on
combined commit `4e1fb9025f9bc17290ee8b448272c90988d9ce26`. PR147 remains
`9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4`, PR148 remains
`cb0b441a2ad505fc0a73071622065e2ff6655e77`, CU PR38 remains
`95e7aea47e137015daa8efcbb210184ee7ce723c`; all three remote heads were refreshed.
No staging/main promotion, production restart, settings write or archive deletion.

## Integration Correction

The initial combined Rust check failed E0061: PR148 introduced an `inspect` call
while PR147 added its required deadline argument. The new call in
`crates/executors/src/routing_triage.rs` now passes `Duration::from_millis(40)`.
After that narrow correction, `cargo check --offline -p server --bin server
--tests` passed in 66.028 seconds. A clean Git merge was not compile evidence.
The correction is separately committed as `9638eb413`.
The compile-only embedded placeholder frontend is NOT a deployable package.

## Findings Requiring Developer Correction

1. **Blocking deletion regression.** The new migration's foreign keys use default
   RESTRICT behavior. Existing workspace deletion directly deletes its parent;
   intent rows created by ordinary read/unread actions now prevent that deletion.
   Finalized-log rows also prevent execution deletion. A private SQLite test with
   foreign keys enabled reproduces `FOREIGN KEY constraint failed`. Establish an
   explicit dependent-row lifecycle compatible with existing deletion and the
   intended receipt audit policy; do not turn off foreign keys to pass tests.
2. **Writer closure proof does not detect evicted history.** The existing
   `MsgStore::history_plus_stream_strict` detects broadcast lag, not pre-subscription
   history eviction. A store that has already evicted report bytes can present
   only Finished to the new writer. That can publish a fence for incomplete data.
   The compiled actual-writer regression reproduces one fence for a zero-byte
   private log (expected zero fences). Add loss-aware capture/closure with a
   race-safe history-to-live boundary. The
   existing separately acquired snapshot/subscription also needs review; that
   interleaving is a source concern, not yet a reproduced concurrency failure.
3. **Replay is not a strict integrity reader.** `final_reply_fingerprint` uses the
   ordinary historical UI replay. `stream_raw_log_messages` skips invalid JSONL;
   `ContainerService::stream_normalized_logs` converts read errors to stderr,
   ignores normalizer join failures and appends Finished. These source paths must
   not certify lossless immutable report identity. Use a strict integrity path
   with explicit error propagation and bounded replay, without weakening normal
   UI recovery or accepting a partial report. This finding is source analysis,
   not a claim of observed production badge loss.

The developer-owned correction scope is the new migration, finalized writer,
strict message capture/replay boundary and conditional report reader. Keep the
exact identity, manual intent, newer-work and idempotency protections. Staging
must rerun the compiled regressions and real isolated routes after correction.
No competing development agent was started or contacted.

## Historical Evidence

Receipt root:
`/mnt/vk-storage/vk-combined-release-20261007/connector-review/historical`.
`historical-report-audit.json` records stable source stat/hash checks around four
bounded private log copies, four exact report hashes matching recorded receipts,
and zero malformed outer JSONL lines. The existing read-only log-history API was
used; neither opening/seen routes nor reconciliation writes were invoked.

`candidate-provenance-and-historical-terminals-v2.json` supersedes the initial
per-chunk terminal scan: concatenating Stdout chunks before JSONL parsing finds
native `turn/completed` in ALL FOUR logs and no malformed reconstructed events.
The initial scan missed two events split between chunks; its receipt is retained,
not used as proof of missing completion. Completed database status, stable bytes,
native completion and matching text are not independently successful storage
writer-finalization evidence.
All four remain uncertified for historical closure. No live fences were populated,
no delivery evidence invented, and no badges cleared. The four connector receipts
remain blocked; missing client delivery callback and stale tool discovery also
remain explicit end-to-end limitations.

## Validation Status

Compiled migration and actual writer regressions are in
`crates/server/tests/report_review_integration.rs`. The first execution completed
in381.153seconds including compilation: **4 passed, 4 failed**, none ignored.
Both deletion tests fail with SQLite787; the history test returns Ok(Finished)
instead of an error; the actual writer publishes one fence despite lost bytes.
The untruncated writer/control, complete-stream control and both flag-trigger
tests pass. Receipt `connector-review/cargo-integration-tests.json` and full log
are retained. The4GiB floor was not hit; minimum free12,998,684,672bytes.
These tests are intentionally red reproductions, not acceptance of the candidate.
These are private in-memory databases and task-local debug logs, not a live
deployment constructor or unrestricted fixtures. The test runner enforces a
4 GiB SSD free-space floor, two build jobs, and no incremental/debug-symbol bulk.
The writer fixture is explicitly bound to this isolated source path; it is not
an unrestricted production or shared-worktree fixture. Preserve that isolation
when adapting the reproduction for the developer's environment.

The final formatted source was rebuilt/retested, reproducing the SAME four
failures and four passes in93.028seconds including build, with no skipped tests.
`connector-review/cargo-integration-tests-formatted.json` and its log are the
final test receipts. Minimum free12,719,669,248bytes; the4GiB floor was not hit.
Both runs finished; no background test job remains. No production data was used
by the writer/migration fixtures. The original read-only historical copies and
all failed receipts are retained, not deleted or rewritten into passing results.

`pnpm run ops:check` and `git diff --check` pass in both worktrees. Required
`pnpm run format` was attempted in both: Rust formatting passed, frontend stage
failed because Prettier is unavailable. No frontend inputs changed. Formatting
reorders the new workspaces module declaration; initial exact candidate hashes
are preserved in the provenance receipt. The candidate also retains three new
unused import/variable warnings in core.rs; warning-free Clippy is not claimed.
Frontend source/shared/package inputs still exactly match accepted PR147 after
integration; this supports eventual reuse, not acceptance of a new server bundle.
Full workspace tests, conditional-route HTTP acceptance and combined-release
native/rollback acceptance are NOT claimed while the reproduced blockers remain.

## Remaining Rollout Gates

Fix and independently review the findings, then exercise conditional HTTP routes
and historical strict closure on the corrected compiled source. Rebuild/bind the
matching backend, AutoSwitch protocol2 module and latest-v2-compatible fallback;
reuse accepted frontend only after exact input compatibility is confirmed.
Rerun affected combined CU/native/HTTP acceptance without paid inference or the
real Android goal. Keep Recommend, scheduling ON and credits OFF.

Specific approval to retire the 27 exact SSD archive copies is still unanswered.
No archive was deleted. Use PR149 `312ac0b20` recovery tools; Desktop B remains
the sole retained archive provider. Fresh complete backup, measured phased
restore/rollback within available SSD space, fresh runtime/model identity,
promotion and actual operator/agent/queue/grant drain remain required. Historical
recovery exceptions stay visible; rollback uses compatible software on the same
latest data, never an older production database.
