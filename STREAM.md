# Production conversation-log reclamation — resumed 2026-11-04

Branch `vk/0815-vk-deduplicate-c`, based on current fork/staging. Preserve committed
format implementation `0192b38de` and inherited qualified narrow-resume prevention.
Current objective: complete production lossless conversion, independently verified
recovery, actual space reclamation and future-growth prevention, coordinating with
the existing Nightly and Vibe owners through deployment and acceptance.

`VK_LOG_RECLAMATION_READINESS.md` is the current operator procedure/status;
`VK_LOG_DEDUPLICATION.md` retains format and six-log preservation evidence.
Python follow-up adds retained WriterFence integration, source-pinned owner-adapter
command, exact terminal/inactive/root checks, independent B-body verification,
durable object-first manifest publication, per-file crash recovery/raw rollback,
metadata retention, backup dependency graph/closure verification and bounded growth
observations. No new background producer, timer, GC or automatic conversion.

45 focused tests plus eight retained fence regressions pass. Real metadata audit:
35,341 logs, 113,194,307,584 allocated log bytes, 3,187 closed/inactive candidates.
Four closed/inactive sample files are prepared; legacy file deferred. Neither
inventory nor a prepared list establishes custody. Six-file 812.1 MiB recovery
potential remains a sample measurement; zero production bytes reclaimed.

Staging's completed owner review found old protected-reader routing on5650:
main-backend-only conversion is unsafe. Current B source-version/normal recall
proof, reader-aware fallback/current-data rehearsal, actual source-pinned owner
adapter and compatible artifacts remain absent. Nightly is commissioning its own
tracker/delivery/job; shared planning question is pending, not acceptance. Disk
owner's guarded preservation recheck is separate; no original retirement cleared.
SSD ~1.9 GiB is below the retained 3 GiB build floor. Local full check/lint stop at
missing Node tools; no bulk install/build bypass. Production is NOT READY.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).

## Production execution resumed

User explicitly requests completion through verified production recovery. Latest
metadata observation: 35,415 raw logs / 114,327,764,992 allocated bytes; 3,221 closed
logs in inactive sessions / 84,557,012,508 logical bytes qualify for finite batch
preparation. Sixty-six bounded selections are recorded privately, beginning with
the four unchanged sample sources. This is no saving estimate or writer custody.
Legacy, active, pending and damaged captures remain preserved and excluded.

Both hosted workflows passed on source `087319cc4`. Rebase onto current staging
`ee2efee4d` preserves all deduplication code bytes and upstream continuity. Latest
SSD observation is 7.5 GiB free; the earlier 1.9 GiB blocker is historical. Existing
Vibe owner execution `62230d3f` owns preparation of both readers, rollback and real
deployment admission. Nightly execution `9fa136d4` retains sole backup production
and its in-progress composed restore. No duplicate producer, source retirement or
service switch has occurred. Current per-batch state and remaining requirements:
`PRODUCTION_EXECUTION_20261104.private.json` under the evidence root.
