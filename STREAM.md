# Complete deduplication, including file-count and speed requirements

Fix the one-file-per-piece layout while preserving exact readable history and
all accepted recovery epochs. Prepare compatible readers and forward/backward
packed conversion; prove real recovery and ordinary behavior before retiring
old loose pieces. Measure file count, performance and net allocation including
staging. [Current design and evidence](VK_DEDUP_PACKED_LAYOUT.md).

Nightly commissioning is explicitly excluded by the user. Do not resume its
composition/current41/bootstrap/calendar work. Preserve its existing tracking,
pending inputs, partial cursor, imports and owners. No new goal/agent/watcher,
uncertain replay, model polling or deferred workspace/archive cleanup.

Daily dedup is held by an exact owned maintenance condition; its saved enabled
calendar is preserved. Long work uses bounded scripts and the same WakeWatch.
Build/test success is a checkpoint, not live migration or final acceptance.

Previous scope: [before packed repair](deployment-history/20261124-before-packed-repair/STREAM.md).
Full historical archive: [STREAM history](STREAM_HISTORY_20261017.md).
