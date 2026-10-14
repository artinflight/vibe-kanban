# Restart efficiency — October 14

Staging owns restart efficiency and the next release. A separate cleanup owner
will take B retention/reclaim work. This preparation does not authorize another
restart, cleanup, timer installation, or a live-controller change.

The combined release completed successfully on October 14 at 18:05:35 UTC.
Source/artifact and actual HTTPS/recovery readback are retained in the existing
private release receipts. All 18 authentic replies remained once-only. Current
data was reused; rollback uses compatible code on latest data, never an older
database. Reader/proxy/frontend, Recommend, models and effort were preserved.
The optional original-manager/original-worker continuation remains deferred.

## Measured costs and honest target

| Phase | Measured elapsed time | Treatment for the next release |
| --- | ---: | --- |
| Matching warm candidate build command | 7m 1s | Build while incumbent stays online; preserve matching compiler cache. |
| Whole-current backup capture | 40m 47s | Prepare online before release; retain verified baseline and verified deltas. |
| Whole restore verification | 19m 34s | Bind to exact baseline; refresh affected evidence when inputs change. |
| Online pre-switch delta | 4m 28s | Move ahead of the idle window; final fenced delta remains required. |
| Actual interruption through verified publication | 1m 55s | Reuse the successful same-current-data switch and latest-data cutback. |

These are individual phase durations, not a measurement of one total pipeline.
The ten-minute objective runs from fix ready through build, validation,
deployment and production work resuming. Build must not be excluded. The measured
build command plus interruption already uses 8m 56s, leaving about 64 seconds
for other work if those durations recur. Cold builds and the complete ten-minute
pipeline are not yet demonstrated. Nightly preparation cannot compile future
fixes, and fresh data/authorization checks cannot become cached passes.

## Reuse existing preparation tooling

The existing `vk_prepare.py`, `vk_prep_common.py` and preparation tests were copied
unchanged into the private efficiency task, with hashes bound to their existing
reviewed combined source. This avoids a competing build/restart framework.
Its evidence cache invalidates on changed source content, build environment,
tool executable, context/configuration, dependent outputs, artifact hashes or
logs. Identical source trees with metadata-only commits can reuse evidence.
Volatile steps remain uncached. Its generic default build recipe is not the
approved private-runtime sandbox command; do not execute that default as a
replacement for the established isolated build boundary.

The next controller fixture replaces serial per-session queue reads with the
existing reader at four concurrent GETs, covering every session, including old
sessions. Failed inventories block the switch. Queue text is preserved and not
included in the adapter's output. Repeat observations are fresh; neither an
empty result nor concurrent reads prove an atomic writer fence. Existing managed
owner/final quiet checks and maintenance/fenced boundary remain essential.
The fixture has a disabled entry point and cannot be armed as a live actor.
Fresh generation identities, policy bindings and acceptance remain necessary.

## Next release sequence

1. Classify the exact changed content. Compatible frontend-only or reviewed
   module changes use their supported publication routes without a backend
   restart. Backend changes retain the private reader overlay and compatible
   rollback, not an older public tree wholesale.
2. Reuse exact accepted components and tests only where their input identities
   match. Build changed components once in the established isolated boundary,
   preserving cache and measuring warm/cold builds separately. Discover missing
   linker/toolchain/sandbox prerequisites before compilation.
3. Prepare the independent whole-state backup/verified chain and restore proof
   while production is online. Validate plan identity, parent dependencies,
   source coverage, deletions, metadata, DB consistency and journal continuity.
   A gap or changed scope requires actual correction; it cannot be called a
   successful incremental. No DB-only substitute for whole-state protection.
4. Prepare transport, package/rollback hashes, schema-copy acceptance and
   release-specific checks before requesting a quiet boundary. Store receipts
   locally and at the authorized independent destination. Validate the complete
   controller path on disposable inputs before arming exactly one actor.
5. At natural quiet, freshly verify active executions, all queued prompts,
   relevant process/cgroup ownership, external-worker independence, disk capacity
   and applicable policy/authority. Keep pending user prompts; no forced stops.
   Preserve the final writer-fenced current-data catch-up and compatible rollback.
6. Switch and verify actual process/source/artifact identity, trusted HTTPS,
   frontend/module compatibility, recovery/history invariants and requested
   enabled behavior. Write atomic terminal receipts independently of chat capture.
   Measure fix-ready-to-work-resumed, preparation, quiet wait and interruption
   separately; report failures and waiting time instead of resetting the clock.

## Backup scheduling and cleanup boundary

No VK nightly timer was observed in the current user systemd timer inventory.
That is not a census of cron or Windows schedules, and no working automatic
schedule is claimed. Existing nightly source is retained; enablement needs a
bound destination, supported scheduled host job and actual schedule/test receipt.
Routine backups should use scripts, not LLM calls. Promote a newly verified
generation atomically before replacing the prior one; incrementals must not
depend on a removed baseline. Failed partials/temporary overlap must be bounded.
Do not silently install a timer or retire any backup in this efficiency task.

B/R payload reads remain held. Use the already authorized healthy independent
destination for future backups only within its existing scope/capacity. The B
cleanup handoff is separate; its 500 GB target is not a release gate or a
permission to remove the warm build cache or unique source/history.
All historical recovery exceptions and the human-QA cleanup boundary remain.

## Private handoffs and validation receipts

- Cleanup: `/mnt/vk-storage/vk-b-retention-list-20261014/PARALLEL_CLEANUP_HANDOFF_20261014.md`.
- Efficiency: `/mnt/vk-storage/vk-restart-efficiency-20261014/`.
- Exact phase timings: `MEASURED_CRITICAL_PATH.safe.json` in that task.
- Current accepted artifact bytes: `CURRENT_ARTIFACT_REUSE_READBACK.safe.json`.
- Tool pin: `EXISTING_PREPARATION_SOURCE_PIN.safe.json`.
- Fixture queue measurements: `QUEUE_BENCHMARK.safe.json`; synthetic only,
  no production load test or runtime adoption claim.
- Validation: `VALIDATION.safe.json`, queue/actor logs and disabled actor fixture.

Private operational receipts remain local/authorized storage. No GitHub or other
external operational diagnostic publication is authorized by this task.
