# Completed response versus recovered storage

A successful agent turn does not prove storage recovery. Previously, the disk
client kept an unresolved incident attached to a completed batch indefinitely.
Phone reminders continued, but that incident could not wake its owner again.

The existing disk client supports `rearm_completed_incidents: true` in its private
configuration. Other consumers keep their existing behavior unless opted in.
This correction reuses the existing timer, owner, incident ledger and transport;
it adds no service, scheduler, model loop, access grant or cleanup authority.

Reassessment requires all of the following:

- An independently reconciled `execution_completed` receipt for the exact batch.
- Fresh same-volume observations still below the existing dispatch threshold.
- The assigned owner, its jobs, queue and custody are idle and known.
- The existing 30-minute cooldown, measured from confirmed completion, has elapsed.
- No dispatching, accepted or uncertain batch is outstanding.

The old batch and its attempt/receipt tombstones remain intact. Only the open
incident becomes pending for a **new** response batch; an old request is never
resent. Normal fresh transport/configuration, native capacity/budget, ownership
and per-action approval checks still run. Failed or killed turns are not silently
restarted. Missing completion evidence or a clock regression holds reassessment.
Recovery thresholds, physical floors and cleanup permissions are unchanged.

While waiting, status distinguishes `unresolved_incident_owner_busy`,
`unresolved_incident_cooldown` and `unresolved_incident_completion_unverified`
instead of implying the disk is healthy. A wake does not guarantee a reclaimable
batch exists, authorize unique-data removal, or resolve an outstanding approval.

Validation uses the stdlib watcher suite, including terminal/unrecovered
reassessment, new-batch identity, no duplicates, busy/queued/job holds, missing or
future receipts, stale/changed mounts, threshold boundaries and recovered cases.
A bounded RAM copy of the real ledger can prove eligibility without changing
production receipts or submitting a synthetic model turn. Hot-apply under the
existing incident lock, retain private preimages and observe a normal timer tick.
Never forge idle owner state to obtain a live-test wake while that owner is active.
