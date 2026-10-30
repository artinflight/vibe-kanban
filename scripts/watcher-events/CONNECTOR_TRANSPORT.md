# WakeWatch through the existing printer connector

## Deployment status — 2026-10-30

The restart-free disk transport is **installed and enabled** since
2026-10-30T11:38:59Z, following explicit operator approval. The existing timer has
loaded it, and live owner/configuration readiness passed. The single approved
acknowledgement test reached Vibe at 11:39:14Z and is capacity-queued behind eight
active executions. Its immutable batch is retained; it will never be resent.
An actual execution and exact reply are still pending, not claimed as passed.
No service was restarted. Original module/config bytes are retained on mounted SSD.

This is an explicit alternative to native `storage-admission-v2`, whose running
backend lacks `VK_STORAGE_ALERT_OWNER_FILE`. The native route remains disabled.
Hot-loading that file's contents cannot supply its missing startup path. The
ordinary connector follow-up path is already live and does not need that setting.

The existing `OP::3D Print Issues` watcher invokes
`/home/mcp/code/vibe-dot-connector/adapter.py` with a JSON-RPC `tools/call` for
`run_session_prompt`, passing the existing session and prompt on stdin. It detects
OctoPrint pause transitions, including Obico-caused pauses, rather than arbitrary
Obico cloud advisory warnings. Retained October 27 and 28 paused-print receipts
identify actual accepted executions. October 29 uncertain events remain unreplayed.
No printer watcher code, service, credential or state changes are needed.

## Scope and controls

`resource-guard.timer` already launches the disk Python runner on each tick.
The runner re-reads its private config and modules. An approved atomic installation
under its existing incident-file lock therefore needs no daemon reload or restart.
No additional watcher, service, timer, MCP tool or agent is introduced.

The explicit transport name is `connector-follow-up-v1`. It preserves the existing
Disk Space owner/session, incident ledger, ntfy coupling, thresholds, episode
suppression, cooldown, approval boundaries and saved CODEX DEFAULT Recommend
configuration. There is no automatic fallback between transports. The generic
`watch_events.py` registry remains on its native transport; this connector option
currently applies to the existing disk runner only.

Before dispatch it checks the existing workspace execution/subagent/queue/process
inventory, unresolved watcher leases and controlled-delegation journals. Unknown
inventory, busy owners, missing custody or saved-config drift hold delivery. It
revalidates the exact saved executor-config SHA256 and fresh observation immediately
before invoking the unchanged connector. The normal Vibe follow-up endpoint retains
its workspace admission lock, provider, capacity, permission and budget controls.

This is **not the atomic native watcher-admission contract**. Client checks can
race with later independent work. Normal Vibe capacity admission may queue a
follow-up. Queued, timed-out, interrupted or uncertain submissions are never
resent. Reconciliation requires exactly one persisted execution with the same
session, full immutable prompt and full executor-config hash. Read-only SQLite
is used for evidence; no Vibe database rows are written by this module.

Each batch retains one exclusive, fsynced outbox file before its only connector
invocation. A crash between commit and invocation deliberately leaves an uncertain
hold rather than risking duplicate work. Sidecars are bounded delivery proofs;
`incidents.sqlite` remains the sole incident ledger. Do not delete either to retry.
The transport must not be switched while an unresolved batch/probe remains.

## Private activation recipe

1. Confirm mounted SSD, existing timer ownership and currently installed hashes.
   Retain original module bytes and private config on SSD for rollback. Check the
   same incident ledger under its `.lock`; require no unresolved old deliveries.
2. Read the existing session's current full configuration through the connector's
   `resolve_followup_config`, including saved UI draft overrides. Require its
   existing workspace, CODEX DEFAULT and Recommend (`routing.mode=shadow`). Pin
   the canonical JSON SHA256; never infer or silently change model/effort.
3. Under the existing lock, install `connector_adapter.py`, `wakewatch.py`, and
   narrowly patched `monitor.py`/`t26_watch.py` together. Preserve other modules,
   private ownership, any event-registry configuration and notification settings.
4. Only after explicit activation approval, atomically set these private fields:

```json
{
  "dispatch_transport": "connector-follow-up-v1",
  "activation_approved": true,
  "connector_transport": {
    "enabled": true,
    "executor_config_sha256": "<sha256 of complete resolved saved config>",
    "max_validation_age_seconds": 60,
    "delegation_journal_dir": "<existing reviewed delegation directory>"
  }
}
```

Keep `native_transport.enabled=false`. Preserve the original native settings,
thresholds, owner IDs and ledger path. Do not copy example identities into a live
binding. Install the small `wakewatch` launcher for the existing Python CLI.

5. Read back `wakewatch status` and `wakewatch check`. Readiness false means hold,
   not permission to interrupt work or bypass checks. After approval for one test,
   `wakewatch queue-test` queues one acknowledgement-only prompt for the existing
   timer. It waits for idle for at most one hour; no cleanup, shell commands, new
   agents/goals or follow-up loops are requested. Repeated calls cannot add turns.
6. Verify the persisted execution and the exact expected reply, then record the
   outcome and backend/connector/printer service invocation IDs. Until that proof,
   report live end-to-end delivery as pending, not passed.

## Rollback without restart

Under the existing lock set `connector_transport.enabled=false` first. This stops
future dispatch on the next tick without stopping observation/notification. If an
accepted/queued/uncertain delivery exists, preserve its probe/outbox/ledger and
reconcile its exact execution before restoring old modules or changing transport.
Disabling dispatch does not cancel a queued or running Vibe turn. Never stop user
work or replay an uncertain request as rollback. Once no unresolved delivery
remains, restore the retained original module/config bytes under the same lock.
No backend, connector, printer watcher or timer restart is required.

## Validation

Prepared isolated changes: 21 connector tests, 28 monitor tests and 10 ntfy-coupling
tests passed (59 total). They cover exact execution reconciliation, lost replies,
capacity queues, config/session drift, busy/stale holds, duplicate evidence,
pre-invocation crash, no-resend persistence, disabled selection and bounded probes.
The full repository watcher suite passed all 185 tests, including compatibility
with the installed connector, owner/custody and infrastructure identity regressions. No Rust or frontend code changed; full Rust/UI builds were not rerun.
Mocks do not prove a live model wake; the explicitly approved one-turn test is
retained in the live capacity queue, with actual execution/reply pending. No artificial disk-pressure incident or cleanup test is performed.

## Live inventory correction and custody

The former process inventory marked every unreadable same-UID process unknown,
including unrelated protected browsers, SSH and user-system services. That made
idle detection permanently false on this host. The correction keeps unknown
processes as holds and uses two narrow forms of positive infrastructure identity:

- Fourteen reviewed unrelated running browser/system/Tailscale processes are bound
  privately by boot ID, PID, start ticks, name and full cgroup. Any restart, PID
  reuse or changed identity invalidates the exception; no broad name/cgroup skip.
- SSH transport brokers and their direct SFTP subsystem are recognized only through
  root-owned sshd ancestry and the expected user-session cgroup. Their shells,
  scripts, agents and other descendants are still scanned normally. No new sudo
  permission, privilege, proc visibility change or service was introduced.

Future new unreadable processes still hold delivery until classified; this is an
explicit operational limitation, not an idle claim. There is no generic fallback
that ignores unknown process inventory.

Live installation uses narrow patches against the pre-existing private disk client;
public source retains its generic configured-owner and event-registry integration.
Exact installed module hashes and source are retained in
`/mnt/vk-storage/wakewatch-connector-20261030/activation.safe.json` and `source/`.
Original bytes are in `rollback/`, including all seven original modules and the
private config. The native/connector/printer service PIDs and invocation IDs match
preparation. Do not restore the old disabled config or modules while this probe is
queued/uncertain. Disable new dispatch under the lock and reconcile first.
