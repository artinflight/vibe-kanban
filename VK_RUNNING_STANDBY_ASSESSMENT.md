# Running Green Standby: Not Ready

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

The remaining operator distinction is whether a loaded but paused Green is
acceptable or Green must remain responsive. Neither alternative is certified.
No new production interruption is authorized by this preparation task. Any
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
