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
Attempt0 stopped before publication at the SSD/memory/PSI resource check. Its
journal does not exist; both originals and sidecars match their exact inodes and
full hashes. Four immutable graph checkpoints remain intact. FAILURE.attempt0 and
ISSUE_RECONCILIATION retain evidence. No service recovery or rollback was needed.
Actual resume1 subsequently waited at full PSI.14 with9.8GB RAM/51.8GB SSD free,
then passed the unchanged guard and verified all8,050 normalB graph members.
RESUME1_BACKPRESSURE_ACCEPTANCE and RESUME1_MONITOR_ACCEPTANCE retain proof.
Do not infer completed conversion from graph verification; read batch RESULT.
Same unit/operation now uses bulk_resume3.py, worker_v5.py and RESUME3_SEAL,
resume3-sdk and resume3-nightly. Never replay any consumed ATTEMPT file.
The terminal worker no longer holds production-owner.lock or Nightly/native B custody.
No service actions, model loop, native goal or automatic retry are used.

Wake event7f4b8876 (20November04:13UTC): resume2 stopped before batch0019
publication while reading MM state.json on Desktop (PermissionError13 masked by
"native real guard health reply unavailable"). Its19 completed batches+canary,
54 logs, exact manifests/inodes/sidecars and B restore records reconcile. Batch19
has no journal and all3 original logs/sidecars retain exact hashes/inodes. Two
immutable graph checkpoints exist; carrier2 failed before checkpoint submission.
Recorded live-log allocated reduction7,672,238,080B includes primary objects and
directories; whole-filesystem/staging final accounting remains open.
RESUME2_FAILURE_RECONCILIATION and FAILURE.resume2 retain evidence.

Resume3 qualified Windows control reads with SHARE_READ|WRITE|DELETE, the same
caller/ACL/path, current-file identity checks and unchanged MM parsing/STOP rules.
A real Desktop fixture reproduced the old errno13 under a publisher's DELETE
handle and the new reader succeeded. The historical exception lacks WinError,
so this proves the mechanism, not its exact occurrence at failure time. Only
WinError32/33 get existing MM4-read/80ms patience; access denial5, unknown errno,
missing/changed/malformed controls still fail. No ACL/STOP/service changes.
Five native fixture cases,34 Python tests and actual candidate B identity/SMART/
control admission passed. RESUME3_VALIDATION and native receipts hold evidence.

Explicit partial-graph recovery validates the exact two-checkpoint prefix,
independently restores those epochs, then creates only the four missing carriers
in new scratch paths. Existing pack2 and all prior sources/epochs stay intact.
Real fixture tests cover full recovered bytes, corruption/refusal and no replay.
Resume3 starts batch19, then continues the original finite selection. Runtime
sources/configs are sealed; do not edit them. WakeWatch follows ARMED resume3.
The converter has no automatic retry. Vibe identities/settings remain unchanged.

Earlier wake7e0af839 reconciled24 installs after a STOP-control read failure;
resume2 finalized staging and advanced to54 logs. B/reader checks, per-object
execution fences, primary copies and exact leases remain enforced.

Earlier wake3f9635a7 was a progress-reporting gap during verified staging
retirement. The worker continued naturally; STALL_EVENT_RECONCILIATION retains
proof. Existing conversion_source_v3/retirement_progress only count actually
retired allowlisted replicas whose primary copies hash correctly. Repeated samples
are not progress; terminal failure remains separately reportable. No extra loop.

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
