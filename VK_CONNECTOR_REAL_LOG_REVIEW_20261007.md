# Corrected Connector: Real-Log Compatibility Blocker

## Outcome

Do not deploy combined candidate2bc909d6375e13d0dd47f370eec0100fae3b2075 yet.
All31 independently rebuilt Rust tests and server compilation pass. All94
connector tests pass. Those results do not cover the real-log incompatibility
reproduced below. Source was fast-forwarded from eacafb3a1 and pushed without
altering the repair; draft integration PR150 preserves PR147/148 exact heads.
Production, badges, receipt ledger, Recommend and credit settings are unchanged.

## Independent Reproduction

The private harness calls the repaired `read_execution_log_strict` and
`normalize_review_log` directly on the four retained, hash-verified historical
copies. It does not construct the application, access production DBs, submit a
receipt, or populate a historical writer fence. All four strict replays fail
with `Invalid native event in review log`, before final-reply identity exists.

- 0026f9d8-8b32-4eb9-8d77-e2cb9983fb7a: `thread/goal/cleared` at reconstructed
line17, plus twelve `item/started`/`item/completed` events whose item type is
`sleep`, at lines1566/1567,1627/1628,1642/1643,1701/1702,1718/1719,1764/1765.
- aec2c0e4-a054-4846-abef-bb8601d6bf96: `thread/goal/cleared`, line15.
- c081fb14-ee8c-4321-bdaf-9deb2b9a9778: `thread/goal/cleared`, line18.
- 862ea4ac-9e04-4607-a7eb-19ddf60ff94a: `thread/goal/cleared`, line17.

`thread/goal/cleared` has a `threadId` parameter. Rejected sleep items have
`type`, `id`, `durationMs`; their envelopes include thread/turn IDs and start or
completion timestamps. No report content, credentials or source evidence is
copied into this document. Earlier chunk-aware audit found native completion
events and matching visible report hashes in all four; that does not make this
new strict validator compatible or prove old writer finalization.

Exact source of the rejection is
`crates/executors/src/executors/codex/normalize_logs.rs::validate_review_line`:
the broad thread/item notification branch delegates to the pinned SDK enum,
which rejects these real runtime event variants. The new normalizer invokes
that validator on every reconstructed stdout line before normalization.

## Developer Handoff

Objective: recognize the legitimate runtime event shapes above while retaining
strict malformed/truncated-input rejection and exact final-reply identity.
Repair belongs to the connector backend development owner, not a live data
workaround. Base against the preserved2bc909d63 combined source or provide a
precisely bound compatible patch. No competing development agent was started.

Success means positive regressions for goal-cleared and sleep lifecycle events,
negative malformed variants, the existing31 tests, and strict replay of these
four unchanged copies yielding the already bound exact report indices/hashes.
Do not simply ignore all unknown events, fabricate a writer fence, reuse tolerant
UI replay as integrity evidence, or blanket-clear badges. Historical closure
validation remains a distinct requirement after parser compatibility. Root owns
actual caller delivery evidence and final receipt reconciliation after readiness.

## Integration CI

Exact-head artifact build37689605524 succeeded and its candidate/fallback bundle
is retained. It is not release acceptance. PR150 test run37690486028 additionally
fails Clippy and Tauri Clippy on `result_large_err` in
`log_history.rs::fingerprint_review_messages` (line339) and
`report_review.rs::validate` (line62). Resolve the narrow new-code lint errors
without a repository-wide suppression. The duplicate artifact job37690486036
was canceled after the exact-head build succeeded; it is not another source failure.

The completed backend CI job ran373/440 tests:370 passed,3 failed,9 skipped;
67 did not run after fail-fast. The three failures are HTTP fixture setup at
`report_review_tests.rs:19`: `Explicit isolated acceptance root required:
NotPresent`. This is a CI fixture-integration gap, not failure of the locally
isolated eight-test HTTP run. Make the reviewed isolation boundary usable in CI;
do not remove its guard, mark tests passed without running, or point CI at live
storage. Schema, frontend, remote, freshness and governance checks passed.

## Receipts

`/mnt/vk-storage/vk-combined-release-20261007/repair-acceptance/` contains
`binding-verification.json`, integration/http/capture/normalizer/compile logs and
JSON results, `historical-replay-result.json`, `historical-replay.jsonl` and
`historical-build.log`. The replay result binds source, harness, binary, all raw
hashes and exact rejected-event line hashes; its exit1 and `passed:false` are
intentional failure evidence, not an accepted deployment.

Harness: `scripts/testing/historical-review-20261007/record.py` and its Rust
source/lockfile. Run only against the reviewed private copies on mounted SSD.
Original developer receipts and all earlier rejected attempts remain retained.
The final formatted harness repeats the same four failures in
`historical-replay-result-formatted.json` (8.437s), with final source/binary hashes.
