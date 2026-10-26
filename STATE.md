# Current-state index

Read this index, [STREAM](STREAM.md) and [HANDOFF](HANDOFF.md), then only the
topic needed for the task. Full prior text, decisions, identities and test
receipts survive byte-for-byte in [STATE history](STATE_HISTORY_20261017.md).
[Archive provenance and section locations](CONTINUITY_ARCHIVE.json) bind that
snapshot to staging `7110930b6d9d1fa3f403a963a1ded49140b3eec1`.
Historical statements describe their dated checkpoint, not present authority.

## Authority and safety

- Code and validated behavior precede this index. A source merge, prepared
  artifact, fixture pass or agent statement alone does not prove deployment.
- Green is the sole active Vibe instance; retired Blue stays stopped/disabled.
  Preserve the incumbent, current data, compatible rollback, private readers,
  proxy/frontend and all original native histories. Never restore stale data
  over later writes. Cleanup stays disabled until human QA and exact authority.
- Preserve Recommend-only, selected models/effort, AutoSwitch, first-run holds,
  usage/credit controls, capacity guards and the user execution lane. At most
  seven occupied coding lanes leave one of eight for the user. No extra worker,
  compiler or browser without resource/owner admission; preserve build caches.
- Preparation does not authorize a restart, admission hold, routing change,
  privilege installation, arbitrary deletion or new security access. Respect
  the current no-restart instruction. Only the release owner holds cutover.
- Full consumer visibility and managed-owner/lease gates fail closed. Expensive
  hashes and SSH preparation precede final held-boundary clearance; bounded
  local identity/freshness checks follow it. A receipt is not an atomic global
  process fence. No blanket sudo or same-account reviewer security boundary.
- Preserve complete recoverable sessions, dirty/untracked/unpublished work,
  attachments, incident/fallback evidence and historical Git obligations.
  A directory named cache/build/target/node_modules is not deletion authority.
- Operational diagnostics, account values and private manifests stay private
  on local/B storage. Publish only reviewed public source. No secrets in Git.

## Topic map and present evidence boundaries

| Area | Read next | Boundary |
| --- | --- | --- |
| Runtime/restart | [Workflow](VK_WORKFLOW.md), [agent runbook](VK_AGENT_DEPLOYMENT_RUNBOOK.md), [restart protocol](VK_BACKEND_RESTART_PROTOCOL.md) | Latest authoritative actor receipt decides live identity; no restart is armed by this index. |
| Queue/preparation | [Preparation](VK_PREPARATION_PERFORMANCE.md), [queue source](crates/local-deployment/src/container.rs) | PR262 merged into staging at `7110930b6`; ordinary wakeup needs compiled-artifact start/readback, not source-only claims. |
| Nightly B/recovery | [Sole integration PR263](https://github.com/artinflight/vibe-kanban/pull/263), [retained restart history](HANDOFF_HISTORY_20261017.md) | Workspace604d is sole backup/package/schedule owner. Counted capacity is not publication or whole-plan restore. Schedule adoption remains unverified; default is 02:00 America/Toronto, DST-aware. |
| Git preservation | [Automatic sync](VK_AUTOMATIC_GITHUB_SYNC.md), [preservation](VK_TURN_GIT_PRESERVATION.md) | Preserve native ledgers/originals and actual held writer fence. Invalid old watcher coverage cannot be reset or replaced by manifest booleans. Scope-specific handover gates do not block independent backup verification. |
| Release integration | [Stop PR264](https://github.com/artinflight/vibe-kanban/pull/264), [Dot steering](VK_DOT_SESSION_STEERING.md) | Staging owns combined build/copy/rollback/queue acceptance. Public artifacts omit retained private bindings and cannot replace the live package. |
| Dot/mobile/reporting | [Notifications](DOT_NOTIFICATION_ROLLOUT.md), [reliability](DOT_RELIABILITY_ROLLOUT.md), [integration](DOT_INTEGRATION_HANDOFF.md), [sent drafts](VK_SENT_STEERING_DRAFT.md) | Preserve mobile, steering, existing connector reporting and paired subscriptions; source-ready and served acceptance are separate. |
| Generated files | [Artifact links](VK_ARTIFACT_LINKS.md) | Upload and verify intended files before offering browser links; filesystem paths alone are not delivery. |

## Maintaining this index

Replace superseded current statements; put detailed receipts in the owning
topic guide and link them here. Do not prepend the same update into all three
pickup files. Keep their combined UTF-8 size below 16 KiB. Historical archives
are immutable evidence, not mandatory reading on every turn. Find a specific
section with `python3 scripts/continuity/pickup.py find QUERY`; read its reported
line range, widening it when the task needs surrounding constraints.

Current release coordination, newer Sidebar adoption and remaining private gates:
[October 17 release status](VK_RELEASE_COORDINATION_20261017.md).

Collapsible issue behavior and approved frontend release: [topic evidence](VK_COLLAPSIBLE_ISSUES.md).

## Nightly integration commissioning — October 26

Nightly remains a separate worker/config/scheduler; it does not require a backend
restart. The accepted historical restore and later verified components remain
retained. Current commissioning is not accepted. Live MM scope explicitly excludes B;
the old copied Staging-only guard is historical. Read the
current branch [handoff](HANDOFF.md) and [Nightly contract](VK_NIGHTLY_BACKUP_EFFICIENCY.md).
All earlier Nightly continuity is preserved byte-for-byte in
[the archive manifest](NIGHTLY_CONTINUITY_ARCHIVE_20261026.json).
