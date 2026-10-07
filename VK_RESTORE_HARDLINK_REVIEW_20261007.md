# Restore Hardlink Review: Confirmed Private Failure, No Evidence Of Production Loss

This is a focused investigation requested before archive retirement/readiness.
Production, source reader, sealed packages and all original archives are unchanged.
The separate overnight release remains pending. No archive retirement is approved.

## Reproduction

`scripts/deployment/probe_vk_restore_hardlinks.py` captures real tiny checkpoint/
delta tar archives through the current capture function, using private synthetic
source files and a process-local mock Desktop transport. It then runs the actual
restore function. No network/provider/service is used; every fixture is retained.
The probe returns nonzero when desired content or inode relationships fail.

Unmodified reader at6bd0b39e5:

| Case | Expected restored content | Actual | Result |
| --- | --- | --- | --- |
| No replacement | A=old, B=old, linked | Same | Pass |
| Atomic replacement of A | A=new, B=old, separate | Both=new, linked | FAIL |
| Atomic replacement of B | A=old, B=new, separate | Both=new, linked | FAIL |
| Both explicitly captured, linked | Both=new, linked | Same | Pass |

In both failure cases `restore_chain` itself reports `passed: true`. The private
source remains correct. This proves a restore correctness bug, not production
data loss. The failing operations already exist in PR142 baseline528282d00:
`target.open("wb")` overwrites an inode previously shared by `os.link`.
PR149 changed surrounding streaming code but did not introduce that combination.

Receipts under `/mnt/vk-storage/vk-hardlink-review-20261007/`:
- `current-reader/probe-result.json`: two failures, two controls pass; exit1.
- `prototype-reader/probe-result.json`: four pass under the private prototype.
- `member-audit.json`: authenticated read-only real archive inventory scope.
- `review.json`: evidence hashes, baseline provenance, current space and guards.

Reader SHA256 remains
`06eaaa3d56f2d2b0bde820b3281fed72c4d163f97f17bf9cf9d2516930627e46`.
The old176-test suite omitted this case; its pass is not complete restore
correctness evidence. Do not hide this new failure in a blanket acceptance claim.

## Real archive scope

`audit_vk_hardlink_members.py` verified every retained member-index checksum
against its completed full-stream audit receipt, the original archive identity,
descriptor checksums and all six current head references. It inspected27indexes:
601905 regular members,82651directories,2752symbolic links, **zero tar hardlinks**.
Symbolic links are not hardlinks and the current reader retains their metadata
without making routes back to production. With a required fresh empty destination,
these chains cannot create the persisted hardlink needed for this specific bug.

This rules out this mechanism in the audited27, not every possible restore bug.
No full filesystem restore was performed, no archive payload reread was needed,
and no actual user-data loss is demonstrated. Keep originals and historical
incident limitations; do not infer deletion clearance from zero hardlinks.

## Minimal fix recommendation

After validating the private restore path, detach the regular-file destination
from any existing shared inode **before** opening it for overwrite; write the
replacement to its own inode and then apply the archived mode. Do not unlink
the other names. Keep explicit hardlink entries in each archive authoritative.
Avoid detaching after opening `wb`, because truncation has already happened.
Review the SQLite destination `copy2` path for the same inode-replacement rule;
that analogous path was not independently reproduced in this investigation.

The process-local prototype intercepts only `wb` on the private restored files,
unlinks the overwritten name when its link count exceeds1, and passes all four
cases. It is a narrow proof of the recommendation, NOT an adopted source fix.
Before adopting, add these assertions to normal regression selection and cover
same-archive relinking, member modes, missing/unsafe paths and failure handling.
Account separately for capture completeness when shared source inodes are edited
in place: the prototype only proves the represented archive cases above.
Do not modify an existing sealed package. Publish/package a reviewed corrected
reader and rerun the focused package check before general recovery readiness.

## Storage remains a separate blocker

Earlier figures remain historical:82.423GiB conditional free after all27 local
retirements, only0.437GiB beyond historical restore +2GiB floor +1GiB growth.
Fresh full capture still had an11.791GiB conservative gap BEFORE rehearsal.
No retirement occurred. The latest receipt has17.939GiB free and ongoing host
growth reduced those conditional figures to82.366GiB and0.381GiB respectively.

With all originals retained, the largest historical low-peak restore estimate
is84,809,768,960bytes; with floor/growth it requires88,030,994,432bytes available.
At the receipt this needs **68,769,439,744 additional bytes (64.047GiB)**.
Fresh full capture's conservative no-compression estimate is97,940,190,668bytes;
with floor/growth it needs101,161,416,140bytes, or **81,899,861,452 additional
bytes (76.275GiB)** at the receipt, before any simultaneous rehearsal requirement.
Even conditional retirement of all27 still leaves12,721,133,004bytes (11.847GiB)
of conservative fresh-capture gap. These are planning estimates, not measured
combined peaks or promises that compression will solve the shortage.

The existing reader enforces BOTH confirmed-mounted `/mnt/vk-storage` and a new
destination below `Path(result['folder']).parent.parent.resolve()`. For these
six heads the only allowed parent roots are:

```text
/mnt/vk-storage/vk-autoswitch-scope-release-20261001/backups
/mnt/vk-storage/vk-blue-autoswitch-v2-20261001/backups
/mnt/vk-storage/vk-green-reprepare-20261005/backups
```

Fresh read-only guard probes for all six heads rejected an unrelated SSD task
directory and a system-disk `/tmp` path before creating either. The named roots
are currently on mounted `/dev/sdb1`, ext4. Desktop B stores archives; it is NOT
a validated Linux extraction filesystem for this tool. More free space somewhere
else is not a usable solution by itself. Required capacity must be available
under these guarded roots, or an explicitly approved, reviewed/tested recovery
path redesign must establish the alternative filesystem and reference semantics.
No mount, security or path-guard changes are authorized or performed here.
