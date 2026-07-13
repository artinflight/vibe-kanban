# VK Agent Deployment Runbook

This file is the pickup guide for agents working on Vibe Kanban from inside
Vibe Kanban. Follow it before editing, building, or deploying this repo.
For the planned clean self-development project/preview model, read
`VK_SELF_DEVELOPMENT_WORKFLOW.md` as well.

## Current Live Truth

- Canonical source repo: `/home/mcp/_vibe_kanban_repo`
- Live service: `vibe-kanban.service`
- Live backend port: `4311`
- Preview proxy port: `4312`
- Live binaries:
  - `/home/mcp/.local/bin/vibe-kanban-serve`
  - `/home/mcp/.local/bin/vibe-kanban-serve-prod`
- Current live binary sha256 as of 2026-06-03:
  - `722a5b0d14ca2350661cdcd0a271ac2cfea980dae4f2dcafc55b8ffe9470ed75`
- Current live frontend pointer as of 2026-06-03:
  - `/home/mcp/.local/share/vibe-kanban/frontend-dist/current`
  - points to `/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/20260603Tqueue-resume-max-active`
  - live asset: `/assets/index-BLreFcjw.js`
- Current live runtime uses isolated Codex home:
  - `CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home`
- Current live runtime uses refreshable frontend assets:
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
the live checks above.

## Absolute Rules

- Do not restart `vibe-kanban.service` without explicit operator approval.
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

Prepare:

1. Start from a clean candidate worktree based on the intended release branch.
2. Confirm all intended fixes are present in the candidate branch.
3. Confirm known live fixes are not missing from the candidate branch.
4. Run focused checks and any required broader validation.
5. Build the release binary and frontend assets from the clean candidate.
6. Write a deploy manifest with:
   - branch and commit
   - build worktree
   - binary path and sha256
   - frontend release path and asset names
   - features intentionally included
   - known fixes that must not regress
   - validation commands and results
7. Take an efficient restore-grade backup and mirror it to Desktop.
8. Verify the backup archive, checksum/manifest, and latest pointer.
9. Check active agents.
10. Stop and report: the only remaining action should be the approved restart
    or frontend symlink switch.

At the restart window:

1. Re-check active agents immediately before touching the service.
2. If agents are active, report them and wait unless the operator explicitly
   accepts interruption.
3. Install the already-built binary/assets.
4. Restart only when backend code changed.
5. Run post-restart smoke before saying the deploy worked.

This workflow exists so the operator can continue using VK while the candidate
is built and validated, and downtime is limited to the final switch/restart.

## Blue/Green Local Cutover Workflow

Use this path when the goal is to reduce restart risk by proving a replacement
local VK stack before `vibe.local` is moved to it.

This workflow does not remove the backup requirement. It adds an isolated
parallel instance, a final sync window, and a reversible route flip.

Required invariants:

- keep taking the lean restore backup and mirroring it to Desktop
- never run two VK instances against the same live state directory
- never share the live VK `CODEX_HOME` between active instances
- never point `vibe.local` at the candidate until the final cutover step
- do not start new work or coding agents on the candidate before cutover
- treat running agents as non-migratable; wait for them to finish or get
  explicit operator approval to interrupt them

Current implementation constraint:

- production data location is selected through `ProjectDirs`, which respects
  `XDG_DATA_HOME` on Linux
- `VIBE_KANBAN_DATA_DIR` is not currently the production data-directory
  selector; do not rely on it for blue/green isolation unless code support has
  been added and validated
- use an isolated `XDG_DATA_HOME` for the candidate, such as:
  `/home/mcp/.local/share/vibe-kanban-green-xdg`
- with that setting, the candidate VK data directory should be:
  `/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban`

Stage 1: Pre-Spin-Up Preparation:

1. Start from a clean candidate worktree based on the intended release branch.
2. Confirm all intended fixes are present and known live fixes are not missing.
3. Run focused checks and any required broader validation.
4. Build the release binary and frontend assets from the clean candidate.
5. Write a blue/green deploy manifest with:
   - source branch and commit
   - build worktree
   - binary path and sha256
   - frontend release path and asset names
   - candidate service name, ports, `XDG_DATA_HOME`, and `CODEX_HOME`
   - features intentionally included
   - known fixes that must not regress
   - validation commands and results
6. Take a lean restore backup and mirror it to Desktop.
7. Record the local archive path, Desktop mirror path, current live service
   status, live binary hash, live frontend symlink target, `/api/info`, active
   `vk-exec-*` units, and running execution-process count.
8. Record rollback notes for the current `vibe.local` route, live backend
   target, binary paths, frontend paths, and backup archive.
9. Stop before creating or starting the candidate service, seeding candidate
   runtime paths for active use, changing reverse-proxy routing, restarting
   `vibe-kanban.service`, or touching `vibe.local`.

Stage 2: Candidate Seed, Spin-Up, And Direct Smoke:

1. Seed the candidate state from the Stage 1 backup into the isolated candidate
   data directory, not into `/home/mcp/.local/share/vibe-kanban`.
2. Copy the live VK Codex home into the isolated candidate `CODEX_HOME` only
   while the candidate is offline. Copy the full continuity state, not just
   `auth.json`.
3. Start the candidate on non-live ports, for example backend `4411` and preview
   proxy `4412`.
4. Smoke the candidate directly by port or by a temporary test-only origin.
   Do not use `vibe.local` for this stage.

Candidate runtime requirements:

```ini
[Service]
Environment=HOST=127.0.0.1
Environment=PORT=4411
Environment=PREVIEW_PROXY_PORT=4412
Environment=MCP_HOST=127.0.0.1
Environment=MCP_PORT=4411
Environment=VK_ALLOWED_ORIGINS=https://vibe-green.local
Environment=XDG_DATA_HOME=/home/mcp/.local/share/vibe-kanban-green-xdg
Environment=CODEX_HOME=/home/mcp/.local/share/vibe-kanban-green-codex-home
Environment=DISABLE_WORKTREE_CLEANUP=1
Environment=VK_DISABLE_PR_MONITOR=1
Environment=VK_USE_SYSTEMD_RUN=1
Environment=VK_TRANSIENT_MEMORY_HIGH=1500M
Environment=VK_TRANSIENT_MEMORY_MAX=3000M
```

Stage 3: Final Sync:

1. Re-check active agents on live:
   ```bash
   systemctl --user list-units 'vk-exec-*' --state=running --no-legend
   python3 - <<'PY'
   import sqlite3
   db='/home/mcp/.local/share/vibe-kanban/db.v2.sqlite'
   con=sqlite3.connect(db)
   for row in con.execute("select count(*) from execution_processes where status='running' and dropped=0"):
       print(row[0])
   con.close()
   PY
   ```
2. If agents are active, stop and report them unless the operator explicitly
   accepts interruption.
3. Pause new live VK work. The final sync needs a short write-freeze window.
4. Take one final lean restore backup and mirror it to Desktop.
5. Stop the candidate, replace its seeded state from the final backup, and
   refresh the candidate `CODEX_HOME` from the final backup/copy while offline.
6. Restart the candidate on its non-live ports.
7. Re-run direct candidate smoke.

Stage 4: Cutover:

1. Confirm live and candidate manifests, backup paths, ports, binary hashes, and
   frontend asset paths are recorded.
2. Confirm `curl` to the candidate `/api/info` reports the expected local-only
   state and no unexpected shared API base.
3. Flip only the reverse-proxy or route that serves `https://vibe.local` from
   live `127.0.0.1:4311` to candidate `127.0.0.1:4411`.
4. Verify:
   ```bash
   curl -skI https://vibe.local/
   curl -sk https://vibe.local/api/info
   VK_SMOKE_BASE_URL=https://vibe.local python3 scripts/vk_live_regression_smoke.py
   ```
5. Keep the previous live instance available but not serving `vibe.local` until
   the operator accepts the cutover.
6. After acceptance, stop the old instance. Do not delete old state until the
   backup and rollback window are explicitly accepted.

Stage 5: Rollback:

- flip `vibe.local` back to the previous live backend
- stop the candidate
- record the rollback reason, candidate ports, backup archive, and any smoke
  failures in the deploy manifest and `HANDOFF.md`

## Backup Workflow

Use the lean restore backup as the default backup before risky VK operations:

```bash
./scripts/run_vk_lean_backup.sh
```

This wraps `scripts/vk_lean_backup.py --mirror-desktop`. It creates a local
restore archive under `/home/mcp/backups`, mirrors it to
`desktop:Desktop/vk-backups`, updates the `latest` pointers, and applies
retention so MCP does not fill up with old extracted backups.

The lean backup is the normal "safe restart" backup. It captures the local VK
state that is not safely recoverable from GitHub, including:

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
systemctl --user show vibe-kanban.service -p MainPID -p ActiveState -p SubState
systemctl --user list-units 'vk-exec-*' --state=running --no-legend
python3 - <<'PY'
import sqlite3
db='/home/mcp/.local/share/vibe-kanban/db.v2.sqlite'
con=sqlite3.connect(db)
for row in con.execute("select count(*) from execution_processes where status='running' and dropped=0"):
    print(row[0])
con.close()
PY
readlink -f /home/mcp/.local/share/vibe-kanban/frontend-dist/current
sha256sum /home/mcp/.local/bin/vibe-kanban-serve-prod
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
systemctl --user restart vibe-kanban.service
```

Post-restart verification:

```bash
systemctl --user show vibe-kanban.service -p MainPID -p ActiveState -p SubState
sha256sum /home/mcp/.local/bin/vibe-kanban-serve-prod
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

Record results in `HANDOFF.md` before saying the deploy is ready or complete.

## Current Regression Traps

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
