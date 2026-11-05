# Codex resume history duplication — source fix, 2026-11-03

Status: source fix locally verified; backend deployment and production acceptance pending.
Branch: `vk/95c6-vk-duplicate-con`. Verified operator staging baseline:
`d90e347461688c06f55713e8a1057c52e51cfd00` (`git ls-remote fork`).

## Cause and solution

Native initialize uses the caller's `clientInfo.name` in its `userAgent`. Vibe
initializes as `vibe-codex-executor`, but `narrow_resume_supported` accepted only
`codex_cli_rs/0.159.2`. The deployed native response identifies itself as
`vibe-codex-executor/0.159.2`, so Vibe omitted `excludeTurns` from resume requests.
The native response included the complete prior thread, and Vibe's raw process
logger persisted it again, split across many outer JSONL records. Repeated
resumes therefore multiplied storage of existing conversation history.

The fix recognizes both exact qualified 0.159.2 identities. It retains the
existing request construction shared by ordinary, original-worker deadline and
delegated resumes, plus empty-turn verification. Other client names/versions
retain their original protocol behavior. The native conversation remains available
to the model; `excludeTurns` controls returned history, not native context.
There are no database, generated-type, frontend or log-format changes.
Requalify this guard when the installed native version or initialize name changes;
unsupported identities intentionally retain the original resume behavior.

## Investigation context (historical evidence, not new production acceptance)

The November 3 investigation measured 4.82 GiB of process-log growth over about
47.5 hours, accounting for most of the 5.25 GiB OS allocation increase since its
November 1 baseline. This is an observed interval, not a predicted future rate.
One 202,859,155-byte process log contained an initial 183,783,269-byte native thread
response. An investigator's native-only resume with `excludeTurns=true` returned
the same thread with zero turns in 6,672 bytes and started no model turn.
These observations establish the mechanism and native support; they do not prove
that a rebuilt Vibe backend has been installed or accepted.

Investigation provenance:
`/mnt/vk-storage/os-drive-growth-20261103/report.html` and
`/home/mcp/code/Operations/tasks/os-drive-growth-20261103/`.
No transcript payloads or private history bindings are copied into this document.

## Validation

- Seven integrated client regressions pass, including the real Vibe initialize
  identity, ordinary/delegated/deadline resumes and legacy compatibility.
- Twenty-six adjacent JSON-RPC compatibility and history normalization regressions
  pass. One private captured-response test remains ignored; no private fixture was
  supplied or represented as tested.
- Two standalone Rust checks compile the actual old/new predicates, reproduce the
  deployed identity false-negative and confirm exact-version/name scope.
- `pnpm run format`, `pnpm run ops:check` and `git diff --check` pass.
- These initial source-fix checks did not cover full workspace/CI validation.
  The broader staging integration attempts are recorded below. Candidate backend
  build, live Vibe resume/send, matched disk-growth observation and deployment
  remain unperformed.

Integrated command: `cargo test --offline --locked -p executors --lib
executors::codex::client::tests -- --test-threads=1`. The resulting test binary also
ran the `executors::codex::jsonrpc::tests` and
`executors::codex::normalize_logs::tests` filters. It used the pinned toolchain,
recovered offline dependency cache, existing shared SSD target, one build job,
`SQLX_OFFLINE=true` and disabled incremental compilation. No dependencies were
installed on the OS drive. Temporary node dependency links used for formatting
were removed after the successful full formatter run.

Task evidence directory: `/mnt/vk-storage/vk-duplicate-con-20261103-95c6/`.
The integrated fixture now returns historical turns when `excludeTurns` is absent,
so the live-identity regression exercises the original defect. Tests inspect the
actual wire requests, returned thread/model/permission metadata and raw log output,
retain new turn output, and reject an ignored flag without retrying. A synthetic
historical payload exceeds 32 KiB; successful narrow resumes capture under 16 KiB
across three resume paths with no historical marker. The legacy control retains
the full historical payload and captures over 32 KiB. These are fixture bounds,
not production storage savings.

## Staging integration

[PR #290](https://github.com/artinflight/vibe-kanban/pull/290) targets staging with
the operator-requested rebase method. Fresh staging was
`d90e347461688c06f55713e8a1057c52e51cfd00`; `git rebase fork/staging` completed
without conflicts or source changes. Original feature commit
`83b96bc3b1ef51a6a6d5dc6e7c51dcdd7abf7057` remains immutable provenance; the PR's
final checks and merge event are authoritative for rebased integration IDs and
readiness. Git integration does not deploy or restart the backend.

The required local integration baseline was attempted using the shared SSD target,
one Cargo job and disabled incremental compilation:

- Full formatting and ops governance pass.
- All four frontend type checks and local-web/UI lint pass.
- `pnpm run check` and `pnpm run lint` stop in the Tauri dependency graph because
  the MCP host lacks `glib-2.0.pc` (GLib >= 2.70). These are incomplete full checks.
- `cargo test --workspace --offline --locked -- --test-threads=1` was invoked, then
  its owned process group was stopped after the same missing mandatory dependency
  was verified in both preceding checks. It is not a passing workspace test run.
- Hosted PR checks supply broad validation on the final PR head. Their actual
  conclusions, including any private-input skips, govern source readiness; local
  host limitations must not be represented as successful full validation.

Evidence: `integration/` beneath the task evidence directory. Existing backend
PID, service invocation and executable hash were recorded before integration and
must match a fresh final readback. The operator explicitly forbids a backend
restart for this task. Deployment and production acceptance remain next-release
work under the existing runbook.

## Deployment requirements and acceptance

1. Integrate the fix through operator `fork/staging` after required branch checks.
   No PR or main promotion is implied by the local fix. Prepare a backend using
   the existing bounded, owned SSD build procedure; preserve the exact private
   retained-history input and all current live changes. Keep the latest public
   frontend and its retained assets. No frontend publication or migration is needed.
2. Follow `VK_AGENT_DEPLOYMENT_RUNBOOK.md`, `BACKEND_DEPLOYMENT_HANDOFF.md` and
   `VK_BACKEND_RESTART_PROTOCOL.md`: fresh Desktop B recovery proof, current-data
   candidate/fallback rehearsal, fresh custody/controller receipts, ingress/writer
   fences, and a coordinated drained boundary under deployment authorization.
   Do not interrupt active agents to force installation or reuse consumed receipts.
3. After activation, verify the serving executable hash and preserved service,
   database, native-home and protected-reader identities. Resume a selected existing
   large-history thread **through Vibe**, verify `excludeTurns=true` and empty
   returned turns, and measure its actual persisted response and outer log bytes.
   Check recent/protected conversation readability, ordinary send, resume metadata,
   approvals, queues, review/settings and resumed consumers. Provider QA must have
   an explicit bounded budget; protocol mocks are not provider acceptance.
4. Compare process-log and OS allocation growth over matched observation windows
   with execution counts/workload noted. New tool/output logs will still grow;
   this fix removes repeated historical resume payloads, not all disk writes.

A read-only check during this task found serving executable SHA256
`137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`,
matching the investigation's affected backend. This source fix has not been deployed.
No live provider turn, service restart, agent interruption, data move or deletion
was performed. Existing accumulated logs retain their space usage. Any later
reclamation needs an exact reviewed file list, live consumer/reference checks,
verified recovery and separate operator authorization; do not truncate or rewrite
retained history as part of this prevention fix.
