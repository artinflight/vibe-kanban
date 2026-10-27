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
