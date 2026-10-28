# Nightly pickup — October27,21:04EDT

Workspace604d/PR263 owns the sole Nightly package and scheduler. Separate worker;
no backend restart, Staging prompt/controller/cutover, unrelated cleanup or spend.
All backup bodies, indexes and temporary backup work stay Desktop B. Preserve
accepted162.70GB/137DB and later148/204SQL/components, partials and gap/epoch truth.

Owner recurring window is22:00–04:00 America/Toronto with a hard04:00 stop.
Tonight’s current baseline/restore is NOT accepted; scheduleOFF/nextNONE.
Initial backlog completion and recurring six-hour qualification remain separate.

D=/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261026
C=D/b-controls-v1. Read actual STATUS/RESULT/STOP and D/LATEST_STATUS.private.json.

## Actual controlled group-commit handover

The original fileV8 received graceful SIGINT20:53:07 after a guarded native
checkpoint. Its actual STOP records KeyboardInterrupt/all completed points kept.
Only its two proven idle/zero-payload SQL6/runtime5 waiters were stopped. All three
old units are terminal with empty cgroups; collected systemd default success
fields are NOT backup acceptance. Both real MCP/native writer leases were then
acquired, actual native health roundtrip passed, and retained map quick_check=ok.
22753accepted file rows/22781version-history rows remained, exceeding pre-stop
counts. Exact original qualified input was independently reopened unchanged.
C/GROUP_COMMIT_RELEASED_VERIFIED_20261028.private.json records that proof;
GROUP_COMMIT_LIVE_CHECKPOINT and OLD_TERMINAL retain the earlier observations.

Current chain actually loads tested source7ddf7674fdcf53b1d2bf907f45cd84c19bb0fd57:
- FileV9 vk-nightly-B-current-file-cycle-inodes-v9-20261027.service,
  PID3735301/start35669970, D/file-points-worker-B-inodes-v9-group-commit.
  controllerSHA6062e53feb4191105b7c2aa402efdedb00c99e336823e83a194b649283dfde2e;
  workerSHA8600262d83971216185da41d422c2a9a061807c4770e4e9008a98096c01412f0.
- SQL7 vk-nightly-B-current-SQL-cycle-inodes-v7-20261027.service,
  PID3735304/start35669999, D/current-SQL-cycle-inodes-v7-group-commit.
  controllerSHAd36e45e2bb264d1dccc09fff37d8abe2b602593b0a0c5a9d2d83605c567e5ddf.
- Runtime6 vk-nightly-B-runtime-component-cycle-v6-20261027.service,
  PID3735310/start35670033, D/runtime-component-cycle-v6-group-commit.
  controllerSHAc4d6e917e045ea545a2c10d273a22d8c200a67fb34ab5da4aafa62e4e1fdb884.

All retain CPU25%/High1536MiB/Max2GiB/Swap0/Tasks64. Actual commands/config/source
hashes and termination budgets are in C/GROUP_COMMIT_ACTUAL_INSTALLATION_20261028.private.json.
File’s original finite deadline remains00:33:13EDT October28 (369669.93monotonic);
SQL/runtime native/unit bounds end no later than owner04:00EDT/08:00UTC. No clock
was reset to extend the original file admission. Never blindly kill healthy work
at that boundary; collect its real result and reuse committed points if needed.

Same sourceV11 PID3849155/start32997998, epoch31ab8db49caf4f9699c7c0bd75c363a2,
configSHAe4bb83f02c2e71f8aebc768cb35d6feda255a181bf1cd24aa85d7dbe2c2641ed.
Live ceiling1048576/fixed bounded outbox/durableB; historical gaps remain explicit.
Exact retained input7b2ddad48873884a4e5dbb32513591f6e445b4b953bc31a802e29e1def8ea054
through5446784/since4404568. No new namespace census/DB recapture. SQL cohort stays
initial-current-inodes-v11-SQL-20261027-v1/indexconsistent-sql-inodes-v11-current-v1;
runtime indexruntime-dependencies-20261027-v1/same2files3200B.

## Measured new behavior and remaining work

FileV9 commits at most16fully independently read-back points together, bounded
proof metadata512KiB, guards before each row and commit. Atomic rollback/lost reply
retains objects and all accepted versions; old packages default to one point.
At20:59:26, actual native telemetry showed304new files/19group commits,
131559sourceB/79345encodedB and5.773s group-acceptance wait. SQL/runtime remain
serially waiting, not completed. A later actual sample is preserved in
C/GROUP_COMMIT_PRODUCTION_PROGRESS_0_20261028.private.json. Actual next156.22s
added624files/600762sourceB/266500encodedB in39group calls/6.964s wait, reaching
1296new files. Own memory events0; no ETA or same-work speedup is inferred. At released checkpoint45869file/219SQL/9replay points
remained; these counts are not bytes to transfer or a fresh current SQL request.

Finish the same file/SQL/runtime chain and resolve actual deferred/replay points.
SQL image ceiling is512MiB; use measured admission/retained layouts for any actual
larger-image deferral, without duplicate completed images. Revalidate14runtime
pins/3aliases and complete117current/111historical scope, preserving owner-retired
root evidence. Bind the independent actual SQL request to the current map; new
explicit dynamic-scope support fails on omitted DBs/roots/epoch changes.

Next unblocked integration work: finish actual whole-cycle/consumer configuration.
The prepared206older+41newer carrier candidates must become ONLY descriptor-
selected dependencies, with actual provider roots/leases. C/COMPOSED_RETAINED_PROVIDER_CANDIDATES_V2_20261027.private.json; SHA
136e184e0002079349c1c012787e15e6d2a34aee7847bfd8a9fc3ffb4a436e32. Actual UID1000
B-backed guest roots/gates are in COMPOSED_ACTUAL_READER_GATE_PREPARATION_20261027.private.json
SHA511d064d17a37b6e10582677cdae715ec8933b139186ddcc960fe1e0a537043a. Never require
all candidate archives merely because they were inventoried. Real body lanes
remain mandatory. Seal the map, complete native proof closure and normal leased
composed restore; then test the ordinary whole incremental window and adopt exact
service/calendar only after real acceptance. No whole-cycle service is installed.

290focused tests pass/one optional user-manager test skipped. Ops/diff/Rustformat
pass; full format stops at missing Prettier. Real RAM/native32point benchmark
used32acceptance requests versus2, medians35.82ms versus17.47ms; not production
throughput. Both later SQL and composed restore evidence remain required.

See [overnight acceptance](VK_NIGHTLY_OVERNIGHT_ACCEPTANCE.md),
[previous exact pickup](HANDOFF_NIGHTLY_HISTORY_20261027_2029.md), and
[retained release history](HANDOFF_HISTORY_20261017.md).
