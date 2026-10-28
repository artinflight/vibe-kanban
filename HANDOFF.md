# Nightly pickup — October28,00:01EDT

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

Indexed counts00:01:5007file points pending,210names need reconciliation,
219SQL sources await image qualification. No source body/global scan.
C/CURRENT_PENDING_COUNTS_20261028T0404.private.json preserves this observation.

## Coordinator fixed and actually handed over, bodies untouched

Old c88 finisher PID4185660/start35971110 was proven idle/zero-body/nochildren,
then ONLY that coordinator stopped. Actual absence/empty cgroup/controller-lease
release are C/DEFERRED_FILE_IDLE_FINISHER_PREFLIGHT and RELEASED_20261028.private.json.
New single unit vk-nightly-current-composed-finisher-80deafdcd-20261028.service,
PID484248/start36301637, D/current-whole-cycle-80deafdcd-deferred-closure.
Source80deafdcdd36d0807ede4927c3ffd1841f252b4d; serviceSHA
b7baa6d9fe7197c592259ae17f5fea8871d173d8e30528746f50fdb986373377.
Actual preflight verifies new code, waiting only on same
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
Digests are in PREPARATION.private.json.
No frozen-input/existing-component replay. Actual timed ordinary run needs the
accepted current baseline and old owners/leases released; preserve original04EDT.

The new D/commissioner-journal-prepared-20261028 contains commissioner+journal
entrypoint plus exact legacy PID/birth list. PREPARATION.private.json binds all
hashes and command. PYTHONPATH must name ordinary-incremental-80deafdcd-prepared
so all unchanged worker80 source/config pins validate. The old f7 installer is
superseded for adoption, not deleted. No new cron or observer restart occurred.
The new entrypoint actually validated that package and skipped live FileV9 with
B_probed=false. It must later deliver/reopen/ACK on actual B after the controller
releases, before adoption. Actual current/ordinary composed restores remain open.

Real gap found: observer serves bounded local outbox; no between-run drainer was
installed. New minute journal-only pulse shares one owned cron block and yields
both controller/body lanes + exact old births; no source body/global scan.
Unchanged cursor skips B/SMART. Last success64KiB; log64KiB; attempt55+5s,
CPU5%/High128M/Max256M/Swap0/Tasks32. Existing admission/network classifier;
other failures retain review and do not retry denial. New installer independently
reopens actual journal report before adoption. See overnight guide.
19 focused checks including actual RAM inotify/native FULL/reopen/ACK pass;
actual production proof remains pending. Ops/diff/Rust format pass; full format
still stops at missing Prettier. Live jobs unchanged.

Next: collect SAME chain terminal receipts, resolve actual deferred points,
accept current composed restore, execute/time actual ordinary cycle and normal
restore, then commissioning gate/enable/next-run. Do not claim RAM fixtures or
historical cold proof as tonight's whole acceptance.
[Full current pickup](HANDOFF_NIGHTLY_HISTORY_20261027_2257.md),
[previous pickup](HANDOFF_NIGHTLY_HISTORY_20261027_2149.md),
[original history](HANDOFF_HISTORY_20261017.md),
[overnight acceptance](VK_NIGHTLY_OVERNIGHT_ACCEPTANCE.md).
