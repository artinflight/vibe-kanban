# Backend deployment runbook

Read [STATE](STATE.md), [STREAM](STREAM.md), [HANDOFF](HANDOFF.md),
[VK_WORKFLOW](VK_WORKFLOW.md), [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json),
[BACKEND_DEPLOYMENT_HANDOFF](BACKEND_DEPLOYMENT_HANDOFF.md) and
[VK_BACKEND_RESTART_PROTOCOL.md](VK_BACKEND_RESTART_PROTOCOL.md) before acting.
The [previous runbook](deployment-history/20261030-before-reconciliation/VK_AGENT_DEPLOYMENT_RUNBOOK.md)
is retained as history, including earlier incidents and UI regression checklists.
Its old service names, install paths and commands are not current authority.

1. Discover actual serving process/hash, public route/assets, data inode/target,
   service environment and protected-reader identity. Do not infer build identity
   from 0.1.42. Preserve dirty canonical work; branch from current operator staging
   in a clean SSD worktree and record included/excluded code explicitly.
2. Reconcile private history bindings, live UI/connector changes, schema and
   generated types. Verify source catalogs. Preserve startup identity, capacity,
   approval and Recommend controls. `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8` remains
   required; current cleanup flags and selected environment are in the manifest.
3. Check SSD mount/free space and active build ownership. Normal shared target:
   `CARGO_TARGET_DIR=/home/mcp/.local/share/vibe-kanban-green-build/cargo-target`;
   `CARGO_INCREMENTAL=0`. The recovered isolated recipe uses its existing owned
   SSD target. Follow the handoff's resource bounds, locks, offline build and
   artifact sealing; never launch an unbounded duplicate build.
4. Run focused tests plus required branch checks, `pnpm run format` and
   `pnpm run ops:check`. Retain logs and skipped/not-run scope. Real native
   provider execution is not certified by protocol mocks or capability routes.
5. Rehearse candidate→compatible fallback→candidate with a fresh copied DB and
   later-write sentinel. Verify all tables, native history, review/settings/
   queues and receipt semantics. Keep original private inputs and attachment
   paths. Do not downgrade by restoring an older DB over current writes.
6. Complete restore-grade current backup and independently reopen Desktop B.
   Source stability and exact ownership must pass; do not weaken them after a
   failed capture. Finish slow preparation before the interruption window.
7. Under current operator authorization, recheck idle native work and hold real
   writer/capacity/ingress fences. If a different owner or active work appears,
   preserve it and reassess. Old PIDs, stopped DB rows and consumed receipts are
   not authority. Preserve the protected reader and exact owned CU process.
8. Supervise the switch independently: verified-progress watchdog 600s and
   separate recovery 300s. Removing the 50-minute total cutoff did not remove
   either mechanism. Failed recovery remains a visible failure, never success.
9. Verify the actual public route/new binary and frontend, protected/recent
   histories, ordinary send, settings/review/queues, stale-child truthfulness,
   artifact retrieval and resumed consumers. Keep every uncertain input without
   replay. Record exact runtime identities and fresh evidence in the manifest.
10. Commit/sync code, tools, tests and operational docs. Keep private receipts,
    credentials, histories and backups out of public Git. Mark unresolved gates
    and CI explicitly. Use the artifact publisher for operator-facing reports.

Antigravity authenticated native acceptance passed and the matched activation is live.
Use [its evidence](VK_ANTIGRAVITY_ACP.md) and the [fresh-package recipe](ACTIVATION_RECOVERY_20261030.md).
Retain the supervised/default-model service settings; no further provider call is
authorized by the completed four-turn acceptance budget. Future runtime changes
require fresh bounded qualification.
