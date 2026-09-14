## September 14 enforcement and reset acceptance

Scheduled admission now verifies the effective native permission profile before
activating the goal: only its workspace is writable, shell networking is disabled,
and external MCP/browser/app/plugin tools and delegated agents are disabled.
Resolved inherited MCP servers must each be disabled; an empty override table
merges with inherited entries and is insufficient. Runtime MCP inventory is checked.
Canonical path checks reject a writable workspace containing the lease, guard or
Codex home, including symlink aliases. Account-home overrides and unverifiable
alternate native profiles/hooks are rejected. Ordinary resume restores normal
permissions; the temporary restriction is not a permanent goal setting.

Real installed-Codex acceptance passed at
`/mnt/vk-storage/codexusage-capacity/vk-continuation-acceptance-9tbq06x9/results.json`:
local edits work, TCP/systemd sockets are denied, outside writes fail, a detached
TERM-ignoring child stops, inherited MCP never starts, delegated launch is rejected,
and the same goal/evidence resumes. Tool advertisement alone is not admission:
the native response still advertises a multi-agent namespace, while the attempted
launch is rejected. Two policy tests cover broadened/ignored settings and symlinks.
The earlier 62 executor tests passed; the new scope test raises this to 63.

Actual CU/VK crash and restart acceptance is recorded in
`/mnt/vk-storage/codexusage-capacity/vk-continuation-http-9uy_k779/restart-results.json`.
SIGKILL of the isolated VK backend left OS enforcement effective (583ms measured
stop), restart did not replay old permission, and fresh authority resumed the same
goal. The final server build passed. The real HTTP reset-boundary driver also
passed: renewed work stops at weekly-reset shutdown headroom, and synthetic fresh
weekly quota cannot reopen the preceding overnight period. Evidence is
`reset-boundary-results.json` in that same HTTP fixture directory. No reset credit
was consumed. The isolated backend on 49173 is stopped and its grant was revoked.

Enforcement is sufficiently validated; delivery remains open. Remaining delivery
work includes a clean source/release bundle, representative development-workflow
validation, current-runtime compatibility, deployment rehearsal and final handoff.
The current local-only profile cannot write external shared build caches, including
VK's required shared Cargo target. Do not claim arbitrary existing development
goals can run unchanged: decide and validate narrowly scoped build-cache support
before release. Network/external-tool work requires ordinary execution. VK
foreground launches preempt background work; outside-client usage reduces the
same quota floor, but instant outside-client activity detection is not implemented.
Physical phone/live Rainmeter rendering remains unverified.

Read-only service inventory confirms live Blue 4711/4712 and retained Green
4511/4512. No production service, route, state or reset was changed. Final cutover
requires the explicit approval in VK_BACKEND_RESTART_PROTOCOL.md after a concrete
candidate and rehearsal; preparation is not cutover authorization.

# STREAM.md

## Current scope

- Branch: `feature/unused-capacity`, from fork staging `9a2591916`.
- Worktree: `/mnt/vk-storage/codexusage-capacity/vk`.
- Objective: VK enforcement and integration for the approved CodexUsage unused
  daily capacity system. Configurable 21:00–04:00 scheduling, native same-goal
  suspension/resume, interactive priority, no earned resets or fresh-week spill.
- Current implementation: expiring execution permissions, independent systemd
  deadlines, native pause/interruption and offline failure tests.
- Controller/API and durable managed-session launch/restart gates are now in
  source, with direct native executor acceptance. CU scheduler, owner controls and six real HTTP/DB stop/resume cases now pass.
  Remaining: worker escape/admission policy, external-client priority limits,
  broader reset/restart acceptance and delivery.

See `VK_UNUSED_CAPACITY.md` and the latest `HANDOFF.md`. This branch is not live.
Production restart/cutover remains a separate final approval after preparation.
