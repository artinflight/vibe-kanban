# Desktop-backed backup integration

This operational branch extends PR142 pin `528282d00` without deploying its
application tree. Production stays on the accepted October5 deployment. The
overnight VK9b3f82538/CU95e7aea47 release is pending separate approval.

## Implemented behavior

- Capture and delivery resume verify parents at the exact receipt-bound Desktop
  locator. A missing/corrupt/unreachable retained copy fails closed, even if a
  local archive happens to exist. No guessed directory mapping is permitted.
- Archive reads stream through SSH and zstd without retaining another compressed
  copy on SSD. Consumers accept scratch output only after the complete stream
  checksum succeeds. Local override remains explicit; Desktop-only forbids it.
- The existing direct-LAN route can be selected with `--desktop-hostname` and
  its matching `--desktop-host-key-alias`. Both are required together, and strict
  host-key verification remains enabled. This changes no network configuration.
- New capture verification hashes archived SQLite snapshots without creating a
  second `verified-payload` database tree. Original snapshot inputs remain.
- Legacy references can resolve through retained descriptors or a hash-verified
  portable recovery package. Preserve original descriptors, manifests and results.
- `vk_prepare.py package-tools` installs the resolver and replaces the remaining
  local-only parent assertion in a **new** handover controller. Missing resolver,
  unknown templates, tampering and attempts to revise sealed packages fail.
- `vk_recovery_package.py` creates a new tool/descriptor/head bundle. Its bound
  entrypoint verifies all files before capture, resume, audit or isolated restore.
  It never runs a service, switches routing or authorizes archive retirement.
- The actual rehearsal driver now downloads only checksum-verified metadata,
  then streams Desktop archives. `--low-peak-restore` retires exact private
  SQLite snapshot duplicates after each archive's full stream and every database
  hash/integrity assertion pass. Final restored databases, non-database files,
  manifests and original archives remain. Default restore retains duplicates.
  Restore writes enforce a 2 GiB free-space floor; failed assertions retain their
  unverified private copies. This is not permission to clean arbitrary fixtures.

## Evidence and adoption

Task receipts are under `/mnt/vk-storage/vk-desktop-backup-20261007/`.
The fresh real Desktop synthetic receipt is
`live-smoke/desktop-smoke-9o_4v3jp/smoke-result.json`: parent-only-on-B capture,
interrupted publication resume, and two-archive restore with both local fixture
archives absent passed. Only these new synthetic compressed copies were retired.

`vk_archive_migration.py` audits the exact OP inventory read-only: a fresh full
local hash, complete Desktop compressed stream hash, manifest/chain identity,
and restored SQLite hash/integrity checks. It inventories legacy sidecars and
never treats them as independent database snapshots. Only its exact new private
SQLite test files may be removed after all assertions and connections close.
Original archives, metadata, directories and incident evidence are untouched.
This audit does not claim a complete materialized filesystem restore.
Completed audit receipts can be resumed only after another full local and Desktop
hash, unchanged original/descriptor identity, and verified member-inventory hash.
Partial or failed work is not reused as acceptance. The default-route audit was
interrupted only to use the previously established direct route; originals stayed.

`real-chain-audit-3/chain-audit.json` now passes all 27 original archives and all
six head graphs. Full local/Desktop checksums cover 69,178,571,021 compressed
bytes; every archived SQLite snapshot was materialized and hash/integrity checked.
Non-database members were streamed, not installed as a full filesystem. Earlier
completed receipts were reused only with fresh full hashes and bound inventory.
Do not repeat the full stream audit merely to reword this evidence.

There are 27 protected originals, 69,178,728,448 allocated bytes (64.428 GiB).
Six head descriptors name overlapping chains. October5 remote deltas are partly
under the scope-release directory; the checked-in code uses receipt locators.
No original archive is disposable merely because this patch exists. A retirement
requires completed real-chain evidence, dependency/active-use clearance, adequate
recovery scratch and explicit approval for an exact list. Keep all directories.

## Next preparation and recovery entrypoint

Pin the committed operational source, not a working diff. Build a new portable
package with `vk_recovery_package.py --root NEW --inventory INVENTORY` and preserve
that package plus its externally recorded SHA256 on Desktop B. Use the package's
`tools/vk_recovery_package.py --root PACKAGE --` followed by normal
`vk_rolling_backup.py` arguments. Its `heads/0.json` through `heads/5.json` hold
the exact inventoried entrypoints. The package's descriptor registry also resolves
legacy parents if their former local descriptors are unavailable.

For a new handover, install the same source with `vk_prepare.py package-tools`
before sealing, bind the receipt into readiness, and run the private rehearsal.
Do not alter the accepted October5 package or reuse its consumed controller.
The remaining template-local parent assertion is migrated by the new installer;
using an old installer does not adopt this change.

## Remaining gates and recovery limits

`real-chain-space-plan.json` models ordered overwrites, deletions, database
replacement and conservative entry/hardlink allowances. Largest historical
restore estimates are 100,742,590,464 bytes normally and 84,809,768,960 bytes
(78.985 GiB) with phased private-snapshot retirement. These are sizing evidence,
not measured full restores. At that receipt, 19,321,933,824 bytes were free.
Retiring only 21 ancestors would leave 66,630,266,880 bytes, insufficient.
Retiring all 27 would leave 88,500,662,272 bytes: only 0.437 GiB beyond the
largest low-peak estimate plus the 2 GiB floor and 1 GiB growth reserve.
Fresh use/dependency/free-space checks and exact approval remain mandatory.

The complete current checkpoint is substantially larger than the earlier
changed-subtree estimate. `/mnt/vk-storage/vk-low-peak-20261007/full-checkpoint-size/`
sizes 288,350 regular files, 68 databases (including all previous 67),
82,599,304,943 non-database bytes and 2,604,078,296 database/WAL bytes.
The no-compression capture upper estimate is 97,940,190,668 bytes (91.214 GiB),
before the free floor/growth reserve or a simultaneous rehearsal. Even after all
27 conditional retirements, that leaves an 11.791 GiB conservative capture gap.
Compression may reduce it, but no measured compressed full checkpoint exists;
90 paths changed during the live scan, so this is not a fenced exact bound.
The old 17.001 GiB estimate was changed/recopy scope, not the complete checkpoint.
Do not start the full workload or claim combined peak acceptance from this data.

Historical directory moves without source evidence require the supported
new full checkpoint transition, retaining the old journal and all recovery limits;
never manufacture source events or silently omit protected roots.

Latest-data cutback never copies an old database over production. The pending
overnight release requires its matching compile-disabled v2 reader, SHA256
`2494f1dc7ca2de8ed26806603b86f9fa3e466c9f19a00e4aab2c8b9712a70c97`,
not the old production reader. Preserve all final candidate and acceptance
receipts. Recommend routing, scheduling ON and credits OFF stay unchanged.

Operations supplied the initial Desktop transport integration and 12 focused
tests. Staging owns legacy real-archive compatibility, portable package adoption,
actual-consumer preflight migration and expanded verification in this branch.
