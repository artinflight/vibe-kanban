# October 10: Live chat-history repair without restarting the backend

At 22:08:14 UTC, the targeted chat read repair became live at https://vibe.local.
The operator explicitly required no restart. Earlier quiet-publication notes
are historical and do not authorize another backend changeover.

## Live behavior and ownership

The gateway's atomic routing file now selects 127.0.0.1:5640. The small proxy
forwards every mutation, other HTTP route and WebSocket upgrade to the existing
primary 5621/preview 5622. Only an exact GET
`/api/execution-processes/<uuid>/log-history` for a completed, non-dropped Codex
execution is eligible for the independent corrected reader on 5650.
Running/non-Codex executions continue to use the primary. Finite paging queries
and upstream statuses are preserved; errors are never replaced by invented text.

Authoritative unit: `vibe-kanban-exact18-pagination-20261010.service`, PID 4089781,
process start ticks 768479166. It remained running throughout. No existing service
or agent was stopped, thawed, restarted or replaced. The gateway closes browser
connections when its route file changes; those connections reconnected. No
capacity ownership, prompts, queues, model settings or credentials changed.

New enabled units are `vk-chat-history-readonly-20261010.service` and
`vk-chat-history-proxy-20261010.service`. Their own writable runtime is confined
to `/mnt/vk-storage/vk-weird-error-20261010/no-restart-reader`.
The helper uses a private SQLite snapshot and isolated workspaces. Its sandbox
binds live captures and credential-free historical native prefixes read-only;
it cannot see the authoritative database or actual native credential home.
Capacity starts paused, its independent token stays private, cleanup is disabled,
and its execution command is `/bin/false`. The proxy synchronizer opens the live
DB with SQLite `mode=ro`, updates only isolated metadata for eligible finished
executions, and refuses the authoritative DB as a write target. This supports
later completed executions without refreshing or replacing the main backend.

The compiled reader is the already accepted Staging artifact, SHA256
`4540183be41330e6dc2017111037f605a0dd0a116630c81c71d0edba10a82fb0`, under
`/mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness/streamed-reader-preparation/artifact/server`.
Its bounded streaming validator accepts 256MiB total captures, 1MiB outer records
and 128MiB native records, with two concurrent readers and 30-second replay bounds.
No alternate reader binary was released. Helper memory high/max are 2560/3072MiB;
these constrain only the new read helper. The existing frozen 5631 candidate
remains untouched. No original capture, writer marker, native transcript,
recovery sidecar or production DB was rewritten by this repair.

Proxy/synchronizer source is pinned to 3c4c03105; later source formatting has no
behavior change. The operational files remain under the named task directory,
so ordinary worktree cleanup cannot remove a running proxy's implementation.

## Validation and limitations

Evidence in the runtime directory:

- `candidate-acceptance.safe.json`: 26 histories, 27 authentic native finals,
  finite pagination, once-only final hashes and unchanged original capture hashes.
  This includes the original 18, whose recovery notices remained visible.
- `live-acceptance.safe.json`:all eight oversized captures/nine native finals
  verified through actual HTTPS, including their order and original capture hashes.
- `live-browser.safe.json`, `live-390.png`, `live-1440.png`:all five affected
  screenshot-workspace captures loaded through the ordinary live UI and earlier
  message controls at 390/1440px. No capture warning or JavaScript errors;
  65/42 WebSocket frames verified. Seen-state writes were intercepted locally.
- `activation.safe.json`:route preimage, activation timestamp, primary identity,
  reader hash and source commit. Primary start ticks matched after acceptance.
- The proxy regression passed query preservation, completed-read selection,
  write body forwarding, fallback and WebSocket routing. Running-execution
  fallback and refusal to use the live DB as a replica were separately checked.
- `pnpm run ops:check` passed. `pnpm run format` passed Rust formatting and stopped
  at missing frontend Prettier. The new JavaScript files were formatted with the
  existing SSD-backed Prettier installation and their regression rerun.

The reader explicitly returns 409 when two replays are already active. One
simultaneous browser/API probe hit that bound; the sequential HTTPS acceptance
passed. Large cold histories can take several seconds. The existing normalizer
also logged broadcast lag during the largest replay: intermediate tool/progress
row counts varied, while the authentic final replies, paging consistency and
raw capture hashes passed. This delivery restores ordinary chat reading and
saved replies; it does not certify every intermediate tool row or repair the
separate durable capture pipeline. No paid inference, production mutation test,
physical-phone test, full frontend lint/typecheck or workspace Rust suite was run.

## Current-data-preserving rollback and retention

Previous route and the small operational implementation are backed up under
`desktop:B:/vk-backups/vk-weird-error-20261010/no-restart-route/`.
To remove this read adapter, first verify the current route still selects 5640
and the original authoritative 5621 service is healthy. Atomically restore only
`route-before.json` to the gateway route file. This preserves all latest primary
data and native agents; it brings back the old large-history limitation. Then
stop/disable only the two newly introduced helper/proxy units after requests
drain. Never restore the private snapshot over production or use rollback as
permission to restart the primary. Keep the task directory and frozen Staging
candidate until their consumers are explicitly removed.

Staging integration should retain the corrected compiled reader and the live
no-restart adapter until an explicitly authorized replacement is verified. This
stream has not opened a PR or merged its independent deployment scripts.

---

The following diagnosis predates this live repair.

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

| Execution                            |  Raw bytes |
| ------------------------------------ | ---------: |
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
