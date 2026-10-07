# Approved Desktop-Only Archive Retirement

## Authority And Exact Scope

Seamus approved exactly the27 redundant local archive files on October7 at
20:18:33UTC, message `Sentinel_b5eda5cf9a608191af86c25d35282c80`, replying to the
specific27-file/64.43GiB request. This supersedes the earlier pending-decision
status, not the recorded original manifests or sealed package evidence.

Allowlist:
`/mnt/vk-storage/vk-desktop-provider-20261007/retirement-approval-files.csv`.
Bound JSON manifest SHA256:
`e3c9b6909c65365254e08db1d8193f8eee4aaa1f2b408b60a30bb580e0cc62b8`.
No other file deletion, new production deployment, restart, Auto activation or
credit setting change follows from this approval. Keep the failed connector
candidate blocked; its developer owns correction, not a competing integration
writer. Production remains on the successful October5 release.

## Verification And Execution Evidence

Receipt root: `/mnt/vk-storage/vk-archive-retirement-20261007`.
`retire_approved.py` separates non-deleting verification from execution bound to
the exact approval ID. It checks CSV/JSON equality, all file identities and
hashes, exact B locators/full hashes, six unchanged chain heads/parents,
retained descriptor/member-inventory hashes and the70-file recovery package.
The portable recovery and acceptance bundles are freshly B-hash verified.
Packaged capture/resume/restore/installer evidence remains authenticated; no old
sealed controller is modified or replayed. PR149 `312ac0b20` remains the approved
Desktop-provider tool pin until validated integration or a reviewed successor.

Exact-file open references and relevant same-user backup consumers are checked
without privileged access. Inspection warnings remain in receipts; unrelated
inaccessible processes are not claimed inspected. Every unlink rechecks the
approved regular-file identity and writes/fsyncs its approved location/checksum
note first. There is no recursive deletion, directory removal or scope expansion.
All B copies, local directories, descriptors, manifests and unique recovery data
remain required and untouched. October5 deltas under the scope-release B folder
retain those exact locators rather than a guessed directory mapping.

Execution is complete: exactly27 approved copies were removed. Allocated space
reclaimed is69,178,728,448bytes (64.427711GiB); measured free-space increase is
69,178,585,088bytes. Immediate free space is81,789,153,280bytes (76.172085GiB),
not the earlier80GiB projection. Small receipt/note writes and concurrent normal
activity explain the difference between allocated reclaim and filesystem delta.

`verification.json` records all27 fresh local/B full hashes, the complete six
chains, retained package/bundle validation and no matching file opens or active
backup consumers. No same-user process was inaccessible. Lsof's two LXD nsfs
mount warnings are retained, not bypassed or claimed as privileged clearance.
These obsolete data archives are not service executables or live data roots.
`fresh-installer-validation.json` freshly rechecks all47 installed tool files.

`retirement-result.json` binds the approval and verification hashes to all27
exact unlinks and notes. `preservation-after.json` passes unchanged directory
identities/ownership/permissions and unchanged production/CU/frozen-fallback
processes. API health is200/success. With all27 local archive paths absent, the
actual packaged reader streams and verifies a complete36,104,364-byte B archive;
its manifest exactly matches the original authenticated inventory. All six
chain graphs and all70 recovery-package files still validate. No new attachment
upload/delete was performed: this operation touched archive payloads only;
attachment roots were compared for preservation, not certified by an upload test.

The original approval manifests and sealed historical evidence remain unchanged.
The consumed unlink operation must not be replayed. Small cleanup receipts and
all27 breadcrumbs are preserved through `preserve_receipts.py` in a separate
B evidence archive; `retirement-evidence-desktop.json` records its full hash.
Verified destination:
`desktop:B:/vk-backups/vk-archive-retirement-20261007/retirement-evidence-20261007.tar.gz`,
45,336bytes, SHA256
`416fceb4faa4f3e519384726a20833d6131115748c376c0b85b70e8680deee2c`.
This small receipt bundle is additional evidence, not a replacement for any of
the27 retained B archives or the portable recovery package.

Ops governance and diff checks pass. All three investigation/retirement scripts
parse successfully. Required `pnpm run format` completes Rust formatting and
then stops because frontend Prettier is absent; no application source changed.

## Independent Backup Preparation

The read-only full-scope sizing refresh uses the existing inventory with current
PR149 tools. It retains the original journal,45 errors, protected roots and
supplemental sources; it is not a repaired journal or fenced backup. Its new
receipts live under `fresh-backup-size` in this task root. Retirement does not
by itself prove the fresh-backup/full-rehearsal peak fits.

The fresh scan took185.817seconds, covering288592 regular files and69 databases
with zero read errors. The additional database is
`/home/mcp/.config/vibe-dot-connector/report-receipts.sqlite`; do not fall back to
the earlier67/68-database lists and omit this new durable ledger. All14 protected
roots are present; all45 journal errors and31 moves outside the old declared
roots remain recorded. There were212 concurrent changed paths: live estimate,
not a fenced snapshot or proof that the operator is idle.

Non-database bytes83,137,901,325; database/WAL allowance2,608,640,288. The
conservative uncompressed stream-verified capture estimate is98,572,928,030bytes.
Including2GiB floor and1GiB growth reserve gives101,794,153,502bytes, exceeding
immediate post-retirement space by20,005,000,222bytes. This is NOT measured
compressed size or a demand for additional storage. Next preparation must bound
or measure compressed capture and phased restore peak before the full job; do
not start an unguarded job, silently drop roots/databases or weaken recovery.

The connector's compiled review remains4passes/4failures at combined source
`eacafb3a1`; do not deploy that candidate. Corrected combined CU/native/HTTP
acceptance, complete fresh backup/appropriate restore/latest-data rollback,
runtime/model binding, promotion and actual operator/agent/grant drain remain
release gates. Keep Recommend, scheduling ON and credits OFF. No older database
may be restored over production.
