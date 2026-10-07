# Runtime Lifecycle Backup Follow-Up

## Scope

Resolve the two runtime-file warnings independently of the connector repair.
No production restart, routing, database restore, badge clearing, agent pause,
Recommend/credit/scheduling change or incompatible-candidate deployment occurs.
Existing conditional cutover authority remains subject to all separate gates.

## Findings And Safeguards

The timestamped shell file is generated from the current shell environment and
deleted on release; the writer-lock file holds OS ownership and is deleted when
released. Neither is conversation history. Existing files remain backed up.
Regeneration is not a claim of byte-identical historical environment recovery.
Source and installed runtime evidence is in
`/mnt/vk-storage/vk-runtime-backup-20261007/lifecycle-evidence.json`.
It records cached source3d2ee51 (0.153.4, not exact build provenance) and actual
CLI0.159.2 binary SHA1748767b230ebfc3d4ab7e4e254920d0c0ad9691fd8c11f190e7d44511a4a92e
with matching lifecycle diagnostics. No secret environment values were printed.

PR149 successor49cf82d603b765b4ceaf5a8b4462f046e6181c0f is committed/pushed.
198 deployment regressions pass in25.914s;11 focused tests include a real
archive/delta/restore of runtime deletion alongside preserved history/dirty work.
The classifier permits individual UUID/nanosecond shell and UUID lock names only,
within known owned non-symlink roots and existing scope. Online observed deletion
and absence remain necessary. Frozen capture, missing sessions, unknown names,
present/recreated files, symlinks, foreign ownership and required paths fail.

The prior warning set now classifies under these checks, recorded in
`prior-warning-classification.json`. The original failed archive/receipts are not
modified or promoted. This task starts a separate full capture, retaining the
original journal instance, all14 protected roots,69 required DBs and all prior
historical journal/missing-edit evidence. No protected roots were dropped.

## Tool Adoption

New verified70-file package:
`/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60`.
The current capture driver verifies this pin before imports are used. Next
production controller must bind it into a new package, not modify a consumed one.
B package: `B:/vk-backups/vk-runtime-backup-20261007/recovery-tools-49cf82d60.tar.gz`,
4,977,437bytes SHA256
`bb98c78bcee45a7c873c54e9904f87ba6fa541332a4f97b2633c54d50299ec76`.
`tools-desktop.json` records the full-file remote verification. B remains the
sole retained archive provider, with SSD used for temporary capture/restore work.

## Current Measured Work

Fresh capture/recovery receipts belong under
`/mnt/vk-storage/vk-runtime-backup-20261007`. The bounded driver is
`scripts/testing/runtime_backup_20261007.py`: per-stage one-hour ceiling and8GiB
free-space floor, terminating only its own subprocess group if a bound is hit.
The new full capture must hash-verify every SQLite payload and deliver archive
and metadata to B before success; then a current delta and actual B-only bounded
restore must pass. No archive or unique data is deleted by the driver. Private
duplicate restore DBs can be retired only by the existing verified phase policy.

Fresh full capture and delivery passed in1578.084s. All69 DBs are newly
snapshotted;23,449,698,976 archive bytes and112,098 metadata bytes are full-hash
verified on B. Checkpoint02136af9b9c24c08bccba0868864e597 SHA256
`9beef7c6ca1e533b9861f186d6654e5db0c4d7e13482bdddc70f0673b9b32e4d`.
Its only archive warning is the verified non-payload updater socket.

Catch-up430d3a842f5d4216862a1703e33232b8 passed in93.548s, refreshing7 DBs and
reusing62 verified snapshots.319,227,816 archive bytes and94,589 metadata bytes
are verified on B. Delta SHA256
`4b2a3881da51148f0c66f773ac292476fab9b3a973f734f09af17e37680f0c53`.
It has no archive warnings and retains384 observed deletion tombstones. Both
archive descriptors are alongside their payloads under the same B task path.
Minimum observed free bytes:20,533,690,368 during full capture and18,908,803,072
during catch-up. These are whole-host measurements, including concurrent usage.
No floor/deadline stop occurred.

B-only recovery passed in408.650s. All69 restored databases passed hashes and
SQLite integrity; all32 selected real files passed content/mode checks. The full
inventory accounts for329,041 entries (329,040 payload entries plus the known
socket), and the delta accounts for219/219. All14 protected roots are accounted
for. Both complete compressed B streams passed their expected hashes, without
downloading compressed copies.76 private duplicate database payloads were retired
only after their assertions; the final69 restored databases remain available.
Minimum free space was13,797,892,096bytes (12.85GiB), above the8GiB floor;
observed whole-host consumption during recovery was5,127,680,000bytes.

The independently full-hash-verified B evidence bundle is
`B:/vk-backups/vk-runtime-backup-20261007/runtime-backup-evidence.tar.gz`,
115,405bytes, SHA256
`65ca093990ccacebe24da9872a61e80b1fde8c8eda87e40dceb8a27132a98bd1`.
It contains the exact driver, logs and measurement/recovery receipts, not secret
environment values or a substitute for the retained archive payloads.

Bounded B recovery materializes all required DBs and32 selected real files while
verifying complete compressed streams. It does not materialize the entire non-DB
tree and is not the release-specific full handover/latest-v2 rollback rehearsal.
That rehearsal, corrected combined acceptance, final current-data capture and
actual inactivity checks remain deployment gates. Chat silence is not idle proof.

## Validation And Remaining Boundary

The198 operational regressions,11 focused tests, actual fresh full/delta/B restore,
ops governance and diff checks pass. Required formatting was attempted in both
worktrees: the operational sparse checkout lacks crates/capacity-guard/Cargo.toml;
the owner checkout completed Rust formatting but lacks the Prettier executable.
No application Rust/frontend changes were made for this independent backup fix.

Production remains the October5 instance. The separately owned combined candidate
2bc909d63 is still blocked on historical goal/sleep replay and CI repairs; this
task does not certify it. Next preparation must bind the verified49cf82d60 tools
into its new package, perform the release-specific complete handover/latest-v2
rollback rehearsal, and refresh capture plus actual agent/operator-idle checks.
No failed partial archive was promoted, historical recovery exception erased,
production service restarted, or current database replaced.
