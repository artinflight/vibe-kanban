# Two concurrent selected capacity goals

CU may authorize up to two selected native goal executions at once. VK advertises
`maxConcurrentGoals: 2` and `targetedStop: true` on its existing authenticated
capacity status route, with selected session/workspace identities for scheduling.
Older CU clients still issue one permission; newer CU falls back to one when the
capabilities are absent. No controller-state or database migration is needed.

Admission remains serialized under the controller lock. A second grant requires
an already bound, non-stopping, unexpired first grant in the same controller epoch,
allocation and hard-deadline window. The third grant is rejected. Duplicate native
threads and concurrent chats in one workspace are rejected. Each accepted grant
keeps its own native execution, lease and independent systemd deadline/guard.

`POST /api/capacity/stop` accepts an optional `sessionId`. When supplied, only that
session's permission is revoked and its native turn/process stopped. Omitting it
retains the existing stop-all behavior. Revision/epoch and owner authentication
still apply. Launch failure revokes only the failed session. Interactive priority,
startup reconciliation, ownership handover and shared CU budget stops remain
global. Pausing preserves the existing native goal objective and evidence.

CU owns the shared quota accounting: adding an agent does not add allowance.
Per-agent caps count overlapping total account consumption, not attributable
agent usage. Only explicitly selected goals are affected. Ordinary agents remain
outside this scheduling mechanism.

## Validation and deployment

The controller regression verifies independent leases/renewal/revocation,
third-grant rejection, shared allocation and duplicate-thread rejection.
82 executor tests pass (3 ignored). The rebuilt server passes real isolated HTTP,
installed Codex runtime and systemd acceptance with two long active native turns:
concurrent start, third-agent rejection, same-workspace rejection, targeted stop
with peer renewal, CU restart reconciliation and same-goal resume, shared daily
floor, independent expiry after loss of CU supervision, weekly reset deadline,
no permission replay after replenishment, retained objectives/evidence and zero
reset calls. Evidence:
`/mnt/vk-storage/codexusage-capacity/vk-continuation-two-__6xzjtl/results.json`.
The reproducible runner is in the companion CodexUsage change:
`ops/test-concurrent-capacity.py` and `.mjs`.

`pnpm run format` and `pnpm run ops:check` pass. Frontend type checks and ESLint
pass. Full `pnpm run check`, `pnpm run lint` and `cargo test --workspace` are blocked
at desktop/Tauri by this host's missing GLib/GTK pkg-config libraries. Server-only
checks are recorded in the handoff; the desktop checks must remain explicit rather
than being represented as passing.

This backend source must be deployed before two agents can run in production.
The operator/deployment agent owns that update; this change does not restart,
stop or reroute live VK or prepare a cutover. Deploy from reviewed staging using
the existing protocol. After deployment, verify advertised capabilities through
the private bridge and that CU shows two slots. There is no new automatic reset
behavior, enrollment, cap, schedule or default-setting mutation.
