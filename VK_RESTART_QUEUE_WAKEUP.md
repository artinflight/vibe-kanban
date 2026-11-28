# Restart preparation and queued-work wakeup

Preparation remains online. Neither a verified backup, an empty queue observation
nor this worker authorizes a cutover or blocks new user work. Staging retains the
actual ownership/writer fence, fresh final catch-up and explicit cutover approval.
The nightly owner supplies the one verified independent baseline and its journal
contract; this change creates no additional backup or scheduled job.

Capacity-queued messages previously depended on another execution's exit monitor
to retry. An idle backend after restart, or capacity released by another owner,
may have no such completion event. The existing background worker now retries
one capacity-queued batch on its five-second cadence, including when Git
publication scheduling is disabled. The checkpoint itself still runs only under
its existing setting. Missed timer ticks are skipped rather than replayed in a
burst. Shutdown stops future retries.

The retry calls the existing consumer and executor admission path. It grants no
extra slot and does not change profiles, routing, Git publication authority,
observation gates or paused goals. Ordinary same-session queued messages retain
their completion-driven behavior. Restored uncertain dispatches and disabled-mode
recovery holds remain held; automatic replay would risk duplicate user work.
Five seconds is a retry cadence, not an execution-start guarantee while capacity,
ownership, Git history or other existing gates block the request.

The new tests run the actual background loop against disposable SQLite state
without a completion event, verify a later capacity-queue arrival, leave ordinary
messages untouched, stop on shutdown and preserve an uncertain restored batch.
They intentionally use missing fixture sessions so no model or agent launches.
They prove wakeup/recovery behavior, not successful production agent continuation.
Hosted compiled tests and an isolated full dispatch/start/readback against the
resulting exact binary remain required before claiming end-to-end adoption.

## Existing preparation runner integration

The already-developed Staging preparation improvements now replace the older
checked-in runner: bounded fresh queue inventory, immediate cache-owner refusal,
required code/config pins, sealed-source verification, corruption-specific cache
invalidation and direct binding to accepted candidate/rollback artifacts. Reuse
still verifies source, artifacts and logs; volatile checks stay fresh. The default
backend build recipe is refused in favor of the established explicit isolated
plan. No new compiler route, command broker or production driver is introduced.

The preparation tests use tiny isolated files on the mounted SSD and loopback
fixtures, never production, a real compiler or model calls. Their mounted-storage
guard remains enforced. The new Rust wakeup cases also run under the existing
hosted scheduling-enabled suite.

Timing distinguishes publication from actual queued-work start. A hash-bound
actor receipt may include `queued_work_resume` with `verified: true`, the exact
`session_id`, `execution_id` and timezone-qualified `started_at`. The release
owner must obtain those from real dispatch/readback; this tool only validates
and consumes that already trusted receipt. The timestamp must follow publication
and cannot be in the future. Without that evidence, the runner reports publication
timing, leaves work-resumed timing unset and cannot claim the ten-minute target.
An empty queue does not require launching unwanted work to manufacture a metric.
The original FIX READY time still includes queue wait, build and validation.

This is a separate source follow-up to current staging. The active Git release
and nightly restore/schedule workspaces keep their files and operational ownership.
No live service, queue, configuration, backup, permission or schedule is changed.
