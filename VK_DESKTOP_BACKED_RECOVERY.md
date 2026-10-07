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

The complete fresh-backup/full-rehearsal peak is not established by small tests.
Use real chain member sizes, the current full backup inventory, a 2 GiB free
floor and live-growth allowance. Full restore must not be started without enough
scratch. Historical directory moves without source evidence require the supported
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
