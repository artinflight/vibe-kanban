# October 6 Archive Dependency Review

This is read-only recovery-owner analysis, not deletion clearance. No archive,
backup descriptor, journal, workspace or retained test evidence was removed.

OP's verified inventory has27 archives. The21 older ancestors account for
47,308,333,056 allocated bytes (44.059GiB); six directly referenced starting
points account for20.368GiB and remain local. All21 ancestors are still named
chain dependencies, not abandoned backups. **None is cleared for deletion yet.**

## Verified And Outstanding

OP's full local/Desktop SHA256 checks and27 descriptor checks passed. Staging
rechecked each current local size/mtime against that verified inventory, each
current starting descriptor/head hash, and complete inventory coverage for all
six referenced chains. Exact mappings and proposed restore commands are exported
to `/mnt/vk-storage/vk-first-run-gates-20261006/archive-retirement-review.json`.
The record incorporates OP's evidence hash rather than claiming a second full
64GiB hash scan occurred.

Pinned PR142 tooling is unchanged. `verified_parent` requires the direct parent
archive at its recorded local path. Retaining the six named heads preserves that
specific capture check, but does not preserve default full-chain restoration:
`restore_chain` still follows local ancestor paths. Its `--archive-directory`
accepts already downloaded copies; it does not automatically retrieve Desktop
files. No descriptor or embedded parent path should be rewritten to hide this.

October5's retained `online-restore-check.json` proves the checkpoint's full
compressed stream,67 SQLite payloads and targeted3052-file five-root restoration.
It is not a fresh full restoration of all three proposed Desktop-only chains.
Current roughly3GiB SSD headroom is insufficient for downloading a20GiB checkpoint
plus expanded restoration. The27 existing Desktop copies remain protected.

## Recovery Procedure To Verify Before Retirement

For a selected retained head, use its exact chain in the exported JSON. Preserve
the head descriptor, every archive/descriptor checksum, local loose manifests,
original snapshots, incident receipts and directory structure. Fetch every chain
member from its recorded Desktop location into a new mounted-SSD task download
directory, checking each full SHA256. Do not assume a common Desktop directory:
the October5 checkpoint and its deltas are stored under different task roots.

Run the exported pinned `verify-restore` command with `--archive-directory`
pointing at those downloaded copies and a new isolated destination beneath the
original backup task root. The tool deliberately rejects existing destinations
and destinations outside that task. Verify full-chain stream/file/SQLite/link
results and record elapsed time and scratch peak. Never aim this verification
at production or restore an old database over current data.

This procedure is source-verified but **not newly executed** for all six heads.
It needs adequate scratch capacity, acceptance of Desktop availability/recovery
time, and recovery-owner verification before local-cache retirement. A small
synthetic restore would not establish the capacity or timing of these real chains.

## Exact Conditional Scope

The21 filenames in OP evidence `conditional_archive_scopes.ancestor_files` are
the complete possible ancestor-only scope; do not enlarge it. Retain all six in
`direct_head_files`, including October5 checkpoint `b8b117feb1db474f9481096447b762c1`.
After actual recovery clearance, other consumers and protected-process references
still need a fresh check, and the operator must separately authorize exact local
filenames. Leave path/checksum/location notes for retired local copies.

No permission to delete Desktop originals, shared Rust output, the held3.711GiB
incident target, production data or pending first-run candidate/fallback artifacts
is implied. The4.13GiB staging temporary-file allowlist remains separately blocked
by protected-process visibility; do not bypass that check.
