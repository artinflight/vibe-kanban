# VK errors recovery — September 14, 2026

## Scope and confirmed failures

1. `VK::Error` workspace `7eb790bd-68e0-4f87-99fe-ff989fbed496` could not
   receive follow-ups. Its branch `vk/7eb7-vk-error` was registered at
   `/mnt/vk-storage/vk-error-fix/source` while VK expected
   `/home/mcp/code/worktrees/7eb7-vk-error/_vibe_kanban_repo`. The live backend
   rejected both Git status and follow-up with `WorktreeError` HTTP 500.
2. `MM::Orchestration Agent` session `c86e3837-e3f7-44bc-8df8-8604b8d220ef`
   repeatedly failed `thread/resume` decoding. Installed Codex 0.153.4 returns
   `misalignmentPolicyViolation` in one historical failed turn; VK's pinned
   0.116.0 protocol does not know that category. Execution
   `f81375c4-a8d7-41ee-b739-2997bd348766` supplies the captured reproduction.
   Its response contains 154 turns. The category describes a real upstream
   safety error; compatibility must preserve the message and failed status.

The prior compatibility commit `3d83e6966` was based on old source and was not
in the live backend. Its recursive rewrite could also touch arbitrary tool data.
This repair is based on current fork/staging `75276e79f`, matching the live binary.

## Runtime recovery completed

The relocated worktree was clean and had no process using it as its working
directory. `git worktree move` restored its expected SSD workspace path without
changing its branch or commit. A compatibility symlink preserves the former
repair-source path. The exact live Git-status request changed from failure to
`success:true`, reporting the preserved `3d83e6966` HEAD and no dirty files.
No follow-up prompt was sent on the user's behalf.

## Source repair

Only typed protocol error locations receive the unknown-category fallback:
thread turn errors in resume/read/fork/rollback responses, turn responses and
live error/lifecycle notifications. Known categories, malformed known payloads,
user tool data, error text and failed turn status are preserved. The normalizer
also uses the compatible response decoder to retain thread/model metadata.
The raw stored response and native conversation are not edited.

Tests include the actual await-response path, a sanitized reproduction fixture,
notification rendering, known/malformed categories, structured future variants,
and preservation of tool payloads. A private ignored integration test can decode
the captured full response using `VK_TEST_RESUME_RESPONSE`.

## Runtime authority and deployment boundary

Fresh routing and process evidence: production is the already-running
`vibe-kanban-blue-pr114-production-20260914.service`, PID 2150526, port 5031.
The service named Green on 4511 is frozen (`cgroup.freeze=1`); its listening
socket does not mean it serves requests. Do not restart or thaw either retained
standby. Historical names in STATE/runbooks are not current commands.

The backend fix requires a validated binary and approved handover under
[the restart protocol](VK_BACKEND_RESTART_PROTOCOL.md). No production restart,
route switch, frontend swap or conversation-history edit has occurred here.
Do not claim the Media Management live resume is fixed until it is exercised
against the repaired deployed backend.

Evidence and private capture: `/mnt/vk-storage/vk-errors-2/evidence/`.
Build output uses `/mnt/vk-storage/cargo-target` with incremental compilation off.

## Validation results

- Live VK::Error Git status passes at its restored original path. A deliberately
  mismatched-executor follow-up reaches the expected HTTP 409 check after
  workspace validation, with execution count unchanged at nine; no prompt was
  launched. This replaces the previous workspace HTTP 500 failure.
- All 73 executor unit tests pass; the captured-response integration also passes
  and retains the original thread ID and all 154 turns. Unknown error rendering
  is covered; the historical failed status and safety message are retained.
- Server workspace tests: 323 passed, four ignored, excluding Tauri. The complete
  workspace command and full lint cannot run here because GLib is missing.
  Focused executor Clippy passes. Frontend lint and all four frontend type checks
  pass; type checks require `NODE_OPTIONS=--max-old-space-size=4096` on this host.
  The initial default-heap check failed before that successful rerun.
- Formatting, ops governance and diff whitespace checks pass.
- Optimized server build succeeds. Candidate:
  `/mnt/vk-storage/vk-errors-2/release/server`; the existing external frontend is
  retained. This binary must not be used without `VK_FRONTEND_DIST_DIR` because
  the backend-only build has the standard dummy embedded frontend.
- Actual old-binary HTTP reproduction: an initial fixture turn completes and
  its next follow-up fails with the reported unknown-category decoding error.
  On the repaired binary, two follow-ups to that same fixture session complete,
  retaining its native thread identity. The fixture uses an offline app-server
  protocol peer, not a live model request or the original user's agent.
- The handover rehearsal uses a private copy of the 922-workspace live database
  plus that fixture. Injected backup failure restores the incumbent's original
  PID and route. Successful switch takes 5.20 seconds (4.86 capture/fencing,
  0.34 activation); recovery takes 0.09 seconds and preserves the incumbent PID.
  Those timings include the replica VK database, not all native-home databases;
  a full native-history backup measurement is recorded separately before proposing
  a production window. Both isolated rehearsal services are stopped afterward.
- An online backup delta is Desktop B: SHA256 verified. This is preparation;
  latest state must still be captured under the approved final writer fence.

PR: https://github.com/artinflight/vibe-kanban/pull/115 (targets staging).
The source/build commit is `fc784f7a2`; deployment preparation is under
`/mnt/vk-storage/vk-errors-2`. No production switch is authorized or performed.

## Build resource lesson

Running the release build and broad tests inside the native agent's 1.5 GiB
memory-high cgroup caused heavy swap/reclaim. Their verified process groups were
moved into the dedicated transient `vk-errors-2-build.scope`, bounded at 12 GiB
memory-high / 16 GiB maximum. Future heavy validation should start in its own
bounded build service rather than inherit the agent's memory pressure. Production
and other agent memory limits were not changed.

The full online delta capture, including native-home SQLite snapshots and Desktop
hash verification, measured 25.35 seconds in a bounded backup service after
removing compiler memory pressure. Plan a roughly 30–45 second production window,
with a strict capture timeout and recovery on abort; this is an estimate, not a
five-second production guarantee. The latest backup manifest records its full
prior-backup dependency chain. Four additional shared-history Codex processes
(OharaFit/CodexUsage app servers and two tmux-owned connections) must be briefly
paused by exact PID/start/inode identity only under the final approval. Private
process pause/resume and wrong-identity rejection were rehearsed successfully.
Other live VK turns must finish before cutover. The controller refuses to bypass
that condition and preserves all retained standby processes.
