# Production conversation-log reclamation — 2026-11-04

Branch `vk/0815-vk-deduplicate-c`, rebased on fork/staging `ee2efee4d`. User requests
completion through production lossless conversion, independently verified recovery,
actual space reclamation and ongoing-growth prevention. Source integration alone
is insufficient. Draft [PR291](https://github.com/artinflight/vibe-kanban/pull/291)
targets staging. Preserve latest live frontend, private retained-history inputs,
protected replay behavior, current database writes, native homes and queued work.

Current checkpoint15:11UTC: **zero production conversions/recovered log bytes**.
Both executables are built and independently byte-hash verified; eight exact
protected replay tests pass. Existing Vibe owner is preparing current-data rehearsal.
Nightly remains sole backup producer; it is reconciling retained versions and
qualifying normal restore. Its accepted archive dependency contract remains valid.
Actual selected B body/metadata recall and real owned custody are still required.

`VK_LOG_RECLAMATION_READINESS.md` is the OP::Disk Space procedure;
`VK_LOG_DEDUPLICATION.md` records format and original six-log evidence. Immutable
private execution state is under `/mnt/vk-storage/vk-log-dedup-20261103-0815/`.
The finite selection contains3,221 closed/inactive logs /84,557,012,508 logical
bytes in66 bounded preparations. Selection establishes neither custody nor saving.
Legacy, active, pending, damaged and nonbeneficial tiny logs stay preserved pending
explicit applicable review; no semantic turn omission or object garbage collection.

Four unchanged canary originals allocate1,053,085,696B; their selected packed graph
allocates222,183,424B including sidecars. The792.4MiB margin excludes directory/store
changes and is not actual recovery. Original six-file potential812.1MiB is separate.
Another33-file/2,020,462,248-byte archive is sealed and reconstructed with unchanged
originals. Resource guards stopped prior attempts; later Rust verification was
refused before startup on renewed shared pressure. No guard was lowered.

Sourcee70732c92 passed hosted Test and Historical recovery.53 focused Python and
eight retained WriterFence tests pass. Formatting/ops and current source hashes
are recorded in durable receipts. Existing owners retain build/deployment and
backup admission. Actual WriterFence requires legitimately quiet dispatch and
physically frozen compatible readers; preserve active jobs and uncertain inputs.
No new producer, timer, automatic conversion or background retry is enabled.

Historical scope: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).
