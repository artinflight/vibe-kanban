# Writer cutover accepted; finite conversion resumed after Desktop outage

November22 recovery1 is live in the same finite unit: PID2054584,
invocation221dd13e67f04147a3113740f9267240. Current controls are
`checkpoint-controls-20261122-recovery` under the operation root. The stopped
accelerated2 attempt had committed69 batches/291 logs. All installed manifests
were rechecked; batch69's seven originals/sidecars still matched their planned
identities and full hashes, with no conversion journal or installed manifest.
Three accepted graph backup receipts were retained and reopened; the incomplete
pack-3 remains untouched. Continuation uses new pack-3-nov22r1. Returned Laptop70
and Desktop71 preparations were independently bound/hash-checked and adopted
without dispatching them again. No Vibe/backend/reader restart occurred.

Desktop SSH transports timed out at02:21UTC; a BrokenPipeError during cleanup
masked the guard-health failure. The acceleration attempt name also made the
failure alert resource53characters, exceeding the installed48-character limit.
That monitoring bug prevented the automatic wake. Bounded deterministic event
IDs now preserve old valid incident keys, carry the full attempt in event values,
and pass the actual failure/stall/success codec and no-replay tests. Alert-routing
errors retain fresh process observations instead of erasing the HUD feed.
The ordinary timer observed recovery1 paused and running with no source/event
error and the same8 delivered batches/8 attempts. Desktop's actual HUD receipt
now says RUNNING. Existing dedicated chat, settings, ledger and timer are retained.

See [recovery evidence](VK_DEDUP_OFFLINE_RECOVERY.md),
[acceleration](VK_DEDUP_ACCELERATION.md) and
[controls](VK_DEDUP_CHECKPOINT_CONTROLS.md). The initial accelerated comparison
remains470.2MB raw/461.0MB allocated release in19.2minutes versus31.8minutes
for a preceding similar batch; it is not a backlog ETA or final net-space figure.
No consumed activation or uncertain remote dispatch may be replayed. Recheck
actual unit, receipts and current control path before acting. Native goal remains
paused; no new goal or agent continuation loop exists.

Desktop's live dedup Rainmeter card is installed directly below Archive Queue.
See [HUD operation and acceptance](VK_DEDUP_RAINMETER.md). It uses the existing
public status publisher; source freshness, pause/wait/failure and final-checks
states remain explicit. It introduces no converter or backend restart.

Prior November21 recovery: same finite unit, PID1316160,
invocation3594484094cb4790885a9b4b7570da3f, attempt controlled1.
See [controls](VK_DEDUP_CHECKPOINT_CONTROLS.md). Package checkpoint-controls-20261121
under the operation root retains preparation, recovery, pause/resume and live
acceptance receipts.122 files/37 batches are committed; next batch37 packed
441,903,688 raw bytes. Packing is not conversion acceptance. Normal WakeWatch
observed pause and resumed progress with the same8 deliveries/8 attempts.

Recovery leaves the old batch0037 directory entirely untouched. The sealed
HANDOFF.batch_override maps that one batch to new isolated staging under the
control package. Preserve the mapping in all subsequent recovery/closure work;
never substitute the empty old path. The existing consumer scan, original worker,
source custody, backup epochs and all rejected alternatives remain unchanged.
No backend restart, forced unlock, duplicate job or synthetic wake occurred.
Status/pause/resume are available through the current package's control client;
pause takes effect at the next verified batch boundary. Read live identity and
acknowledgement, never blindly rerun a consumed activation or resume request.

## Historical failure wake — recovered November21

Wake8ae7dc66 reached the dedicated chat once at11:54UTC November20; execution
c1548168 ended blocked at12:02UTC. All122 installed logs and their backups were
intact. Its record is wakewatch/chat-handoff-20261120/FAILURE_WAKE_8ae7dc66_RECONCILED.private.json.
The current isolated-staging route supersedes that block without removing the
consumer scan or reusing the inaccessible directory. All prior evidence remains.

## Operator restart ownership correction —19November2026

The operator explicitly reaffirmed: backend restarts belong to the managing agent
outside Vibe; individual workspace agents must hand off the actual restart. A
standalone systemd controller is not that agent handoff. The v4 cutover did stop
and start the main backend, with221s maintenance; its evidence does not establish
external managing-agent ownership. Describe this plainly as a backend restart.
No backend restart is needed for checkpoint controls or normal online conversion.
Any future necessary restart must be prepared here and handed to that manager.
Future Codex resume replay prevention is active for qualified runtime versions;
it is not automatic recurring deduplication of every future log. The current
conversion is a finite backlog job; ongoing scheduling remains unimplemented.

Current operation6d4d022ab2f84d1ea72f39d6a6382d1c:
/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117/efficiency-20261118/online-20261119-v1
Unit vk-online-dedup-bulk-20261119-v1.service;
current PID2054584 / invocation221dd13e67f04147a3113740f9267240; attempt recovery1.
Former controlled1 PID1316160 exited at its verified65-batch checkpoint; retained
handoff in checkpoint-controls-20261122-fast-v2 proves the clean transition.
OldPID4119270 is gone; its terminal invocation3b0f92bbd65a47afb1a599b7d3015003 is historical.
Read exact unit identity, ARMED, PROGRESS, COMMITTED, RESULT/FAILURE and per-batch
journals before acting. Never duplicate the worker or replay an uncertain batch.
Earlier attempts and their exact recovery proofs are retained in
[checkpoint-control history](deployment-history/20261120-checkpoint-controls/HANDOFF_HISTORY.md).
Qualified legacy inputs remain bulk_resume3.py, worker_v5.py, RESUME3_SEAL,
resume3-sdk and resume3-nightly. Sources are unchanged and sealed. Never replay
consumed attempts or infer completion from preparation/graph validation alone.

The finite selection is3,361 additional closed logs /90,874,060,091 source+sidecar
bytes in395 batches. Input volume is not expected savings. One canary is already
complete. Closed current workspace logs are included; archived/completed workspace
cleanup, active/pending/unknown captures and tiny nonbeneficial files are preserved.
Fresh metadata and real per-execution locks still decide actual admission.

Main writerPID70372 / invocation81dd8bb21f894aa1bd286f8f0029b770,
SHA01495f7f911a222f022354d406789ffa7f634f6faab81798828413d3582cc0a0.
Cutover904ccb9583b845d9a6644d02013b8780 succeeded; evidence in sibling
cutover-20261119-v4. Maintenance221.01seconds. All60SQL tables, selected histories,
review/settings/queues,35 pending inputs and latest GPT6.2 frontend were preserved.
Protected server2573735 / unit2573723 and proxy2573727 unchanged. Never rerun it.

Canary converted15,543,547 raw bytes while this agent remained active. Actual B
original and all675 graph members restored independently; one packed carrier
replaced15 tiny-file checkpoints. Full Python/Rust EOF and identical ordinary
history passed;673 staging object replicas retired. Live-log allocated reduction
including objects/directories10,596,352bytes; task staging is separately accounted.
The bulk job retires only its exact newly-created duplicate carrier/object copies,
retaining all primary objects, immutable B epochs, manifests and recovery records.

Desktop1440 and mobile393 viewport history/settings/review/queue flows passed4
cases with0 operator writes; physical phone testing is not claimed. Current real
native resume on0.159.2 returned0 historical turns /3,904bytes; old measured
prevention baseline8turns /10,746,496bytes. This bounds initial replay, not all
future log growth. No new inference/provider test call was issued.

WakeWatch now targets the separate “WakeWatch — Deduplication” chat in this
workspace:036f0739-6fcc-4e30-911a-e4c6e7e1f388. The20November operator-requested
handoff preserved all7 settled deliveries, settings, ledger and timer. See
wakewatch/chat-handoff-20261120 under the operation root for continuity and audit.
Future issue/success reports go there; no new execution or restart was needed.
Live progress, independent of Vibe maintenance:
https://mcp-server.tail744c4.ts.net/vk-dedup-status
It shows resolved/selected and converted counts plus actual verified phase/time.
Native goal remains paused; do not create another goal or continuation loop.

When bulk success wakes: reconcile every exact batch, re-inventory remaining
eligible beneficial logs, close the complete resulting archive dependency tree
including pre-existing/unreferenced objects and recovery records on normalB,
capture/restore currentSQL and retain compatible software/frontend backup links,
verify ordinary UI/history/review/settings/queues and exact ordinary monitoring,
measure total net allocated AND filesystem release including new staging and
any open old descriptors, then finish growth/operating/restore documentation.
Use FULL_OBJECTIVE_CHECKLIST.private.json. Bulk RESULT deliberately says full
objective unverified. Per-batch checkpoints alone do not close complete-tree backup.
Preserve current writes, pending inputs, selected settings, all epochs/other owners.

Historical170-case qualification, native resume measurement, guards and prior
resource/custody tests remain in [the retained pickup record](deployment-history/20261122-before-offline-recovery/HANDOFF.md).
Do not rebuild or repeat sufficient qualification without new invalidation.

History: [before v4](deployment-history/20261119-before-v4-cutover/HANDOFF.md),
[HANDOFF history](HANDOFF_HISTORY_20261017.md).
