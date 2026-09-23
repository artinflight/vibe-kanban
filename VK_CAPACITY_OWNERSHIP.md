# Capacity Ownership Handover

This implements explicit scheduling ownership transfer between compatible VK
backends. It does not authorize a production restart, replace the deployment
controller, or permit two active writers to the VK database.

## Contract

The existing private capacity token authenticates all endpoints:

- `GET /api/capacity/ownership`: protocolVersion1, owned, and owner state. A
  released/standby instance returns state:null rather than a stale snapshot.
- `POST /api/capacity/ownership/release`: epoch and revision of the current
  owner. Requires no running VK executions and no outstanding capacity grants.
  Releases the existing lock descriptor and returns the last owned state.
- `POST /api/capacity/ownership/acquire`: epoch and revision from the last
  owner's release receipt. Acquires the same lock inode, verifies persisted
  generation under that lock, reloads the latest state, and issues a new
  controller epoch/revision. An already-owned instance rejects acquisition.

Release fences controller writes and foreground/background launch admission in
that process. It does not automatically relinquish authority on a GET, restart,
timer or subsequent write. Ordinary status requests fail while released; the
ownership endpoint remains available for the independent controller.
Grants must drain first, including issued but not yet bound permissions.
Used grant IDs and foreground priority persist across ownership changes.
Process identity for persisted actions remains distinct from controller epochs,
so new scheduled work remains valid after reacquisition without accepting old
grants. No database schema, native thread identity, or user model choice changes.

`VK_CAPACITY_START_PAUSED=1` starts the controller without acquiring ownership.
Use it for a handover candidate. Only0/1 are accepted; absent/0 preserves normal
legacy startup behavior. This flag is not permission to start a second backend
against production while its incumbent can still write.

## Deployment Sequence

Probe protocol support on both compatible builds before offering a cutover.
The read-only lock availability barrier remains necessary before acquisition,
but fails normally while the incumbent owns the controller.

During the separately approved window, fence incoming writes, stop the CU
companion, drain executions and grants, and release incumbent ownership while
its API is still responsive. Save the receipt before freezing it. Perform the
final verified backup; start the candidate in ownership-standby mode, acquire
using the receipt, then perform live checks and change routing. Keep CU stopped
until the intended owner and routing are established. Do not skip the actual
CU connection/reconciliation check.

For cutback, fence/drain the candidate, release its ownership, then stop or
freeze it. Thaw the original incumbent and acquire using the candidate's latest
receipt before reopening traffic or CU. The original process/PID stays loaded,
but its controller reads the latest disk state rather than its cached copy.
Continue refreshing other cached VK settings per the existing restart protocol.

After an aborted backup, reacquire the incumbent using its own release receipt.
If a drained candidate dies before returning a receipt, verify its process and
children have exited and read the current controller file, not a backup, to
obtain the generation for acquisition. Outstanding grants are a blocker until
reconciled; these endpoints do not prove arbitrary crashed executions are safe.
For an uncertain HTTP result, inspect ownership status and retained receipts;
do not blindly repeat the complete handover.

The helper `scripts/vk-capacity-ownership.py` supports status/release/acquire
against direct loopback ports with a private token file. It performs no service
changes. Mutation calls require an explicit generation receipt. Never log the
token or use a public gateway for ownership administration.

## Transition And Approval

The Green process already running from September15 does NOT contain these
endpoints. A capability probe must reject it before any pause. Updating files
alone cannot add this support to that process. A separately approved one-time
upgrade is needed before same-PID ownership handover can be used in production.
Do not claim that implementing this code makes the current Green switch ready.

The operator explicitly prohibited the final cutover without fresh permission
and is using VK again. This implementation and its rehearsals use isolated data;
production Green must stay running and unchanged until permission is given.

## Validation

Executor tests cover competing ownership, stale generations, grant drain,
released-instance launch fencing, and same-object acquisition of latest goal
choices and used grant history. Isolated HTTP acceptance uses actual backends,
one shared controller root, private token, copied database and unchanged PIDs.
It also exercises failed-backup return and drained-candidate exit recovery.
Results and limitations are recorded in HANDOFF.md after tests complete.
