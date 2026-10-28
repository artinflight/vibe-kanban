# Overnight backup qualification

Nightly is a separate worker, not a Vibe backend restart. The owner-corrected recurring
window is **22:00–04:00 America/Toronto with a hard stop at04:00**. Scheduling remains off until
an actual complete incremental backup and composed restore fit that window.
An initial retained backlog, a throughput estimate, component tests or separate
historical eight-hour phase limits do not establish that result. Cold commissioning and
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
are in [the handoff](HANDOFF.md). The optimized file continuation is now installed
and advancing; whole-backup and overnight completion remain unverified.

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

## Actual optimized handover — October 27, 18:42 EDT

The owner requested a controlled checkpoint/resume. The old file worker stopped
on an actual SQLite lock in its progress-status upsert before any requested
signal was sent. Its queued SQL/runtime controllers correctly stopped on that
failed predecessor. A concurrent checkpoint read may have contributed; the
observations do not establish causation. This was neither a drive-failure report
nor loss of completed backup bytes. The corrected upsert retries only the same
idempotent metadata operation within the existing finite contention allowance,
retaining actual host/native/STOP controls. It never retries a body capture.

All old controllers were verified terminal, with empty cgroups. The successor
actually acquired both the inherited MCP writer lease and native B object-store
lease before launch. A normal independent B reopen passed map `quick_check`,
retained all 14,594 file-acceptance rows and authenticated the exact selected
journal input. No immutable baseline or completed body was recopied. The new
controller resumes that qualified input rather than enrolling a fresh suffix;
later source events remain durably tracked for subsequent delta consumption.
The original absolute file and dependent waiting deadlines remain unchanged.

The file, SQL and runtime successor packages pin source `539e0280c`; 224 focused
tests pass, including actual native SQLite reader contention/STOP, interrupted
file reuse, exact retained-input reopening, memory-streamed normal consumer and
whole-cycle publication after independent restore. Actual command lines and
config/source hashes bind the new loaded packages. Production file progress
contains the new control-roundtrip and independent-readback telemetry. In one
80.8-second mixed-file interval it added 89 files, read 404,058 source bytes and
sent 154,637 encoded bytes to B. This is observed progress, not a supported ETA,
a same-work before/after speed comparison or overnight acceptance.

The B-resident whole-cycle ledger preserves original deadlines and authenticated
phase receipts across interruption. Fixed serial integration completes the
recorded file delta dirtied by SQL selection without chasing another live global
suffix. An accepted pointer advances transactionally only after a matching normal
leased consumer result. The fixed existing WSL route checks its registered B
placement and streams pinned consumer code/packet in memory to UID1000. These
whole-cycle helpers have isolated native-protocol integration evidence; actual
complete current-set execution and operational calendar adoption remain open.


## Owner-corrected hard stop and executable calendar — October27

The22:00 evening is the run identity until04:00 the next day; midnight and the
repeated DST hour cannot create another run. Normal nights have six elapsed
hours, spring-forward five and fall-back seven, always ending at local04:00.
Tonight's target is04:00EDT October28/08:00UTC. It is not an accepted cutover
baseline until file, SQL, runtime and normal composed readback actually pass.

The fixed calendar invokes only `vk_nightly_service.py` with the authenticated
configuration, evening and absolute hard deadline. A monotonic cap prevents a
backward clock correction extending a run. Graceful owned-group termination
starts inside the window and escalates only for that newly launched owned group;
there is no extra payload grace after04:00. Native B guards cap their ownership,
identity and SMART waits to the same remaining time, check again after a slow
query and refuse further operations/requalification at expiry. The normal reader
also checks the absolute deadline. Already-issued kernel IO can finish during
cleanup; it does not authorize another operation or late baseline acceptance.

Completed atomic objects and independently reopened B ledger phases remain.
Unaccepted partials are preserved and cannot become an accepted baseline. A
late success is recorded as window-stopped, never a completed night. The current
accepted pointer stays intact. Each evening has a deterministic new SQL cohort;
retrying it reopens the original predecessor/binding and never resets its clock.
Other activity retains genuine capacity/memory/access/identity/STOP controls and
the existing shared writer lease; an occupied producer causes deferral, not a
foreign stop. Daytime pulses do not admit backup work.

Actual tests cover both DST transitions, midnight duplicate exclusion,04:00
refusal, real owned child stop with completed output preserved and an unrelated
fixture child left alive, clock rollback, slow native query expiry, exact terminal
component reuse, actual native B-protocol phase retention and publication refusal
at04:00. They are RAM fixtures, not tonight's complete production restore proof.

The service can authenticate older immutable package DATA without executing it,
then use the new independently pinned finishing implementation. It waits only
for exact original component identities and rejects failed, missing or replaced
units. The composed consumer holds the actual native object/capture lease and
must pass final fresh B health before its result can advance the pointer.
The41 newer v8i file components use their actual immutable catalog layout and
full archive/record/member bindings;206 older definitions remain independently
reusable. No catalog conversion or archive recopy is needed.

Scheduling remains OFF. Exact installed complete service/config, current full
restore and an actual ordinary overnight cycle remain commissioning gates.


The current waiting SQL5/runtime4 controllers were proven zero-payload and
childless, closed normally19:49:30, and replaced serially with SQL6/runtime5 from
tested source`b732a1ec6`. The active fileV8 PID2494862 was never signalled. The
replacement units' original cohort/component bindings and caps were rechecked;
top/native08:00UTC (04:00EDT) guards and actual systemd termination budgets agree.
This is the current commissioning chain, not proof of a recurring nightly cycle.

The existing normal B-backed guest verified all12candidate provider roots under
UID/GID1000. Twelve new explicit reader gates now live outside the accepted tree
under Bcontrols, with actual kernel exclusive/shared-lock refusal checks. The
162.70GB restored tree and all archive bytes were unchanged. Those gates coordinate
readers; they never substitute for the real MCP/native body lanes. Successful
transient-unit collection is handled by former-process identity plus actual
native leases and independently reopened B terminal receipts, not invented unit
success. The current file/SQL/runtime results and composed restore remain needed.
