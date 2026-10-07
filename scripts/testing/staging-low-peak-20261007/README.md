# SSD-only rehearsal preparation

These staging-owner tools are an **incomplete operational follow-up**, not a
replacement production controller. No live restart, capability exposure, routing
change, backup-chain retirement or database restore is performed by them.

## Source and execution

The backup library and regression suite remain pinned to PR142 commit
`528282d00c985230aad3033dc235d8cd943e5f4d` at
`/mnt/vk-storage/vk-green-reprepare-20261005/operational-source/scripts/deployment`.
Do not edit a consumed/sealed deployment package to install these helpers.

Run each command with a **new** output directory on the mounted SSD:

```bash
python3 -B scripts/testing/staging-low-peak-20261007/inventory.py --output /mnt/vk-storage/NEW-TASK/audit
python3 -B scripts/testing/staging-low-peak-20261007/reconcile_evidence.py --audit /mnt/vk-storage/NEW-TASK/audit
python3 -B scripts/testing/staging-low-peak-20261007/run_checks.py --output /mnt/vk-storage/NEW-TASK/checks
```

The inventory preserves the entire original journal report. It sizes changed
directory contents, every declared recovery-copy root, every moved destination,
all original databases and newly discovered databases. Existing snapshots, WALs,
uncompressed archive overhead and verification copies are counted. It does not
assume a compression ratio. Concurrent changes explicitly prevent this live
inventory from being represented as a final fenced upper bound. Missing sources,
unknown imports and historical recovery gaps are not cleared.

Move reconciliation is evidence classification, **not acceptance**. An incoming
recovery placement receipt and a current replacement Git registration explain
history; neither automatically overrides the pinned journal's source/watch rules.
The original source/destination events and all 14 protected roots remain intact.

## Phased retirement contract

`scratch_retirement.py` provides a guarded API, not a general cleanup command.
It is not yet wired into an executable full-workload rehearsal. Callbacks must
use the pinned archive member verifier, a fresh full Desktop hash/location
verification, and actual private-fixture consumer checks. Tests mock Desktop and
consumer callbacks explicitly; they do **not** prove a new Desktop round-trip.

Only the new private `handover-*` fixture's exclusively owned regular SQLite
copies can be selected. Paths through links, hardlinks, changed inventories,
unverified remote copies and replayed retirement are rejected. The archive,
manifest, runtime originals, incident receipts and full restore output survive.
Receipts record the exact allowlist before unlink and partial progress on failure.

The permitted phases are:

1. After checkpoint verification/delivery: retire only `verified-payload` SQLite
   duplicates, retaining original snapshot payloads and the archive.
2. After **all four** handover/cutback assertions: retire only the private capture
   payload SQLite copies. Preserve even the deliberately failed-delivery archive
   on Desktop before retiring its duplicates. Then run the unchanged complete
   Desktop recovery test, including every database and current held-goal state.

The next integration must retain source-fenced VK9b3f82538 candidate and its
matching compile-disabled v2 reader, CU95e7aea47, real frontend and all assertions.
Do not reuse the old full-workload adapter's historical incumbent binary or its
six-database incremental sample. The current inventory includes 68 databases:
all earlier 67 plus the candidate worktree's small development seed database.

`SpaceBudget` reserves at least 2 GiB free. `run_checks.py` samples free space and
task allocation every 100 ms, reserves another 256 MiB while tests run and stops
only its own test process group if that margin is lost. Other host writes are
not attributed to this task. Full rehearsal requires its own conservative
combined-phase budget and monitored execution, not the small test measurements.

## Remaining adoption gates

The full driver must call the guard at those exact completed phases, provide real
consumer/Desktop verification, bind fresh coverage and database manifests, and
pass an integration test preserving the four handover assertions and full restore.
This integration and the full-sized run remain blocked, not implicitly completed.
No sealed tool hash, original archive, production service or owner setting is
changed by publishing this code. Retain the 27 local backup-chain parents.

See `VK_LOW_PEAK_PREPARATION_20261007.md` for the current measurements, evidence,
specific unresolved moves and rollout hold.
