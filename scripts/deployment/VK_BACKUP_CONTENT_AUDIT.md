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

Report measured source logical, allocated (only where actually available), unique
content, archive compressed bytes and retained generation/chain bytes separately.
Lean-size estimates must name retained state, omitted candidate classes, database
and metadata gaps, compression assumptions and uncertainty. A smaller application
source-only backup is not equivalent to recovering native histories, attachments,
local repositories and all active user work. Do not promise MB-scale full recovery
without measured restore evidence. No scheduling, cleanup, archive reread or
production restore is part of these audit helpers.
