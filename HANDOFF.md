# Writer cutover accepted; finite converter STOPPED after natural failure

Nov20 checkpoint controls are tested (59 tests) but NOT ACTIVE. See
[control handoff](VK_DEDUP_CHECKPOINT_CONTROLS.md). Resume3 failed naturally at
11:36UTC on a read-only systemd query. Both backup locks are free; no agent stop
or forced unlock occurred.118 logs are committed;4 installed tail logs retain
full recovery proof and need final staging retirement/commitment. Next batch37
is empty. The attempted paused activation stopped at an inaccessible consumer
scan before changing conversion data, watcher or services. The failed attempt
is retained under checkpoint-controls-20261120; never blindly replay it. Automatic
approval review rejected both proposed scan changes, and neither edit executed.
External privileged inspection or explicit approval for an alternative is needed
before activation. Original sources, main/protected identities and settings match.

## Dedicated failure wake reconciled —20November2026

WakeWatch batch8ae7dc66-43d4-4a4e-b84c-bdaeef8b974f arrived once in the dedicated
chat (executionc1548168-ce0b-45b3-8699-2a217339f49e). Fresh read-only checks verified
all38 journals, all122 installed manifests and required sidecars, retained normalB
proofs,23 prepared source pins, both live reader hashes/mounts/protocol/settings,
and unchanged converter invocation.118 files remain committed;4 installed files
in batch0036 await carrier retirement/commitment; batch0037 is empty. The natural
failure log names `Transport endpoint is not connected` from systemd. Both backup
lease inodes have no kernel lock at the inspection snapshot.

The consumer scan still fails at `/proc/1119/cwd`. No activation, resume, stop,
unlock, settings change or recovery-data mutation was performed. Existing rejected
scan alternatives remain rejected. The next step requires privileged inspection
of consumers of the exact empty batch0037 directory (device2065/inode21119143),
including same-user PID1119, followed by independent reconciliation of the consumed
activation; then activation must start paused. Do not run the existing uid-based
scan as root without preserving its intended mcp-user scope. Any subsequent resume
must follow the explicit control authorization; this alert grants no auto-resume.

Evidence: operation `wakewatch/chat-handoff-20261120/FAILURE_WAKE_8ae7dc66_RECONCILED.private.json`.
Recorded committed live-log allocation reduction is15,590,174,720B, plus413,466,624B
for the installed tail. These are not net filesystem savings: final staging,
growth and old-descriptor accounting remain open. This response reclaimed0B.
The ordinary watcher still reports failure_recovery_pending with one attempt for
this wake. The selected finite conversion and final backup/UI/accounting acceptance
remain unfinished; no full deduplication acceptance is claimed.

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
terminal MainPID0 / invocation3b0f92bbd65a47afb1a599b7d3015003; attempt resume3.
OldPID4119270 is gone; no replacement controller was launched.
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

Qualification:170 Python tests ran,165 passed and5 optional probes skipped.
The resource guard retains3GiB SSD/4GiB available RAM/.10 full PSI thresholds,
waits up to the existing600s no-progress bound, rechecks owner/mount identities,
and records exact metrics without crediting waiting as progress. Packed immutable
B-derived RAM uses1s remote owner polling and64-member read-only graph checks;
every byte/EOF/metadata is still verified. Publication guards remain uncached.
Watcher fixture proves accepted issues are not replayed and a manually reconciled
attempt can report a new issue. No automatic controller retry was added. Real
production canary passed. Existing Rust lock/reader qualification remains retained.
Rust formatting passes; web formatting unavailable because Prettier is missing.
Bulk source/config/inventory pinned in RESUME1_SEAL; do not edit active inputs.
worker_v3 pipelines the next request through the same real B context and groups
RAM replays in unchanged32-member sealed caches under a512MiB total batch bound.
MemoryHigh1.5GiB/Max2GiB; actual SSD/memory/Desktop admission remains enforced.

History: [before v4](deployment-history/20261119-before-v4-cutover/HANDOFF.md),
[HANDOFF history](HANDOFF_HISTORY_20261017.md).
