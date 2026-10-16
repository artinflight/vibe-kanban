# Backup content audit and lean recovery proposals

`vk_backup_content_audit.py` reads an existing verified reconciliation SQLite
index with read-only/immutable connections, an 8 MiB SQLite cache and no mmap.
It does not open source contents or archive payloads. It counts categories,
paths, tar regular payloads, hardlinks and distinct content hashes separately.
Current source inode identities are counted separately from complete content
hashes: an un-hashed source is not assumed equal to another file. Hash/inode and
prefix cardinalities are bounded; category labels never authorize exclusions.
The caller retains index provenance, input identity, resource admission and
scope memory/peak/swap/pressure receipts. Operational reports stay private.

Category totals are not compressed archive allocations. Compression spans files;
index entries do not reveal compressed bytes per category or historical allocated
blocks. A tar hardlink has logical file size but no second regular payload. Equal
hashes in independently stored files can be deduplicated even when tar did not
hardlink them. Per-category unique counts can overlap across categories and must
not be added as a global unique total. SQLite snapshot payloads and embedded
manifests may be outside the source-path comparison index; reconcile that gap
against accepted physical restore totals rather than call it zero.

A future normal nightly should preserve one self-contained manifest with all
required unique state. Developer dependency copies, tool/package caches, generated
outputs and virtual environments are candidates for reviewed exclusions. A name
such as node_modules, target, build or dist is not proof of reproducibility: it
can contain local patches, unpublished source, untracked work or the exact current
recovery artifact. Git objects can contain unpublished commits and history proof;
no generic Git-object exclusion is authorized. Native session histories, active
state/DBs, attachments and dirty work retain their existing recovery obligations.
Existing accepted full/partial chains and separately protected evidence are not
nightly retention candidates.

`vk_backup_lean_contract.project` is a pure fixture/proposal helper. It requires
exact indexed directory roots, preserved hash-bound rebuild inputs and an explicit
protected-work/runtime inventory. It rejects protected paths inside an exclusion,
missing/changed/excluded recipe inputs, Git-state exclusions and file/symlink roots.
An excluded canonical hardlink cannot strand a retained alias: the retained
manifest owns that content object. The helper never changes production plans or
files and never authorizes an exclusion. Same-account manifests are not a new
security boundary. The controller still needs authoritative dirty/untracked and
required-state coverage plus actual restore/rebuild acceptance for each proposed
root. A fixture with an offline pinned dependency is not proof that arbitrary
real registries, native modules or toolchains remain available after disaster.

`vk_backup_rebuild_proof.certify` adds an exact-root acceptance boundary for an
independently rebuilt artifact. The controller supplies the captured inventory,
approved roots, protected-work inventory and hash-pinned retained recipe/inputs.
The proof compares every descendant pathname, file size/hash and symlink literal,
then physically reads every rebuilt file within an explicit byte budget. Local
patches, extra ignored files, deleted package files, changed inputs and changes
during readback reject the entire proposed root. The reader callbacks must address
the independent rebuild, not the original dependency tree. This helper neither
executes recipes nor attests that a registry or toolchain is available.

The result includes both a reduced capture projection and the **complete original
restore catalog**, including original metadata and hardlink relationships. A
controller must retain that catalog, every required recipe/input object and any
content shared with retained aliases. Never pass the reduced projection alone to
an unchanged manifest/restore implementation: that would silently lose the omitted
files. Production adoption requires the integrated restorer to recreate the exact
complete catalog from a single current generation and verify it independently
without the old generation, original output directory or online package registry.
No real directory is certified merely by the offline fixture test. Pending proof
means keep the directory in the payload; it is not a reason to omit user work.

Report measured source logical, allocated (only where actually available), unique
content, archive compressed bytes and retained generation/chain bytes separately.
Lean-size estimates must name retained state, omitted candidate classes, database
and metadata gaps, compression assumptions and uncertainty. A smaller application
source-only backup is not equivalent to recovering native histories, attachments,
local repositories and all active user work. Do not promise MB-scale full recovery
without measured restore evidence. No scheduling, cleanup, archive reread or
production restore is part of these audit helpers.
