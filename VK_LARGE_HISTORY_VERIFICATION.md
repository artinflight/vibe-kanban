# Large native-history verification

The native input reader previously rejected histories over 128 MiB, then retained
the full history, parsed inputs and serialized prefix in memory. Increasing that
bound alone would multiply allocations and would not validate real native formats.

The shared startup/invocation path now reads one JSONL record at a time, with a
16 MiB per-record bound. It hashes the original compact JSON array representation
incrementally and counts authorized suffix inputs per native kind and durable
receipt digest. It still parses output/accounting records, so malformed ignored
records cannot evade validation. Memory scales with one record and receipts,
not accumulated history or sealed input count. Parsing runs in a blocking task;
a shared permit limits this verifier to one in-flight scan, including cancellation.
There is no new total-file cap or special case for a particular thread.

The verifier reads only the initial file extent, rechecks file object, size,
mtime/ctime, index binding and index object, and refuses a changed view. It does
not follow an indefinitely growing file or retry after uncertain verification.
The trusted backend/native writer boundary is unchanged; these checks do not
claim protection against a hostile same-UID process falsifying host state.

Native world-state records contain instructions and permissions. They are part
of the sealed amendment sequence, alongside compaction/rollback. A new world
state after capture fails closed; it cannot match a plain-text continuation
receipt. Token-usage records are parsed accounting data. Unknown envelopes still
fail closed. Legacy seals over previously supported formats retain their exact
encoding. A history containing world-state records was previously unsupported;
this change never recaptures or updates a release contract to authorize it.

Tests use synthetic data only: 192/384 MiB histories through the real startup
loader and ledger freshness path, a 160 MiB input prefix, malformed/truncated
and unauthorized tails, changed sealed input, repeat-input accounting, index
escape/rebinding and concurrent append/truncate/rewrite/replacement. Existing
production launch, profile/collision, terminal and no-replay regressions remain.

The check-only Large history verification workflow exports the exact source's
optimized compiled read-only test verifier. An independent test-only reference
materializes the original payload array using the workspace's Rust JSON number
encoding and key ordering. This avoids cross-language seal serialization drift;
its private receipt is not an adopted grant. The private request specifies native home,
thread, seal and authorized receipt digests outside Git. The ignored verifier
opens only the native index/history read-only; it neither opens a VK ledger nor
adopts a contract, starts a server or dispatches input. Its output contains only
pass/refusal and elapsed time. Resource measurement and private manifests remain
on mounted secondary storage. A reference prefix generated solely for this
inspection proves reader compatibility, never owner authority or activation.

Validation: code/test commit df717cf8e passed hosted Test run 38376417585 with 548 Rust
tests (13 skipped), schema, Clippy, frontend and Tauri checks. The 192/384 MiB
production startup/admission fixture passed. The optimized focused workflow
38376417683 passed 8 tests (two explicitly private probes skipped in CI). Both
private original histories and their stable snapshots then passed the compiled
read-only verifier against the original Rust materialized-array reference,
each below 3 seconds and 24 MiB peak RSS. Precise private receipts, identities,
source snapshots and measurements remain outside public Git.

Local format, ops governance and frontend lint passed. Local TypeScript ran out
of Node heap; hosted frontend validation passed. No Cargo compilation occurred
on MCP. The first Python inspection reference was refused because cross-language
JSON encoding did not match Rust; no live seal was changed. The accepted reference
uses the original Rust serialization, and streaming measurements exclude reference
materialization. A concurrent manager snapshot was refused before a stable copy
was obtained without prompting or stopping the source session.

Draft PR #245 carries the final published-head checks. The documentation follow-up
changes no executable source. Reader acceptance does not certify release adoption
or a live continuation: the capability remains default-off. Independent review,
release-owner adoption, separately authorized live acceptance and the unchanged
final user review/Figma gate remain. No restart, deployment, activation, live
grant write, original-history change, target prompt, merge or promise of restart
inclusion is part of this repair.
