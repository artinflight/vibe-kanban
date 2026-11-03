# Lossless log deduplication — pickup, 2026-11-03

Current branch `vk/0815-vk-deduplicate-c`. Read `VK_LOG_DEDUPLICATION.md` for the
format, OP::Disk Space procedure and deployment gates. The inherited resume
prevention fix is documented in `VK_DUPLICATE_HISTORY_FIX.md`; neither is deployed
by this task.

New code: `crates/utils/src/log_archive.rs` and existing log/recovery readers;
offline tooling/tests in `scripts/log-dedup`; backend-reader verifier in
`crates/utils/examples/verify_log_archive.rs`. Frozen source plans, packed objects,
receipts and test logs are private under
`/mnt/vk-storage/vk-log-dedup-20261103-0815/`. They contain no source retirement
permission. No conversation log, sidecar or native history is replaced; no conversation
rows are rewritten or service changed.

Verified sample: six logs, 1,089,056,768 original allocated bytes versus
237,555,712 archived bytes including metadata; 851,501,056 bytes (812.1 MiB) recovery
potential, zero live bytes reclaimed. All restored originals/sidecars hash-match
unchanged sources; only the generated restore copies were then retired. The Rust
backend reader independently verifies all six packed files. Ten migration tests and 36 utility tests pass (one existing
private probe ignored), plus utility clippy, full format and ops. Seven unchanged
prevention tests were rerun in their qualified cached binary. Final server library
check passes (`cargo check --offline --locked -p server --lib`); no runnable release
or public UI acceptance is claimed. See the runbook for
limits and pending broader acceptance.

Deployment requires current Desktop B recovery, exact inactive-file and consumer
checks, preserved private inputs/live features, qualified backend build, compatible
current-data fallback rehearsal and authorized drained custody. Install objects
before manifests. All rollback consumers need archive readers or restored raw
JSONL. Reserve reconstruction space. Do not enable object GC or background
conversion, infer production acceptance from fixtures, or extrapolate sample gains.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
