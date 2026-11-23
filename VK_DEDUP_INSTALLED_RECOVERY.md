# Installed-batch recovery — November23,2026

Wake64e99dc4-6719-4c10-9bea-f9455d67930d reported a real terminal failure of
operation6d4d022ab2f84d1ea72f39d6a6382d1c, attempt recovery1. The completed prefix
was161 batches/1,317 logs; batch161's15 additional logs were fully installed.
Its production-reader EOF and original/graph/control recovery proofs were present.
No staging-retirement plan or deletion had started, and no next batch was prepared.

All163 journals,1,332 installed manifests and capture sidecars,77 source pins,
and both live reader hashes/mounts/protocol/settings were independently checked.
The old converter was dead; main writer70372 and protected reader2573735 retained
their qualified identities. The isolated batch37 mapping was preserved.

## Cause and conservative correction

All5,358 staging objects and their primary copies decoded to the expected content
hash and length.2,962 had different valid gzip representations (21,099,250 staged
compressed bytes). Local packing can encode logical chunks differently from an
existing primary object. Retirement required identical compressed bytes and
correctly refused to delete copies it could not regenerate exactly from primary.

`fast_retirement.py` now retains those alternate representations, records their
exact identities/hashes and allocated blocks, and retires only physically identical
copies. Corrupt content, changed ownership/inodes, multiple links, open consumers,
lost custody and failed directory flushes still refuse deletion. Primary objects
and all B epochs remain intact. A retained-only batch earns no deletion progress
in the watcher. Final net-space accounting must include these retained copies.

## One-shot recovery contract

`installed_checkpoint_recovery.py` accepts only this exact failure boundary: a
verified complete installed journal, unchanged manifests/sidecars and prior proofs,
no retirement/finalization evidence, no later preparation, and the exact dead old
controller. It verifies the entire committed prefix under the existing production
ownership lock before recovery. A durable attempt directory forbids automatic retry.

Recovery reopens the original B epochs, restores every archive dependency and
original log with Linux metadata, reruns the production reader to EOF, and verifies
the retained dynamic control checkpoint through normal B restore. It preserves
all original journal/proof files and the original before-allocation measurement.
Only then may it retire identical staged objects and qualified duplicate carriers,
write the missing after-accounting/result, and append the single missing commit.
It never calls conversion, preparation, or remote dispatch. Any uncertain failure
requires inspection of its retained attempt and exact paths before further action.

The finite controller's later activation requires the finalized-tail proof and
its exact checkpoint/failure binding. It starts paused and uses one retained resume
request. The old failure, control package and all backup epochs remain available.
The previously returned Laptop batch162 job a78d3ba8-5210-4159-a1d8-137d291c5a24
is adopted without redispatch; the Desktop preparer's disabled state is preserved.
Resource limits, selected settings, serving processes and other owners stay intact.

## Evidence and limits

Evidence lives beneath the operation's `checkpoint-controls-20261123-recovery`:
RECOVERY_PREPARATION, installed-recovery/ATTEMPT and subsequent reopen/result
receipts, source pins and QUALIFICATION.txt. The dedicated chat evidence also
retains FAILURE_64e99dc4_OBJECT_DIAGNOSIS and FAILURE_64e99dc4_ALL_JOURNALS.
An attempt is not success: inspect the actual result and current unit before acting.

The consolidated suite ran110 tests:108 passed;2 existing optional Rust-probe
cases were skipped. Coverage includes corrupt/incomplete/changed tail rejection,
unchanged before-accounting and epochs, failed B reopen before retirement,
physical duplicate versus alternate encoding disposition, real kernel consumer
leases, crash/flush behavior, strict activation, disabled-host preservation,
completed-job adoption, checkpoint controls and truthful monitoring.
Required format passed Rust and stopped at missing Prettier; no web code changed.

Finite backlog completion and full acceptance remain separate. The final archive
and current-SQL/software/frontend closure, ordinary desktop/mobile/history/review/
settings/queue checks, net allocated/filesystem accounting including staging, and
growth/restore acceptance remain pending. Nightly scheduling remains off until its
authorized prerequisites pass. Deferred workspace/archive cleanup remains excluded.

## Production result

Recovery completed and batch161 is committed:162 batches/1,332 logs,1,334 resolved
files including2 individually nonbeneficial exclusions.2,396 identical staging
copies retired;2,962 alternate copies remain (27,607,040 allocated bytes). The
batch's494,219,264-byte live-log allocation reduction spans its original conversion
window; it is not new net filesystem recovery attributable to this alert response.

Recovery2 PID3798264/invocation7de4161820194cb68dacb2976e760e9c acknowledged pause,
then resumed once with UUID6a5af7ca-ed37-4b8b-84fb-26a213d3eb6f. Laptop162 was
imported and validated without redispatch; its next archive carrier checkpoint
verified. The normal watcher reports RUNNING with10 deliveries/10 attempts and
no source/event error. Desktop's unchanged Rainmeter PID128024 displays RUNNING
and1,334 resolved files. Ordinary history and the public status route returned200.
Serving identities and other selected watcher settings remain unchanged.
LIVE_ACCEPTANCE, DESKTOP_HUD and ORDINARY_READS retain these bounded checks.
Full conversion and full-objective validation remain pending.
