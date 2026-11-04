# Nightly commissioning — November 3, 2026 (EST)

The user requested the actual operational Nightly service. Historical October28
restore acceptance remains valid; it did not install a nightly scheduler. As of
19:30EST, body schedule is still OFF and no next run is claimed. No backend or
Staging restart is required. PR263 remains the sole source integration.

## Live ownership and exact continuation

D=/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261103.
The existing current-composition-v15-lease-wait job owns the metadata writer:
unit vk-nightly-current-composition-v15-20261103.service,
PID103466/start95825707. Read its STATUS/RESULT.private.json; do not duplicate it.
It reuses prior B namespace, qualification and accepted bodies, without reading
source bodies or putting indexes on SSD. The historical cold restore is reused.

The finite serial collector vk-nightly-serial-commissioning-20261103.service
PID377969 waits for this SAME job, then runs the exact worker-v17 bootstrap,
actual incremental qualification, normal composed restore and gated installer.
D/SERIAL_COMMISSIONING_STATUS.private.json and its pinned CONFIG identify stage
and original deadlines. Its own lease prevents a second collector. Child logs
retain only a64KiB RAM tail, fixed local health mirrors, and authoritative B
phase receipts. It does not enable scheduling from source tests or a partial set.
Check actual unit/PID/start and receipt before continuing or replacing anything.

P=D/worker-v17. PREPARATION.private.json pins every module and config:
normal service e2e797194ae4910454754bac0916dd929ea9240df4abc1932c480ac062cff2f3;
calendar3852bad67a3f0179ddfbaaddeaa8b94ea081b2bd7e4e12d736ebb33bc268c3dd;
bootstrapf7eea2ec5264472a659c2556347a51f0be41c2d9c5530c58f9cf293bde3341b6.
Exact code is HEAD65fff2188 plus current source fixes (uncommitted at this note).
Never modify loaded packages; install another version only after real leases
and exact terminal ownership permit handover. The calendar remains22–04Toronto,
with a hard04:00 stop preserving completed B objects/phase checkpoints.

## Actual repaired tracking and gap evidence

OldV11 died on local SQLite COMMIT BUSY; V12 filled its8MiB undrained outbox.
No between-run B delivery or recurring whole-cycle commissioning was installed.
The bounded COMMIT retry retries only SQLITE_BUSY within the SAME transaction,
checking STOP/admission and rolling back if it cannot finish. FULL/access/
integrity errors remain fatal. Automatic journal delivery is installed through
vk-nightly-journal-delivery.timer; it defers under real controller/body leases.
Its25percent CPU corrects measured startup overhead inside the55second envelope.
After verified cron installation the collector disables only this redundant
owned timer; the accepted cron pulse then delivers the journal each minute.

Observer vk-nightly-observer.service is enabled: PID3868069/start95598773,
epoch3006ed41a73f42d5be33c4ac08d59b18, configobserver-v14-runtime,
838481 watches/errors0, ~641MB actual cgroup memory/847MBpeak/swap0.
The owner-approved1048576 live watch ceiling is verified. No persistent sysctl
file was found in inspected standard locations; reboot continuity is NOT
claimed. A changed observer epoch requires explicit authenticated gap closure,
never relabeling the old epoch as continuous. Fixed local outbox/reserve is
~17MiB; growing namespace/map indexes and data are on B.

New119-source scope retains all117 prior roots and adds the actual current
backend and logical frontend pointer. Dot directory-alias changes are recorded.
Gap-reconciliation-v14-runtime completed18:51EST:852916 paths,98978directories,
0pending/replay errors, separate normal B reopen, terminal gap proof
0545a730d2c17ae80e690eef6122d13dee01bcfb5756e1ecdb7f9cb5c922333a.
Bnamespace305389568B;0source bodies/new body payload/SSD index bytes.
Old gaps and old source epochs remain explicit. This is metadata acceptance,
NOT tonight's file/SQL/runtime/current-baseline or ordinary-cycle acceptance.

## Current source and normal consumer

Actual backendPID645213 executabledeployment-reconcile-20261030/activation-build-1/
candidate-server; frontendcurrent -> invisible-workspaces-20261103-75db/paired/
candidate; Dotcurrent -> dot-delivery-recovery-20261103/python-release-v2.
Package captures18 exact pins/299631163B observation, reused by full unchanged
stat/xattr fingerprints without another299MB source hash. Runtime always-points
are requalified into distinct B components when changed; native fixtures prove
unchanged repeat uploads0 bytes.119-root retired-source contract keeps both
exact authority records consistent without retiring more data.

The normal UID1000 B-backed consumer VK-Candidate-20261009 remains usable:
399 logical providers/18physical roots all present, every inode unchanged.
Actual metadata-only probe passes. Fresh root placement is requalified before
packet sealing because B drvfs device numbers change across WSL mounts; inode,
B mount/registry/native identity, leases, hashes and access checks stay pinned.

## Acceptance still to collect

Read serial status and same job results first. Required: current file capture,
SQL/API images (4GiB individual cap), runtime integration, explicit descriptor/
original-gap dispositions, complete native body proof and independent normal
composed restore. Then an actual same-package incremental cycle <=6h/no later
than04:00, durable journal reopen, exact installed worker/config and next run.
No replay of a200GB cold copy or ordinary global source walk is needed.
RAM/tmpfs demand is freshly checked; existing SQL scratch/recovery is preserved.
B health/identity/STOP/capacity/access and original finite deadlines remain.
Desktop-off/readiness failure is not a drive-fault report. No source deletion.

Focused source/native-RAM tests and actual B namespace/provider checks pass;
ops and diff checks pass. Rust formatting passed; local full formatting stops
at missingPrettier. Tests are not production whole-cycle acceptance. Current
source/PR/installed package parity must be recorded after source preservation.

The accepted October28 evidence and exact B capsule/interface are preserved in
[prior handoff](HANDOFF_NIGHTLY_HISTORY_20261103_1930.md). Never present that
retained restore as a newly current or commissioned nightly backup.
