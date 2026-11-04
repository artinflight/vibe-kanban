# Conversation-log reclamation readiness

**Production conversion is blocked.** The installer, rollback, growth audit and
backup graph tooling are implemented and tested. That does not qualify the live
readers, a recovery set, or a deployment boundary. No live log is converted or
retired by this preparation.

Source review is [draft PR #291](https://github.com/artinflight/vibe-kanban/pull/291),
targeting staging. Both hosted workflows passed on source `087319cc4`. A subsequent rebase onto
current staging preserves all dedup code; new-head checks govern integration.
The user has now requested production completion, including deployment and recovery;
actual ownership, recovery and admission checks still govern every operation.

## Current readiness and ownership

| Gate                            | Evidence and remaining action                                                                                                                                          | Owner                                             |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Lossless format/readers         | Committed base `0192b38de`; six real logs reconstructed and restored byte-exactly                                                                                      | Deduplication                                     |
| Guarded conversion and rollback | Source-pinned controller entrypoint, retained physical fence, durable objects before manifests, per-file journal and interrupted rollback recovery pass fixtures       | Deduplication; deployment owner admits actual run |
| Every serving reader            | Main backend remains the older build; completed history can reach the separate old protected reader on 5650, sharing the source directory                              | VK::Staging Check                                 |
| Compatible rollback             | Reader-aware fallback, or verified raw reconstruction before an archive-unaware reader is released; current-data roundtrip still required                              | VK::Staging Check                                 |
| Current Desktop B recovery      | Historical October 28 acceptance does not prove the selected current versions; exact bodies, sidecars, metadata mappings and independent normal recall remain required | Nightly Backup Efficiency                         |
| Future archive backups          | Exact manifest/object/sidecar graph export and provider readback/closure verifier implemented; actual B consumer qualification outstanding                             | Nightly Backup Efficiency                         |
| Build capacity                  | Latest SSD observation is 7.5 GiB free; fresh build ownership/resources and retained 3 GiB floor still apply                                                        | OP::Disk Space and deployment owner               |
| Actual owner adapter            | Trusted source-pinned admission adapter and fresh config are required; no dummy production adapter or receipt is supplied                                              | VK::Staging Check, with Nightly B provider        |
| First batch custody             | Prepared selection is not a physical fence; reselect/recheck under actual held ownership                                                                               | Deployment owner                                  |

Staging completed its requested read-only review and conditionally accepted source
integration into the next compatible release, **not deployment or conversion**.
Its durable assessment identifies the main and protected-reader artifacts, exact
private input, consumers, current frontend pointer and retained custody interfaces.
Keep the latest live frontend; do not deploy the older source checkout's assets.

Nightly is actively commissioning its existing tracker/delivery/backup workflow.
A shared project question records the exact current-version and archive-graph
requirements; it is not a received owner acceptance or a current B proof. Do not
interrupt commissioning or create a second producer. OP::Disk Space's prior safe
verification stops cleared zero files for retirement. A current recheck was
requested under unchanged guards; no new deletion authority was given. That recheck
passed initial admission at23:28:55UTC, then stopped source hashing at23:29:26UTC
when full memory PSI reached0.14, above the unchanged0.10 limit. At23:30:07UTC,
SSD free space was1,943,719,936bytes:1,277,505,536bytes below the build floor. No
source retirement or further automatic retry was authorized by that result.
A separate frozen inventory found2,482 compiler-metadata files totaling2,463,285,248
allocated bytes in the shared debug target. This is a proposed reproducible-output
review, not disposal clearance. Vibe's completed provenance review conditionally releases only 2,104 exact files /
1,811,595,264 allocated bytes as regenerable compiler metadata. The other 378 files
remain excluded. This is not deletion authorization or global non-use clearance.
The frozen private plan is `compiler-metadata-retirement-plan.json` in this task's
evidence directory; its exact identities, header bytes and path-list digest must
remain unchanged. Preserve all executable/test binaries, rlibs, shared libraries,
fingerprints, dep-info, source/toolchains and private release inputs.

Before that separate action, the Vibe owner requires exact action authorization,
fresh resource/consumer checks and retained nonblocking exclusive locks on the
**existing** Staging `authorized-release-20261021/owned-build.lock`, followed by
`/mnt/vk-storage/cargo-target/debug/.cargo-lock`. Never create or replace either
lock. Inaccessible process views prevent a global non-use clearance from this
review; `sudo -n` also requires an operator password. The owner identifies an
exact-file kernel-lease check as a possible separately authorized alternative,
not an already performed clearance. Any contention, unavailable proof, changed
file or lease break must preserve the candidate and stop. No compiler metadata
was removed and no build-floor clearance is claimed. Even the full proposed
saving is temporary build headroom; budget later artifact growth before a build.

## Runnable conversion interface

The original [measurement/packing procedure](VK_LOG_DEDUPLICATION.md) remains the
format and preservation reference. New scripts are in `scripts/log-dedup/`:

- `reclaim.py::Batch`: bounded batch, at most 64 unique files and 2 GiB logical
  originals; exact canonical source root; existing `WriterFence` instance with its
  real held lease; terminal execution/session checks; unchanged source versions,
  sidecar set and bytes; source-root binding in `fence.binding.log_source_root`.
- `controller.py`: executable entrypoint using **verified adapter source bytes**.
  Adapter hash, literal owned path, restrictive writability and protocol are
  checked before executing it. There is no `--force`, `--backup-ok` or
  `--fenced=true` bypass.
- `graph.py`: deduplicated physical namespace dependencies with physical SHA256,
  separate reconstructed-original hashes, and actual independent provider-body
  verification with manifest reference closure. A graph export is not a backup.
- `audit.py`: bounded read-only metadata inventory and comparison; no transcript
  payload collection, automatic cleanup, service changes or new scheduler.

After the owners supply the real reviewed adapter/config and close all gates:

```bash
python3 scripts/log-dedup/controller.py \
  --plan "$SELECTED_PLAN" --archive "$PACKED_ARCHIVE" \
  --journal "$NEW_OPERATION_DIRECTORY" \
  --adapter "$REVIEWED_OWNER_ADAPTER" --adapter-sha256 "$OWNER_ADAPTER_SHA256" \
  --config "$FRESH_OWNER_CONFIG"
```

The same command with `--rollback` reconstructs the original raw bytes. These
variables are required reviewed inputs, **not a ready production invocation**.
Do not reuse a consumed activation package, its old PIDs/leases, or expired B
admission. The wrapper does not independently stop/freeze services.

The adapter protocol is `PROTOCOL = 1` and
`admit(config, plan, rollback=False)`, a context manager yielding:

```python
{
    'writer_fence': actually_held_retained_writer_fence,
    'recovery': independently_reopened_canonical_B_provider,
    'reader_guard': current_reader_consumer_tracking_guard,
    'reserve_bytes': owner_admitted_reconstruction_reserve,
}
```

This is trusted executable deployment code, pinned by source hash. The owner must
verify every imported dependency and config too. The `reader_guard` must verify
actual build/reader identities, all consumers including the protected reader,
log-root bindings, source tracking/backpressure and recovery ownership; it cannot
just return a JSON ready flag. Existing ingress holds, queue boundary, capacity
custody and deployment failure recovery remain authoritative.

The B provider exposes its actual canonical
`desktop:B:/vk-backups/...` location and
`open_original(relative_path, expected_sha256)`, a context manager over independently
reopened original bytes. The installer hashes complete bodies and checks exact
lengths for each original and sidecar. Historical receipts alone do not pass.
The graph verifier's separate `open_member(relative_path, physical_sha256)` checks
archived physical members through the normal B reader. Normal namespace restore
and Linux metadata acceptance still require the backup owner.

The operation directory must be private and outside source/archive. Its exclusive
lease and durable journal bind the plan, selected files and expected manifests.
Publication peak and full raw reconstruction headroom are reserved before copying
objects and checked again before each replacement. Object publication is create-only; existing objects are checked before reuse.
Every object is durable before any original is atomically replaced. Original
mode/owner/group/xattrs/time mapping is retained. New object directories/files
are private, so every consuming UID/ACL must be explicitly qualified.

On failure, the **owner context must retain maintenance/custody or complete its
verified recovery before releasing consumers**. The library does not resume
services. Resume the exact operation; unknown newer data/inodes and foreign
staging are preserved. An interrupted raw rollback pins its staging inode before
writing payload, and pins manifest/restored inodes before publication. Owned partial stages
can be retired only after fresh recovery/fence validation; unknown stages stop.
No per-execution object GC is introduced. Shared objects remain after rollback.

## Prepared selection and backup graph

A new read-only observation selected four closed logs in inactive sessions from
the six-file measurement sample: 1,053,055,464 logical bytes. The entire OP::Disk Space session is deferred while its owner rechecks
preservation; its legacy log is also excluded from automatic selection. Selection is time-specific and must be refreshed if work resumes; all
selected sessions/executions are checked again under actual custody.
The selected subset can reuse the verified immutable six-file archive without
converting the deferred file or duplicating its staging payloads.

Its dependency export has 30,339 physical members / 157,557,122 physical bytes.
That includes manifests, shared compressed objects and sidecars. The provider
verifier rejects missing referenced objects even if all supplied bodies hash-match.
It does not itself establish live B coverage or normal restore acceptance.

```bash
python3 scripts/log-dedup/graph.py --root "$PACKED_ARCHIVE" --plan "$SELECTED_PLAN" > "$EVIDENCE/archive-graph.json"
```

The earlier **812.1 MiB** measured recovery potential remains evidence for the
original **six-file** sample, not a verified saving for this four-file selection
or the whole population. Production reclamation remains **zero**.

## Managing future growth

Deploy the inherited exact-qualified Codex narrow-resume prevention together with
all required readers. Qualify new native identities/versions instead of widening
that guard blindly. Preserve model context and new deltas. Measure returned resume
turns and persisted bytes through Vibe after deployment under a bounded QA budget.

Take finite metadata observations under the existing OP::Disk Space workflow:

```bash
python3 scripts/log-dedup/audit.py --root "$SOURCE_SESSIONS" --database "$CURRENT_DATABASE" > "$EVIDENCE/before.json"
python3 scripts/log-dedup/audit.py --root "$SOURCE_SESSIONS" --database "$CURRENT_DATABASE" --previous "$EVIDENCE/before.json" > "$EVIDENCE/after.json"
```

Observations separate raw logical bytes, regular-log/object allocation, shared
object counts, append growth, new/missing execution files and conversion activity.
Unique inodes are counted once; sidecars, directory metadata and external staging
are explicitly outside this payload metric. The existing disk monitor's filesystem
free-space/capacity view remains authoritative. Never add decoded logical size to
physical allocation or mistake OS recovery for SSD build headroom.

A 232.9-second observed interval grew allocated log payload by 163,840 bytes and
logical output by 164,968 bytes, with zero new execution logs/conversions. That is
an unmatched-workload observation, **not prevention acceptance or a forecast**.
Record workload/resume counts and post-install reader/send behavior before judging
new growth. Later closed-log batches use the same B/reader/fence checks; legacy or
pending/damaged captures remain explicit owner review. No new timer, background
retry, retention policy or automatic conversion is enabled here.

## Validation and exact next gates

Forty-five focused migration/controller/audit/graph tests and eight retained physical
fence regressions pass locally. Fixtures cover forward conversion, exact raw
rollback, complete command plumbing, body/graph corruption, missing dependencies,
wrong root/owner, active sessions, changed sidecars, foreign inode preservation,
object-publication failure, interrupted manifest/rollback publication and staging
recovery. These are detached fixtures, not live B or deployment acceptance.

The prior 36 utility tests, source server check and real six-log reconstruction
remain recorded in the format runbook. No Rust source changed in this follow-up.
Full local check/lint attempts currently stop at absent `tsc`/`eslint`; no duplicate
Node install was made. Full Cargo/workspace builds must not violate the SSD floor.
Required formatting, ops, source integration/CI and owner reviews are recorded in
the final handoff with any gaps. Provider execution QA is not claimed.

Close the table's missing reader/B/admission/capacity gates; qualify the source and
private-input artifacts; rehearse current-data candidate/fallback/candidate with
protected/recent histories, later-write sentinel and original review hashes; then
obtain/hold the actual drained run boundary. Report **ready** only with those
receipts, exact source/adapter/config hashes and a fresh bounded batch. No source
retirement may precede that evidence.

Private plans, graph, growth observations, tests and owner coordination evidence
remain under `/mnt/vk-storage/vk-log-dedup-20261103-0815/`. Do not publish transcript
objects, raw logs, backup bindings or the private retained-history input.


## Production completion requested — 2026-11-04

The operator explicitly requests carrying the task through production conversion,
verified recovery and actual reclaimed-space acceptance. Existing Nightly and Vibe
owners are coordinating their actual recovery/reader/deployment interfaces. The
accepted `NIGHTLY_BACKUP_CONTRACT.private.json` retains whole-session object-store
closure, physical versus logical hashes and normal-reader/fallback semantics.
No semantic turn omission is permitted; Nightly commissioning proceeds independently
of unactivated conversion and remains the sole backup producer.

Current observation has 3,221 closed/inactive files (84,557,012,508 logical bytes)
selected into 66 finite bounded preparations, beginning with four unchanged
sample originals. This is an exact selection accounting, not recoverable capacity.
`PRODUCTION_EXECUTION_20261104.private.json` binds the selection and outstanding
source, B recovery, both readers, admission, conversion, acceptance and accounting
outcomes. Legacy/active/pending/damaged records remain excluded and preserved.
The older resource/owner observations above are dated provenance, not renewed
clearance. No production bytes have yet been reclaimed by this stream.


## Normal Nightly reader bridge

`recovery_stream.py::NormalRecovery` bridges Nightly's existing validated,
lease-held `HeldRecoverySet` (`index.entry`, `blocks`, `check`) to the installer's
`open_original` and graph verifier's `open_member` interfaces. The trusted owner
must pin the accepted source namespace, real handle, native B admission and every
provider/index lease. It adds no transport, capture, lease acquisition or fallback.

Reads are bounded to 1 MiB, preserve the original namespace, verify selected
physical version/length/hash and require complete consumption to verified EOF.
Lost custody, partial reads, corruption, traversal and cross-session substitution
fail. Eight new fixture regressions cover those cases and the existing full
original/sidecar verifier integration. This interface does not itself establish
live B qualification, deployment admission or production recovery.

## Current production checkpoint — 2026-11-04 15:06 UTC

Production conversion and recovered log space remain **zero**. Main reader built
and independently byte-hash verified; the protected reader requires its corrected
build, exact production replay checks and current-data rehearsal. The existing
Nightly owner is reconciling retained versions and qualifying normal restore;
no replacement producer or schedule was created by this stream. Actual current
B original/sidecar readback and the held owner/provider/writer boundary remain
mandatory before any source replacement.

The four unchanged canary logs occupy 1,053,085,696 allocated bytes. Their exact
selected packed graph contains 30,339 members and occupies 222,183,424 allocated
bytes including sidecars. The 830,902,272-byte difference (792.4 MiB) is a measured
preparation margin across filesystems; it excludes directory/existing-store effects
and is **not actual reclaimed space**. The earlier six-file 812.1 MiB sample remains
a separate measurement. Final accounting must include complete affected session
object stores, selected logs/sidecars and directory allocation, and report filesystem
free space separately after the original descriptors are released.

A subsequent 33-file batch (2,020,462,248 original bytes) is now packed, reopened,
fully reconstructed and sealed, with all original identities/contents unchanged.
It passed unchanged resource admission after prior pressure stops. An additional
Rust readback was refused before child startup by a later resource check; no
extra payload job or guard relaxation followed. These are prepared copies only.

Source `e70732c92` passed hosted Test and Historical response recovery workflows;
53 focused Python checks, formatting and ops checks passed. Seven additional
reader call sites were reviewed: streamed history, capture validation, report/review
and historical recovery hashes reach reconstructed original bytes. Fixtures and
static review do not replace protected-reader/current-data or live B acceptance.

At15:11UTC, the corrected protected executable also built successfully and was
independently byte-hash verified; all eight exact production replay tests passed.
Current-data rehearsal, actual selected B body/metadata recall, qualified owner
admission and production conversion/recovery remain outstanding.
