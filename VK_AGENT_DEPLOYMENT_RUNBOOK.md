# VK Agent Deployment Runbook

This file is the pickup guide for agents working on Vibe Kanban from inside
Vibe Kanban. Follow it before editing, building, or deploying this repo.
For the planned clean self-development project/preview model, read
`VK_SELF_DEVELOPMENT_WORKFLOW.md` as well.

## Current Live Truth

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

Read [`VK_PREVIEW_GUIDE.md`](VK_PREVIEW_GUIDE.md) first. It is the concise,
canonical agent procedure for choosing, starting, publishing, verifying, and
troubleshooting a preview. The details below remain as deployment context.

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
- proxies API calls to the existing green backend on `127.0.0.1:4511`
- starts at preview port `3002` unless overridden
- can expose a tailnet-only Tailscale Serve URL when Tailscale is available
- must use the approved `8443` Tailscale Funnel route for an operator browser
  that is not connected to the tailnet

Useful overrides:

```bash
VK_PREVIEW_PORT=3030 pnpm run preview:light
VK_PREVIEW_PORT_START=3040 pnpm run preview:light
VK_PREVIEW_BACKEND_PORT=4511 pnpm run preview:light
VK_PREVIEW_TAILNET_PORT=18460 pnpm run preview:light
```

Public operator review:

```bash
preview_port="$(cat .vk-preview/port)"
tailscale funnel --bg --https 8443 "http://127.0.0.1:${preview_port}"
curl -skfI https://mcp-server.tail744c4.ts.net:8443/
curl -skf https://mcp-server.tail744c4.ts.net:8443/api/info
```

Never report an `184xx` Serve URL as publicly reachable. It is tailnet-only
and commonly produces `ERR_CONNECTION_TIMED_OUT` in the operator's browser.

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

Follow [the established backend restart protocol](VK_BACKEND_RESTART_PROTOCOL.md).
Green remains usable during builds, testing, bulk backup transfer and isolated
Blue rehearsal. Measure the complete interruption and obtain explicit "cut over
now" before any production change. Preparation approval is not restart approval.

The prior numbered procedure treated retired blue as production and permitted
stale-state route rollback. It is removed from this runbook; Git history preserves
it for incident analysis, not execution. Retired vibe-kanban.service stays stopped.
See [the lessons learned](VK_RESTART_LESSONS_LEARNED.md) for the failure evidence.

Preserve worktrees and attachments during both candidate startup and rollback.
The guarded artifacts require DISABLE_WORKTREE_CLEANUP=1,
DISABLE_STATUS_WORKTREE_CLEANUP=1 and DISABLE_ATTACHMENT_CLEANUP=1.
Use the mounted SSD for bulk work and the dedicated shared Cargo target;
CARGO_TARGET_DIR=/home/mcp/.local/share/vibe-kanban-green-build/cargo-target
is the retained logical build path; verify it resolves to the mounted SSD.
CARGO_INCREMENTAL=0 remains the build policy. Do not enable cleanup as part of
a cutover. Preserve latest accepted data on rollback, never an old test snapshot.

## Backup Workflow

Codex history preservation includes `thread_history_*.sqlite`, not only
`state_*.sqlite` and rollout JSONL files. Copy every continuity database with
SQLite-aware snapshots and retain the complete home. A September 11 isolated
test omitted `thread_history_1.sqlite` and falsely returned empty recent threads;
all 29 affected histories passed read and resume once that database was included.
Rehearsals must reproduce the full storage contract before diagnosing data loss.

For candidates containing the attachment preservation guard, set
`DISABLE_ATTACHMENT_CLEANUP=1` during protected cutovers. Startup otherwise runs
orphan attachment deletion, and workspace links alone do not cover every reason
an attachment must be retained. This flag suppresses automatic startup cleanup,
not uploads, downloads or explicitly requested deletions. Pair it with the
worktree cleanup guards and verify attachment IDs and bytes before/after startup.
Do not assume older binaries recognize this flag. Retention cleanup is separate
from deployment and needs its own review.

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
