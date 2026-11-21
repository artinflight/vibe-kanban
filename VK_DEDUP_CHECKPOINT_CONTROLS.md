# Dedup checkpoint controls — live November 21

The finite converter is running again under checkpoint pause/resume controls.
Operation6d4d022ab2f84d1ea72f39d6a6382d1c uses the same unit
`vk-online-dedup-bulk-20261119-v1.service`, PID1316160,
invocation3594484094cb4790885a9b4b7570da3f, attempt controlled1. Recheck these
identities before acting. Writer cutover remains complete; full deduplication is
not complete. No Vibe/backend/proxy restart occurred.

## What happened

Resume3 failed at11:36UTC November20 on a read-only systemd status query.
WakeWatch delivered batch8ae7dc66 once to the dedicated chat at11:54UTC; that
agent finished at12:02UTC without recovering the job because the recovery's
consumer inspection was permission-blocked. The watcher remained active, but an
already-delivered event did not create repeated paid response turns.

The November21 route avoids touching the blocked directory altogether. The old
empty `batch-0037` is neither moved, reused, deleted nor written. Its inode and
contents remain unchanged. A fresh private directory under the new controls
package is explicitly mapped to batch37. The original consumer scan and sealed
legacy conversion/reader/backup/custody code remain unchanged. The rejected
scan-removal and in-place-reuse proposals were not applied.

The completed batch36 was independently reconciled and finalized using its
existing recovery proofs and exclusive carrier leases. Counts are now37 batches,
122 files committed. The next batch has packed441,903,688 raw bytes across4 files;
packing is not conversion acceptance. Earlier receipts, backup epochs and the
failed November20 activation package are retained.

## Operator controls

- `pause` requests a hold after the current complete batch, including normal B
  restoration, original-byte checks, journal, staging retirement and commitment.
  It does not interrupt a write or force-release a lock. Existing next-batch
  preparation may finish before the hold.
- `paused` is acknowledged only after backup contexts close and their lease
  descriptors are absent from the worker cgroup. The dedup operation lock stays
  owned, preventing a second converter. Other backup owners use normal admission.
- `resume` continues the same finite selection without reconverting committed
  batches. Commands have retained UUIDs and sequence numbers; replaying an older
  command cannot override a newer one. A pause never expires automatically.
- Initial backup contention waits without pretending to make byte progress.
  Unexpected errors or uncertain partial work still require exact reconciliation.
- WakeWatch follows the dedicated chat, existing timer, incident ledger, settings
  and receipts. Pause requests, verified pauses, backup waits and failures remain
  distinct. Completed alert responses do not mean conversion was repaired.

Operation root:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/online-20261119-v1`.
Current package beneath it: `checkpoint-controls-20261121` (`PACKAGE` below).

```sh
python3 -B PACKAGE/source/checkpoint_control.py \
  --root PACKAGE --operation 6d4d022ab2f84d1ea72f39d6a6382d1c status
# pause/resume additionally require one retained --request-id UUID and --reason.
```

A request is not an acknowledgement. Read status and live process identity before
reporting a pause. Do not rerun the consumed activation. For future recovery use
the sealed handoff's batch_override mapping: batch37 lives in isolated staging,
while the original directory remains untouched. Other batches keep original paths.
The controls retain the same resource floors and one finite background job.

## Validation and limits

63 focused tests passed, plus the new isolated-retirement observer test. Real
fixtures exercise an open consumer of the untouched old directory, exact mapping,
partial-work/corruption refusal, pause/resume without replay and backup contention.
The isolated observer counts verified staging retirement and still exposes failure.

Production activation first acknowledged pause with released backup descriptors;
a single retained resume then advanced actual source-byte progress and packing.
The normal timer independently observed both pause and running states, no source
error, and the original8 delivered events with8 attempts. No synthetic wake was
sent. Main/protected serving identities and all existing watcher settings match.

Evidence in the current package: PRIOR_ATTEMPT_RECONCILIATION, PREPARATION,
HANDOFF, ACTIVE, RESUME_INTENT, RESUME_RECEIPT and LIVE_ACCEPTANCE private JSON.
Full conversion, archive-tree/current-SQL recovery closure, final ordinary-service
acceptance and net filesystem/growth accounting remain. Deferred cleanup stays
excluded and the native goal stays paused. Web formatting remains unavailable
because this worktree lacks Prettier; Rust formatting and Ops checks pass.
