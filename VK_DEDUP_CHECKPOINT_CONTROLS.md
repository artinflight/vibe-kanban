# Dedup checkpoint controls — prepared November 20

The operator requested better control after the frontend recovery mirror was
blocked by historical conversion. Pause/resume/status controls are prepared and
59 tests pass, but **the controls are not active**.

While controls were being prepared, resume3 failed naturally at11:36UTC during a
read-only systemd identity query. Both backup locks are free. No signal, job stop,
forced unlock or backend restart was performed. The118 committed logs and4 fully
installed tail logs remain intact; the tail still needs final staging retirement
and commitment. The next batch directory is completely empty.

The attempted paused activation failed before recovery or launch because the
consumer scan could not inspect `/proc/1119/cwd` (the same-user systemd manager).
Privileged inspection requires credentials unavailable to this agent. Automatic
approval review rejected removing the check and rejected an alternative that
would retain/reuse the empty directory; neither rejected edit executed. Original
source pins, watcher/settings, serving identities, journals and locks are unchanged.

`ACTIVATION_ATTEMPT`, `ACTIVATION_FAILURE.private.json` and
`FAILED_ACTIVATION_RECONCILED.private.json` retain the exact outcome. Do not retry
the consumed activation. Resolve the privileged consumer check or obtain explicit
approval for an alternative, then reconcile the attempt before proceeding.
The frontend owner can use normal backup admission now; its publication remains
separately owned. Finishing historical conversion is not a prerequisite for this
backup access.

## Intended behavior

- `pause` requests a hold after the current complete batch, including its normal
  B restore, original-byte checks, journal, staging retirement and committed
  record. It never interrupts a write. Existing next-batch preparation may finish
  before the hold.
- The worker reports `paused` only after closing its backup contexts and proving
  their lease descriptors are absent from its cgroup. It retains dedup operation
  ownership, so there is no second converter. Other owners can use normal backup
  admission while it is paused.
- `resume` continues the same finite selection from the verified completed
  prefix. Completed batches are not converted again. Commands have durable IDs;
  replaying an old command cannot override a later command. Nothing resumes
  automatically because time elapsed or the backup lock became free.
- Normal backup contention at either initial conversion lease waits safely.
  Unexpected errors, partial preparation, incomplete graph checkpoints and
  uncertain journals require explicit recovery; they are never blindly retried.
- WakeWatch and the existing progress page distinguish a requested pause,
  verified pause, backup wait and actual failure. Waiting is not progress. Dead
  owners, stale pause records, held backup descriptors and failures still alert.

## Prepared transition options (not performed)

For a still-running legacy worker, the old worker cannot consume a pause request. The prepared activation client
waits for its **existing controller admission lock** to close naturally. It takes
that normal lock without signals or forced unlocking. The old worker finishes
local retirement/commit and then refuses its next B admission before conversion.

Continuation is permitted only when the exact old process has exited with that
specific initial-admission error, all committed batches have complete recovery
and retirement records, their installed manifest identities/hashes still match,
and the next batch has no journal, result or archive checkpoint. An unrelated
failure does not qualify. Every historical receipt and backup epoch is retained.

The same converter unit then starts the controlled driver **paused**. Backend,
proxy, database, frontend and selected settings are untouched. The frontend owner
still owns its backup/publication approval and validation. That release must
finish its normal backup operation before dedup is explicitly resumed.

This is not a backend restart and does not require one. A backend restart, if
needed for another task, still belongs to the external managing agent.

## Package and activation boundary

Operation directory:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/online-20261119-v1`.
Package beneath it: `checkpoint-controls-20261120`.

`PREPARATION.private.json` pins the exact old process/unit, qualified legacy
sources, new control code, watcher destination, serving identities and unchanged
resource limits. `VALIDATION.private.json` records the tests and read-only live
prefix checks and the reconciled failed activation. The source verification command below
is read-only; it does not clear or retry the consumed activation:

```sh
python3 -B PACKAGE/source/activate_checkpoint_controls.py \
  --preparation PACKAGE/PREPARATION.private.json
```

The activation client uses `--activate` with a retained `--authorization-ref`.
The consumed failed attempt must be reconciled before any further activation.
Its wait is bounded to90minutes; recent completed batches took15–46minutes.
It never kills the old process on timeout. Any failed or uncertain activation
requires exact receipt/unit reconciliation, not re-invocation. No activation
command is scheduled or running now. The natural terminal failure has a separate
qualified recovery path; it encountered the inspection block described above.

After activation, commands use the existing private package:

```sh
python3 -B PACKAGE/source/checkpoint_control.py \
  --root PACKAGE --operation 6d4d022ab2f84d1ea72f39d6a6382d1c status
# pause/resume additionally require one retained --request-id UUID and --reason.
```

Status distinguishes requested intent from the worker's acknowledged state.
Check `ACTIVE.private.json`, the live process identity, actual released lease
custody and the next ordinary WakeWatch tick before declaring activation accepted.
The ordinary watcher reloads its new source/config without any service restart.

## Evidence and limits

The new control tests exercise real subprocess/kernel-lock handoff; durable
commands and interruption; actual driver orchestration with fixture conversion/
backup adapters; prefix corruption and partial-work refusal; pause/resume without
replay; and truthful monitoring. Existing reader-custody, packed-graph and staging
retirement tests also pass. Production prefix receipts and installed manifest
hashes were read independently; the current in-flight batch correctly refused
qualification for immediate takeover.

These are preparation and failed-activation reconciliation results. They do not claim a production handoff, a new
Desktop B round trip, completed historical conversion or final backup/UI/growth
acceptance. Deferred cleanup remains excluded. The native goal remains paused.
