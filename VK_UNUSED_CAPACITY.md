# Unused daily capacity: enforcement work in progress

CodexUsage owns the daily quota ledger. VK owns execution permission and native
goal suspension. This branch is not deployed. The new scheduling API is disabled unless its private controller and credential are configured.
The CU implementation is in `/home/mcp/code/codexusage`, branch
`feature/unused-daily-capacity`; its design and pacing checks are in
`docs/unused-capacity.md`.

## Implemented enforcement

`capacity-guard` is a small standalone executable placed inside each background
execution's systemd service. A private lease binds its ID, allocation, execution,
expiry, immutable stop time and renewal sequence. It refuses missing/corrupt
permissions, expiry, revocation, identity changes, backward sequences and clock
jumps. Once stopped it cannot reopen. An fsynced exclusive started marker blocks
replaying the same permission. VK launch metadata also carries a process epoch:
a persisted launch request from an earlier VK process cannot start after restart.

Native goal follow-ups accept internal capacity metadata only for `/goal resume`
on Codex, without message-history reset. They bind the real execution UUID before
spawning. Profiles cannot override that identity. Background execution requires
systemd; the guard cannot silently fall back to an ordinary child process.

Before launch, VK arms an absolute systemd kill timer slightly before the fixed
stop time. The service also has RuntimeMaxSec, a one-second shutdown limit,
KillMode=control-group and Restart=no. The absolute timer addresses startup delay
and a frozen guard; RuntimeMaxSec provides a monotonic backstop. The guard polls
at 100 ms and uses TERM then KILL. systemd contains detached setsid descendants
remaining in its cgroup. Finished execution timers may remain until their fixed
cutoff; their unique execution unit names cannot target a later execution.

The native client watches the same permission and starts graceful suspension two
seconds before expiry/cutoff. It calls thread/goal/set paused and turn/interrupt,
each bounded independently, then signals a successful scheduled suspension. It
does not replace the objective or clear checklist evidence. A separate permanent
stop flag prevents ordinary pause bookkeeping from reopening that execution.
RPC acknowledgement alone is not proof of process exit. The OS guard remains
responsible if native RPC or VK itself fails.

## Validation

All test homes and artifacts live on the mounted SSD. No model allowance,
earned reset or real development agent was used by these tests.

- `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target CARGO_INCREMENTAL=0 cargo test -p capacity-guard`:
  five fence tests passed (expiry, renewal, identity/revocation, clocks, lifetime).
- `python3 scripts/test-capacity-guard.py --guard /mnt/vk-storage/cargo-target/debug/vk-capacity-guard`:
  real user-systemd tests passed for expired start, lease expiry, lost supervisor,
  missing permission, changed cycle, renewed permission at hard deadline and a
  frozen guard. Each launches a detached TERM-ignoring child, verifies containment
  and rejects permission replay. Latest results:
  `/mnt/vk-storage/codexusage-capacity/guard-acceptance-tk5vyjt5/results.json`.
- Ignored `native_goal_runtime`, offline fixture scenarios `capacity-stop` and
  `capacity-expiry`, passed against installed Codex App Server. The strengthened
  v2 scenarios preserve a completed checkpoint through active-turn interruption
  and same-thread resume, checking objective and creation identity. Homes:
  `/mnt/vk-storage/codexusage-capacity/vk-continuation-{stop,expiry}-v2`.
- `cargo test -p executors --lib`: 55 passed, one opt-in native test ignored.
  Includes persisted-request rejection across VK process epochs.
- The actual systemd spawn + guard + native client integration passed initial
  and same-goal resumed expiry runs (about six seconds each, before the eight
  second deadline), preserving completed checkpoint evidence. Reproduce all
  native checks with `python3 scripts/test-native-capacity.py --guard /mnt/vk-storage/cargo-target/debug/vk-capacity-guard`.
- The harness also supports `VK_GOAL_TEST_GUARD` with an absolute guard binary and
  `VK_USE_SYSTEMD_RUN=1` to exercise the actual spawn/guard path with the native
  expiry fixture. Use a fresh isolated `CODEX_HOME` containing `vk-continuation`.
- Latest reproducible native suite: all four cases passed, artifacts at
  `/mnt/vk-storage/codexusage-capacity/vk-continuation-acceptance-jdnps8ur/results.json`.
- `cargo check -p executors -p server` passed before the final test refinements.
  The final `cargo run --bin generate_types` compiled the executor/server dependency
  chain and regenerated shared types successfully. `pnpm run ops:check` passed.
  Full workspace/frontend release checks remain for delivery.
- `pnpm run format` uses the matching isolated Prettier install at
  `/mnt/vk-storage/codexusage-capacity/format/node_modules/.bin` on PATH.

## Remaining integration; not release ready

The private VK controller and API now exist in source. The controller holds an
exclusive filesystem lock, records eligibility/goal identity and intent before
launch, binds the execution UUID at lease creation under the same lock, and
persists renewal revisions before extending the permission file. Only one grant
can be outstanding across eligible goals, so CU capacity is shared. Restart
marks outstanding grants stopping and revokes their files before accepting work.
Old process epochs/revisions, changed native objectives, late renewals and reused
permissions are rejected. Pending or uncertain grants block replacement work.

Background launches never use the ordinary execution queue. The common native
execution entry point revokes background permission and records a ten-minute
foreground hold when interactive work starts. Managed eligible sessions reject
ordinary/queued launches; use the owner eligibility control to take a selected
goal out of this mode before manual continuation. Other ordinary sessions retain
their existing behavior. The API also checks running foreground executions before
a start or renewal, including long foreground runs beyond that hold.

`POST /api/capacity/stop` revokes first, invokes native pause/interruption, and
checks the deterministic execution unit and cgroup before clearing its grant.
An absent unit cannot allow a delayed launch because its durable grant/file has
already been revoked. Stop uncertainty remains visible and blocks replacement.
CU still needs to drive this reconciliation on startup and expired/completed runs.
Seven focused authority tests passed, including revocation before launch,
cancelled grant replay, restart/late renewal and persistence failures. The expanded
native acceptance suite passed (four stop/expiry cases plus two managed executor
runs) at `/mnt/vk-storage/codexusage-capacity/vk-continuation-acceptance-7ilu_z49/results.json`.
HTTP/DB integration acceptance is still required; the controller/executor path
has been exercised directly with a real offline native goal.

Configuration (not installed into a live service):

- `VK_CAPACITY_STATE_DIR`: private absolute durable controller directory on SSD.
- `VK_CAPACITY_GUARD`: absolute built guard executable.
- `VK_CAPACITY_TOKEN_FILE`: absolute private 0600 bearer token file, at least 32
  characters. CU reads the same secret server-side; no browser/Android exposure.
- `VK_USE_SYSTEMD_RUN=1`: mandatory for background execution.

API: authenticated GET `/api/capacity` and `/api/capacity/candidates`; POST
`/api/capacity/eligibility`, `/start`, `/renew`, `/stop`. Mutations require the
current controller epoch/revision. Start also specifies a new grant UUID, selected
session UUID, allocation identity and fixed expiry/stop times. Renew specifies the
existing grant/allocation/sequence and a later expiry within its fixed deadline.
No endpoint redeems credits. The CU bridge in `src/vk-capacity.js` validates the
origin, keeps credentials private and never retries ambiguous mutations.

CU still needs the shared scheduler, interactive-priority preemption (including
same-account work outside VK), adaptive shutdown reserve, reset interlock during
stopping/uncertain execution, owner configuration and eligible-goal UI. The fixed
quota floor must remain authoritative; native token budgets cannot replace it.
Full cross-system failure tests and normal-use regression checks remain.

Containment currently covers descendants in the service cgroup. Explicitly
remote/external launches that escape the cgroup must be prevented or enrolled in
the same deadline before a profile is eligible. This limitation must be resolved,
not hidden behind a successful local setsid test.

No live service, database, route, frontend asset pointer or APK was changed.
Prepare a clean, validated deployment artifact and current live-state inventory
before the final production-cutover approval described by the restart runbook.

## September 14 CU scheduler and HTTP acceptance checkpoint

CU now implements durable shared scheduling and private owner controls. Real
isolated VK HTTP/SQLite/systemd/native Codex tests passed long-turn stale-quota
interruption, same-goal/evidence resume, independent expiry after CU supervision
loss, restart reconciliation, shared quota-floor stop and zero reset calls.
Artifacts: `/mnt/vk-storage/codexusage-capacity/vk-continuation-http-9uy_k779`.
CU drivers: `ops/test-capacity-integration.mjs` and `ops/test-capacity-controls.mjs`.
Browser selection/window/owner checks passed at desktop and mobile sizes.

VK source changes after controller commit: status reports running IDs and process
states; start reloads workspace after ensure_container_exists (real HTTP exposed
the stale container_ref bug). Candidates and actual native admission preserve
needs-input/budget pauses. Native regression passed for those final changes, including needs-input and
budget-limit rejection: vk-continuation-acceptance-06p90z_e/results.json.

Remaining: prevent/enforce remote or external worker escapes; define honest
interactive priority for clients outside VK; broader cross-system reset/restart
acceptance and final prepared deployment. Keep production disabled. This feature
worktree's debug dev_assets holds only isolated fixture data, never live data.
The isolated 127.0.0.1:49173 backend is stopped; no running DB executions or
outstanding grants remain. Preserve SSD evidence.
No production VK service, database, frontend pointer or account allowance changed.
