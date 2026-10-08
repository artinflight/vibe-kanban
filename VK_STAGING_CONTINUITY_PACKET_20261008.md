# VK Staging Continuity Packet — October 8, 2026

## Purpose

This packet transfers the durable state of `VK::Staging Check` to a fresh agent
session without resuming the blocked Codex thread or treating its historical
instructions as current authority. It records the mission, current evidence,
constraints, acceptance criteria, and unresolved questions. The receiving agent
retains discretion over implementation.

The source workspace is clean and pushed:

- workspace: `VK::Staging Check`
- worktree: `/home/mcp/code/worktrees/4e18-vk-staging-check/_vibe_kanban_repo`
- maintenance branch: `vk/4e18-vk-staging-check`
- maintenance head: `7a025f1082df08095d7ffc8af3fd743a96d92208`

## Objective

Restore trustworthy VK release preparation after the October 7 verification
incident. The immediate desired outcome is a reviewable prevention and recovery-
verification repair that closes the incident class while production remains
untouched. A restart or cutover is a later decision, not part of this handoff.

The work matters because an unsupported inspection argument reached normal server
startup, opened the wrong database, and allowed startup reconciliation to affect
shared worktrees. Recovery restored the backed-up baseline without overwriting
survivors, but preservation of every post-backup edit is not proven.

## Current Authority

### Hard requirements

- Production deployment, restart, route switching, and cutover remain blocked.
- Existing production data, active work, shared worktrees, incident evidence, and
  surviving files must not be overwritten or placed at risk by development or
  rehearsal.
- Prevention work must be isolated and reviewable; it must not be mixed into the
  maintenance branch or the pending release candidate.
- Ambiguous, wrong, empty, or mismatched runtime identity must fail closed before
  stateful startup or workspace reconciliation can affect shared state.
- Supported read-only inspection behavior must terminate without starting the
  server or initiating cleanup/reconciliation side effects.
- An unsupported invocation must be rejected before database opening, server
  startup, or cleanup/reconciliation side effects.
- Shared workspace paths must remain unchanged when ownership or database/root
  identity is missing or cannot be positively established.
- Recovery verification must support its claims with content and metadata
  evidence, not path existence alone, and must represent journal gaps and
  post-backup uncertainty truthfully.
- Tests must reproduce the incident conditions only in isolation or private
  fixtures. A rehearsal must be incapable of modifying real shared worktrees.
- Consumed incident placement and cleanup scripts must not be replayed.
- Desktop `B:` remains the retained archive provider. Bulky temporary work belongs
  on mounted `/mnt/vk-storage`, subject to current capacity.

### Current non-authority

- Earlier conditional cutover authorization does not waive the new incident gates.
- The old native goal objective and completed checkpoints are historical evidence,
  not permission to deploy.
- The consumed approval for removing 27 verified SSD archive duplicates applied
  only to that exact completed action; it does not authorize further removals.
- Green CI on the candidate and incident-review PRs does not establish recovery
  completeness, safe startup behavior, or deployment readiness.

### Preference

Prefer the smallest coherent repair that establishes the safety properties and
can be independently reviewed. The receiving agent should choose the design,
test structure, and implementation approach after inspecting current source.

## Incident Facts

At approximately 23:16 UTC on October 7, the candidate rollback server was run
directly on the host with the guessed argument `--vk-build-info`. The source
supported `--capacity-build-info`; the unknown argument fell through to normal
startup. The unintended process opened the legacy default database rather than
the production green-XDG database. Startup orphan reconciliation then treated
shared worktrees as untracked.

The unintended process was stopped. Production and the companion service were
not restarted. Recovery used authenticated Desktop-backed archives and atomic
no-replace placement:

- 106,286 missing baseline paths across 85 worktree roots were restored.
- 116,402 regular files were hash-verified before placement.
- 24,016 existing paths were retained rather than overwritten.
- 171 worktree/Git-registration placement operations completed.
- The affected owner's uncommitted edits were reconstructed from pushed source
  and retained transcript/tool evidence.
- The audit found no remaining missing path from the baseline list.

These facts do **not** prove preservation of every edit to an existing filename
after the accepted backup. That remains an explicit recovery limitation.

Authoritative incident record:

- `VK_RECOVERY_INCIDENT_20261007.md`
- incident evidence: `/mnt/vk-storage/vk-combined-release-20261007/incident-2316`
- Desktop packet:
  `B:/vk-backups/vk-incident-20261007T2316/incident-20261007T2316-evidence.tar.zst`
- packet SHA-256:
  `bf757ac1e257c7b9ca5edacba7491177b300c1db9677f0e94018dae9e8d88aa7`

## Current Verified Live Snapshot

Observed read-only at `2026-10-08T08:29:14Z`:

- `vibe.local` routes through the standby gateway to green port `5511`.
- production service PID: `3027197`, started October 5 at 15:33 UTC.
- production executable:
  `/mnt/vk-storage/vk-green-cutover-20261005/release/server`
- API version: `0.1.42`; preview proxy port: `5512`.
- production database:
  `/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite`
- database `PRAGMA quick_check`: `ok`.
- saved chat messages: `12`.
- one non-dropped execution was running; it was the separate `VK::Error`
  inspection session, not evidence that Staging was idle.
- mounted SSD available bytes: `6,308,020,224` (reported 99% used).

The observed free space is below the previously validated 8 GiB recovery floor.
It is therefore not current evidence that a full capture or rehearsal can run
safely; future work must re-measure and respect the applicable proven bound.

These values are volatile and must be refreshed before relying on them. Chat
silence is not proof of inactivity.

## Durable Work Already Completed

### Backup and recovery foundation

The most recent successful Staging turn established:

- 198 operational regressions passed for the runtime lifecycle backup repair.
- Fresh full and catch-up archives were hash-verified on Desktop `B:`.
- B-only recovery authenticated both complete streams, accounted for all 14
  protected roots, and restored all 69 databases plus 32 selected real files.
- All restored databases passed hashes and SQLite integrity checks.
- The measured recovery stayed above 12.85 GiB free at that time.
- Generated shell snapshots and released writer locks received narrow lifecycle
  handling without broad recovery exclusions.

Primary record: `VK_RUNTIME_BACKUP_RECOVERY_20261007.md`.

The verified recovery-tool pin is
`49cf82d603b765b4ceaf5a8b4462f046e6181c0f`; its package is
`/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60`.
It is evidence and a candidate dependency, not proof that a future controller has
adopted it.

### Candidate release work

Before the incident, combined candidate validation included focused Rust checks,
server compilation, connector/HTTP fixtures, historical replay checks, packaged
native cases, CU/HTTP/browser fixture groups, and an AutoSwitch reload test.
Those receipts remain useful but do not substitute for a successful full-scale
handover after the incident repairs.

### Goal checkpoint evidence

The old thread's native goal checkpoint records `backup`, `readiness`, and
`release` as completed, with `cutover` and `durability` unresolved. Because the
incident occurred after those earlier readiness claims, the checkpoint is
historical evidence only. Do not mark the inherited objective complete or rely on
the old cutover authority.

Checkpoint path:
`/home/mcp/.local/share/vibe-kanban-green-codex-home/vk-goal-progress/01a03e74-2c1a-72f0-9e00-8e4293fe910d.json`.

## Open Reviews And Source State

Verified through GitHub at packet creation:

- [PR #149](https://github.com/artinflight/vibe-kanban/pull/149): draft,
  open, green; Desktop-backed recovery pin `49cf82d60`.
- [PR #150](https://github.com/artinflight/vibe-kanban/pull/150): draft,
  open, green; combined candidate `5ec572245`; not deployed.
- [PR #152](https://github.com/artinflight/vibe-kanban/pull/152): draft,
  open, green; narrow incident/recovery review `2d73b121a`.

The maintenance branch is not the application repair branch. Current source
areas implicated by evidence include server argument handling and workspace
cleanup/reconciliation, but those references are context rather than a mandated
design:

- `crates/server/src/main.rs`
- `crates/local-deployment/src/container.rs`
- `crates/workspace-manager/src/workspace_manager.rs`

## Unresolved Outcomes

The prevention work is successful when independent evidence shows all of the
following:

1. Unsupported server invocations cannot cross into stateful startup behavior.
2. Supported inspection behavior has no server, database, cleanup, or shared-root
   side effects.
3. Missing, wrong, empty, or mismatched database/workspace identity cannot grant
   authority over shared worktrees.
4. Normal, correctly identified startup behavior remains functional.
5. The exact incident-shaped cases are covered by regression tests with external
   sentinels proving shared paths remained unchanged.
6. Any automatic orphan/reconciliation behavior requires positive, trustworthy
   ownership evidence; ambiguous state is recoverable and non-destructive.
7. Recovery audits verify the properties they report, including file content,
   type, mode, link handling, and journal coverage as applicable.
8. Post-backup modified content and new-file uncertainty are measured or reported
   as unresolved rather than converted into a zero-loss claim.
9. The repair receives independent review and is documented well enough for later
   release preparation to consume without relying on this old conversation.

After those outcomes are met, release preparation still needs fresh, current
evidence for controller/rollback compatibility, B-backed capture and restoration,
full handover rehearsal, frontend/module/runtime binding, and actual inactivity.
Those are later readiness questions; they do not authorize a production switch.

## Known Failure Of The Old Session

The old Codex thread is approximately 135 MB and reports very large accumulated
token usage. On October 7 at 23:56 UTC, its next request was blocked as
`misalignment_policy_violation` with reason `Potentially unintended activity`.
VK then automatically injected the blocked request into interrupted-turn recovery.
Remote compaction and later retries reproduced the same policy block.

Do not resume that thread for this work and do not paste its raw recovery wrapper
into a new session. This packet carries forward the durable facts without making
the blocked request executable continuity.

## Evidence Index

Read in this order, selecting deeper historical documents only when needed:

1. `AGENTS.md`
2. this packet
3. `VK_RECOVERY_INCIDENT_20261007.md`
4. `HANDOFF.md` — current October 7 section first; older sections are chronology
5. `STREAM.md` — current October 7 scope first
6. `VK_WORKFLOW.md` and `VK_AGENT_DEPLOYMENT_RUNBOOK.md`
7. `VK_RUNTIME_BACKUP_RECOVERY_20261007.md`
8. `VK_COMBINED_BACKUP_BLOCKERS_20261007.md`
9. incident-review source in draft PR #152 and its retained evidence root

The rollout remains preserved at:
`/home/mcp/.local/share/vibe-kanban-green-codex-home/sessions/2026/08/26/rollout-2026-08-26T14-23-16-01a03e74-2c1a-72f0-9e00-8e4293fe910d.jsonl`.
Use it only for targeted factual recovery; it is not the new agent's prompt.

## Fresh Session Prompt

Use `VK_STAGING_FRESH_SESSION_PROMPT_20261008.md`. It deliberately describes the
destination, context, constraints, and success criteria while leaving the route
to the receiving agent.
