# Restart Lessons And Proposed Blue Cutover

Date: 2026-09-11. Status: the [backend restart protocol](VK_BACKEND_RESTART_PROTOCOL.md)
is established; a production cutover is NOT certified ready. Historical planning
and evidence below do not override its approval and measured-window requirements.

## September 11 Attempt And Operator Correction

Green was stopped during an attempted handover before a native-process identity
assertion failed. The controller returned to protected Green on the same data;
production Blue was not started and no final stopped-boundary snapshot was made.
The agent failed to establish agreement on the stop-and-switch arrangement and
failed to run that identity check before interrupting service. A Linux deleted
executable label was not evidence that conversation files were missing.

The operator's established model is now explicit: keep Green usable throughout
preparation, test isolated Blue, finish bulk backup work and measure the complete
handover before asking for a brief cutover window. Do not leave the operator idle
through builds or silently turn preparation approval into an interruption.
Keeping two writable copies is not a rollback plan; preserve all later writes.

## Decision

Prepare a new, isolated blue candidate while green continues production. Keep
green's binary, frontend and state available for rollback. Do not revive the
retired `vibe-kanban.service` or reuse its old data as the candidate.

Two instances reduce deployment risk, but two independently writable production
copies create divergent histories. There must be one authoritative writer at a
time. An immediate route rollback is lossless only before blue accepts production
writes, including background writes. Once blue accepts work, rollback must preserve
that work and account for schema compatibility. A stale green database is not a
lossless rollback target.

The objective is no lost work and a short, predictable handover, not an unproven
promise of zero interruption. Existing agent processes are not demonstrated to
be transferable between these backends. Drain them on green; preserve unsent
browser drafts and expect tested reconnects during the route transition.

## Evidence And Limits

- September 7 recovery audited 2,600 original threads and restored 2,178 missing
  native rollouts. All 2,599 available histories passed native reads; one original
  resume was tested without starting a model turn. These are historical results,
  not a fresh September 11 coverage certificate.
- Two native histories remain incomplete in that report: FR::Viral::Running
  lacks three later turns and PG::Redesign Mobile Layout lacks one. Their original
  execution logs were recovered separately. One killed startup has no located
  rollout. Existing malformed records were preserved, not silently discarded.
- Evidence: `/mnt/vk-storage/thread-recovery-20260907/README.md` and
  `evidence/final-audit.json`. The verified Desktop recovery bundle is at
  `desktop:B:/vk-backups/vk-thread-recovery-20260907/`; it is not a fresh complete
  production backup. The exact deletion event/date was not established.
- September 11 read-only service inspection: green is active, PID `2886161`,
  configured executable under `vibe-kanban-green-releases/20260831T1436Z-84a55972d`.
  Retired `vibe-kanban.service` is inactive. The HTTPS proxy targets `4511`;
  `vk-frontend-static.service` is also active. This is not a complete route audit.
- `/mnt/vk-storage` was verified mounted from `/dev/sdb1`, ext4. Verify the mount
  again at deployment time. Candidate payloads and bulk staging belong on this
  SSD; permanent VK backups belong on Desktop `B:/vk-backups/`.
- Source reviewed at `a31c1f579`, not the future candidate: DB initialisation runs
  migrations (`crates/db/src/lib.rs`); local deployment schedules orphan-file
  cleanup (`crates/local-deployment/src/lib.rs`); container startup schedules
  workspace cleanup, and shutdown processes running execution rows
  (`crates/local-deployment/src/container.rs`, `crates/server/src/startup.rs`).
  These behaviours must be reassessed against the exact candidate source.
- The live HTTPS proxy selects its backend from startup environment and pipes
  WebSocket upgrades to that target. A frontend swap alone does not switch API
  ownership, and a seamless dynamic route reload is not established.

## Lessons And Required Evidence

| Failure or gap | Lesson and evidence required this time |
| --- | --- |
| Restart readiness was overstated before all work was reconciled. | Separate prepared, validated, backed up, activated and operator-accepted states. Each claim needs dated evidence; approval is not proof of safety. |
| T25 and other work were inferred from board labels or ambiguous summaries. | Map every In Staging issue to all relevant workspaces, pushed commits and exact candidate inclusion. Check rebased/squashed equivalents by content where ancestry differs. Report omissions explicitly; test Turn Steer and Stop agent separately. |
| New-thread fallback was presented as recovery. | Restore authentic original IDs and native histories. A new thread or exported transcript is not an original-history restore. |
| Recent/active-only checks missed dormant referenced histories and retired-home paths. | Inventory every referenced thread, including earlier session threads, archived-project workspaces and explicitly scoped archived work. Resolve absolute paths across all homes and preserve provenance. Creation dates in filenames do not make histories disposable. |
| Backups existed but did not establish complete restore coverage. | Compare expected files/IDs/content with actual archive contents and an isolated restore. Preserve native rollouts as well as VK logs, databases and indexes. Verify scheduling actually runs; September 7 found the documented cron disabled. |
| Saved messages vanished across desktop/mobile despite data or API checks. | Compare exact saved-message contents and unknown preference keys through persisted state, REST, WebSocket hydration and actual desktop/mobile use. Check unrelated preference updates do not erase fields or trigger false guards. Preserve drafts and verify pending saves before freezing. |
| Navigation and other live-only fixes regressed after asset changes. | Inventory live hotfixes; prove candidate source and served assets retain colour, flyout, filters, notifications, clipboard and attachment behaviour. Never overwrite green's immutable release directory. |
| Retired 4311 and external callers made instance ownership unclear. | Inventory every service, route, direct-port client, codexcommand caller, preview and scheduler. Verify Operations and Oharafit callers use the authoritative generation. No silent split board. |
| Existing worktree paths collided; SSD migration risked path loss. | Preserve dirty/untracked files, Git metadata, worktree registration and logical paths. Investigate collisions without deletion. Validate mounts, attachment roots, owners and permissions. |
| Process health was mistaken for successful recovery. | Require representative original-thread resume, execution, persistence, mobile UI and attachment checks, not just HTTP 200 or a running PID. |
| Multiple final-style reports obscured the actual outcome. | Use plain progress messages and exactly one final report after validation and operational work finish. Record unresolved exceptions in durable docs. |

## Proposed Handover

### Isolated rehearsal while green stays live

Use a uniquely named new-blue service and SSD directories, recorded in a release
manifest with distinct ports, XDG data/config/cache, Codex home, frontend and
execution ownership. Names and ports are chosen after inventory, not copied from
old examples. Check canonical paths, symlinks and indexed absolute rollout paths:
copying a home does not redirect embedded paths automatically.

The candidate must not mutate production DBs, rollouts, attachments, repositories,
worktrees, previews or transient execution units. Isolate external credentials,
webhooks, callbacks, polling and scheduled actions too. Cleanup flags alone do
not establish this isolation. Rehearsal starts only after startup side effects
are contained. Test work uses disposable isolated repositories and synthetic
executions, never a cloned production execution competing with green.

Build backend and frontend from one recorded, validated release boundary. Reconcile
the complete In Staging inventory and live hotfixes. Rehearse migration from a
consistent recent backup, including actual migration versions/checksums and custom
triggers. Test the old binary's compatibility with candidate-written state in an
isolated copy if that is the proposed post-write rollback mechanism. Do not edit
migration records to force compatibility.

### Final consistent boundary

Before the window, capture all active execution/session/thread IDs and owners,
including queued turns, approvals, subagents, previews and direct-port automation.
Let running work finish on green. Any required interruption needs explicit
acceptance for named executions; never label interrupted work completed.

Enforce a write freeze across browsers, API clients, direct ports, WebSockets,
queues and background writers. Asking the operator not to click is insufficient.
The mechanism to fence green while keeping its process available is not yet
implemented or verified. If it cannot prevent writes and side effects, a stopped,
drained green is safer than an unfenced running green; obtain agreement on that
change rather than promising both continuous availability and safety.

Take a fresh consistent restore-grade backup after draining and freezing. Use
SQLite-aware snapshots, not a raw live DB/WAL copy. Include VK data, all referenced
native histories and indexes, logs, attachments and required roots, dirty and
untracked work, Git refs/metadata, profiles, settings, release artifacts and service
and route configuration. Protect credentials and permissions. Stage only on the
mounted SSD and verify Desktop transfer plus restore coverage. Keep the September
7 exceptions separately identified; require no newly missing histories.

Refresh blue while it is offline from this final boundary; do not promote a stale
rehearsal snapshot or overwrite rehearsal evidence. Validate migrated state against
the final inventory, including exact saved-message content and thread identities.
Green remains fenced. Never run both generations on a shared writable SQLite DB
or shared writable Codex home, even temporarily.

### Route switch and acceptance

Treat frontend assets, API, `/v1`, WebSocket upgrades, preview routing and direct
automation callers as one versioned routing contract. Discover the actual LAN,
Tailscale/mobile and hostname paths before selecting a switch mechanism. Preserve
old hashed assets for existing tabs. Test connection drain/reconnect, authentication,
service-worker caching, pending drafts and retries without duplicate submissions.
Do not assume changing one frontend pointer moves all clients.

Keep production writes fenced for initial route and read-only acceptance checks.
Some GETs or background tasks may write; measure this rather than equating HTTP
method with read-only behaviour. Before releasing writes, rehearse rollback and
confirm the operator can see saved messages, correct navigation and original
histories through both desktop and mobile entrypoints.

Once blue is the sole writer, perform controlled functional checks: create a test
workspace, run a representative agent, verify durable history and original-thread
continuation, distinguish steering from cancellation, and upload/retrieve an
attachment with matching bytes. Track these test writes and any new real work.
Check database integrity, original IDs, thread links, preferences, missing-path and
permission errors, previews and external callers. These tests cross the post-write
rollback boundary. Do not claim an instant stale-snapshot rollback afterwards.

## Rollback Contract

| Point of failure | Safe response |
| --- | --- |
| Isolated rehearsal | Keep green authoritative. Preserve candidate evidence; repair and retest blue without affecting green. |
| Route switched, no unreconciled authoritative writes on either side | Fence blue, return the complete route contract to green, verify reconnect and state, then release green writes. Retain blue evidence. |
| Blue has accepted writes or executions | Fence new work, drain or explicitly account for active blue executions, and preserve blue's latest complete state. Use a rehearsed compatible transfer to old software or a verified reconciliation that preserves all new IDs, histories, files and schema semantics. Never restore the older green snapshot over newer work. |
| Compatibility/reconciliation is not proven | Keep the last authoritative data protected and repair forward or maintain a controlled pause. Immediate lossless rollback is unavailable; do not invent it. |

Keeping green running can avoid its startup delay, but does not keep its data
current. A post-write rollback may require refreshing state while green is stopped
and restarting it; an already-running process can hold stale connections/caches.
Retain green's artifacts and snapshots until acceptance and the agreed rollback
window end. Retention cleanup is a separate authorised task, never part of cutover.

## Remaining Preparation

This report does not start blue, take a new backup, certify staging, implement
fencing, test migration compatibility or authorise a route switch. Before calling
the next restart ready, produce the candidate manifest, complete issue inventory,
fresh thread/attachment/worktree coverage, tested isolation and fencing, route
handover evidence, restore rehearsal, functional regression results and a rollback
choice that explicitly covers post-cutover writes. Record durations from rehearsal
instead of promising an instantaneous or uninterrupted changeover.
