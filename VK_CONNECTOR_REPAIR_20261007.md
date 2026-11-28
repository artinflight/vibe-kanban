# Conditional unread review repair for Staging — 2026-10-07

WHAT: Repair the reviewed connector backend candidate on its own isolated branch.
WHY: four real integration failures and a lossy verification reader blocked safe
unread reconciliation. CONTEXT: exact combined source base eacafb3a1e5b42d5fbc69f076dbc07c438e1cf54;
Staging review/handoff146b29a8d remains untouched. SUCCESS: compiled migration/writer
regressions and isolated real HTTP/recovery acceptance pass without live badge writes.

## Root causes and repair

1. The migration's default RESTRICT references prevented normal parent deletion.
   Intent and hold-event rows cascade with workspace deletion; closure rows cascade
   with execution deletion. Receipt audit IDs are historical scalar identities,
   deliberately not live foreign keys, so deletion retains immutable proof/event audit.
   Ownership is validated by the receipt route before insertion. Foreign keys stay ON.
2. Strict MsgStore capture previously checked broadcast lag only. It did not know
   history was evicted, and snapshot and subscription were separate acquisitions.
   History now records eviction permanently; push publication and capture/subscription
   share one lock. Lossless review capture rejects eviction or lag. The actual writer
   cannot publish closure for an incomplete capture, empty log, failed flush/sync,
   malformed stored records or a pre-existing append target. Closure records actual
   stored byte count and SHA256. UI consumers retain their previous surviving-history
   recovery behavior via a separate recoverable stream; no display filtering fixes
   integrity and no lossy replay is admitted as review proof.
3. The verification helper used UI historical replay, which skips invalid JSONL,
   turns read failures into stderr, ignores normalizer joins and synthesizes Finished.
   Review now reads the bounded native file directly, requires complete UTF-8 JSONL,
   rejects damaged/partial/unsupported records, and matches writer length/hash. No
   debug fallback to production logs, legacy DB log fallback, UI cache or UI error
   recovery participates. Reconstructed stdout joins split chunks before strict native
   JSON/schema validation. Finite input precedes normalization; every task join and
   retained-history integrity check succeeds before a completion marker is synthesized.
   Failed/timed-out normalization aborts remaining jobs. The same bounded reducer
   returns the exact last assistant index/raw UTF-8 hash. Strict native identity is
   currently implemented for Codex; unsupported executors fail closed, never clear.
4. Receipt marking still serializes SQLite's writer BEFORE reading hold/intent/activity,
   checks exact revision/ownership/all sessions, deduplicates source events and marks
   only the existing reviewed turn. It now also rejects a coding-turn revision that
   changed during durable replay. Future changed replies reopen their own turn.
   Duplicate receipts after manual unread return their old proof without marking again.

Bounds: raw file32MiB and100,000 records; normalization retention64MiB; reducer8MiB
serialized patches/100,000 operations; production verification timeout10s. Exceeding
any bound preserves unread. A closed-log proof is required even for old approved
reports. Stable bytes, completed status, terminal native events and matching reply
hash alone do not create a writer proof. The four historical approvals remain blocked
until the release owner establishes supported historical closure; no live backfill here.

## Isolated acceptance

Use an explicitly bound SSD checkout, never a Vibe deployment constructor. Export
VK_REVIEW_ACCEPTANCE_ROOT to the exact checkout root; tests compare this with their
compiled source root and dev_assets canonical path. Run with CARGO_TARGET_DIR on
mounted SSD, CARGO_INCREMENTAL=0, SQLX_OFFLINE=true, CARGO_BUILD_JOBS=2 and dev/test debug
symbols disabled. The receipt runner retains logs, exit codes, duration and a4GiB
minimum-free floor in /mnt/vk-storage/vk-connector-repair-20261007/evidence.

Commands (all offline):

- cargo test -p server --test report_review_integration -- --test-threads=1
- cargo test -p server --lib routes::workspaces::report_review::tests -- --test-threads=1
- cargo test -p utils -p services --lib review_ -- --test-threads=1
- cargo test -p executors --lib codex::normalize_logs::tests -- --test-threads=1
- cargo check -p server --bin server --tests

HTTP tests bind ephemeral127.0.0.1 listeners and real disposable SQLite files on SSD.
They invoke the exact production receipt/state/hold handlers through a narrow dependency
interface, the actual raw writer and strict native normalizer. There is no application
constructor, paid inference, worker launch, cleanup service or production configuration.
Unread readback uses the actual CodingAgentTurn::find_workspaces_with_unseen query.
The installed Python Adapter tool also submits one disposable receipt through a real
Rust HTTP backend and private receipt ledger; its transport/ledger bindings are local
only to that test process. Compatibility read routes in that fixture read actual data,
not a fake conditional backend. No fake user review reaches the real connector ledger.

Final validation: **31 Rust tests passed,0 failed,0 ignored**: Staging's original8,
real HTTP/recovery8, strict capture/replay7, existing Codex normalizer8. Explicit
cargo check --offline -p server --bin server --tests passes. No new compiler warnings.
Existing connector Python suite94/94 passes. Rust formatting, ops checks and
Git diff whitespace checks pass. Full pnpm format stops after successful Rust
formatting because Prettier is absent; no frontend/shared/package/lock inputs changed.
Minimum free SSD bytes over passing Rust runs:79,311,470,592;4GiB floor never hit.
HTTP/readback fixtures are disposable, not actual voice delivery or live flag writes.
Earlier failed repair attempts and Staging's red review evidence are retained.
Full workspace, combined CU/native/rollback and production acceptance are NOT claimed.

## Caller and release boundaries

Root can immediately submit genuine handled/delivered source events through installed
Adapter(None).handle with the existing scoped record_workspace_report_delivery tool;
Desktop, credentials or another user request are unnecessary once real delivery is
observed. See /mnt/vk-storage/vibe-dot-connector-maintenance/ROOT_VOICE_RECEIPT_INTEGRATION.md
for the exact envelope, evidence and retry contract. Runtime discovery advertises20
scoped tools, parent still14. There is no exposed voice playback/chat delivery callback
or caller tool-cache refresh API. Actual client callback -> tool invocation and catalog
refresh remain necessary. No polling or startup sweep is installed. This is not
automatic end-to-end delivery capture or live marking.

Only the release owner may integrate this delta into its combined candidate, rerun
combined native/rollback acceptance and perform a separately authorized safe adoption.
Do not edit/restart Staging or Vibe here. This migration has never been installed in
production; recreate disposable old-candidate fixtures instead of rewriting SQLx
migration checksums. Preserve live user holds and receipt ledger across compatible
same-latest-data software rollback; never revert to an older database to roll back.
The compile-only embedded frontend fixture is not a deployable frontend bundle.
