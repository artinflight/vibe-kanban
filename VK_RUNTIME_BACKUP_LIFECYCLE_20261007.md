# Runtime File Lifecycle And Online Backup

## Finding

The October7 failed full capture reported a timestamped shell snapshot and a
thread writer lock disappearing. The retained journal records DELETE for both;
the files are absent, not replaced by links. They are not thread rollouts or
databases. No user history was deleted by the backup.

Locally available Codex source3d2ee51ca2d5db578f328aa75e20aa22c0197c9a documents
the lifecycle in `codex-rs/core/src/shell_snapshot.rs` and
`codex-rs/thread-store/src/local/writer_lock.rs`. This cached source is0.153.4,
not a claim of exact installed0.159.2 build provenance. Installed runtime strings
independently contain the matching shell-create/delete and writer-lock-cleanup
diagnostics. Runtime and source hashes are recorded by the staging-owner audit.

The shell snapshot is generated from the shell environment, validated, renamed
to `<thread UUID>.<nanosecond nonce>.sh`, and removed when its owner is dropped.
A later execution generates its own snapshot. The file can contain sensitive
environment values, so its contents are not printed in evidence. Regenerable
does not mean identical to an earlier process's environment. Existing snapshots
remain in the backup scope; no directory-wide exclusion is introduced.

The writer lock is opened with create/no-truncate, holds an OS file lock, and is
closed/deleted under a coordination lock on release. It stores no conversation
payload. Restoring its bytes cannot restore live OS lock ownership. Live writer
ownership must still be checked independently before handover.

## Narrow Change

The runtime warning adapter accepts only exact UUID/nanosecond shell filenames
or UUID writer-lock filenames within the two known scoped Codex homes. It adds
the individual path, never its directory, to transient-warning classification.
The original validator still requires online capture, a recorded deletion and
current absence. Symlink or foreign-owned parents, currently present/replaced
files, unknown names, sessions, explicit required paths and frozen-boundary
deletions fail closed. No database or protected root is removed from the plan.

The full capture retains its start journal sequence; a following delta captures
current changes and deletion tombstones. This is consistent online preparation,
not a global point-in-time snapshot or authorization to skip the final fenced
capture. Old failed archives/evidence stay failed unless the strict independent
recovery path verifies them; current staging will instead make a new full capture.

## Validation

All198 deployment regressions pass in25.914seconds, including11 focused tests.
The new real-tar/inotify test backs up a present snapshot, deletes shell/lock
files immediately before a later tar read, verifies the narrow warning result,
then restores the next delta with history and dirty work intact and released
runtime paths absent. Negative tests cover absent journal proof, non-deletion
events, frozen capture, extant files, symlink files/parents, unknown filenames,
required files, foreign ownership and scope mismatch. Existing closed-database,
committed-WAL, move and hardlink tests stay green.

Ops governance and diff checks pass. Required format command was attempted;
this sparse operational checkout lacks `crates/capacity-guard/Cargo.toml`.
No Rust or frontend source changed. Real fresh-backup/recovery acceptance is a
separate measured receipt, not established by these synthetic regressions.
