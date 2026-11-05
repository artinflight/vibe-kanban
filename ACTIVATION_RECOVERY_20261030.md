# Antigravity activation and recovery evidence

This records the October 30 host-specific recipe. The exact live outcome belongs
in [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json); dated release directories are
consumed evidence, never a request to rerun them.

## Release provenance

- Backend source: `9a4179e8bdf38e93d1a81faca6c665cadd6fddc7`; sealed binary SHA256
  `137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
  Build receipt: `activation-build-1/RESULT.private.json` under the investigation
  root `/mnt/vk-storage/vk-deployment-reconcile-20261030`.
- Exact private retained-history input was read-only bound from the October 29
  source and checked against its deployed catalog hash. The public file remains
  `{}`. Do not build production from that empty public input.
- Matched frontend CI source: `aaacd278b30021814d04c9d2a9c616ccdae960d7`, run
  [40990973645](https://github.com/artinflight/vibe-kanban/actions/runs/40990973645).
  Artifact 12949546000, archive SHA256
  `e613e117f139648afdfab58f1997668525604ae947ce67686dab3c87e662b8f0`.
  All 417 manifest files were verified. Frontend inputs are identical between
  that revision and the backend build source; the binding receipt records this.
- `pair_frontend_assets.py` creates fresh candidate/fallback roots retaining 403
  hashed assets from both versions, verifies collisions byte-for-byte, and keeps
  each original index. It never overwrites the original releases. This protects
  lazy chunk loads in open tabs in either direction.
- Immediate fallback is the working `ddaaf64a` / `a63eb3a68173…` backend and its
  paired frontend. The older `d154fe9d` bundle is also retained. All use the same
  current compatible DB; no data restoration is a normal software cutback.
- Source integration is tracked by [PR #284](https://github.com/artinflight/vibe-kanban/pull/284).
  Rebase changes Git commit IDs, not the deployed build. Keep original source IDs,
  branch and immutable receipts; the PR merge event records integration into staging.

## Backup boundary and the rejected first attempt

The large native history is 3,129,262,080 bytes. A single Python SQLite serialize
allocation failed at this size. `vk_native_stream_backup.py` instead uses the
standard SQLite backup API to a uniquely owned file on verified `/dev/shm` tmpfs,
checks RAM/cgroup bounds, converts only the detached copy to standalone journal
mode with SQLite's API, independently reopens it for integrity, then streams
bounded objects to Desktop B. No backup payload is staged on the system disk.

The online history checkpoint was fully read back from B and sealed. A final
fence can reuse it only with exact DB/WAL/journal generation and native accepted-
object identity checks. `verify_retained_custody` uses the existing native B
`probe_accepted` protocol in batches of at most 64, authenticating the previous
independent readback receipts and encoded-file identities. It explicitly reports
**no fresh body decode and no new SQLite API epoch**. An online measured check
passed in 5.86 s. Changed or missing sources/objects require a fresh capture.

The first activation's final capture was correctly refused before installing a
binary. Its outer comparison treated SQLite's read-only creation of an empty WAL
on `goals_1.sqlite` as an external write. A detached RAM copy reproduced unchanged
main/journal identity and a newly created zero-byte WAL. The fix admits only that
exact open-time transition. Main changes, nonempty WALs, existing WAL replacement,
concurrent commits, changed source inodes and bad B readback still fail closed.
All final captured source generations and rollout selection are checked again.

`activation-release-1/RECOVERED.private.json` records return to original backend
PID 2100850 with **data_restored=false**. Its owned consumers resumed and the
original CU process was thawed. Failure evidence and exact used controller source
are retained. The corrected attempt uses a fresh `activation-release-2` package,
fresh current-data roundtrip and refreshed exact owner inventory.

## Repeatable package preparation

1. Verify mounted SSD, Desktop B availability, resource reserve, shared compiler
   ownership and current live manifest. Preserve private histories and dirty work.
2. Build/seal a matched candidate using the bounded offline recipe in the backend
   handoff; verify exact private history input and generated schema. Require the
   provider qualification only when its runtime/adapter behavior changes.
3. Create a **new private release directory**. Its `BINDING.private.json` pins
   candidate/fallback paths, sizes, hashes and source commits; frontend roots;
   both service drop-in hashes; incumbent connector hash; retained primitive and
   stream-backup hashes; current PID/invocation; exact native checkpoint receipt;
   private history selection/dataset; and cutback-bundle manifest hash. Copy the
   current service drop-in and connector as the fallback. Never use old owner IDs.
4. `python3 -B scripts/deployment/rehearse_current_pair.py FRESH_RELEASE_DIR`
   snapshots current data and runs candidate→fallback→candidate in an isolated
   network/filesystem sandbox. It verifies all 60 tables including the later-write
   probe, 99 migrations, 18 protected/four recent histories and both frontend
   indices/assets. Pin the completed receipt's path/hash in the binding.
5. `python3 -B scripts/deployment/antigravity_activation.py FRESH_RELEASE_DIR init`
   is a read-only preflight. It seals the binding hash and exact current unit
   identities/members, route, public pointer and connector. Recheck every input
   if a candidate or owner changes. A previous init is not permission to switch.
6. Under the operator's current deployment authorization, run its `supervise`
   mode in an independent bounded user service. The verified October 30 limits
   were MemoryHigh 7G, MemoryMax 9G, MemorySwapMax 0, CPUQuota 100%, Nice 15,
   TasksMax 160. It fences only exact owned/drained writers, freezes the original
   CU monitor, captures six native DBs and changed rollouts to B, snapshots current
   application SQLite and verifies source/queue/review stability before stopping
   the old runtime. It preserves the protected history reader.
7. Acceptance checks running hash, settings, histories, queue boundary, paired
   public UI, desktop/mobile browser rendering and Antigravity installation/model/
   supervised policy. Existing saved profiles are unchanged. After accepting new
   work, never stop it as an automatic rollback shortcut.
8. Mirror explicit sealed artifacts and terminal evidence with
   `mirror_release_evidence.py --manifest HASH_BOUND_ALLOWLIST --output NEW_RECEIPT`.
   It streams bounded chunks and independently reopens B objects; no tar staging.
   Keep private manifests/history/session identifiers out of Git and reports.

The 600 s verified-no-progress watchdog and separate 300 s recovery ceiling remain.
There is no total 50-minute cutoff. The first attempt exercised actual failure
recovery; tests exercise stalls, continued real progress, changed owners and
cleanup failure. Recovery now resumes the original CU monitor even if accepted-
release cleanup fails. Unknown runtime/consumer owners are preserved.

## Qualification limits

The real native provider test used four model turns total and passed approval,
denial, native resume and cancellation (about 40 ms to reap). Post-deployment
checks use zero additional inference. This does not claim a new production
workspace Antigravity conversation was run. Automatic provider failover remains
disabled; runtime reset/fork and alternate permission modes remain unsupported.
Future cutback after new executions/schema changes requires a fresh compatibility
check and drain. The immediate fallback recognizes Antigravity records but disables
Antigravity execution. Required private dependencies and the unlimited top-level
service memory settings remain explicitly documented.
