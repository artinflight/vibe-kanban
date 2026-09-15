# Deploy the unused-capacity integration from VK staging

The deployment omission found after PR114 was separate from PR114's backend
code fix. Its repair now lives in this VK repository: the versioned MCP profile
`scripts/deployment/mcp-capacity.json` and `scripts/vk-capacity-deployment.py`.
They replace dependence on a private CU worktree or a particular Blue/Green
service name. No credential value is committed and no automation is enabled.

## Required deployment step

For every MCP VK release, build and package **both** `server` and
`vk-capacity-guard` in the same release directory. Nominate the actual service
and absolute server path; never infer the current writer from its colour.

During online preparation, render the candidate drop-ins on the mounted SSD:

```bash
python3 scripts/vk-capacity-deployment.py render \
  --unit CANDIDATE.service --server /mnt/vk-storage/RELEASE/server \
  --output /mnt/vk-storage/RELEASE/capacity-config
```

This generates `<candidate>.service.d/capacity.conf` and
`codexusage-preview.service.d/capacity.conf`. It includes the controller/token,
Codex home, approved build roots, release-matched guard, CU database and stable
CU gateway origin. The token must already exist privately on the host; the tool
never creates or replaces credentials or controller state.

Install the settings when committing the target service configuration under the
established restart protocol, **before its next start**:

```bash
python3 scripts/vk-capacity-deployment.py install \
  --unit CANDIDATE.service --server /mnt/vk-storage/RELEASE/server
python3 scripts/vk-capacity-deployment.py check \
  --unit CANDIDATE.service --server /mnt/vk-storage/RELEASE/server
```

`install` writes only the two capacity drop-ins and runs daemon-reload. It does
not start, stop, freeze, restart or enable either service. It refuses missing
executables, missing/private-token violations and unsafe build directories.
`check` is read-only and verifies effective settings and the service command.
A failed check blocks capacity deployment readiness; never solve it by removing
capacity configuration or by prematurely restarting production.

CU follows the stable gateway, not the old backend port. Its PartOf/After
relationship points to the nominated VK service; VK Wants CU. For a new service
generation, installing changes CU's lifecycle relationship, so do not install
while another agent is performing a cutover. Render and inspect first. Account
for any retained legacy unit dependencies during the cutover's service inventory.
Never start a rehearsal service with production CU dependencies: use private
service names, copied data and a separate profile for an isolated lifecycle test.

After the separately authorized restart and route switch:

```bash
python3 scripts/vk-capacity-deployment.py live-check \
  --unit CANDIDATE.service --server /mnt/vk-storage/RELEASE/server
```

This requires the actual running processes to have loaded the settings, the
routed backend to be the nominated executable/port, and CU to be connected and
reconciled. A successful `check` is **not** evidence of live activation.
No command selects goals, submits turns, redeems resets or enables overnight
scheduling. Preserve the user's existing selections and disabled/enabled state.
Only explicitly selected goals are subject to background scheduling; ordinary
unselected goals keep their existing behavior.

## Scope and verification

`python3 scripts/test-capacity-deployment.py` checks new service/release names,
configuration quoting, missing settings, wrong guards/origins/dependencies,
wrong executable, service-name injection and the distinction between next-start
and running configuration. The current host's installed settings also pass the
read-only `check`. No production service was restarted for this patch.

The existing CU/native acceptance proves active stop, same-goal resume, stale
quota/floor/reset limits and independent expiry. This patch changes deployment
packaging only; it does not alter or re-test the native executor. Full Rust and
frontend builds are not required to execute these Python configuration checks.
The separately active VK::Errors 2 worktree and deployment resources are not
modified by this patch.
