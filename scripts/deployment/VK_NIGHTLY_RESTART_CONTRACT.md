# Nightly baseline and restart integration

The October16 integration also supports explicit `chunked-zlib-1-v1` objects.
The leased baseline reader reconstructs complete bytes and checks all chunk and
full-file hashes before successful stream completion. Every generation owns
its entire chunk closure. It remains a separate format from legacy tar chains;
physical whole-plan acceptance and controller adoption are still required.

The nightly object-store format and the restart tar-chain format are different.
A verified full-plus-partial archive chain remains dependent on every referenced
archive. It must not be labeled an independent current nightly or enrolled in
nightly-only retention. Existing recovery/incident/fallback evidence stays outside
that retention set.

`run_capture(..., journal_reader=reader)` accepts a trusted source callback for an
existing owner-managed journal. The nightly runner checks its coverage but never
starts, closes, replaces or repairs that owner's watcher. The CLI's default private
watcher still produces an independent backup, but closing it means subsequent
restart catch-up needs complete reconciliation. There is no new journal service,
command-valued configuration or automatic adoption of an unreviewed reader.
The controller owner must bind the actual journal interface, including its existing
namespace/move coverage validation, before wiring this callback into scheduling.

After archive/index verification, the nightly producer records `restart_capture`
in the manifest's existing `capture_context`. It binds the original capture plan,
source scope, source prefix, consistent database object hashes and capture START
journal instance/sequence. Using the end sequence would skip changes that occurred
during online capture. A transport delta still produces one complete independent
current index; its metadata does not create an archive-parent dependency.

The restart controller consumes `held_baseline(store, plan, generation=...,
manifest_sha256=..., physical_readback=...)` as a context manager. It holds the
existing store lease through the last baseline read and catch-up selection. The
adapter checks the exact published pointer, complete object hashes, database
bindings and a separately supplied exact physical B readback receipt. `blocks(key)`
reads only manifest-listed regular content or its validated hardlink target, with
bounded decoded size/hash checks. It never follows archived symlinks or writes a
restore target. The caller keeps native B authentication and the existing physical
restore verifier; same-account callbacks are advisory operational gates, not a
privilege boundary.

`handle.catchup(reader)` returns the explicit `vk-nightly-restart-baseline-v1`
contract and the journal report since the START sequence. A new instance, overflow,
unready coverage, changed scope/plan or backward sequence fails closed. Complete
content/metadata reconciliation is a separate reviewed route; this adapter does
not forge continuity or repair historical errors. Old manifests without this
contract cannot be silently upgraded into restart parents. The controller must
understand this object format rather than pass it to legacy `Archive(reference)`.
Fresh SQLite snapshots remain mandatory for catch-up; no old database generation
proof is synthesized. Managed writer/ownership fences, runtime identity,
latest-data rollback, Git obligations at affected handovers and human QA remain
with their existing owners. A baseline receipt grants no activation or retirement.

The supported schedule remains the existing unprivileged cron pulse plus the fixed
calendar, 02:00 America/Toronto. It handles DST, bounded resource retries and local
completion checkpoints. The old source-only systemd timer renderer now also names
Toronto, but is not a replacement for the calendar's spring-gap/retry behavior.
No schedule is enabled by this integration.

Before activation, require refreshed current payload/runtime/source/config pins,
the controller owner's accepted journal/consumer binding, enough measured B
capacity for verified replacement overlap, real whole-plan physical recovery
acceptance for the exact package, and reviewed unprivileged schedule adoption.
Failure reporting is private local status JSON and cron stdout; remote notification
delivery remains unverified. Never infer a successful backup or active schedule
from source fixtures or a historical restart receipt.
