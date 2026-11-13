# Reproducing and managing the recovered Vibe deployment

The Antigravity-enabled release is live, accepted October 30 at 03:18:14 UTC.
[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json) records exact identity and limitations;
[the checklist](DEPLOYMENT_CHECKLIST_20261030.md) records validation scope.
[Activation/recovery evidence](ACTIVATION_RECOVERY_20261030.md) supplies the fresh-
package procedure, actual failed-boundary recovery and corrected successful run.

## Serving components and preserved data

Public `https://vibe.local` → gateway 4720 → history proxy 5640 → backend 5621,
service `vibe-kanban-native-review-20261015.service`. Backend source is
`9a4179e8bdf38e93d1a81faca6c665cadd6fddc7`; binary SHA256
`137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
Last observed PID 645213. These observations do not authorize a future stop/kill.
Version 0.1.42 alone cannot identify the build. Public and backend frontend roots
now match: JS `index-DNMY17oB.js`, CSS `index-CUBB2mA2.css`. Both paired frontend
roots retain 403 old/new hashed assets; open-tab old assets were checked over HTTPS.

The same green database resolves to
`/mnt/vk-storage/vk-original-access-recovery-20261025T1748/working90.sqlite`, with
99 migrations. Preserve its latest writes/sidecars, original native Codex home,
rollout paths, attachments, attention/review state, queues and saved settings.
The protected `vk-chat-history-readonly-20261010.service` remains untouched.
Blue remains retired. Do not create a second writer or re-enable cleanup from
obsolete instructions. Seventeen uncertain inputs were retained without replay.

Antigravity is available with tested `gemini-3.8-flash-low`, supervised permissions
and the existing personal account. Service-scoped executable/model defaults leave
saved profiles unchanged. Actual approval/denial/resume/cancel passed in the Vibe
adapter; post-deployment API checks sent no inference. The four-turn native test
budget is spent. No new production workspace conversation was created for QA.
[Antigravity guide](VK_ANTIGRAVITY_ACP.md) contains runtime/harness hashes and limits.

## Repeat the read-only live verification

```sh
python3 -B scripts/deployment/read_live.py --manifest LIVE_DEPLOYMENT.json --ca VERIFIED_CA_FILE --output NEW_SSD_RECEIPT.json
```

Use the installed trusted origin CA, never disabled TLS validation. The tool
checks stable service identity/executable, backend/public health and capabilities,
JS/CSS byte parity, selected frontend and current DB target/inode/migrations.
It does not read conversation contents or mutate the system. Post-activation
receipt `LIVE_READBACK_POST_ACTIVATION.safe.json` passed at 03:20:10 UTC.
`LIVE_READBACK_PRE_PR284_MERGE.safe.json` independently passed at 09:20:33 UTC
with `mutation=false`, confirming the same deployed executable/frontend and DB.
Separately check `/api/agents/check-availability?executor=ANTIGRAVITY` and
`/api/agents/preset-options?executor=ANTIGRAVITY`; expected installation found,
model `gemini-3.8-flash-low`, permission `SUPERVISED`. This is not authentication
proof by itself; real account acceptance is recorded independently.

## Source custody and required private inputs

The clean branch starts at fork/staging `2bf2676d2d3841c252fa7f2a9b4e7993128bb093`.
`fork` is artinflight/vibe-kanban; `origin` is upstream BloopAI in this checkout.
Confirm remote URLs before syncing. Preserve the dirty canonical checkout and
unrelated work. [PR #284](https://github.com/artinflight/vibe-kanban/pull/284)
targets staging using the operator-requested rebase method; the merge event is the
authoritative integration record. Main promotion remains separate.

- `scripts/deployment/releases/20261029-source.json` retains 134 historical deployed
  source hashes and reconciled public hashes. Never overwrite its old deployed
  hashes to make them match a newer release. October 30 provenance is separate.
- Public `crates/server/src/routes/execution_processes/historical_response/additional-reviewed-requests.json`
  intentionally contains `{}`. Production needs the exact private sixteen-entry
  input from `/mnt/vk-storage/vk-new-build-repair-20261029/source/` at that relative
  path, authenticated against the historical catalog's deployed hash. Do not
  publish its bindings or substitute a public build for the retained reader.
- The private-input omission and adjusted public test cardinality are intentional;
  Clippy/format fixes and the explicit supervised new/load handshake are recorded
  source changes. Actual source is pinned by the build receipt, not current HEAD.
- `scripts/deployment/` contains queue/writer/ingress fences, history acceptance,
  proven orphan repair, native-B/SQL update and reuse, independent supervision,
  owned activation, current-data rehearsal, bounded RAM backup, asset retention,
  live readback and release mirroring. Host adapters still depend on the exact
  retained Nightly controls/profile; this is not a generic installer.
- `scripts/deployment/incidents/20261029/` holds 27 inert source templates. Dated
  PIDs, leases, manifests and controllers are consumed historical evidence.
- `scripts/dot-connector/deployed-20261029/` holds 50 hash-bound source/test files.
  One private usage-workspace binding is omitted. Tunnel, approval-event bridge,
  Node/MCP runtime, subscriptions and receipt stores are retained dependencies.

```sh
python3 -B scripts/deployment/source_custody.py --root . --catalog scripts/deployment/releases/20261029-source.json
python3 -B scripts/deployment/source_custody.py --root scripts/deployment/incidents/20261029 --catalog scripts/deployment/incidents/20261029/sources.json
python3 -B scripts/deployment/source_custody.py --root scripts/dot-connector/deployed-20261029 --catalog scripts/dot-connector/deployed-20261029/sources.json
```

Private incident/connector token maps remain under the investigation root as
`INCIDENT_TEMPLATE_BINDINGS.private.json` and `CONNECTOR_BINDINGS.private.json`.
`source_custody.py --bindings PRIVATE_MAP` verifies original hashes without writing;
optional `--output NEW_SSD_DIRECTORY` reconstructs only after all hashes pass, with
restrictive modes and inert suffixes. It never executes or installs. Backend
private JSON is a separate exact input. Byte-identical public rebuild is not claimed.

## Rebuild procedure

1. Create a clean SSD worktree at the intended source. Reconcile intended features,
   private dependencies, live repairs and generated schema. Do not reset canonical work.
2. Use the archived bounded offline recipe (`promotion/build-command.json.txt`,
   `guest.py.txt`, `build-v3.py.txt`, `prepare.py.txt`) with fresh source/tool/config
   bindings and live owner observations. Do not execute stale controllers. The
   October 30 `activation-build-1` guard/command/result files record the actual
   invocation. Rust nightly 2025-12-04, recovered offline registry, SQLX_OFFLINE,
   one job, profile `acceptance`, incremental off and the already-owned SSD target
   were used. No production DB/account state is writable in the build sandbox.
3. Hold the existing owned-build lock/shared-target lease. Continuously require
   mounted SSD, >3 GiB free SSD and >3 GiB MemAvailable. User-service build limits:
   MemoryHigh 4G, MemoryMax 5G, MemorySwapMax 0, CPUQuota 100%, Nice 15, TasksMax 160.
   Never duplicate a large target or install bulk dependencies on the system disk.
4. Run focused tests and generated-type checks; require branch CI. Seal the final
   binary by copy/fsync/hash; never deploy mutable target output. Hosted workflow
   `deployment-frontend-artifact.yml` produces the matching frontend with a file
   manifest and artifact-viewer verification. Verify archive and every file hash.
5. Prepare both frontend roots with `pair_frontend_assets.py`; collisions must be
   byte-identical. Preserve exact private input and verify all protected histories.
   Use the fresh-package recipe linked above for rehearsal, backup and activation.

## Hosted validation and source integration

All eight hosted workflows passed on reconciliation commit
`a4213813210ea15affb1d91a306883cb27f452e3`, including the final recovery and mirror
tooling. These are commit-specific results; any later documentation commit must
pass its own required PR checks before merge.

| Workflow | Successful run |
| --- | --- |
| Test | [40997851611](https://github.com/artinflight/vibe-kanban/actions/runs/40997851611) |
| Deployment recovery contracts | [40997851621](https://github.com/artinflight/vibe-kanban/actions/runs/40997851621) |
| Deployment frontend artifact | [40997851518](https://github.com/artinflight/vibe-kanban/actions/runs/40997851518) |
| Dot steering acceptance artifact | [40997851669](https://github.com/artinflight/vibe-kanban/actions/runs/40997851669) |
| Bounded native final repair | [40997851763](https://github.com/artinflight/vibe-kanban/actions/runs/40997851763) |
| Historical response recovery | [40997851506](https://github.com/artinflight/vibe-kanban/actions/runs/40997851506) |
| Scheduled goal acceptance artifacts | [40997851493](https://github.com/artinflight/vibe-kanban/actions/runs/40997851493) |
| Native reviewer compatibility | [40997851531](https://github.com/artinflight/vibe-kanban/actions/runs/40997851531) |

Hosted private remote checks skip without the deploy key; the combined capture
consent acceptance job was also skipped. Neither is certified by a green workflow.
Local format, governance, focused native and recovery/source tests passed.

[PR #284](https://github.com/artinflight/vibe-kanban/pull/284) is the durable record
of final-head checks, review and rebase integration into staging. Rebase assigns
new staging commit IDs. Preserve the original reconciliation branch, immutable
build source `9a4179e8b`, frontend artifact source and release/catalog receipts;
do not rewrite deployed provenance to the new staging HEAD. A Git merge does not
deploy a binary or change data. Main promotion and any future deployment require
their own validation. Refresh the clean reference worktrees under
`/mnt/vk-storage/vk-reference/{main,staging}` after merge, preserving the unrelated
dirty canonical checkout.

Top-level live MemoryHigh/MemoryMax remain unlimited;
per-executor 1500M/3000M and native capacity admission are separate safeguards.
Whole-host OOM resilience is not certified by this task.

## Failure recovery and safe cutback

Follow the backend restart protocol and current operator authorization. Complete
slow work online, then recheck exact owners, drained work/queues, ingress/capacity
custody and physical writer fences. Preserve new or unknown owners. The actual
first attempt refused before installing a binary; recovery restored public service
and owned consumers on the original PID, without restoring any database. The
strict empty-WAL fix and fresh rehearsal preceded the successful second package.

The 50-minute total cutoff remains removed. A separate supervisor terminates only
its worker group after 600 seconds without verified progress and invokes recovery
with a 300-second limit. Progress means completed work/data, not a heartbeat. Tests
cover stalls, continuing progress, worker failure and changed owners. A cleanup
fix ensures the original CU monitor resumes even after accepted-release cleanup
fails. Preserve failure receipts and never blindly rerun a consumed package.

Immediate fallback is source `ddaaf64a5870124842c385e490a0b40e1174db86`, binary
`a63eb3a68173d90b894bd933b6676d989ec8325d7ba31135ea52b214bd06c336`, with the saved
working drop-in and paired frontend. Fresh current-copy candidate→fallback→candidate
preserved all 60 tables including a later-write probe, 99 migrations, 18 protected
and four recent histories. The older `d154fe9d`/`95312f4f…` T63 bundle remains retained,
but is not the immediate fallback qualified for this activation. After new work
or schema changes, drain/recheck compatibility and take a fresh backup. Cut back
software against latest data; never restore stale data over new writes. Antigravity
execution becomes disabled on the immediate fallback; records remain recognizable.

## Evidence and handoff

October 29 recovery: `/mnt/vk-storage/vk-new-build-repair-20261029`.
October 30 investigation: `/mnt/vk-storage/vk-deployment-reconcile-20261030`.
Successful package: `activation-release-2`; rejected/recovered package:
`activation-release-1`. Keep both and all prior fallback artifacts.

Key successful receipts: `RESULT.private.json`, `ACCEPTED.private.json`,
`ANTIGRAVITY_LIVE.safe.json`, `PUBLIC_ANTIGRAVITY.safe.json`,
`BROWSER_CANDIDATE.private.json`, `roundtrip/RESULT.private.json`,
`CURRENT_BACKUP.private.json`, `CURRENT_BACKUP_DESCRIPTOR.private.json`,
`native-recovery-fenced/RECEIPT.private.json` and release mirror receipt.
Six native DBs plus nine changed rollouts total 3,607,837,269 bytes. All were backed
by independently verified B bodies; unchanged large-image reuse explicitly carries
its old API epoch plus fresh native custody proof. Backups use
`desktop:B:/vk-backups/vk-nightly-efficiency-20261026/objects-v1`; exact descriptors
and hashes, not a directory name, establish recovery evidence.
`RELEASE_B.private.json` verifies 45 sealed release items (201,792,843 bytes).
`TERMINAL_B.private.json` verifies 62 terminal/reconstruction items (7,944,662
bytes), including 53 fallback-only assets. `FRONTEND_RECOVERY.safe.json` records
reconstruction from the verified frontend archive plus those retained assets;
keep each release's original index. Both mirrors completed without disk payload
staging.

Remaining limits: private host/history dependencies, separate main promotion,
no extra production-workspace inference, unlimited top-level
service memory, disabled automatic failover/external-effect continuation and
unsupported Antigravity reset/fork/non-supervised modes. Preserve Recommend and
all existing approval/billing controls. No more operator sign-in is needed.
