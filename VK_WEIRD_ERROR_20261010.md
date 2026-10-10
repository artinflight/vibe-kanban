# October 10: Large conversation captures rejected by the history reader

The screenshot's message, “Capture completeness could not be verified. Earlier
messages are not a current status report.”, comes from the deployed conversation
history hook when the finite history API returns `capture_error`.

## Verified cause

Read-only discovery at 19:45 UTC found `vibe.local` using backend port 5621,
preview proxy 5622, PID 4089781, unit
`vibe-kanban-exact18-pagination-20261010.service`. Older deployment notes in this
branch do not identify the current service.

The deployed source snapshot is under
`/mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness/exact18-preparation/source/source`.
In `crates/server/src/routes/execution_processes/log_history.rs`,
`capture_error_for_process` calls `validate_native_capture` with the review
subsystem's `MAX_RAW_BYTES` (33,554,432 bytes / 32 MiB). The strict reader rejects
oversized logs. The caller collapses every validation error into the same
incomplete/damaged/unverified capture response, with zero entries.

Workspace `4e18b628-4a0d-4102-b111-0eca9dc76733` (`VK::Staging Check`), session
`7d6734c1-c8d0-4d55-ac27-b1f763d15a6e`, reproduces the error through the live
`/api/execution-processes/{id}/log-history?limit=50` endpoint:

| Execution | Raw bytes |
| --- | ---: |
| a310e7af-f663-4267-84e9-96b9a6b17048 | 34,894,910 |
| b8338039-efcc-45f4-b45a-d751f5f3334f | 34,997,373 |
| 00babbe8-b6fb-4afd-98f0-a93be34e4c52 | 35,289,408 |
| 794c1b74-2689-4cec-89d5-17990fc40ac0 | 34,153,157 |
| b6643fdb-9966-4697-8da1-b07972d60e91 | 60,343,746 |

All five have completed status and exit zero. Independent inspection verified
each outer log is UTF-8, newline terminated, and contains only valid Stdout/Stderr
JSON records; concatenated stdout is newline terminated and every native JSON
record parses. Every capture sidecar says `closed`, and each stream contains one
native `turn/completed` event. This establishes the size-limit rejection; it
does not certify task success or review acknowledgement.

An earlier execution, `ce235aa7-1e5a-4b7a-a916-e8493353cd4a`, has 32,300,033 bytes
and returns nine entries without a capture error.

## Scope and next step

This is diagnosis only. No runtime, application code, conversation bytes,
review state, service configuration or live deployment was changed. The repair
should give chat-history validation its own bounded streaming policy, preserve
review safeguards, and distinguish oversized captures from actual corruption.
Prepare that change against current staging; this branch's source predates the
deployed history reader. A browser refresh alone cannot change this rejection.

Screenshot and formatter output are stored on mounted secondary storage at
`/mnt/vk-storage/vk-weird-error-20261010`. `pnpm run format` was attempted: Rust
formatting passed, but frontend formatting stopped because this worktree lacks
`prettier`. No product changes or browser acceptance were exercised.
