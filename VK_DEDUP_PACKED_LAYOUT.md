# Deduplication file-count repair

Status: isolated format/build and all11current-data stages accepted; live original restoration accepted; production packing independently accepted; normal-B recovery independently accepted; reader lifetime protection accepted; packed publication rehearsal accepted; production admission recovery running.
No packed manifests are installed live.
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


Current-data checkpoint preparation: both compatibility artifacts independently
accepted, with unchanged serving readers. Protected SHA65fbcb15ea6e006c5f2e66b0d94b9d464576c01bc8be52dbbafe98087b3c3073;
fallback SHAfcfe4d7fbaac25ee5763e5b6b9b930fe71b6068f0063851534525690180bbb02.
Each passed10reader tests and exact sample full-EOF checks. The separate existing
protected-history and native166 behavior remains in its respective artifact.
Fallback does not provide the current writer's mutation protocol; automatic
conversion must stay held while that fallback serves.

One finite current-data-v1 job now snapshots the actual current main and protected
DBs, checks all tables and later writes through candidate/fallback/return, exercises
packed histories through real HTTP APIs, compares protected replies/pagination,
settings/review/queues and frontend assets, and rejects corruption in a disposable
pack. Six closed histories are prepared on SSD; live sessions stay read-only.
Private network/PID/manager namespaces and disabled provider command prevent live
execution. No production migration or Desktop-B restore is implied by this test.
The same WakeWatch hook/ledger reports its next checkpoint; no model polling.


The first current-data rehearsal stopped in the existing-reader baseline because
its assertion disallowed normal startup cleanup of copied running executions.
Two rows changed only status and completion time; all identities, inputs, other
fields/tables and baseline main APIs were preserved. This was a test error before
packed-reader exercise. The failed evidence and snapshots remain retained.

The corrected audit, `scripts/deployment/check_rehearsal_orphans.py`, permits only
running→failed with a completion time inside the first startup interval and no
other field change. It requires identical schemas and execution identities and
exact equality for every other table. Every subsequent phase still compares all
tables exactly. Eight tests reject input/history changes, missing/extra rows,
incomplete orphan cleanup and invalid/out-of-window timestamps. One recovery
script takes fresh DB snapshots and reuses verified pack fixtures; the existing
WakeWatch reports results. This does not claim live deployment or full recovery.


Current-data replay failure (November25): one1,814,677-byte history rendered109
entries under the existing main reader and103 under the packed candidate, with
different reply hashes. Both logs reported raw MsgStore broadcast drops. Actual
compiled full-EOF reads of loose and packed originals have identical SHA-256;
storage integrity passed, but display integrity did not. The previously built
main/fallback packed binaries must not be deployed on that evidence.

The existing protected reader already uses bounded Codex replay input queues.
Slow normalization backpressures the reader; input failure cannot produce a
successful EOF. That preserved patch and its tests are now applied to main and
fallback, retaining all writer/native/private inputs. One serial script runs
replay input/output and archive tests, builds/seals both artifacts and verifies
full EOF. Protected already includes the mechanism and needs no repeat build.

After build acceptance, require exact current-data API results against the bounded
protected implementation on the same raw/loose fixtures, then repaired main on
loose/packed storage, fallback/return and protected histories. The demonstrated
lossy old-main response cannot certify complete expected history. Never remove
the affected history or ignore dropped-message errors to make the test pass.
Keep all-table/later-write/settings/queue, corruption and real recovery checks.


Replay-repair-build-v1 is independently accepted: main and fallback each pass
10input replay,8historical output and10archive tests; sealed binaries/probes and
full-EOF sample hashes match. Serving identities remain unchanged. Main artifact
SHAc4895660de59f1624205c1868301afaf0c1659189103230b274eb2e854330406, fallback
SHAc6362dd1c9b5285dec1413ba7ec0ed195369ae3f1dfaf915dfcd9ec3c482d290.

Current-data-repaired-v1 now runs11finite steps against fresh main/protected DB
copies, reusing verified pack fixtures. The existing bounded protected reader
supplies the same-data reference for main histories; repaired loose/packed,
fallback/return and protected cases must match exactly, including pagination.
Any broadcast-loss log fails the check. All tables/later writes/settings/review/
queues/frontend checks and3deliberate corruption rejections remain mandatory.
No live source or reader change, Nightly commissioning or final acceptance is
implied. Existing WakeWatch owns the next checkpoint.


Current-data-repaired-v1 exposed only a two-entry diagnostic-order race: both
readers return149and50entries with identical replies and no broadcast-loss logs.
A bounded four-start diagnostic reproduces two leading startup records exchanging
positions0/1; exact content multisets, all remaining order and metadata match.
Both failed original hashes match those reproduced permutations. Original tables,
later writes, snapshots and live/source identities remain verified intact.

The test helper now permits only the two independently pinned entry-body hashes
at indices0/1 for those two specific histories. Raw page hashes remain in receipts.
Everything else remains exact, including contents, duplicates, remaining indices,
pagination and error metadata. Eight tests reject broader changes, and all four
real diagnostic runs validate the narrow rule. No production code or artifact
changed. One current-data-repaired-v2 job runs the same11steps under WakeWatch;
full current-data/recovery and dedup acceptance remain open.


Current-data recovery dependency checkpoint — November25: all five main reader
transitions passed exact page/settings/table/later-write comparison. The protected
baseline then found18original capture dependencies absent while recovered-final
records remained. The serving reader reproduces refusal. Preserved independent
originals match historical and sidecar hashes exactly (16,713,100B); cause of
absence is unproven. This invalidates present retained-history acceptance.

current-data-originals-v1 uses only private read-only mounts of those18originals;
seven mount-plan tests cover neighbour preservation and refusal to shadow existing
data or follow symlinks/escaping paths. The same11phase rehearsal and existing
WakeWatch remain responsible. No live restore/packing/deployment yet. Following
success, restore only exact absent dependencies with create-only publication and
fresh owner/hash checks; verify all18normal API replies before final acceptance.
Include any restored allocation in final growth accounting. Recovery originals,
old epochs, missing-file evidence and deferred cleanup remain untouched.


November25 current-data acceptance: all11stages independently verified, including
protected6native+18retained histories, compatible fallback/return, original tables,
later writes, pagination/ordinary APIs/frontend and3corrupt-pack rejections. The
18originals were private read-only overlays; acceptance did not restore live data.

The create-only restoration ran separately as live-original-restore-recovery1.
It held protocol1mutation locks for each exact terminal execution, preserves both
current SQL bindings/settings/sidecars and refuses any existing destination. The
first attempt stopped before payload creation on saved0664permissions; preserved
copies were left untouched and18verified private0600SSD copies prepared. Additional
staging16,752,640B. Eight targeted tests pass. Success requires18restores plus all
36protected/public normal API reply checks with explicit incomplete-capture recovery
notices preserved; the independent acceptance below now verifies these results.
No new packed publication, reader cutover or full acceptance.


Original recovery independently accepted: all18exact original files and36protected/
public replies verified, SQL targets/settings/readers/backups preserved. The script
finished these steps before a final nonmutating memory-pressure guard refused; a
fresh read-only reconciliation accepted the actual result without replaying writes.
Restored allocation16,752,640B,parent delta4,096B,private staging16,752,640B. Source
absence cause remains unresolved. Both failed script receipts stay immutable.

One packed-production-preparation-v1 script now selects eligible closed terminal
V1archives, checks conservative SSD demand, prepares per-session packs, verifies
every packed log using the optimized production reader and records file/allocation
counts. Sources and sidecars stay unchanged; raw/incomplete/pending/unbound captures
are excluded. No live publication/retirement/reader cutover or normal-B acceptance
is implied. Existing WakeWatch owns completion/problems; no model polling.


November25 packing acceptance reconciles every selected source, sidecar and SQL
binding, all274 group receipts,580 complete pack hashes and3,639 production-reader
EOF results (92,399,255,974 decoded bytes). Selected physical files fall from
1,057,171 to4,219 in the prepared copy. Its6,768,685,056 allocated bytes include
549directories; the prior8,835,260,416 counts selected files only. Final live and
net filesystem figures remain pending. All raw/pending/incomplete captures stay.

One finite packed-normal-recovery-v1 job now uses the existing normal Desktop-B
owner to independently restore all4,219 files, both current SQL points, five
current/compatible binaries,1,465frontend files and recovery sources, then seals
the complete reconstruction index. Separate immutable intents/capture/restore
receipts prevent uncertain replay; six regressions pass. Bounded48MiB/64file
checkpoints use RAM, preserving SSD staging and all backup epochs. It does not
commission Nightly or publish/retire live archives. After recovery acceptance,
guarded migration/forward publication, live reader activation, ordinary behavior
and final staging-inclusive savings/count/performance checks remain required.


November25 normal-B acceptance:223 checkpoint triples and the root index reconcile
5,862real file restorations/7,504,774,098B, two consistent SQL points, five binaries
and1,465frontend files. Every prepared packed file has an exact normal restore proof.
No live publication or retirement has happened. Reuse unchanged packed proofs.

Reader lifetime correction: parsing previously closed the original manifest before
lazy chunks finished. Both archive readers now retain that descriptor until drop;
Linux build-info advertises executionLogArchiveReaderPinProtocol=1. Two real kernel
lease tests exercise a renamed/replaced manifest and verify that retirement remains
excluded until the old reader drops, including after full EOF. All12main archive
tests pass. Nine-step reader-pin-build-v1 builds allthree compatible variants using
the existing shared target and WakeWatch. New artifacts still need acceptance and
recovery coverage. Retirement must retain old manifest inodes and prove reader
release with exclusive leases, alongside remaining-reference and object guards.
No migration/publisher or live performance/file-count acceptance is implied.

November25 reader-pin build acceptance reconciles the exact terminal unit,
allthree binary/probe hashes,36archive tests and18actual full-EOF checks. This
adds runtime capability proof; it does not activate the readers.

`packed_publication.py` uses actual scoped writer locks and reader-process
qualification, create-only content-addressed packs, atomic manifest replacement,
original-inode hard links and durable replacement identities. Retirement refuses
unreleased lazy readers, open objects, other manifest references, unexpected
inodes/metadata and missing original pins. Durable safe-release evidence precedes
original unlink, so an interrupted release can be reconciled without guessing.
`packed_forward.py` prepares raw files directly into packs and reuses existing
session chunks; neither live nor staged loose-object fanout is required.
Fourteen focused tests cover those boundaries. The complete existing packed test
set passed before the last two recovery tests, which also pass. Recovery/consumer
adapters remain controller responsibilities; fixture callbacks cannot authorize
production. No automatic timer release or live migration has occurred.

The new12-stage finite rehearsal uses current SQL copies, allthree qualified
readers and a copied-session scoped publication under the actual isolated main
process. It deliberately interrupts publication and holds an old reader before
retirement, then checks API history, tables and ordinary routes. Existing
WakeWatch handles completion/problems. Its fixture recovery is not a new B proof.
Next: independently accept the rehearsal, integrate exact normal-B proof and
production ownership, cover only changed artifacts in B, prepare measured cutover,
then final current recovery/ordinary qualification and net space accounting.
Nightly commissioning and deferred cleanup remain excluded.

November25: PACKED_TRANSACTION_REHEARSAL_ACCEPTED independently reconciles all12
stages,11API/table phases,60/59original tables and9/4later-write sentinels. Three
actual isolated scoped transactions retire7,854copied loose objects after busy
reader/interruption checks; ordinary APIs remain identical. No live mutation.

Production integration adds exact immutable-checkpoint reads with no local-body
fallback, B-restored metadata/sidecar mapping, both SQL bindings, actual serving
root/database mounts and the qualified scoped writer/pinned-reader adapters.
Eleven tests pass. Preparation groups are storage-sharing units, not transaction
limits:13of274groups exceed64files/2GiB. They now split into311bounded transactions
while reusing the same580packs; no second packing pass or duplicate data.
The first read-only admission run stopped before B capture/mutation and is
independently reconciled. Its recovery job is a separate finite witnessed dispatch.

The current five-stage job prepares all311plans, protects the exact mapping,
three new reader binaries(330,824,784bytes) and tools, exercises actual normal-B
admission for three production groups, and seals a recovery index. New-control
input ceiling512MiB; unchanged4,219packed files retain their existing proof.
No current-SQL recapture or Nightly commissioning is performed in this stage.
Final controller/activation/live qualification/accounting remain open.


November25 admission recovery: the311-plan mapping is retained, with fresh
original-byte/metadata/sidecar/SQL checks and unchanged prepared-file versions.
The first stopped attempt held no remote backup context. The next restored the
map through actual normal B, then hit a lowercase software-checkpoint naming bug
before any software capture. Both failures are reconciled with zero uncertain
captures. The map checkpoint is reused read-only; no repeated data packing/backup.

A bounded five-minute availability check now precedes the single authoritative
backup lease acquisition. It preserves competing owners and refuses inode changes;
it never retries a recovery context or capture. Checkpoint names are validated
before opening that context. Four real-lock tests and eight checkpoint tests pass.
The single recovery3 job protects only new reader artifacts/tools and completes
actual B admission proof; existing WakeWatch handles its result. Live migration,
forward activation and final acceptance remain open.


November25 recovery3 is independently accepted:25checkpoint triples/94files,
341,068,615bytes restored,331,392,539new control bytes, three reader binaries and
three real B admission groups. All311plans/current source and owner bindings
reconcile. The completed map and unchanged packed data were reused, not recaptured.

The finite controller now journals a frozen selection under the existing lock
and refuses existing/failed runs. Production integration requires actual reader,
writer and B ownership plus both exact reader-build EOF probes before retirement.
Forward inventory checks both SQL owners and prepares raw captures directly as
packs with session reuse; it preserves pending/active/nonterminal/unbound logs.
Eleven new controller/forward tests and eleven admission regressions pass;
fourteen existing publication/forward regressions also pass. Daily production
wiring and new forward graph/map normal-B closure remain open.

One narrow isolated rehearsal exercises this controller with fresh main SQL and
three current history copies, real writer/reader protocols/kernel locks, both
qualified EOF probes, ordinary API comparison and latest-copy fallback. It reuses
accepted protected/corruption coverage; fixture recovery is explicitly not B.
Live data, services, calendar and Nightly commissioning remain untouched.


November25 controller qualification is independently accepted: four stages, three
API phases,60original tables/four later-write sentinels and latest-copy fallback.
Two backward+one raw-forward transaction reduce copied histories7,826files to18;
allocation71,741,440B to54,546,432B. Both exact reader probes pass before original
retirement; all31fixture journals reconcile. This is isolated evidence, not live
reclamation or normal-B recovery. Original owners and inputs remain unchanged.

Forward recovery now restores the prepared graph and metadata mapping through
actual B, preserving canonical backup selectors and capturing only new bodies.
Four tests cover body reuse, new manifests, nonbeneficial refusal and damaged
remote data with no local fallback. One finite packed-forward-normal-v1 qualifies
one actual closed1,577,508-byte log and a second prepared namespace to prove zero
new body captures on reuse. Cap64MiB control input; existing WakeWatch rearmed.
No live mutation, daily activation, Nightly commissioning or deferred cleanup.
Production invocation/cutover/current final recovery/ordinary checks/whole staging
and filesystem accounting remain required before full dedup acceptance.


November25 actual forward recovery accepted:6checkpoint triples,84files/5,948,994B;
one1,577,508-byte raw original preserved;212,719-byte graph reused with zero new
body captures. All intents/restores/identities reconciled; unit empty/PID180142 gone.
Added packed_incremental.Adapter using existing daily runner/lock/automatic hold/
monitor contract. One normal-B context/run, exact-session selection and preserved
prior catalog selectors.3new integration tests plus7runner/9automatic regressions
pass. One isolated packed-daily-rehearsal-v1 now qualifies actual daily execution,
both reader EOF probes, ordinary APIs and latest-copy fallback against fresh SQL.
Fixture restoration is clearly distinct from the accepted actual Desktop-B proof.
No live/timer/Nightly changes. Required Rust format passes; web formatting cannot
run because Prettier is absent. Ops and whitespace checks pass. Full dedup remains
open pending deployment/configuration/live conversion/final checks/accounting.
