# Running Green Standby: Not Ready

## September 12 Paused-Green Preparation

The operator now explicitly permits pausing Green and resuming the same process
for cutback. The responsive-standby question below is resolved. Production Green
has not been paused or stopped during this preparation.

Full isolated rehearsal004206 passed with a VK-only routing gate, same Green PID
freeze/thaw, original-thread continuity both ways, Turn Steer versus Stop, goals,
saved messages and attachments retained after Blue writes. It also changes
configuration and executor profiles on Blue and refreshes Green's cached values
before routing back. Browser tests explicitly reload desktop/mobile pages.
Measured private window30.83s; rollback with continuation5.52s. These measurements
are not a guarantee for the forthcoming production boundary.

The actual `vibe.local` API route and MCP HTTPS3443 entrypoint now pass through
gateway4720 to unchanged Green4511. Desktop/mobile saved messages and WebSockets
passed; Green remained PID2669659. Original routing configs and gateway tools
are verified on Desktop. No production Blue activation has occurred.

The independent paused controller forbids Green stop/restart, gates requests,
drains its own execution via the existing API, freezes Green, verifies a stable
current backup, then starts separate-port Blue on the same data. Recovery uses
latest config/profiles and refuses automatic rollback across new active work.
Six controller decision tests and gateway tests pass. Release build and final
candidate/controller acceptance remain pending; readiness remains withdrawn.

Evidence and current pickup: `/mnt/vk-storage/vk-cutover-20260911/PROGRESS.md`.

The operator requires Green to remain running as the fallback while Blue serves
production. The stop/start controller does not implement that requirement and
must not be retried. Production Green remained active during this investigation.

## Verified Constraints

- Production Green and the prepared production Blue unit both bind4511/4512.
  The Blue unit explicitly Conflicts with Green. Starting it stops Green.
  The existing isolated Blue4641 preview is a different, disposable database.
- LocalDeployment loads and caches configuration and writes it during startup.
  Configuration requests return cached state; updates save a complete config.
  Two running processes do not automatically refresh one another's caches.
- Background cleanup, execution monitoring and queues exist outside HTTP routes.
  A proxy-only switch is not an exclusive-writer mechanism.
- The inspected runtime has no supported hot standby/demotion/promotion mode.
  Simply suspending it may retain SQLite transactions/locks and stale caches;
  that is not a verified same-latest-data rollback design.
- The currently running Green binary cannot gain a new standby lifecycle just
  by changing a service file or frontend address. No production changes were
  made to pretend otherwise.

## Required Outcome Before Readiness

Both generations need independent listeners and a verified exclusive active
owner for requests, background writers and execution launch. Demotion must drain
work and release transactions; promotion must refresh current persistent state,
including configuration, queues and execution ownership. Tests must cover Blue
writes followed by return to Green, crash recovery, existing connections and
external native-home consumers. The same latest data remains authoritative.

The operator has chosen a loaded but paused Green. The earlier stop/start design
is not approved for reuse. Any
proposal requiring Green replacement/restart must be explicitly disclosed and
approved, not hidden inside a claimed frontend switch.

## Repeated Recovery Text

Read-only DB evidence shows recent replies completed with exit0 and nonempty
summaries, but without a per-turn native-session field. The recovery query used
that field as an extra acknowledgement requirement, so it kept selecting old
interrupted prompts after genuinely completed replies. Stored interrupted prompts
already contain older recovery wrappers, explaining nested repetition.

The narrow source fix separates the recovery acknowledgement boundary from
native resume-anchor selection. A completed, nondropped, exit0 turn with a
nonempty summary acknowledges earlier recovery. New interruptions still appear;
blank summaries, nonzero exits and dropped turns do not clear recovery. Native
resume-anchor selection is unchanged. No historical DB records are rewritten.
This is a source fix, not a live Green repair; deployment remains pending.
