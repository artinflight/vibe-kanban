# Overnight backup qualification

Nightly is a separate worker, not a Vibe backend restart. The existing calendar
defines the Toronto overnight window as 02:00–10:00. Scheduling remains off until
an actual complete incremental backup and composed restore fit that window.
An initial retained backlog, a throughput estimate, component tests or separate
eight-hour phase limits do not establish that result. Cold commissioning and
ordinary nightly deltas must be reported separately.

## Measured overhead and correction — October 27

The retained native health receipt measured three successful full SMART/PHY
queries at 1.172, 1.343 and 1.406 seconds. Earlier observations exceeded the
wrapper's fifteen-second patience. A timeout establishes an unavailable
observation, not a reported drive fault. The cause of those slow calls remains
unproven. Neither physical OOM nor drive damage is inferred.

The old native transports each requested full health every five seconds. The
new explicit `native_health_poll_seconds=60` configuration separates expensive
health queries from cheap controls; the default remains five for old packages.
This is an engineering polling interval, not a user-imposed safety threshold.
At 600 seconds of active guard calls the executable guard fixture performs ten
full polls instead of 120. The original five-second STOP/MM/kernel-identity
observation bound remains; actual free capacity is checked on every guard call.
Full fresh health and full destination identity remain mandatory at admission
and final completion. Separate cadence requires kernel identity continuity.
There is no persistent/shared health-result cache. The existing finite native
health mutex serializes observations; slow or unavailable due observations
block I/O. SMART failure, changed counters/identity, STOP and access errors still
fail closed. Only the existing one finite query-timeout requalification applies.

Successful observations emit cumulative query count and duration; unavailable
observations explicitly report `reported_drive_fault=false` and permit no I/O.
Control telemetry records operation counts, total/max roundtrip wait and no SQL
text/parameters. Source and worker packages must be pinned together before use.

New object acceptance already restores into a separate RAM inode, reopens and
hashes it. Its verified bytes now feed the ordered full-file hash immediately,
avoiding a second identical recall/reopen. Previously accepted objects still
receive an actual readback. Exact prefix ordering, whole-file SHA/length, Linux
metadata, native durable object acknowledgement and atomic version-bound map
acceptance remain required. Interrupted map commits reuse completed objects.

In three actual isolated RAM protocol trials per version, a 12,288-byte file
with three chunks (one repeated) used seven outbound control frames instead of
eleven and three independent chunk reads instead of five. Median time was
50.793 ms versus 54.495 ms without artificial delay, and 202.683 ms versus
309.070 ms with an explicit 25 ms delay per outbound frame. The latter is a
latency model, **not** a measured production Desktop speedup. No Desktop B
payload or production reader was created for these fixtures.

## Required production acceptance

1. Preserve the existing producer, accepted map, objects and source epoch. Use
   an exact terminal/component boundary and existing leases for a serial
   source/config upgrade; never edit loaded packages or launch a second writer.
2. Record actual native health durations/counts, control operation wait,
   changed-name/byte counts, completed-point reuse and end-to-end elapsed time.
   Do not project the initial backlog as the ordinary nightly delta, or hide
   unfinished work behind a successful bounded phase.
3. Complete file, SQL, runtime/alias and immutable current-map acceptance. Run
   native proof closure and the normal leased composed reader, with independent
   hash, SQLite/schema and Linux metadata checks. Preserve original gaps and
   later carrier epochs. Reuse the accepted 162.70 GB restore and completed
   components; no repeated global census or cold copy is required.
4. Test unchanged-workspace reuse, interruption, Desktop-off/low-space recovery
   and the complete ordinary final-delta cycle under its real shared deadline.
   Whole-cycle wall time includes source delivery, query/health waiting and
   restore acceptance. A hypothetical sum or individually passing stages is
   insufficient.
5. Bind the tested installed worker/config and accepted whole-cycle proof to
   the calendar, then verify its next run. The legacy calendar targets a former
   supervisor and must not be enabled as this new integration on source tests.

Current progress, exact live owners and the pending baseline/service integration
are in [the handoff](HANDOFF.md). This document claims neither production adoption
of the performance changes nor overnight completion.
