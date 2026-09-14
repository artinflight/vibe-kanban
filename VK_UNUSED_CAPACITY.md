# Unused daily capacity: enforcement work in progress

CodexUsage owns the daily quota ledger. VK owns execution permission and native
goal suspension. This branch is not deployed, and no scheduling API is enabled.
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

The authenticated VK scheduling API and durable managed-goal records are still
required. They must supply trusted metadata, serialize grant/renew/revoke,
reject stale/expired generations, reconcile ambiguous launch/stop outcomes,
and prevent ordinary queued/recovery paths from resuming managed background
work without fresh permission. Actual process/cgroup termination must be observed
before reporting stopped or issuing replacement work. An active native goal left
on disk after hard kill must be paused before thread loading. Explicit resume
already follows this ordering; ordinary managed-session paths need gating.

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
