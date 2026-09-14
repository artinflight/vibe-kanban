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
