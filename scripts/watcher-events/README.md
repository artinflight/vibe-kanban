# Reusable watcher-to-agent events

For WakeWatch on the current MCP host, see [the explicit printer-connector
transport](CONNECTOR_TRANSPORT.md). It permits disk wake delivery without a backend
restart; implementation is prepared, with production activation and live acceptance
still pending. The native implementation described below remains distinct.

The Vibe module connects existing watchers to existing agent sessions through the
native admission path. Disk Space is its first consumer. Adding a source,
condition or compatible target uses reviewed configuration files after the initial
backend release; it does not require another Vibe restart.

`watcher -> local conditions -> Store.dispatch -> NativeAdapter -> native admission -> existing session`

It reuses Operations PR215's durable dispatcher and Vibe PR277's native admission
implementation. There is one native route/launcher and no new cleanup worker,
scheduler, listener, browser path or credential acquisition. Disk cleanup stays
with its existing owner and existing per-action approval rules.

Read [SETUP.md](SETUP.md) for schema, setup commands, cross-system SSH/stdin input,
private bindings, pending delivery and the acceptance checklist.

## Current behavior

- Root warns/dispatches strictly below **10,000,000,000 available bytes**; work SSD
  below **25,000,000,000 bytes**. Reports include decimal GB, exact bytes, actual
  mount/device/UUID and measured growth. These do not change build/safety floors.
- Known active coding or independent work covers that incident episode. Queues,
  unknown inventory, unbound reservations and unsettled job lifetimes retain
  pending delivery. Recovery does not wake an agent.
- Intent and attempt commit before POST. Accepted/uncertain deliveries reconcile
  by exact receipt GET. Duplicate events cannot create duplicate executions;
  positive capacity/queue deferral requires strictly newer fresh evidence.
- Controlled jobs reserve bounded durable leases before inference under the same
  workspace lock as native input/admission. Only confirmed terminal status or
  definite refusal before inference closes a lease. Drop/restart retains unknown
  exclusion; confirmed live child acknowledgments are distinguished from it.
- Root capture closure, live native clients, complete descendant state and the
  existing controlled-delegation journals also gate admission. Unknown is a hold.
- Cooldown, hysteresis, bounded backoff and persisted receipts survive client
  restart. State/audit/input quotas fail closed without deleting tombstones.

## Native contract and release boundary

Protocol remains `storage-admission-v2`; POST `/api/storage-alerts/batches` and
GET the exact batch with `intent_sha256`. The hot-loaded owner file supports a
legacy single binding or version-1 registry of at most16 existing owner pairs.
Bindings preserve the complete saved executor configuration and require reviewed
existing `delegation_journal_dir` custody. Current compatible targets use saved
**CODEX DEFAULT Recommend** configuration; other executor types are not claimed.

Both migrations belong in forward and compatible latest-data recovery:
`20261018140000_storage_alert_admission.sql` and
`20261027153000_watcher_job_leases.sql`. The parser-only `native-overlay` files
are retained provenance; the integrated implementation is in the Vibe crates.
[The native contract](../../VK_STORAGE_ALERT_ADMISSION.md) links current details.

This source is not installed or activated by publication. Existing Staging owns
initial backend adoption, source-bound artifacts, compatible recovery, existing
ingress/access review, actual saved bindings and live acceptance. Keep both live
watcher activation flags false until those prerequisites pass. HTTP200 HTML is
not an admission API. Preserve the existing timer, initial incident and running
jobs; do not install another watcher or reset state to force a delivery.

## Validation

```sh
PYTHONPATH=scripts/watcher-events \
python3 -B -m unittest discover -s scripts/watcher-events/tests -v
```

The local current client suite has158 cases:157 passed,1 optional existing-connector
compatibility case skipped without `STORAGE_CONNECTOR_SOURCE`. Native tests use
real router/SQLite/default launch/approval code with synthetic executor I/O;
they do not establish a live model turn or completed cleanup.

[Run40544909753](https://github.com/artinflight/vibe-kanban/actions/runs/40544909753)
on source `f331e2e369c7f3faa138f19c45c73989c3dd1ca9` is green:644 native tests
passed (16 intentionally ignored), both explicit native pairings passed, and
frontend/schema/Clippy/Tauri/governance/preservation checks passed. Existing
remote checks were skipped by the workflow without its private deploy key;
no remote deployment paths changed. The current Python suite passed157/158,
with the optional connector-source compatibility case skipped as described above.
See retained history/CI logs for earlier failures and their corrections.

The current pair covers strict disk boundaries, both-low coalescing, actual
receipt/execution binding, lost acknowledgment and client reopen, an unrelated
printer-report target added through file configuration, recovery and a settled
condition edit. It compares actual Rust backend PID/start ticks/executable hash
across configuration changes. All capacity/status/time inputs are safe fixtures;
no real disk pressure, deletion, printer action or production turn is used.

[Migration provenance](MIGRATION_PROVENANCE.json) records original source hashes,
not a seal of subsequently edited files. [Retained migration/validation history](MIGRATION_HISTORY_20261027.md)
preserves the prior notes. The implementation belongs in VK Dev and
`artinflight/vibe-kanban`, targeting its existing `staging` branch. Original
Operations/workspace/session history and PR277's source branch are preserved.
