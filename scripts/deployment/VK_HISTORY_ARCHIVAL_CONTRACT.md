# Complete-session backup compaction: experiment and restore contract

This is source-only investigation, not an adopted archive format or authorization
to trim history, change a capture plan, remove local files or retire a backup.
Operational samples, identities, sizes and receipts stay in the private handoff.
The separate consolidation owner retains ownership of the B backup and all held
payloads. This work never opens those payloads.

## Required recovery outcomes

There is no supported universal last-N-turn, last-N-token or date cutoff. A model
context window is not the complete durable session. Preserve every historical
session, including failed/interrupted turns and any unterminated captured tail.
Date-based removal eventually destroys whole sessions and is not this design.

For active-agent resume, retain consistent application/provider databases and
their references, the complete native rollout for the chosen safe resume anchor,
the associated working tree (including dirty/untracked/ignored local work), Git
state, required configuration, durable goal/checkpoint state and referenced
attachments within the already approved recovery scope. A summary alone is not
a native resume anchor. Credential recovery follows the existing approved route;
this contract does not add credential collection. Process RAM and in-flight tool
effects are not reconstructed by copying a transcript.

The inspected application source selects a completed, successful agent turn with
a nonempty summary and provider session ID, then calls `thread/resume`. Vibe's
completed conversation reader reloads raw process logs and normalizes them when
no resident store exists; database logs are a fallback. Preserve the database
relationships among workspace, session, execution and coding-agent turn, provider
session/message identifiers, original log paths, raw process logs, native
rollouts, relevant provider state/indexes, attachments and compatible reader
artifacts. Do not substitute rendered chat or summaries for either raw layer.

The inspected raw logger stores Stdout/Stderr and updates identity rows. It does
not persist every normalized JsonPatch as a process-log record. Its provider
callback logs protocol responses, while completed UI pagination reduces replay
in memory. Neither UI pagination nor context compaction establishes permission
to discard original logs. Source inspection is not a newly run real-agent resume
or an acceptance of archive-backed browsing.

## Complete archive plus small recovery working set

Keep one independent current manifest, not a sequence of parent manifests. Its
closure includes consistent current databases, active native sessions and log
tails, current recovery artifacts, all preserved work, and a catalog of EVERY
historical session/execution/native ID and its exact original byte stream.
Immutable completed sessions may share content-addressed objects. An active
session may reuse sealed prefix objects and append a newly captured tail; the
new manifest still explicitly owns every referenced object. No object may depend
on a generation that retention will remove. A small restart transfer delta is
not the size of the full recoverable backup.

Each file retains original path/metadata, ordered chunk IDs and lengths, full
byte count and full SHA256. Preserve duplicate records and their order, newlines,
escaping, binary fragments and incomplete final records. Authenticate/pin the
manifest through the existing controller, and verify both objects and full files
on recovery. A hash alone does not prove SQLite consistency or a complete scope.
Incremental reuse requires sealed unchanged identity/content and actual journal
continuity, otherwise existing reconciliation applies. Publication still needs
the reviewed verified replacement and bounded-overlap lifecycle.

For future local archival, hydrate the ENTIRE original session/rollout at its
expected path before native resume or current Vibe browsing. The current readers
are not archive-aware. Their SQLite/path references and a remotely stored archive
alone do not make local removal safe. Adding demand hydration or archive-aware
readers, real resume/browse acceptance and any local retirement authorization are
separate work. A consolidated B package can preserve all history without those
application changes: recovery restores the original paths and bytes first.

## Bounded experiments, not a new backup engine

`vk_history_compaction_probe.py` is an in-memory experiment, limited to 16 MiB,
64 logical files, 65,536 block references and 64 KiB blocks. It tests exact-record
and content-defined chunk reuse with independent flat manifest/object closure.
Zlib6 is an explicit fixture comparator, not the installed backup codec. Always
include manifest bytes and compare compressed size as well as raw unique size:
many small separately compressed objects can be WORSE than a solid archive.
There is no filesystem capture, install, retention or service entrypoint.

The optional reversible stdout projection extracts a string only when its JSONL
record roundtrips to precisely the original bytes. Fragment lengths and all
noncanonical/partial/non-Stdout records remain in the package. Reassembling stdout
can expose repeated protocol payload despite different 4 KiB wrapper boundaries.
Restoration verifies the original complete-file size/hash. It never semantically
drops an apparent duplicate, tool result, context, encrypted value or image.

Fixtures cover duplicate records, changed wrappers, giant records, exact Unicode
and escaping, partial/binary tails, corruption/missing/trailing objects, replay,
path/expansion bounds and an independent next generation retaining entire old
sessions. A physical fixture restores SQLite and checks session/process/native
references and all file bytes without its predecessor. Real provider resume,
real whole-catalog archive recovery, production-scale chunk metadata bounds and
operational adoption remain untested. Sampled savings must not be extrapolated
to the full archive without evidence.

## Exact reproducible-output exclusion contract

Do not exclude a basename such as node_modules, target, dist, cache or venv.
For EACH exact indexed root, preserve and pin the source tree including all
dirty/untracked/ignored or locally patched material, workspace packages, manifests,
lockfiles, patch files, package-manager/toolchain/platform versions, install/build
scripts and required recovery runtime. Identify every file/link underneath the
root against a trusted pristine package/build inventory. Git status alone does
not inspect ignored dependency patches. Missing proof means keep those bytes.

An accepted recipe must recover required packages/toolchains without relying on
a cache that the same plan excludes, then independently rebuild/restore the root
and validate the recovery contract. Pin local workspace/file dependencies and
postinstall-generated or native modules; registry availability is not established
by a lockfile. A global tool installation without a pinned bootstrap manifest is
not yet an exclusion candidate ready for adoption. Never exclude unpublished Git
objects or the sole compatible runtime artifact. Existing scope-specific Git
history/fence obligations remain intact.

Exact same-content files can share physical objects immediately in a proposed
lossless representation while retaining ALL logical paths and file metadata.
That is distinct from declaring their containing roots disposable. The private
handoff lists exact measured candidates and pinned inputs, and labels any missing
pristine/local-patch/rebuild proof explicitly; no production exclusion is applied.
