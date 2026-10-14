# Restart efficiency — October 14

Staging owns restart efficiency and the next release. A separate cleanup owner
owns B retention/reclaim work. The audit and focused preparation implementation
are complete locally; no production restart, cleanup, timer installation or
live-controller change was performed.

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
| Focused reader test compilation and run | 8m 29s | Reuse exact unchanged test evidence/executables; otherwise run with the coherent test profile. |
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

The baseline `vk_prepare.py`, `vk_prep_common.py` and preparation tests matched
the actual reviewed Staging source exactly. They are now present in this task's
`scripts/deployment/`, with focused repairs to the existing runner. This avoids
a competing build/restart framework. The cache invalidates on changed source content, build environment,
tool executable, context/configuration, dependent outputs, artifact hashes or
logs. Identical source trees with metadata-only commits can reuse evidence.
Volatile steps remain uncached. Generic backend recipe generation is rejected;
use the established approved isolated build plan instead.

Implemented improvements:

- An existing cache owner causes an immediate refusal instead of an indefinite
  lock wait or duplicate preparation.
- Step graph, commands, finite timeouts, declared inputs and tool availability
  are checked before work. Private overlays, namespace drivers and manifests can
  be pinned with `required_files`; changed/missing inputs block before build.
- A malformed cache receipt reruns its affected step rather than aborting the
  release or discarding the entire cache. Reuse still verifies output bytes,
  modes, log hashes and input stability. Explicit volatile steps cannot be cached.
- `source_snapshot` supports the real sealed non-Git private build snapshot.
  It verifies the pinned manifest, source identity, every tracked file hash and
  link target before/after work and reuse, without cloning or changing source.
  The reviewed tree identity is supplied from the existing authenticated source
  binding; the tool does not invent Git provenance from a tar archive.
- `verify-artifacts` verifies an already accepted candidate and compatible
  rollback against a pinned manifest and exact source tree. It invokes no
  compiler, copies no payload and makes no new behavioral acceptance claim.
  Plans can bind `accepted_artifact_manifest` directly, avoiding another artifact
  copy; the files are still hash-checked before/after preparation and completion.
- `finish` binds total pipeline timing to the exact successful publication
  receipt, preparation tree and artifact hashes, plus expected HTTPS/data/18
  recovery evidence. It does not perform deployment or fresh live verification.
  Only an explicit fix-ready clock can establish the ten-minute target; an
  ordinary preparation clock cannot. Failed/mismatched receipts cannot complete
  the pipeline. Previously completed results cannot be replaced silently.

The queue adapter is now in `vk_prepare.pending_sessions`, using four concurrent
GETs and covering every session, including old sessions. It does not eagerly
queue thousands of requests: on refusal, submission stops and only in-flight
requests settle. Failed inventories block the switch. Queue text is preserved
and excluded from the summary. Repeat observations are fresh; neither an empty
result nor concurrent reads prove an atomic writer fence. Existing managed-owner,
final quiet, maintenance and fenced checks remain essential. The integrated
controller test fixture has a disabled entry point; fresh generation identities,
policy bindings and acceptance are needed before any live adoption.

## Audit conclusions and verified implementation

The long release was not a three-day service interruption. Capture/restore alone
cost about one hour of online preparation, and failed build attempts were
additional. Retained receipts identify an omitted linker-alternatives namespace
mapping, a guarded memory-pressure stop, and mismatched test-only debug profiles
across server/utils/rust-embed. Keep the corrected namespace and coherent test
flags, preflight them before a future build, preserve caches and retain resource
guards; do not broaden host access to make compilation pass.

54 preparation regression cases pass. These include real disposable Git/source
snapshots, cache/log/artifact corruption, missing prerequisites, exclusive cache
ownership, changed source/config/overlay, volatile checks, total timing and early
queue refusal. The updated complete controller fixture passes 16 regressions,
including compatible latest-data cutback, queued/active-work refusal, original
profile-byte preservation and the real gateway on a disposable loopback route.
Consequential lifecycle, ownership, backup and API transports are mocked there.

The real existing 2,523-file private source snapshot and accepted candidate/
rollback completed repeat binding in 3.60 seconds, with zero compiler work,
payload copying or full-backup repetition. This is input/artifact verification,
not a new current-data/runtime acceptance certificate.
The reproducible offline cache fixture reused both build and acceptance on
unchanged input and metadata-only promotion; all four fresh checks still ran.
Its initial/repeated durations were 0.78/0.18 seconds. Those synthetic durations
prove skipped work, not a real Rust build speed or ten-minute production SLA.

The actual ten-minute end-to-end release remains unmeasured. No cold compiler
build, new whole-state backup or production load test was launched for this audit.
The next actual code release should use these preparation repairs and record the
full fix-ready/build/validation/wait/switch/work-resumed interval once.

## Operator-independent use for the release owner

The CLI is for the authorized release owner/scripts, not manual operator commands:

```text
python3 scripts/deployment/vk_prepare.py start --root <task> --fix-ready-at <actual UTC time>
python3 scripts/deployment/vk_prepare.py verify-artifacts --manifest <pinned manifest> --manifest-sha256 <SHA> --source-tree <reviewed tree>
python3 scripts/deployment/vk_prepare.py run --source <isolated source> --root <task> --plan <reviewed plan>
python3 scripts/deployment/vk_prepare.py queues --origin <direct loopback backend> --database <current DB> --out <task receipt>
python3 scripts/deployment/vk_prepare.py finish --root <task> --publication-receipt <verified actor receipt> --publication-receipt-sha256 <SHA>
```

All roots and bulk/cache/log outputs remain below mounted `/mnt/vk-storage`.
Use the existing private namespace preflight/build commands in an explicit plan;
test-only server, utils and rust-embed debug flags remain coherent and do not
change artifact profile. Bind that boundary/configuration and private snapshot
manifest in `required_files`/`context_files`. The source snapshot mode accepts a
manifest path/SHA, authenticated source commit and reviewed tree, while retaining
the snapshot's existing generated assets and stricter original build guards.
It is not an authority to enroll a new builder, mount data or relax isolation.

Offline reproducible cache benchmark (no compiler, network backup or services):

```text
python3 scripts/deployment/benchmark_vk_preparation_cache.py --root <mounted task>
```

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
- Completed implementation/audit: `implementation-r2/AUDIT_COMPLETE.safe.json`,
  `VALIDATION.safe.json`, `REAL_SNAPSHOT_REUSE_RESULT.safe.json`,
  `ACCEPTED_ARTIFACT_REUSE.safe.json` and `CACHE_BENCHMARK.safe.json`.

Private operational receipts remain local/authorized storage. No GitHub or other
external operational diagnostic publication is authorized by this task.
