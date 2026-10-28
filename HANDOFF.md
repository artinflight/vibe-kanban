# Nightly pickup — October27,23:14EDT

Goal: tonight's current backup/independent composed restore, then22–04Toronto
nightly automation with hard04:00stop. Separate worker; no backend restart.
Tonight's baseline/ordinary-cycle/commissioning remain incomplete. Actual
22:51crontab has ZERO Nightly commands/owned blocks: OFF, nextNONE. Preserve
162704613801B cold restore/137DB/later components/original gaps/all partials,
including unsealed RAM inode33476/2968010752B. Bodies/indexes B only.

D=/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261026
C=D/b-controls-v1. D/LATEST_STATUS.private.json is the current actual snapshot.
C/CURRENT_CHAIN_AND_PENDING_20261028T0310.private.json SHA
 7e8cdccbd034fac552f347a25ea95b90eb6c3b27fa7c8950f651262052e7df70;
shared pressure copy NIGHTLY_CURRENT_CHAIN_AND_PENDING_20261028.private.json.

## Same live components — do not duplicate or interrupt

- FileV9: vk-nightly-B-current-file-cycle-inodes-v9-20261027.service,
  PID3735301/start35669970, D/file-points-worker-B-inodes-v9-group-commit.
  Source7ddf7674fdcf53b1d2bf907f45cd84c19bb0fd57; groups16, CPU25%/High1536M/
  Max2G/Swap0/Tasks64. Original deadline00:33:13.838796EDT October28,
  monotonic369669.93 unchanged. At23:14:28911NEW committedfiles,
  8636454815sourceB/2669141620encodedB/8211.35s, still streaming, no stop/result.
  Memory.high297; max/OOM0, hostPSI0; full snapshot private. No ETA claimed.
- SQL8: vk-nightly-B-current-SQL-cycle-inodes-v8-20261027.service,
  PID4176947/start35965218, D/current-SQL-cycle-inodes-v8-large-admitted,
  source2a284d4ae. Waits SAME FileV9, same cohort/index, no SQL body yet.
  API image3.049GB measured; max3.25GiB, actual peak freshly checked at allocation.
  CPU25%/High7G/Max8G/Swap0/Tasks64; retained layout needs one extra image.
- Runtime7: vk-nightly-B-runtime-component-cycle-v7-20261027.service,
  PID4176951/start35965221, D/runtime-component-cycle-v7-large-SQL,
  source2a284d4ae; waits SAME SQL8, same2paths3200B/Max2G, no body yet.
- ObserverV11 PID3849155/start32997998, epoch31ab8db49caf4f9699c7c0bd75c363a2,
  fixed outbox/durableB unchanged. No new namespace census.

Exact map/input/cohort digests are in the full pickup/private receipt.
Pending-keyset23:06:12981names/6.11GBlogical, not transfer demand.
149names need reconciliation at23:06, including the CU JSON point.

## Coordinator fixed and actually handed over, bodies untouched

Old c88 finisher PID4185660/start35971110 was proven idle/zero-body/nochildren,
then ONLY that coordinator stopped. Actual absence/empty cgroup/controller-lease
release are C/DEFERRED_FILE_IDLE_FINISHER_PREFLIGHT and RELEASED_20261028.private.json.
New single unit vk-nightly-current-composed-finisher-80deafdcd-20261028.service,
PID484248/start36301637, D/current-whole-cycle-80deafdcd-deferred-closure.
Source80deafdcdd36d0807ede4927c3ffd1841f252b4d; serviceSHA
b7baa6d9fe7197c592259ae17f5fea8871d173d8e30528746f50fdb986373377.
Actual startup preflight/command/status verify new code, waiting only on same
file/SQL/runtime. CPU25%/High1536M/Max2G/Swap0/Tasks64; original cycle start
01:46:44.229164UTC and hard08:00UTC/04EDT preserved. No duplicate finisher.

It reopens exact terminal B receipts under both body leases, then closes recorded
unresolved files BEFORE acceptance. Old code rejected the changing CU point too
early. Original receipt/epoch/status survive; a new native reader proves closure. No new suffix or
repeat accepted bodies. Next: final delta/seal/native proof/normal leased restore.
Selected pins/runtime/API SQL restore sequentially with3.25GiB+16MiB scratch/
8GiB total and fresh actual-peak+4GiB memory admission. Integrity/lease/root/
identity/access/STOP/health guards remain.

## Ordinary package and final adoption are prepared, not accepted

D/ordinary-incremental-80deafdcd-prepared remains DISABLED/not a job.
Exact service/calendar digests are in PREPARATION.private.json and full pickup.
Service/calendar preflight and actual crontab-stdin syntax pass. No existing-
component/frozen-input replay; fresh bounded deltas, High7G/Max8G/Swap0/Tasks64,
64KiB cron tail. No cron installed. Its actual timed run still needs baseline
acceptance and prior controller/body owners actually released. Run using
--scheduled-night 2026-10-27 and --hard-deadline-utc 2026-10-28T08:00:00+00:00
with separate correct CLI arguments and original hard04 bounds (see full pickup).

Installerf7cef9f0d618b7a7d160aae8a00270257246b2bd is separately prepared:
D/commissioner-f7cef9f0d/vk_nightly_commission.py,
Use PYTHONPATH=D/ordinary-incremental-80deafdcd-prepared, python3 -B -S,
--calendar <exact disabled config> --sha256 <315316...>; PREPARATION binds both.
Default only qualifies actual native B evidence; authorized --install follows
ordinary exact-template/phase-chain/normal-restore/window proof, under actual
leases/guards. Versioned enabled config/own cron readback/next run; no deletion.
It has NOT executed. Worker80 and installerf7 are distinct pinned sources.

169 focused tests plus3 post-storage-guard checks pass. Native RAM tests cover
changed-file closure/receipt preservation/no-recopy and finite positive SSH255
network retries; access/STOP/host-key/reported faults stay blocking. Ops/diff/Rustformat pass; full format stops at missing local Prettier.
PR263 mergeable; collect newer exact-head CI.

Next: collect SAME chain terminal receipts, resolve actual deferred points,
accept current composed restore, execute/time actual ordinary cycle and normal
restore, then commissioning gate/enable/next-run. Do not claim RAM fixtures or
historical cold proof as tonight's whole acceptance.
[Full current pickup](HANDOFF_NIGHTLY_HISTORY_20261027_2257.md),
[previous pickup](HANDOFF_NIGHTLY_HISTORY_20261027_2149.md),
[original history](HANDOFF_HISTORY_20261017.md),
[overnight acceptance](VK_NIGHTLY_OVERNIGHT_ACCEPTANCE.md).
