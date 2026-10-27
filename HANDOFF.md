# Nightly — current pickup,October26 21:24EDT

Finish the existing operational Nightly goal/PR263. No backend restart. Calendar
is disabled; next run null. Do not duplicate active jobs or accepted bodies.
Read fresh private receipts under vk-nightly-efficiency-20261017/
commissioning-20261026 before relying on saved running observations.

Growing controls now run on native Desktop B under
B:/vk-backups/vk-nightly-efficiency-20261026/controls-v1. Six full original index
checkpoints and working copies passed independent SHA/SQLite/normal-consumer
proof; SSD replicas became pointers, releasing2085306368allocatedB. The latest
2321969152B cold task footprint is mostly retained prefix/scale evidence; it was
not deleted. No backup payload or growing index is staged on OS/work SSD.

Source observation is separate from Desktop: one8MiB local database plus9MiB
preallocated PERSIST/FULL journal, native allocation overhead and two64KiB health
files. V7 PID3632010/start26998675,epocha685913e7c07452cb13efc761f0a64b0,
107010watches/errors0; tracking-worker-local-v7 configSHA
 d0213d97077dce0175fafe49d11f2f4fe59b4ecbdc5f0e77d0958825bc0cc255.
Actual B copy/reopen then generation-safe ACK passed through25692. The normal
B-prefix/live reader returned279names with0inventory/body reads. Preserve the
original pre-ACK result flag; local_acknowledged establishes actual compaction.
V6 closed normally only after its completed gap and real new/old/new barriers
were stored/read back on B: V6_V7_VERIFIED_HANDOVER proof8c4e3c1e4111dcb1d479906e67cfce517bf8def9e2670522d844bc7fafff65a5.
Old source DB/journal remain preserved pending verified B relocation. No old
SSD-growing observers are enabled. Never query an acknowledged local prefix
as empty; use retained_prefix_report through the authenticated B provider.

Later gap enumeration COMPLETE:919022paths/107010directories/errors0,
383changed-name closing suffix,0source-body bytes. V6_GAP_NAMESPACE_RESULT
and all earlier epochs remain. B-map successor unit
vk-nightly-B-map-v6-namespace-adoption-20261027,PID3776518, package
recovery-map-worker-B-v2 configSHA
6b4e2b779044c96a5924e625e4bdab2344bc455e42980bbd4a8c286a1d3e6efa,
is adopting that same-scope epoch and preserving old gap/absence rows. Do not
restart it. A competing SQLite read was correctly refused; the supported
nonlocking probe showed995311616B and fresh native mtime, not SQL acceptance.
Previous complete map:918974names/753701qualified versions reused;70169file
points and17133qualifications were still pending. Logical sizes are not net
transfer demand. Continue from the successor's actual terminal demand.

Sole body writer: vk-nightly-B-large-SQL-point-v6-20261027,PID3387982,
capture-worker-B-v6 configSHA
f102d6786b9d19bacf26b1382298af6e3f14b01bed1fcd02604e69a48f6802d5.
146accepted images were reused(137old/9new,143142689encodedB). The remaining
3GB API point is uploaded with a durable layout and independent RAM readback
is advancing. Do not recapture it. Its prior unsealed RAM inode33476 is retained.
The map has66SQL names outside the old147-source cohort, mostly copied review
fixtures; SQL_RESIDUALS_V6 records exact names. Use tested explicit cohort
inheritance and CAS reuse, not omission or completed-image recopy.

Remaining: collect SQL/map terminals; qualify/capture only unresolved versions;
apply the383-name suffix plus proven observer bridge/current delta; disposition
extra SQL/special/absent names; pin current runtime/frontend; accept the complete
composed descriptor/readback; integrate the ordinary cycle and only then enable
02:00America/Toronto. Root-history migration is separate. Preserve162.70GB
accepted restore,137/148SQL cohorts,all components/supplements/original gaps.

Source a9b7daa08 hosted recovery passed704tests/1skip; new focused epoch/native
cases41pass. Public general CI found pickup-budget excess; this compact handoff
repairs it while preserving the complete prior text in
[the dated archive](HANDOFF_NIGHTLY_HISTORY_20261027_0124.md), bound by
[its provenance](NIGHTLY_CHECKPOINT_ARCHIVE_20261027_0124.json). Ops and Rust
formatting pass; Prettier unavailable. See VK_NIGHTLY_BACKUP_EFFICIENCY.md and
STREAM.md for scope and historical evidence.

Full earlier history: [Nightly](HANDOFF_NIGHTLY_HISTORY_20261026.md) and
[original upstream pickup](HANDOFF_HISTORY_20261017.md). Their original bytes
and provenance manifests remain unchanged.
