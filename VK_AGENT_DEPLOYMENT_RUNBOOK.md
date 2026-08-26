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
   - frontend source commit, release path, asset names, and asset sha256
   - proof that the frontend bundle was built from the same intended release
     commit as the backend, unless an explicit mixed-version exception is
     approved and recorded
   - features intentionally included
   - known fixes that must not regress
   - validation commands and results
7. Take an efficient restore-grade backup and mirror it to Desktop.
8. Verify the backup archive, checksum/manifest, and latest pointer.
9. Check active agents and Codex rollout availability:
   - query the live VK database for `execution_processes.status = 'running'`
   - join to `coding_agent_turns.agent_session_id` when present
   - verify each active Codex thread's `rollout_path` exists
   - query Codex threads updated today and verify their rollout files exist
   - if any referenced rollout path is missing, restore it before restart or
     report the exact gap as unresolved
10. Stop and report: the only remaining action should be the approved restart
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
- treat the frontend bundle as part of the release, not as a reusable artifact
  unless its source commit and required feature fingerprints are verified
- never promote a candidate whose backend binary and frontend dist come from
  different commits unless the operator explicitly approves the mixed-version
  release and the manifest lists the reason, expected missing changes, and
  rollback path
- saved messages are release-critical state. They must survive the cutover, and
  the operator must explicitly confirm them in-browser before the old stack can
  be stopped.

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
   - frontend source commit, release path, asset names, and asset sha256
   - candidate service name, ports, `XDG_DATA_HOME`, and `CODEX_HOME`
   - features intentionally included
   - known fixes that must not regress
   - source-map or source-hash evidence for high-risk UI features that must not
     regress, such as code-block copy, chat image rendering, attachment flows,
     subagent activity, workspace pin state, and repo-default behavior
   - UI preference inventory from live, including saved-message count and any
     legacy/unknown UI preference keys that must be preserved
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
5. Verify candidate frontend provenance directly from the candidate route:
   ```bash
   curl -sk http://127.0.0.1:4411/ | rg -o '/assets/index-[^" ]+\.(js|css)' | sort -u
   ```
   The returned JS/CSS asset names must match the manifest and the frontend
   release directory. If source maps are present, spot-check hashes or source
   presence for must-retain UI features before proceeding.
6. Verify candidate UI preferences against live before cutover. At minimum,
   compare the global `UI_PREFERENCES` scratch payload for:
   - `saved_chat_messages` presence and count
   - `local_project_order`
   - `local_project_customizations`
   - `selected_project_id`
   - any keys present in live but absent in candidate
   Do not proceed if the candidate has fewer saved messages or has dropped
   unknown preference keys.

Use this read-only helper for the comparison. Replace `GREEN_DB` if the
candidate data directory differs:

```bash
LIVE_DB=/home/mcp/.local/share/vibe-kanban/db.v2.sqlite
GREEN_DB=/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite
python3 - <<'PY'
import json
import sqlite3
import os

UI_PREF_ID = bytes.fromhex("00000000000000000000000000000001")

def load(path):
    con = sqlite3.connect(path)
    row = con.execute(
        "select payload, updated_at from scratch "
        "where scratch_type='UI_PREFERENCES' and id=?",
        (UI_PREF_ID,),
    ).fetchone()
    con.close()
    if not row:
        raise SystemExit(f"missing UI_PREFERENCES in {path}")
    payload = json.loads(row[0])
    return payload.get("data", {}), row[1]

live, live_updated = load(os.environ["LIVE_DB"])
green, green_updated = load(os.environ["GREEN_DB"])

for name, data, updated in (
    ("live", live, live_updated),
    ("green", green, green_updated),
):
    saved = data.get("saved_chat_messages")
    print(
        name,
        "updated=", updated,
        "saved_present=", isinstance(saved, list),
        "saved_count=", len(saved) if isinstance(saved, list) else "n/a",
        "keys=", len(data),
    )

missing = sorted(set(live) - set(green))
extra = sorted(set(green) - set(live))
print("missing_in_green=", missing)
print("extra_in_green=", extra)

live_saved = live.get("saved_chat_messages")
green_saved = green.get("saved_chat_messages")
live_count = len(live_saved) if isinstance(live_saved, list) else 0
green_count = len(green_saved) if isinstance(green_saved, list) else 0
if green_count < live_count:
    raise SystemExit(
        f"green saved-message count regressed: {green_count} < {live_count}"
    )
if missing:
    raise SystemExit(f"green is missing UI preference keys: {missing}")
PY
```

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
4. Instruct the operator to refresh or close active VK browser tabs after any
   settings changes, then wait for the UI preferences scratch record to update.
   Saved messages live in the global `UI_PREFERENCES` scratch payload; if the
   browser has not flushed them to the server, a DB backup cannot preserve them.
   If the saved-message count is `n/a` or lower than expected, stop and have the
   operator open Settings, confirm the saved messages are visible, make a small
   saved-message edit if needed, and wait until the DB check reports the
   expected count.
5. Take one final lean restore backup and mirror it to Desktop.
6. Stop the candidate, replace its seeded state from the final backup, and
   refresh the candidate `CODEX_HOME` from the final backup/copy while offline.
7. Restart the candidate on its non-live ports.
8. Re-run direct candidate smoke.
9. Re-compare live and candidate `UI_PREFERENCES` after the final sync. Saved
   messages and unknown/legacy preference keys must match before route flip.

Stage 4: Cutover:

1. Confirm live and candidate manifests, backup paths, ports, binary hashes, and
   frontend source commit, asset paths, and asset sha256 values are recorded.
2. Confirm `curl` to the candidate `/api/info` reports the expected local-only
   state and no unexpected shared API base.
3. Confirm the candidate service environment points at the recorded frontend
   dist:
   ```bash
   systemctl --user show vibe-kanban-green.service -p Environment --no-pager
   ```
   `VK_FRONTEND_DIST_DIR` must match the manifest. Do not accept a stale Stage 1
   or preview build artifact just because the backend binary is correct.
4. Confirm the final candidate `UI_PREFERENCES` inventory matches the recorded
   live inventory, including saved-message count. If it does not, stop and
   repair the candidate state before route flip.
5. Flip only the reverse-proxy or route that serves `https://vibe.local` from
   live `127.0.0.1:4311` to candidate `127.0.0.1:4411`.
6. Verify:
   ```bash
   curl -skI https://vibe.local/
   curl -sk https://vibe.local/ | rg -o '/assets/index-[^" ]+\.(js|css)' | sort -u
   curl -sk https://vibe.local/api/info
   VK_SMOKE_BASE_URL=https://vibe.local python3 scripts/vk_live_regression_smoke.py
   ```
   The `vibe.local` asset names must match the candidate manifest. If they do
   not, roll the route back or fix the candidate frontend before user testing.
7. Verify in the browser that saved messages are still present before accepting
   the cutover. Do not treat API and asset smoke as sufficient for UI
   preference continuity.
8. Keep the previous live instance available but not serving `vibe.local` until
   the operator accepts the cutover.
9. After acceptance, stop the old instance. Do not delete old state until the
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
