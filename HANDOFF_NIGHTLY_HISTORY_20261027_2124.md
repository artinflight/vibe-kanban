# Nightly pickup — October27,21:24EDT

Workspace604d/PR263 owns the sole Nightly worker and scheduler; no backend restart
is required. Goal: tonight's complete current backup/independent restore, then
accepted automated22:00–04:00 America/Toronto with a hard04:00 stop. Schedule is
OFF/nextNONE; current production baseline and ordinary whole-cycle acceptance
are NOT complete. Direct Desktop B only; MCP SSD contains bounded code/control.
Preserve accepted162.70GB/137DB, later valid SQL/components and original gap truth.

D=/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261026
C=D/b-controls-v1. D/LATEST_STATUS.private.json is the current exact chain snapshot.

## Same actual production chain — no replacement

- FileV9 unit vk-nightly-B-current-file-cycle-inodes-v9-20261027.service,
  PID3735301/start35669970, D/file-points-worker-B-inodes-v9-group-commit.
- SQL7 unit vk-nightly-B-current-SQL-cycle-inodes-v7-20261027.service,
  PID3735304/start35669999, D/current-SQL-cycle-inodes-v7-group-commit.
- Runtime6 unit vk-nightly-B-runtime-component-cycle-v6-20261027.service,
  PID3735310/start35670033, D/runtime-component-cycle-v6-group-commit.

All load immutable tested7ddf7674fdcf53b1d2bf907f45cd84c19bb0fd57, CPU25%,
High1536MiB/Max2GiB/Swap0/Tasks64. File original finite deadline remains
00:33:13EDT October28/369669.93monotonic; SQL/runtime end by04:00EDT/08UTC.
SourceV11 PID3849155/start32997998, epoch31ab8db49caf4f9699c7c0bd75c363a2,
configSHAe4bb83f02c2e71f8aebc768cb35d6feda255a181bf1cd24aa85d7dbe2c2641ed
is unchanged. Same input7b2ddad48873884a4e5dbb32513591f6e445b4b953bc31a802e29e1def8ea054,
current-map seed22ed9b20187bda7f943b7a8e5b37e85427750b138a38e0741317b2435d20e17c,
SQL cohort initial-current-inodes-v11-SQL-20261027-v1/indexconsistent-sql-inodes-v11-current-v1,
runtime indexruntime-dependencies-20261027-v1 and2prepared files3200B.

At21:24EDT, FileV9 had4704NEW committed files,419401737source bytes read,
142539266encoded bytes sent; actual independent readbacks continue. One point
was deferred and must be honestly resolved/accounted for in later acceptance.
SQL/runtime still wait. No global inventory or DB recapture was started here.
Host PSIavg10=0, root17.62GB/SSD22.75GB available. Actual memory/events are in C/CURRENT_CHAIN_AND_FINISHER_20261028T0125.private.json,
SHAfa7982dba4184922947475eece455551abd42bc2fdd05f9d11cb75ed4675ba35.
No throughput ETA is inferred. Released checkpoint's45869file/219SQL/9replay
counts were dated metadata, not remaining bytes or evidence of full coverage.

## Actual self-collecting composed finisher

Tested sourcea37fda3897d14a7f6409ee20e2269f49c58e6291 is separately prepared in
D/current-whole-cycle-a37fda389-prepared (2032393B source/config/control metadata).
Exact service.private.json SHA
dbfc3e0992db816dee949fed2c1d862dff125f7fee2280736f84ee8e8ba495e0
passed actual code/config/source-observer preflight. It is now installed/running:
vk-nightly-current-composed-finisher-a37fda389-20261028.service,
PID3959283/start35819801, same CPU25%/High1536MiB/Max2GiB/Swap0/Tasks64,
absolute04:00EDT stop including unit termination budget. INSTALLATION.private.json
SHAcb2a2e55f7f08f3d47d8009d86ec1d4a3fa457e6b0536923f781803e1fb25da7.

The finisher currently reports awaiting-same-existing-component-chain/zero new
capture bytes. Never launch a second finisher or repeat completed capture. It
waits for exact original terminal identities, then acquires real MCP/native body
leases and independently reopens all actual B phase receipts before adoption.
It then consumes the recorded SQL suffix's remaining file points, seals the
complete ready map, audits content-proof/catalog closure and runs the ordinary
leased B-backed Linux composed restore. Only actual success can advance the B
ledger nightly-current-whole-cycle-v1 accepted pointer; source tests cannot.
Authoritative results remain B. Fixed STATUS/RESULT/STOP mirrors are retained;
stdout/stderr are null rather than unbounded local append logs.

The contract authorizes selection ONLY from its authenticated247carrier pool
using complete sealed map recipes. Unknown layers fail; unused archive providers
are excluded. Runtime late-binding independently reopens adopted B points and
compares their exact hashes/lengths/scope/sealed component against installed
finite source pins. Dynamic SQL scope independently reopens both main namespace
and actual cohort request; no DB may be omitted. Mandatory readbacks include all
runtime pins, explicit runtime components and current always-API SQL targets.
Normal consumer admission is528MiB peak tmpfs/8GiB total selected readback plus
actual4GiB RAM/1GiB swap headroom; actual demand exceeding those bounds fails
closed with all points retained. Refresh real admission if a larger proof is
actually needed. No arbitrary old selector budget is treated as transfer demand.

## Next unresolved work

Collect same V9→SQL7→runtime6→finisher actual results/STOP. Resolve actual deferred
points or SQL images above existing512MiB admission using measured retained work;
do not recapture the accepted cold set. All219 current SQL points were still
pending at the separate bounded native metadata query21:16EDT; no legacy SQL
providers were selected. Actual B health before/final passed; query0.312s, nofault.
All14finite source identities still matched their retained observations21:19.

After real current composed restore, qualify one ordinary timed incremental
whole cycle (reuse, interruption, Desktop-off/lowSSD/health/local bounds), then
adopt exact recurring22–04calendar and verify installed config/next run/health.
A source-only cron fix now drains output but keeps only its last64KiB per wakeup;
it is not applied to the active immutable finisher and no schedule was enabled.
124focused checks pass/one optional user-manager fixture skipped (125total).
Ops/diff/Rustformat pass; full pnpm format fails because Prettier is absent.

The body chain remains the prerequisite; preserve all historical proofs/gaps.
See [previous exact pickup](HANDOFF_NIGHTLY_HISTORY_20261027_2104.md),
[historical archive](HANDOFF_HISTORY_20261017.md), and
[acceptance details](VK_NIGHTLY_OVERNIGHT_ACCEPTANCE.md).
