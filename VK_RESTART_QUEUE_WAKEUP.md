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

This is a separate source follow-up to current staging. The active Git release
and nightly restore/schedule workspaces keep their files and operational ownership.
No live service, queue, configuration, backup, permission or schedule is changed.
