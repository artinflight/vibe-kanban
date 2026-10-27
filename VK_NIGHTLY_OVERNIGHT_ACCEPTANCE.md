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

## Executable restore integration and recovered dependency

`vk_nightly_finalize_current.finalize` now uses the normal native B protocol to
refuse unresolved map/journal states before making a checkpoint, independently
read back/accept the sealed image, build its typed descriptor and run complete
body-recipe proof closure against exact immutable catalogs. A required SQL cohort
comes from an independent normal reopen, with matching map/plan/scope and required
API selection. The returned candidate cannot publish an accepted baseline.

`vk_nightly_composed_consumer.py --packet-sha256 <full-digest>` reads the owner's
bounded JSON packet from stdin in the admitted B-backed Linux reader. The packet
binds the external scope/retirement/runtime/SQL contract, descriptor, actual
provider device/inode placements, existing leases, native content proof, catalogs,
selected readbacks, RAM demand and original absolute whole-cycle deadline. It
rejects root and mismatched UID/GID. It opens the normal leased complete reader,
hashes/opens the immutable index without copying it, independently restores the
required samples sequentially in tmpfs, and reports SQLite/schema, Linux metadata
and actual elapsed time. Missing leases, changed placements, low RAM, STOP or
expired deadlines fail closed; failed RAM outputs remain preserved. Replaying an
old packet cannot reset the whole-cycle deadline. The caller must retain the
existing native B identity/STOP/health/capacity admission and actual source pins;
the Linux entrypoint does not claim to establish physical B admission itself.

An actual isolated native-protocol fixture passes seal, independent metadata
readback, immutable content audit and this executable consumer together; replay
reuses its completed checkpoint. Separate real SQLite/API/protocol fixtures pass
SQL integrity/schema and lost-RAM layout recovery. These are component/integration
evidence, not production current-set or overnight acceptance.

Retained SQL layout recovery now paces its extra health RPCs at the same five
seconds as normal capture. Every-block host guards and native streamed-read
controls remain. One actual 8,192-byte retained API fixture (two chunks) used one
extra health RPC instead of four, with identical full SHA/SQLite integrity, zero
source API reads and zero new body payload. RAM elapsed times were about 48/52 ms;
no speedup or production timing is inferred from that noise.

The runtime V2 controller genuinely stopped while waiting at 17:33 EDT: its
one-hour capture timeout was incorrectly applied to its separately declared
sixteen-hour predecessor wait. The fixed controller uses the existing wait limit
while waiting, then resets only its original one-hour capture clock. Runtime V3
was admitted at 17:51 EDT after V2 was proven terminal; it preserves the same
prepared component, SQL predecessor, source epoch and original absolute wait/
unit deadlines. All memory/CPU/swap/access guards remain. File V6 and SQL V4 were
not stopped or replaced. This is recovery of a waiting dependency, not a second
capture or a claim of runtime/baseline completion.
