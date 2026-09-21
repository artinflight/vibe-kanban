# Overnight capacity workflow audit — 2026-09-21

This is a consolidated backend candidate following the failed September 21
scheduled start. Production VK must not be restarted by this task.

## Corrections

- PR121 corrected app-server `usageLimited` versus SQLite `usage_limited`.
- Candidate discovery and pre-grant launch now verify the persisted native goal
  and its identity, not just the progress sidecar. Native resume validates again.
- Selection no longer prevents ordinary work. Active same-goal takeover revokes
  permission, pauses native work and verifies the execution cgroup is stopped.
  Selection remains saved. Foreground priority fences later scheduled starts.
- Follow-up admission occurs before slot acquisition/reset, so a selected run
  cannot occupy the slot required to replace it. Active-turn queue/steer messages
  use the same handoff. Ordinary unselected steering retains its existing path.
- Native control commands such as `/goal resume` bypass recovery-prose wrapping.
  The integrated rehearsal reproduced the previous failure: after an interrupted
  run the wrapper converted a command into ordinary chat, so no autonomous
  continuation started. Ordinary prompts still retain interrupted-turn context.
- Asynchronous launch failures persist a specific reason. CU records start
  requests, failed starts and stops durably and shows recent activity.

## Validation setup

The HTTP fixture is disposable, has exactly one session and no auth.json, and
uses an isolated Codex home/SQLite database, port 49173 and a local deterministic
Responses provider. It runs the installed native Codex app-server, actual VK
HTTP routes, actual CU scheduler, and real systemd execution containment.
No production session, quota, selection or service is mutated by these tests.
The manual-priority ten-minute hold is advanced only in the stopped fixture's
ledger, rather than sleeping for ten minutes. Actual process/permission/reset
deadlines use real wall time.

The debug build uses the checkout's `dev_assets` path. In this isolated checkout
that path points to the disposable fixture's `release-xdg/vibe-kanban` directory.
The initial empty auto-created debug directory is retained in the audit artifact
directory. Never point a debug test checkout at production data. The fixture's
profile launcher override must match this checkout's local test provider.

## Final-source validation

- `cargo test -p executors --lib`: 74 passed, zero failed, three ignored.
  Log: `/mnt/vk-storage/cu-pace-ui/audit-final-executor.log`.
- `cargo build -p server --bin server` passed after the recovery-command fix.
  Log: `/mnt/vk-storage/cu-pace-ui/audit-resume-build.log`.
- `python3 scripts/testing/capacity-workflow-audit.py /mnt/vk-storage/cargo-target/debug/server`:
  all 12 result entries passed. This exercised actual native usage-limited resume,
  readiness rejection for blocked/completed/budget-limited/input-needed goals,
  queue-route active takeover, idle manual native resume after interruption,
  selection retention and scheduled resume after manual work.
  Evidence: `/mnt/vk-storage/codexusage-capacity/workflow-audit-20260921/results.json`.
- That rehearsal also ran CU's real HTTP integration against the same candidate:
  stale quota stopped the long active turn in 4.5 seconds; independent expiry
  stopped it after supervision loss; restart did not renew old permission; the
  protected quota floor stopped work; zero earned-reset calls occurred.
  `cu-http-results.json` and `reset-boundary-results.json` in the fixture directory
  record nine and three passing entries respectively. Weekly shutdown headroom
  stopped renewed native work and new-week readings could not reopen that period.
- `scripts/test-capacity-guard.py --guard /mnt/vk-storage/cargo-target/debug/vk-capacity-guard`
  passed independent systemd cases, including frozen supervision, detached children,
  changed cycle and hard deadline. Evidence: `guard-acceptance-k9qxg0yy/results.json`
  under `/mnt/vk-storage/codexusage-capacity`.
- `scripts/test-native-capacity.py --guard /mnt/vk-storage/cargo-target/debug/vk-capacity-guard`
  passed seven results: actual native stop/expiry/resume, workspace edits and build,
  descendant containment, inherited-MCP exclusion and ordinary permissions restored.
  Evidence: `vk-continuation-acceptance-7n_g5mtk/results.json` under the same root.
- `pnpm run format` and `pnpm run ops:check` passed. Full `pnpm run lint`
  passed local-web/UI lint, then stopped in the desktop workspace build because
  this host lacks the required gobject-2.0 development library.
- CU: 100 Node tests, real one-day scanner, JavaScript syntax and desktop/mobile
  activity-panel/browser-toggle checks passed. Logs/screenshots are under
  `/mnt/vk-storage/cu-pace-ui/audit-*`.

These tests use the installed native runtime and real local control/process paths,
with a deterministic offline model provider and synthetic account observations.
They do not claim a live overnight account run or eliminate quota-reporting delay.
Full workspace Rust/remote builds were not repeated: this host has about 5 GB free
on its build SSD; the relevant executor suite, backend build and actual integrated
runtime were validated instead. No SQL schema, shared API types or remote code changed.

## Delivery boundary

Deploy the consolidated VK staging backend (including PR121 and this audit), and
CU staging for the accompanying durable activity history. Preserve existing runtime
configuration, private credentials, frontend asset override and selected goals.
The production checkout contains unrelated edits: do not replace it wholesale.
Deployment/restart remains operator-owned. No production service was restarted,
no live goal was resumed, and no selection or scheduling setting was changed.
At acceptance completion VK still had PID 1674994 and its September 15 start time.
Do not describe the merged source as live until the operator deploys it.

