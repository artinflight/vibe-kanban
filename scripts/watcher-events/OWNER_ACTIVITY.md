# Shared assigned-owner activity

The October 30 owner correction supersedes the earlier “active owner covers this
episode” behavior: keep an eligible alert pending while its assigned agent is
busy, queued or uncertain; admit it once after that agent becomes idle. Recovery
still does not wake it. Nothing here grants new action or cleanup authority.

`owner_activity.py` is the common read-only implementation. Disk `t26_watch`,
connector preflight and generic registry drains use it. The existing printer
observer calls its CLI for each pending decision, so later helper updates need
no observer or Vibe restart. No new watcher, timer, listener, dispatcher, model,
credential, security permission or owner is introduced.

## Decision and uncertainty

The exact private workspace/session binding selects native SQLite execution
state, jobs for that workspace's sessions, their queues, unresolved job leases
and existing delegation journal custody. Other workspaces' active turns/jobs do
not hold this owner. Current turn reports its execution UUID, status and reason;
setup/cleanup scripts and other sessions in the same workspace still exclude a
new turn. Persistent devservers are not coding turns. A final fresh native turn
read catches arrivals during slower status reads. No idle cache is retained.

Protocol `watcher-owner-state-v1` returns the binding, `current_turn`, `turn_state`,
`state`, activity IDs and bounded `owner_uncertainties` with component/session.
`state=idle` permits existing preflight; busy, queued and target-specific unknown
all retain pending delivery. The legacy `inventory_unknown` alias is set only
when the assigned binding/turn snapshot itself is unavailable; partial uncertainty
retains known turn evidence and its component-specific hold. Unknown job/provider
states, missing native binding,
unreadable owner custody and uncertain leases never certify idle. This advisory
reader does not replace backend admission, capacity, budget or approval checks.
The existing connector independently rejects a running session; capacity may
queue an accepted request. Queued/accepted/uncertain submissions are never resent.

Process matching is evidence of the assigned owner's work, not a host-wide
permission census. Readable owned paths, the exact native execution unit and
stable parent/child links attribute processes to the target. Attributed unfamiliar
or unreadable work holds that owner. Unattributed unreadable processes are counted
and retained as at most16 metadata-only diagnostics. They do not change a known
native turn to unknown and are never treated as proof of another agent's activity.
No browser-name allowlist, pinned-PID exception, `/proc` privilege change or sudo
is needed. Command lines, environments, browser profiles and secrets are not
retained. The recent protected-Chrome PID churn is the regression case; the rule
applies equally to any unrelated or unfamiliar program.

## Pending delivery and installation

Busy waits use the existing observation cadence, not exponential transport-error
backoff. Actual attempt/receipt backoff, cooldown, hysteresis, TTL, exact saved
configuration, immutable incident/batch identity and lost-reply reconciliation
remain intact. One legacy migration restores only unrecovered “covered” incidents
that have no batch or a positive no-admission deferred batch. It retains their
UUIDs and audits once; accepted or unknown delivery is untouched. Historical
host-inventory-only scheduler waits may reset once only if no delivery was ever
attempted. Receipt and incident tombstones are not deleted.

Install the shared module before its callers. Patch the existing disk modules
under their `incidents.lock`; atomic file replacement and retained preimage
hashes preserve rollback custody. Keep config/transport selection, existing
ledger, notification policy and owner unchanged. Existing disk ticks load new
Python files. A previously running printer observer needs one controlled
observer-only reload when first adopting the CLI caller; Vibe, the connector,
printer hardware and agent turns are not restarted. Preserve all printer events,
frames and dispatching/unknown receipts. Later helper fixes load per decision.

Printer owner config is private0600 at its existing state root (`owner.json`):

```json
{"workspace_id":"EXISTING_WORKSPACE_UUID","session_id":"EXISTING_SESSION_UUID",
 "vibe_db":"/private/current-vibe.sqlite","owner_roots":["/private/owned-worktree"],
 "dispatch_transport":"connector-follow-up-v1",
 "delegation_journal_dir":"/private/existing-producer/delegation"}
```

Read-only status: `python3 -B /approved/module/owner_activity.py --config /private/owner.json`.
`wakewatch check` also reports the exact assigned owner; neither sends a wake.
Do not create another live probe. Validate busy-to-idle and one-send behavior with
injected statuses and existing fixture transports. Then read back the installed
hashes, ordinary timer result and real native execution/receipt if an existing
eligible incident is admitted. Preserve current approval/resource holds rather
than forcing a wake. Native v2 remains disabled until its separately documented
startup owner-file/access/release prerequisites are met.


## October 30 validation

211 watcher regression cases passed with the installed connector compatibility
check enabled, plus20 tests of the existing printer consumer. These include the
protected-Chrome restart case, target-scoped unknown job/provider states, owned
unfamiliar descendants, exact running-turn precedence, late arrivals, queues,
lease/journal custody, busy-to-idle one-send, lost replies and legacy ledger
preservation. Read-only live checks and the existing timer's genuine incident
admission passed; exact private receipt/native execution evidence is retained
with the installed preimages. No extra live probe, real-pressure manipulation,
printer control, cleanup action by this module or Vibe restart was used.

Only Python clients and documentation changed. Ops governance and Python AST
checks passed. Required full formatting completes Rust formatting but the local
checkout lacks frontend Prettier; no dependencies were installed. No new native
or frontend runtime build is claimed for this client correction.
