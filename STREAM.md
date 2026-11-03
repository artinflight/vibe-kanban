# Lossless conversation log deduplication — 2026-11-03

Branch `vk/0815-vk-deduplicate-c`. Implement content-addressed, compressed completed
process-log storage and safe offline preparation following the disk investigation.
The inherited qualified Codex narrow-resume fix prevents ongoing history replay.

Preserve original reconstructed bytes, hashes, execution paths, review semantics,
capture/recovered-final sidecars, native homes and attachments. Readers are updated
for raw/history, strict review, capture framing and recovery hashes. New captures
remain raw; archived logs reject appends. Objects are session-local. No live
conversion, deletion, provider turn, backend restart or deployment is included.

`VK_LOG_DEDUPLICATION.md` contains OP::Disk Space's measurement/preparation,
consumer audit, deployment and rollback procedure. The CLI builds a separate
verified tree from a frozen plan; it never replaces originals. Source retirement
requires reviewed recovery and authorized deployment custody. Old backends cannot
read manifests; fallback needs compatible readers or reconstructed raw files.

Validation: 36 utility tests, ten migration tests, server library compilation,
utility clippy, required format and ops pass. The real six-file archive and full
restore hash-match originals; 851,501,056 bytes (812.1 MiB) recovery potential is
measured, with zero production bytes reclaimed. See the runbook and HANDOFF. Deployment, provider acceptance, full-population recovery and actual
reclaimed space remain separate requirements, not inferred from source tests.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).
