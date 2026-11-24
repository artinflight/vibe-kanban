# Deduplication file-count repair

Status: isolated qualification passed; no packed manifests are installed live.
The speed/file-count objective remains unfinished. Original lossless conversion
acceptance is retained; it does not establish performance acceptance.

## Cause and measurement

The initial content-defined layout stores each unique 16–256 KiB piece as one
gzip file. The measured source tree grew from 38,791 to 1,065,426 regular files
while allocated size fell from 91,761,684,480 to 9,324,318,720 bytes. Full reads
open and decode each piece; metadata scans must visit every physical file.
This design reduced bytes but introduced a substantial metadata cost.

An isolated sample of five real histories (197,877,075 decoded bytes) contained
7,229 physical files. The first packed prototype used eight files, with exact
full-stream hashes preserved. Allocated bytes fell 59,072,512 to 42,692,608.
Three alternating warm-cache Python trials reduced summed median read time
5.1902 to 3.8651 seconds. Metadata walks dropped from 0.1372 to 0.000698 seconds.
These are same-filesystem sample results, not live/UI or cold-cache guarantees.
The unoptimized actual Rust reader showed approximately unchanged warm-cache
read time (49.53 versus 49.21 seconds); optimized qualification is separate.

## Compatible layout

VKLOGCAS2 manifests retain ordered chunk SHA-256 and decoded lengths, adding
an immutable pack hash table and bounded byte ranges. Existing gzip bytes are
copied into shared per-session packs without recompression. Default new packs
are 16 MiB to fit existing 24 MiB recovery carriers; readers accept at most
64 MiB per pack, 1,024 pack entries and 100,000 chunks per manifest. The first
benchmark used the earlier 64 MiB default. Default-size fixtures also pass.
Each reader keeps at most four pack descriptors open. Every returned chunk is
checked for gzip framing, decoded length and SHA-256; complete-file acceptance
requires EOF and the original full SHA-256. Pack full hashes are independently
checked during preparation and recovery. Prefix reads do not prove full EOF.
Raw logs and VKLOGCAS1 remain readable. Writers refuse append to either archive
format. Active/pending captures and settings remain untouched.

Python reconstruction, graph export/verification, normal recovery member paths,
closure inventory, readback version pins and accounting recognize both formats.
The old publication mutator explicitly refuses V2: merely teaching readers the
format must not allow publication without a qualified migration.

## Validation and remaining work

One hundred focused Python tests passed, including packed reconstruction through
the existing recovery contracts after fixture source files and staging carriers
were removed. These use isolated fixture stores, not actual Desktop B. Ten Rust
archive-reader tests passed. Twenty-four watcher tests passed, including dedup-only
checkpoint scope and a visible maintenance pause. Formatting passed for Rust;
the required whole-repo format command stops because Prettier is not installed.
Ops governance and whitespace validation passed after the documentation update.

The matched optimized main build is running from the sealed deployed source,
with only the three archive-reader files changed and an isolated probe added.
The existing shared target/build lease, offline isolation and resource guards
remain. No live reader is replaced by building it. Exact receipts live under
`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`.

Still required: finish both compatible serving builds and current-data fallback;
qualify forward packed conversion and an idempotent guarded backward migration;
verify actual normal-B restore of new packs and ordinary history/UI behavior;
then retire only proven unreferenced owned loose pieces, and remeasure net space
and performance including all staging. Preserve every accepted backup epoch and
unrelated/deferred cleanup. There is no new Nightly commissioning authorization.

## Maintenance and continuation

The saved daily conversion schedule is preserved but held during repair. A plain
stop was undone by mcp-boot-recovery at 22:09:41 UTC. A runtime mask could not
override the higher-precedence user unit. The final exact timer drop-in uses a
ConditionPathExists maintenance flag, which prevents the recovery service from
starting conversion while retaining the enabled calendar. It survives reboot.
The ineffective runtime mask was removed. Reconcile TIMER_MAINTENANCE_HOLD_ACCEPTED
before release; remove only the pinned owned drop-in and flag after qualification,
reload and start the same timer. Do not disable the host recovery service.

Reuse the existing WakeWatch source, timer, incident ledger, owner and executor
selection for one scripted build checkpoint. A successful build is not live
migration or objective completion. Never replay an existing STARTED/uncertain
launch. Do not add model polling, another watcher, another agent or a goal.

Live checkpoint: operation6cfd3d05308b431aa7e3a9a51d60b131, unit
`vk-dedup-packed-main-build-v1.service`, PID1551698, invocation
`e7def46cdf3c4033b393f56c3ad32a88`. Normal existing WakeWatch tick sees the
healthy exact build and maintenance hold, with no source/event errors. No new
delivery was requested. Reconcile current receipts; never relaunch this identity.

## Build deadline recovery

Wake b87e8bd4-7a8f-4c8e-b835-e98dd78c11de arrived once after the first build
hit its 45-minute deadline. It had passed all 10 archive tests in the optimized
profile and completed 689 server dependency artifacts with zero compiler errors;
the last artifact finished 21.2 seconds before termination. Unit failed/MainPID0,
original processes gone, lease available and frozen/live executable hashes intact.
BUILD_FAILURE_RECONCILED retains exact evidence; original logs remain immutable.

The current attempt is main-build-recovery1, same operation and shared target,
using original frozen overlays without changing mtimes. Its exact successful
reader-test proof is reused. The optimized probe and full-EOF comparison run
before completing the server build. A 60-minute finite cap replaces the inadequate
first cap; 600-second no-progress, memory/SSD/no-swap/CPU and ownership protections
remain. Unit vk-dedup-packed-main-build-recovery1.service, PID2109474, invocation
2b2f09983334496691cc5d1bc95d3c98. Existing WakeWatch package is now
checkpoint-monitor-recovery1; no new watcher, agent, target or deployment.

The optimized sample checkpoint passed during recovery: all five histories across
three groups reconstruct exactly to full EOF. Summed medians were 3.877284 seconds
loose and 3.768843 packed (2.8% lower, three alternating warm-cache trials).
This is a small read improvement, not evidence of a large live/UI speedup. The
file-count, metadata-walk and allocation gains remain the main measured benefits.
The server build is still running; normal existing watcher sees 3/4 checkpoints,
no source/event errors and the held daily timer. Final migration remains open.

## Main accepted; protected and fallback builds

Success wake cf383e6c-6cbf-4bc6-b2cd-bd8ac446986e was accepted once. Reconciliation
verified terminal unit/process, all pinned source/tool records, sealed server and
probe hashes, full-EOF results and unchanged live executable identities. Main
artifact SHA-256 is 4a14b76bc3f0ce85c702f099e901b89fe6cc962df3221ab476845a80d3d87957.
The build-info asset directory varies with the inspection environment; compiled
identity/safety fields match exactly. No live environment was changed.

A single compatibility-build-v1 script builds the protected reader and prior
native-166 fallback with V2 support, retaining each separately verified source
variant. Both 2,959-file base catalogs and the fallback native overlay match.
Only archive-reader modules and a probe change. Each variant runs reader tests,
builds its sealed server, then verifies full EOF on raw-reconstruction-equivalent
V1/V2 samples. This is build acceptance, not current-data/UI or actual B recovery.
The fallback retains its prior runtime capabilities, so automatic online conversion
must remain held when it is used. Unit vk-dedup-packed-compatibility-v1.service,
PID2330678, invocation87b62ce5c0d04583bbddd548286e903c. Same shared target and lease,
original resource guards, 600-second progress guard, 90-minute finite pair limit.
Existing WakeWatch uses checkpoint-monitor-compatibility1; no new watcher or agent.

The normal existing watcher tick accepted compatibility-build-v1 at1/6 after
protected archive tests passed, with no source/event errors and14 retained
batches/14attempts. This is current scripted progress, not deployment acceptance.
Rust formatting and ops/whitespace checks pass; full format still stops at the
pre-existing missing Prettier executable.
