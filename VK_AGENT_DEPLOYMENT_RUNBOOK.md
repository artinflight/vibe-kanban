# VK Agent Deployment Runbook

## Candidate Executables Cannot Be Inspected Directly On The Host

Read VK_RECOVERY_INCIDENT_20261007.md. Never guess a server flag or run a candidate
directly against the host for version/help/build inspection. An unrecognized
argument can fall through to normal startup and shared-worktree deletion.
Verify source/manifest without execution first. When execution is necessary, use
the existing reviewed `scheduled-first-run-validation.py` isolation boundary with
the bound binary hash, private filesystem/PID/network/manager and bounded lifetime.
The current source supports `--capacity-build-info`; knowing that spelling is not
permission to bypass isolation. Environment-only path overrides are insufficient.
Only the separately sealed, approved production controller may launch a candidate
with real production paths. Wrong-argument rejection and positive cleanup ownership
need development-owner regression coverage before this pending rollout proceeds.

## Desktop-Backed Recovery Tools For Next Preparation

Current sole-provider authority supersedes the older tool pin below: use PR149
49cf82d60 or a verified descendant. Read VK_BACKEND_RESTART_PROTOCOL.md's
Desktop B policy and /mnt/vk-storage/vk-desktop-provider-20261007 receipts.
The hardlink defect and runtime-release warning handling are corrected and198
regressions pass. The newer package must be explicitly verified/bound; do not
change older sealed packages. Do not retain duplicate
SSD archive chains as a standing requirement or use full simultaneous filesystem
extraction as the only provider acceptance method. Exact deletion approval and
separate production rollout approval remain required.

Read VK_DESKTOP_ARCHIVE_MIGRATION_20261007.md. Draft PR149 operational pin
6bd0b39e546ba1f2337cac5dbf27f3b14446fe91 includes PR142 plus authenticated
Desktop-only legacy-chain resolution. The new64-file recovery package and
actual-template installer are verified; install that pin into a NEW unsealed
handover package before readiness and verify its receipt. Never modify a sealed
or consumed package to claim adoption. Existing local archive copies are still
protected; Desktop verification is not deletion approval. Full current backup,
measured rehearsal/capacity and explicit overnight rollout approval remain gates.
The compatible pending-release v2 reader uses the latest data; never restore an
older backup over production. Older PR142-only pins below describe past packages.

## Attention Acceptance Before Completion

Before any operation that can change review state or its display, take a current
production semantic snapshot with `scripts/vk_workspace_review_snapshot.py`,
verify it on Desktop, and preserve the live `workspace_review_events` journal.
Afterwards compare per-turn flags/mappings and the displayed desktop/mobile list;
account for legitimate reviews and new completions using the journal. The snapshot
is mandatory for frontend swaps, data repairs and migrations too, not only backend
restarts. Read the mandatory-snapshot section in VK_ATTENTION_PRESERVATION.md.
The frontend publication script enforces this gate; fresh external controller
packages must adopt it before use, without rewriting consumed recovery artifacts.

Read VK_ATTENTION_PRESERVATION.md. Compare original turn seen/review flags
independently from issue statuses; verify live desktop/mobile sections with the
read-only summaries POST permitted, including older items beyond50. Opening a
visible chat must clear attention. Hidden mobile/background views and summary
polling must not; do not replace this workflow with manual-only review. Preserve live frontend repairs in
candidate and cutback bundles and rebind source/hash/Desktop recovery evidence.
Do not mark a readiness goal complete with an unresolved reported regression.

Review-state recovery must use one verified production boundary and preserve
later reviews/new completions. Never union every historical unread flag or treat
an old build DB inside a fresh archive as current production. The October2 union
repair revived stale work; see the corrected incident evidence in
VK_ATTENTION_PRESERVATION.md. Where requester/visibility history is missing,
report the exact reconstruction limit instead of claiming restored review intent.

This file is the pickup guide for agents working on Vibe Kanban from inside
Vibe Kanban. Follow it before editing, building, or deploying this repo.
For the planned clean self-development project/preview model, read
`VK_SELF_DEVELOPMENT_WORKFLOW.md` as well.

September30 AutoSwitch deployment: follow the runtime/telemetry requirements in
VK_BACKEND_RESTART_PROTOCOL.md. Production must use verified Codex0.159.2 and
the same private VK/CU routing feed. Check the seven-model proof's launcher,
account, home and24-hour freshness; refresh only bounded availability when needed.
Check actual running process environments after activation, not just unit files.

## Required Existing-Chat Model Check

Include the model catalog and reasoning dropdown, not only selected labels and
submitted defaults. PR117 fixes the September15 missing GPT-6 capabilities and
obsolete Codex choices. It must be integrated before the next staging release.
The live frontend and paused-Blue cutback frontend now carry f175c1b5b. See the
expanded model gate in `VK_BACKEND_RESTART_PROTOCOL.md`.

For goal-checkpoint display, exercise continuing, input-needed and legacy
completed reports, including expandable evidence at desktop/mobile sizes.
The September14 parser accepted only the first two states, exposing completed
reports as raw protocol despite passing six tests. Carry PR113's completion
renderer/tests into future builds. Rendering a completion report is not proof
that the native goal engine marked the objective complete; do not rewrite logs.
Invalidate prior candidate readiness whenever a missing live fix is discovered.

Follow the [existing-chat model preservation gate](VK_BACKEND_RESTART_PROTOCOL.md#existing-chat-model-preservation-gate)
before declaring any restart, frontend swap or cutback ready or accepted. Compare
per-chat choices at the final boundary with the reopened selector and actual
submitted model. A correct global default or successful new-chat test is not
sufficient. September 12 acceptance missed this regression; the cause and repair
remain unresolved. Preserve choices and drafts, and do not bulk-reset chats.

## Current Live Truth

September30 authority: Green2506054 is live on5261/5262 and vibe.local with
Codex0.159.2; Blue764264 is frozen/boot-disabled for latest-data cutback.
CU2506120 is connected/reconciled and shares VK's private routing event feed.
Read VK_GREEN_LIVE_20260930.md and the v2 attempt receipts. Both September30
attempts are consumed. The dated inventories below are historical.

September15 authority: Green1674994 is live on5091/5092. Blue2150526 is frozen
for latest-data cutback; old Green2778969 and historical Blue2590517 remain
frozen separately. CU1674995 is connected/reconciled with automation off. Read
VK_GREEN_LIVE_20260915.md. The inventories below are historical.

Every candidate now includes the versioned capacity deployment profile and
release-matched guard from staging PR116. Render/install/check next-start
configuration, account for the CU companion restart, and require the separate
post-cutover live-check. Configuration success is not live activation. Preserve
automation settings and goal selections; do not enable scheduling to pass tests.

**September14 supersedes the historical inventory below.** Production is
`vibe-kanban-paused-blue-20260912.service` on4711/4712, PID2590517, behind
gateway4720. Original Green PID2669659 was deliberately retired without thaw;
`vibe-kanban-green.service` is masked-runtime/boot-disabled. The new staging
Green service is isolated test state on4911/4912. Its separate prepared
production unit is NOT activated. The authoritative data paths still contain
`green` in their names; color is not ownership. See `VK_GREEN_READY_20260914.md`.

### Historical August 28 Inventory

- Canonical source repo: `/home/mcp/_vibe_kanban_repo`
- Current green live service as of 2026-08-28: `vibe-kanban-green.service`
- Retired blue service: `vibe-kanban.service`
- Current green backend port: `4511`
- Current green preview proxy port: `4512`
- Retired blue backend port: `4311`
- Retired blue preview proxy port: `4312`
- Current green data directory:
  - `/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban`
- Retired blue data directory:
  - `/home/mcp/.local/share/vibe-kanban`
- Current green Codex home:
  - `/home/mcp/.local/share/vibe-kanban-green-codex-home`
- Current green binary as of 2026-08-28:
  - `/home/mcp/backups/vk-green-rollout-resume-fix-sanitized-20260826T211600Z/server`
- Current green frontend release as of 2026-08-28:
  - `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260826Tstaging-main-fc312a073`
  - live assets: `/assets/index-BiiblWjF.js`, `/assets/index-DnGjt7Sn.css`
- The green frontend release also has a live `index.html` saved-message shim
  and `/vk-saved-chat-messages.json` sidecar. Do not replace the whole release
  directory with a newly built dist unless the build is proven to include all
  live-only retained behavior.
- Legacy blue live binaries:
  - `/home/mcp/.local/bin/vibe-kanban-serve`
  - `/home/mcp/.local/bin/vibe-kanban-serve-prod`
- Retired blue binary sha256 as of 2026-06-03:
  - `722a5b0d14ca2350661cdcd0a271ac2cfea980dae4f2dcafc55b8ffe9470ed75`
- Retired blue frontend pointer as of 2026-06-03:
  - `/home/mcp/.local/share/vibe-kanban/frontend-dist/current`
  - points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`
  - live asset: `/assets/index-BLreFcjw.js`
- Retired blue runtime used isolated Codex home:
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
- Current green runtime uses isolated Codex home:
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban-green-codex-home`
- Current green runtime uses refreshable frontend assets:
  - `VK_FRONTEND_DIST_DIR=/home/mcp/.local/share/vibe-kanban/frontend-dist/current`
- Current live runtime must allow multiple Codex agents:
  - `VK_CODEX_MAX_ACTIVE_EXECUTIONS=8`
- Current live ordering guard:
  - synthetic projects must be sorted deterministically before `/api/projects`
    returns them; do not reintroduce unordered `HashMap::values()` append order.
- Current live duplicate-project guard:
  - synthetic `PROJECT_REPO_DEFAULTS` projects must be suppressed when their
    repo is already linked to a real project in `project_repos`, even if the
    names differ by punctuation or case (`foxtrot-lima` vs `FoxtrotLima`).

Treat older deployment details in historical docs as history unless they match
fresh live checks. If `systemctl`, listeners, service env, and frontend asset
identity disagree with this section, update this section before planning a
restart.

## Absolute Rules

- Do not restart `vibe-kanban.service` without explicit operator approval.
- Do not restart `vibe-kanban-green.service` without explicit operator approval.
- Do not deploy from a dirty checkout.
- Do not deploy from `/home/mcp/_vibe_kanban_repo` when it has unrelated dirty files.
- Do not assume code is live because it is merged, committed, or present in a worktree.
- Do not overwrite or roll back user/agent changes you did not make.
- Do not remove or alter:
  - `/home/mcp/.local/share/vibe-kanban/db.v2.sqlite`
  - `/home/mcp/.local/share/vibe-kanban/codex-home`
  - `/home/mcp/.local/share/vibe-kanban/sessions`
  - `/home/mcp/code/worktrees/...`
  - `/home/mcp/backups/...`
  unless the task explicitly asks for that operation and a retention rule is clear.
- If active agents are running, report them and wait for approval before any restart.
- Do not assume port `4311` is the active VK instance. Always discover live
  service and listener state before backup, deploy, restart, or recovery.
- Do not "fix" a live frontend regression by copying an entire newly built
  frontend over the active release directory. Publish a new release directory
  and atomically switch a pointer, or apply a tiny documented hotfix with a
  one-file rollback path.

## Required Read Order

1. `AGENTS.md`
2. `STATE.md`
3. `STREAM.md`
4. `HANDOFF.md`
5. `VK_WORKFLOW.md`
6. `VK_AGENT_DEPLOYMENT_RUNBOOK.md`
7. `VK_SELF_DEVELOPMENT_WORKFLOW.md`
8. Relevant crate/package `AGENTS.md`
9. Code paths for the task
10. `DELTA.md` only when compact history is needed

## Safe Worktree Model

Use this model for all VK changes:

1. Inspect canonical repo state:
   ```bash
   cd /home/mcp/_vibe_kanban_repo
   git status --short
   git branch --show-current
   git remote -v
   ```
2. If the canonical checkout is dirty, do not build or deploy from it.
3. Create a clean detached worktree from the intended base:
   - normal feature/fix: latest `origin/staging`
   - direct production hotfix: latest `origin/main`
4. Apply only the intended patch.
5. Validate in that clean worktree.
6. Build from that clean worktree.
7. Deploy only after the deploy manifest, backup, active-agent check, and operator approval.

The current canonical checkout often has unrelated dirty files. Treat that as
expected and work around it instead of reverting it.

## Feature Prep Workflow

Use this path for normal fixes and features.

1. Create the work in the active `VK Dev` project.
2. Confirm the workspace repo is `_vibe_kanban_repo` and the base is `staging`.
3. Let the setup guard run. If it fails, fix the setup guard or workspace
   configuration before editing product code.
4. Keep the branch scoped to one concern.
5. Update source, focused tests, and continuity docs together.
6. Run the narrowest useful validation during development.
7. Run `pnpm run format` before final handoff.
8. For a feature branch, open the PR into `staging`, not `main`.

Feature prep must not restart production VK, switch the live frontend symlink,
install live binaries, or mutate live DB/project rows. Those actions belong to a
separate release/deploy task.

## Preview Workflow

Use preview before promoting UI work into `staging` or before staging it for a
live frontend swap.

Frontend-only preview:

```bash
pnpm run preview:light
pnpm run preview:light:status
pnpm run preview:light:logs
pnpm run preview:light:stop
```

Default behavior:

- serves the local frontend from the workspace
- proxies API calls to the existing live backend on `127.0.0.1:4311`
- starts at preview port `3002` unless overridden
- can expose a Tailscale HTTPS preview when Tailscale is available

Useful overrides:

```bash
VK_PREVIEW_PORT=3030 pnpm run preview:light
VK_PREVIEW_PORT_START=3040 pnpm run preview:light
VK_PREVIEW_BACKEND_PORT=4311 pnpm run preview:light
VK_PREVIEW_TAILNET_PORT=18460 pnpm run preview:light
```

Inside a Vibe Kanban preview panel, prefer:

```bash
pnpm run preview:light:run
```

That keeps the preview attached to the panel lifecycle.

Backend/runtime preview:

- do not use the live state directory
- do not use the live Codex home
- do not point `vibe.local` at the preview
- use isolated lab paths such as:
  - `VIBE_KANBAN_DATA_DIR=/home/mcp/.local/share/vibe-kanban-lab`
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban-lab/codex-home`
- use ports separate from live `4311` and preview proxy `4312`

If backend behavior must be exercised against real production data, stop and
turn the task into an operator-approved release/deploy task first.

## Restart-Ready Staging Workflow

When a change needs a backend restart or a coordinated frontend/backend release,
do all slow and risky work before asking for the restart window.

### 2026-09-07 thread preservation correction

A checksum-verified audit found 2,179 missing rollout files referenced by 388
non-archived workspaces across 29 projects. Checking only running executions or
threads updated today did not protect dormant work. Three additional files
passed existence checks but contained malformed JSON records.

- Audit every thread referenced by every non-archived workspace, including
  workspaces in archived projects and earlier threads in each session. Record
  any excluded archived work separately; age is not proof that data is unused.
- Resolve every absolute rollout reference across current, retired, and shared
  Codex homes. A backup of the selected home alone is insufficient.
- Validate original thread identity, JSONL contents, and available history, not
  just file existence, DB integrity, archive hashes, or service health.
- Compare the expected thread inventory with the actual archive contents and
  restore/read results. Missing or unreadable histories remain explicit blockers
  to a claim that all work is preserved.
- Do not replace missing histories with new threads. Do not overwrite current
  state with an older whole database. Restore originals additively and preserve
  provenance, conflicting versions, and the current state before repair.
- Check actual backup scheduling. On September 7 the documented hourly backup
  cron entry was disabled. Documentation of a schedule is not evidence it ran.

Incident evidence: `/mnt/vk-storage/thread-recovery-20260907/README.md`.
Recovery restored 2,178 original files and verified 2,599 native history reads.
Two native histories still lack four later turns whose execution logs were
recovered separately; one killed startup lacks its rollout. These exceptions
remain open. Consult the incident report before another deploy; do not convert
this partial recovery into a blanket preservation guarantee.

### 2026-08-26 restart incident rules

These rules were added after a restart window where the backup existed but the
operator was not given a clear active-agent interruption gate, and a stale
Codex rollout path was incorrectly treated as a fallback-to-new-thread problem
instead of a restore problem.

- A restart is not safe just because a backup exists.
- A restart is not safe just because the operator says "proceed" if they also
  asked not to lose active agent work.
- If active agents exist, list each running execution by workspace, branch,
  execution id, session id, agent session id, and rollout path status.
- Ask for explicit acceptance of interruption for those exact executions before
  touching the service.
- Do not describe "start a new Codex thread" as fixing a missing rollout. A new
  thread is only a fallback. First look for and restore the referenced rollout
  file from same-day backups or older session archives.
- When a live Codex state database contains rollout paths under a retired
  `CODEX_HOME`, verify that those old-home paths either still exist or are
  covered by a backup before saying resume state is protected.
- A restart/deploy check must inventory every VK instance lineage on the host:
  green, blue, retired, lab, and any service exposed by `vibe.local`. Backups
  must name which lineage they cover. A backup of green is not a backup of
  retired blue `4311` state.
- If a retired instance has a zero-byte or otherwise broken DB, search Desktop
  archives before concluding the state is gone. Do not overwrite current green
  with a retired DB; import missing rows selectively after a dry run.
- A board column named "In Staging" is not proof that the work is merged into
  the deployed candidate. Compare branches and commits. Require the last agent
  summary to say `Committed and Pushed` or verify the commit exists in
  `origin/staging`.
- If any "In Staging" workspace is `Committed / Not pushed`, or its branch has
  commits missing from `origin/staging`, stop and report it as not included in
  the restart package.
- UI preferences and saved-message behavior require both backend preservation
  and frontend hydration. If the running backend serializes a typed
  `UI_PREFERENCES` payload that omits a field, the field can exist in SQLite
  and still be absent in API/WebSocket responses. Verify through the API,
  scratch WebSocket, and UI before saying preferences are safe.
- Do not use `curl` alone to validate frontend state that initializes through
  WebSockets. Confirm the relevant route, transport path, and browser-visible
  behavior.
- When a live-only frontend hotfix exists, record it in the deploy manifest.
  The next full frontend build must either include that behavior in source or
  explicitly remove it with operator approval.

Prepare:

1. Start from a clean candidate worktree based on the intended release branch.
2. Confirm all intended fixes are present in the candidate branch.
3. Confirm all board "In Staging" items are actually in the candidate branch:
   - list the workspace branch and last summary status
   - verify branch commits are pushed
   - verify each commit is reachable from the candidate
   - record excluded items by name and reason
4. Confirm known live fixes and live-only hotfixes are not missing from the
   candidate branch.
5. Run focused checks and any required broader validation.
6. Build the release binary and frontend assets from the clean candidate.
7. Write a deploy manifest with:
   - branch and commit
   - build worktree
   - binary path and sha256
   - frontend source commit, release path, asset names, and asset sha256
   - proof that the frontend bundle was built from the same intended release
     commit as the backend, unless an explicit mixed-version exception is
     approved and recorded
   - features intentionally included
   - board "In Staging" items intentionally excluded
   - known fixes that must not regress
   - live-only hotfixes that are included or intentionally retired
   - validation commands and results
8. Take an efficient restore-grade backup and mirror it to Desktop.
9. Verify the backup archive, checksum/manifest, and latest pointer.
10. Check every VK instance and state lineage:
   - `systemctl --user list-units 'vibe-kanban*' --all`
   - `ss -ltnp` for `4311`, `4312`, `4511`, `4512`, `80`, and `443`
   - `systemctl --user cat` for active and retired services
   - current DB paths and sizes for every lineage
   - Desktop archive names that cover each lineage
11. Check active agents and Codex rollout availability:
   - query the live VK database for `execution_processes.status = 'running'`
   - join to `coding_agent_turns.agent_session_id` when present
   - verify each active Codex thread's `rollout_path` exists
   - query Codex threads updated today and verify their rollout files exist
   - if any referenced rollout path is missing, restore it before restart or
     report the exact gap as unresolved
12. Stop and report: the only remaining action should be the approved restart
    or frontend symlink switch.

At the restart window:

1. Re-check active agents immediately before touching the service.
2. If agents are active, report the exact inventory and wait unless the operator
   explicitly accepts interruption for those listed runs.
3. Install the already-built binary/assets.
4. Restart only when backend code changed.
5. Run post-restart smoke before saying the deploy worked.
6. Re-run the Codex rollout availability check before saying agent resume state
   is safe.

This workflow exists so the operator can continue using VK while the candidate
is built and validated, and downtime is limited to the final switch/restart.

## Blue/Green Local Cutover Workflow

The established [backend restart protocol](VK_BACKEND_RESTART_PROTOCOL.md)
governs this section and the restart-window checklist above. Green stays usable
during builds, validation, bulk backup transfer and rehearsal. Report measured
end-to-end interruption, not just startup time, then wait for a fresh explicit
"cut over now". A preparation/proceed instruction is not production approval.
If Green must stop or Blue must restart to attach current data, explain and agree
that specific arrangement first. Do not repeat a failed handover automatically.

The [September 11 lessons and cutover report](VK_RESTART_LESSONS_LEARNED.md)
supersedes the former blue/green procedure and its hardcoded paths. Those examples
described green as a candidate even though green is now production, and the old
rollback instructions did not preserve writes accepted after cutover.

Prepare a NEW isolated blue candidate; do not restart the retired
`vibe-kanban.service`. Keep green authoritative during preparation. Candidate
paths and bulk staging belong on the verified mounted SSD; backups belong on
Desktop `B:/vk-backups/`. Verify actual data selectors and absolute references
against the candidate code, not directory labels or unsupported environment vars.

A candidate must not mutate green's DB, Codex home, worktrees, attachments or
execution units. Startup cleanup, migrations and background jobs require isolation
before the first start. Test only in isolated disposable rehearsal state.

Final handover requires drained executions, an enforced write freeze, a fresh
verified restore-grade backup and an offline refresh of candidate state.
Keep green fenced after blue takes ownership. Route frontend, API, WebSockets,
previews and external callers coherently; a frontend swap alone is insufficient.

A fast route rollback is valid only before unreconciled authoritative writes.
After blue accepts work, preserve its latest state and use a rehearsed compatible
data transfer or reconciliation. Never return users to a stale green snapshot and
claim no loss. If keeping green running cannot be made passive, report that
constraint and agree on a drained stop rather than running two writers.

This report is a preparation design, not evidence that isolation, fencing,
migration compatibility, rollback or the next release have already been tested.

## Backup Workflow

Do not run the historical lean-backup wrapper with its defaults as a restart
guarantee. Its selected-home/process-log discovery needs a complete reference
inventory, and its old system-disk staging and retention behaviour must not be
used for this cutover. Verify current implementation and configuration first.

Stage backup payloads only on mounted `/mnt/vk-storage` and mirror to
`desktop:B:/vk-backups/`. Do not prune originals, recovery evidence or prior
backups as part of deployment. If neither destination is available, stop rather
than falling back to the system disk.

The restore-grade backup must capture state not safely recoverable from Git,
including:

- `db.v2.sqlite`
- sessions
- isolated VK Codex home state
- relevant systemd service config
- deployed VK launcher/binary files
- deterministic workspace git metadata and bundles for local-only work
- restore metadata and checksums

Before saying the backup is ready, record:

- the local archive path
- the Desktop mirror path
- whether the `latest` pointer was updated
- whether the backup command exited successfully
- any restore gaps or warnings

Restore references:

- backup doc: `docs/self-hosting/local-backup-recovery.mdx`
- backup script: `scripts/vk_lean_backup.py`
- wrapper: `scripts/run_vk_lean_backup.sh`
- restore script: `scripts/vk_restore_lean_backup.py`
- restore latest wrapper: `scripts/run_vk_restore_latest.sh`

Use a heavier manual/full backup only for schema migrations, auth migrations,
or any operation that the lean backup doc says it cannot cover.

## Frontend-Only Deploy

Use this path only when the change is truly frontend-only and uses APIs already
available in the live backend.

1. Build from a clean worktree.
2. Publish a new release directory:
   ```bash
   release="/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/YYYYMMDDTscope"
   mkdir -p "$release"
   cp -a packages/local-web/dist/. "$release"/
   ```
3. Write a release manifest before switching:
   - source branch and commit
   - build worktree
   - release path
   - JS/CSS asset names
   - asset sha256
   - features intentionally included
   - features that must be retained
4. Switch atomically:
   ```bash
   ln -sfn "$release" /home/mcp/.local/share/vibe-kanban/frontend-dist/current
   ```
5. Do not restart VK for this path.
6. Verify:
   ```bash
   curl -sk https://vibe.local/ | rg -o '/assets/index-[^" ]+\.js' -m1
   curl -skI https://vibe.local/
   python3 scripts/vk_live_regression_smoke.py
   ```

If the frontend bundle causes project-list, archive, order, menu, or marker
regressions, roll back the `current` symlink to the previous known-good release.

## Backend Deploy / Restart

Backend changes require a build and service restart. This interrupts active
agent runs unless they have finished. Do not proceed without operator approval.

Preflight:

```bash
systemctl --user show vibe-kanban-green.service -p MainPID -p ActiveState -p SubState
systemctl --user list-units 'vk-exec-*' --state=running --no-legend
python3 - <<'PY'
import sqlite3
db='/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite'
con=sqlite3.connect(db)
for row in con.execute("select count(*) from execution_processes where status='running' and dropped=0"):
    print(row[0])
con.close()
PY
readlink -f /home/mcp/.local/share/vibe-kanban/frontend-dist/current 2>/dev/null || true
sha256sum /home/mcp/backups/vk-green-rollout-resume-fix-sanitized-20260826T211600Z/server
```

Backup before restart:

```bash
./scripts/run_vk_lean_backup.sh
```

Do not proceed until the backup is mirrored to Desktop and the backup path is
recorded in `HANDOFF.md` or the deploy manifest.

Build and install from the clean worktree:

```bash
cargo build --release --bin server
install -m 0755 target/release/server /home/mcp/.local/bin/vibe-kanban-serve
install -m 0755 target/release/server /home/mcp/.local/bin/vibe-kanban-serve-prod
```

Restart only after explicit approval:

```bash
systemctl --user restart vibe-kanban-green.service
```

Post-restart verification:

```bash
systemctl --user show vibe-kanban-green.service -p MainPID -p ActiveState -p SubState
sha256sum /proc/$(systemctl --user show -p MainPID --value vibe-kanban-green.service)/exe
readlink -f /home/mcp/.local/share/vibe-kanban/frontend-dist/current
curl -skI https://vibe.local/
curl -sk https://vibe.local/api/info
python3 scripts/vk_live_regression_smoke.py
```

Also verify the binary contains expected backend strings when applicable:

```bash
strings /home/mcp/.local/bin/vibe-kanban-serve-prod | rg -F 'expected unique text'
```

## Mandatory Regression Smoke

Every deploy, restart, or frontend symlink swap must verify or explicitly mark
unverified:

- active and archived project counts/order
- archived projects do not reappear in active left nav
- Archive access exists in the left nav
- removed Remote/Export/GitHub/Discord actions do not return
- issue-view workspace menu includes expected Rename, Archive/Unarchive, Unlink, Delete
- project-linked workspace creation defaults to that project repo, not global recency
- needs-review markers appear for completed coding-agent work
- needs-review markers clear only on intentional review
- interrupted/triangle-only state does not count as needs-review
- collapsed Kanban columns show horizontal mobile labels and item counts
- Kanban drag status/order persists after refresh
- queued follow-up state clears/reconciles without page refresh
- workspace action menu exposes the full action set including spin-off where valid
- direct issue status selector works from the issue page
- codeblock copy works
- paste/drag/drop/mobile attachment selection shows visible success or error
- active sub-agent indicators show active work only, not stale historical counts
- saved messages are visible from desktop `https://vibe.local`
- saved messages are visible from mobile/Tailscale `https://Vibe.local`
- `UI_PREFERENCES` scratch state preserves saved messages through both
  `/api/scratch/...` and `/api/scratch/.../stream/ws`
- left navigation project coloring, flyouts, archive access, and active markers
  match the pre-deploy baseline
- active VK instance count is understood: service names, ports, DB paths, and
  frontend paths are recorded

Record results in `HANDOFF.md` before saying the deploy is ready or complete.

## Current Regression Traps

- As of 2026-08-28, green is the live service on `4511/4512`; old blue `4311`
  can still have recoverable historical state in Desktop archives even when the
  local blue DB is empty. Do not call a green backup a `4311` backup.
- Whole-directory frontend swaps can erase live-only UI behavior. The
  2026-08 restart briefly regressed left-nav coloring/flyouts by copying a
  rebuilt dist over the active release. Use release directories and pointer
  switches, or one-file hotfixes with backups.
- Saved messages can be present in SQLite but missing from the UI if the
  running backend type drops `saved_chat_messages` when serializing
  `UI_PREFERENCES`. Verify the REST response, WebSocket initial patch, and
  browser UI.
- Stale worktree launcher folders can contain broken symlinks that make
  `git worktree add` fail with `Invalid repository ... already exists`. Before
  deleting anything, inspect whether the path is a real worktree, a normal
  directory with work, or a broken symlink. Back up or move only the stale
  obstruction.
- The missing-rollout Codex resume fix has source prepared in the restart
  candidate worktree but is not live unless the binary hash changes from
  `7c63eb8fa7b2b46f6567ef7f8606df1d7a794bb6685d14cd7bf951c531f00e46`
  and the live binary contains the missing-rollout prompt text.
- The live frontend is intentionally pinned to `20260514Tworkspace-unpin`; do
  not replace it with an older or dirty bundle.
- Several historical frontend bundles regressed archived project visibility and
  order because they were built from dirty maintenance checkouts.
- Queue handling has both frontend and backend pieces. Do not claim queue fixes
  are live unless the running backend binary contains the backend path and the
  frontend release contains the polling/reconciliation path.
- VK may lose tracking of Codex app-server work while Codex rollout files keep
  updating. Before declaring an agent stopped, check both DB execution rows and
  the Codex rollout file under `codex-home/sessions`.
- `LIVE_DEPLOYMENT.json` and older sections of `STATE.md` may lag reality.
  Always verify with `systemctl`, `sha256sum`, `readlink`, `curl`, and the smoke
  script.

## Documentation Requirement

Before handing off:

- Update `STATE.md` with durable facts and invariants.
- Update `STREAM.md` with branch-local status, risks, and next safe steps.
- Prepend `HANDOFF.md` with a short pickup note.
- Append `DELTA.md` only for compact history worth preserving.
- Record exact validation commands and what was not validated.

Do not leave deployment state only in chat.
