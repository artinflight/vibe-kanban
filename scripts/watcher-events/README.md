# Modular watcher events — VK Dev source

This module belongs in `artinflight/vibe-kanban`, developed in VK Dev and
integrated through the repository's existing `staging` branch. Operations PR217
was a misplaced source merge. Its original commits, source, tests and issue/
workspace history remain preserved; Operations staging is not this module's
integration destination.

Disk Space remains the first configured consumer and its existing owner retains
cleanup responsibility. The module reuses PR215's durable dispatcher and v2
receipt codec. The native admission implementation remains with the existing
[T64 owner / PR277](https://github.com/artinflight/vibe-kanban/pull/277), at
`8534a6a655e03e4903e4e517cfea21c3b91c4636`. This migration neither edits that
owner's branch nor creates another dispatcher or cleanup worker.

[SETUP.md](SETUP.md) describes registry updates, existing SSH/stdin input, private
owner bindings, incident durability, cooldown/recovery and native acceptance.
[MIGRATION_PROVENANCE.json](MIGRATION_PROVENANCE.json) maps every implementation,
test, example and native proposal to its original content hash. Original private
deployment identities and operational evidence stay in preserved private source;
public Vibe code requires an explicit private existing-owner binding.

The chain is `watcher -> configured conditions -> existing Store.dispatch ->
NativeAdapter -> native admission -> existing session`. Events cannot select an
executor/target or supply authorized instructions. Adding sources, conditions and
targets uses reviewed files after initial backend adoption. No second native API,
ordinary-follow-up fallback, listener, new credentials or scheduler is introduced.

Run from the Vibe repository root:

```sh
STORAGE_CONNECTOR_SOURCE=/path/to/existing/vibe-dot-connector \
PYTHONPATH=scripts/watcher-events \
python3 -B -m unittest discover -s scripts/watcher-events/tests -v
```

156 isolated tests passed with0 skips: the preserved154 cases plus two
private-owner-binding portability checks. Tests cover real concurrent ingress/
SQLite locking, registry replacement, two unrelated targets, lost receipts/reopen,
independent jobs/queues/unknown, retargeting, hysteresis and bounded state, using
safe injected observations and receipts. They do not prove live native execution.
Resource-guard, service/timer/drop-in and patch files are retained existing-host
references/fixtures, not instructions to install another watcher, invoke memory
recovery or restart services.

The source-only `native-overlay` proposal extends the existing owner file to
multiple targets while retaining native routes/schema/receipts/fences. T64 owns
integration. Its two Rust tests remain unexecuted. Backend acceptance still needs
authoritative independent-job lifetime exclusion and both arrival/admission race
orders, current-client/native pairing and saved configuration/access gates.
Native targets currently remain CODEX DEFAULT Recommend only; additional executor
support remains backend work.

This migration is not a release or a completed Vibe pre-merge baseline.
`ops:check` passed; required `pnpm run format` completed Rust formatting then
failed because frontend Prettier is absent. No dependencies were installed.
Full check/lint/native workspace tests, the changed native boundary and matched
combined candidate/recovery remain with the admitted integration/release work.
Do not merge or deploy based only on client tests.

Existing Staging owns the authorized initial backend release and compatible
latest-data recovery. Live acceptance needs real Disk and unrelated-target
receipt/execution/owner readbacks, proving unchanged backend PID/startticks/hash
across the second connection and a condition update. Installed observation/ntfy
continues separately with native dispatch fail-closed. No live DB edit, restart,
credential change, deletion, model call, hosted CI or API deployment occurred.

## Native integration in progress, October 27

This branch now contains PR277 by ancestry (integration merge `7495ba41a`),
plus the same-route multi-owner registry. The prior migration-only handoff above
is retained history. The current owner is completing native validation here;
PR277 and its owner's source are preserved. No staging merge or runtime change
has occurred.

The current isolated pair is `modular_native_integration.py`, driven by
`native_modular_watchers_decimal_disks_and_hot_second_connection`. It uses the
real native router, migrated SQLite, default launch and approval bridge with
synthetic executor I/O. It tests both strict decimal boundaries, capacity reports,
dedup/recovery and a second unrelated source/target hot-loaded on one backend,
including actual committed receipt recovery after a lost response. These are
written scenarios until compiled CI reports a pass. Existing frozen historical
PR215 pairing remains separately available and is not current-policy evidence.

Admission now additionally checks capture closure, unresolved/running independent
jobs and the provider's complete descendant graph; missing/unreadable inventory
or an open producer edge holds dispatch. These conservative checks are not yet
proof of all independent producer lifetime/arrival races. That native requirement
remains open, including controlled-delegation journals and executor teardown.
Do not activate based on inventory snapshots alone.

Safe local client suite: 157 cases,156 passed,1 optional existing-connector check
skipped without its explicit source path. A native `owner_busy` receipt now covers
the episode instead of retrying after that owner finishes; capacity/queue holds
keep durable pending delivery. Current hosted native results are still pending.

The independent-job source now also includes bounded durable pre-inference
leases shared with native owner admission. Terminal acknowledgment closes a
lease; parent exit, cancellation uncertainty, Drop and restart do not. Native
adoption requires the additive `20261027153000_watcher_job_leases.sql` migration
and reviewed existing `delegation_journal_dir` binding for legacy jobs. New Rust
race/reopen/legacy-journal tests are written and await compiled acceptance.
Existing frontend, clippy, Tauri and governance CI passed on `27c7a1f21`; native
workspace tests and current pairing are still running at that checkpoint.

Hosted validation run40529828966 on `27c7a1f21` completed: frontend, schema,
Clippy, Tauri, governance and preservation passed. Native suite:629 passed,
8 failed,16 skipped; both explicit pairing steps failed. The failures share the
new fixture's invalid zero-byte closure receipt, which the unchanged production
CHECK correctly rejected. The fixture now serializes synthetic Finished I/O and
hashes its positive bytes; no production closure constraint is weakened. This
correction and the newer producer-lease work need a fresh compiled run.
