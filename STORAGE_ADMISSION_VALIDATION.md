# Storage admission validation checkpoint

Source-only; not release-ready. Baseline verified against remote fork staging
`5b43524ea35b2eb5dd80d0881dc8445489f4442f`. Client requirements verified at
Operations PR215 `82805b71556d94e22073e5c790bb79d090f409ae`.
[The native contract](VK_STORAGE_ALERT_ADMISSION.md) defines the implemented
`storage-admission-v2` wire shape. T90 joint review/client adaptation remains
pending; production client transport is disabled.

## Observed local evidence

`cargo test --offline -p services --lib storage_admission -- --test-threads=1`
compiled the native services test executable and ran **14 tests: 13 passed,
1 failed**. Incremental compilation was disabled and there was one compiler
job. No live owner, backend service or paid model request was dispatched.

Passing isolated migrated-SQLite/native-queue cases:

- competing same-batch deliveries create exactly one native execution row;
- competing batches/duplicate incident identities cannot launch twice;
- busy owner defers, unrelated active owner does not veto;
- memory/durable queues and unhandled user receipts remain unchanged;
- changed intent/owner/hash do not alias an accepted receipt;
- definite capacity deferral requires a new attempt and fresh validation;
- timeout after commit recovers the exact execution by read-only lookup;
- cancellation fences a late insert and keeps a terminal tombstone;
- failures before and after execution binding have different outcomes;
- not-found/conflict/history loss never grant resend authority;
- stale/invalid scope/evidence cannot launch;
- normal native insertion respects a durable abandoned reservation;
- fingerprint ordering and Unicode serialization agree with the fixed vector.

The database-reopen test failed opening its fixture file (SQLite code14) after
a `VACUUM INTO` snapshot. It is now changed to create, migrate, admit, close and
reopen the **original on-disk WAL database**. That correction has not yet been
rerun locally. Do not claim restart acceptance from the earlier failing run.

`pnpm run format` completed successfully after installing the locked tooling.
Subsequent source edits are rustfmt-formatted before publication.
`pnpm run ops:check` and `git diff --check` passed.
The aggregate `pnpm run check` was interrupted during local-web typechecking
before reaching backend Cargo, for shared storage/resource coordination.
It is not a passing aggregate check. Full lint and workspace tests were not
started locally after that hold.

The first normal hosted Test run `39132359649` at source `7b2a904c1`
reported a misplaced controller test fixture reference and a large-error Clippy
warning in the synchronous configuration parser. Source corrections move the
test into its existing fixture module and return a small parser error mapped at
the HTTP boundary. The wire contract is unchanged. Successor CI is required;
these diagnostics are not represented as passing native tests.

## Prepared native tests, not yet accepted

The server suite uses the actual HTTP router/handler, default native
`ContainerService::start_execution`, migrated on-disk SQLite, native queue and
real interactive approval bridge. It replaces executor/process I/O and OS
inventory in isolated child test processes, pins only synthetic test settings,
and disables model execution there. It includes normal user-follow-up contention,
actual native capacity-gate outcomes, own native budget/paused-goal holds,
unrelated Nightly context, approval waiting/denial, saved configuration drift,
post-binding spawn failure, HTTP replay/GET/cancellation and missing receipts.
These tests are source, not executed acceptance at this checkpoint.

Executor tests additionally exercise the real controller's no-takeover check
and read-only native goal database hold, without changing unrelated grants.
Native LocalContainerService queue-consumer regressions and complete crate/
workspace checks are still required. Compiling the services crate does not
prove these server/LocalContainer paths compile or pass.

## Resource and integration boundary

The original local Cargo job has exited; no owned compiler/linker/check remains.
All existing source and shared outputs are retained. No further host build or
link allocation is authorized by this checkpoint. The existing Disk owner has
private terminal-process and zero-future-growth handoffs. No cache deletion,
file move, allowance change or live service action was used as a remedy.

The repository's normal pull-request checks use GitHub-hosted Ubuntu runners;
they can validate this source without a new host compiler or SSD payload.
No custom workflow dispatch, deployment or hosted release is requested. Exact
CI results must be recorded before claiming source acceptance. The combined
private-reader release/rollback/native runtime acceptance remains Staging-owned
and separate even if public CI passes.

The current base adds a receipt migration, two narrow native admission checks,
workspace serialization shared with normal input/queue consumption, and one
new API module. It does not replace a release bundle. Before Staging adoption,
compare its current release head, reconcile additive changes against the latest
private routes, and require compatible forward/rollback migration checksums
with all receipts/fences retained. No production migration was performed.

The smallest later activation requirements are: coordinated exact wire-contract
review and real client/native integration; fresh authoritative physical and
allocation producer input; Staging's combined native/rollback acceptance; exact
saved owner/config/freshness binding using existing authenticated ingress;
then separate explicit native release and monitor tuning/access/timer approval.
Existing phone alerts, model/effort/Recommend, cleanup and genuine spending/
approval limits remain unchanged.
