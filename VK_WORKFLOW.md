# Vibe source and runtime workflow

Current deployment truth is [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json), checked
against the running executable and public routes. The operating recipe is
[BACKEND_DEPLOYMENT_HANDOFF.md](BACKEND_DEPLOYMENT_HANDOFF.md); interruption follows
[VK_BACKEND_RESTART_PROTOCOL.md](VK_BACKEND_RESTART_PROTOCOL.md). Older runtime
inventories are archived in [the previous workflow](deployment-history/20261030-before-reconciliation/VK_WORKFLOW.md).

Code lives in `/home/mcp/_vibe_kanban_repo`, which currently has unrelated dirty
work. Use a clean SSD worktree. In this checkout `fork` is the operator's repository
and `origin` is upstream; confirm URLs before fetching/pushing. Normal work targets
fork/staging, then reviewed staging→main promotion. Commit/push is not deployment.

The sole current writer is `vibe-kanban-native-review-20261015.service` on5621,
with the existing green data/native home. Public gateway 4720 serves the paired
frontend and routes API through the protected history proxy 5640. Blue is retired.
Backend root pages have a legacy frontend; use `https://vibe.local` for UI checks.
Never restart an old service just because its name appears in an archived guide.

Preserve existing runtime environment, receipt-bound startup identity, native
history readers, approval/capacity integration and Recommend routing.
`VK_CODEX_MAX_ACTIVE_EXECUTIONS=8` remains the saved guardrail, with per-executor
memory limits and systemd execution enabled. Status cleanup is currently disabled
for recovery protection; old notes requiring re-enablement do not apply.

Normal shared build configuration uses
`CARGO_TARGET_DIR=/home/mcp/.local/share/vibe-kanban-green-build/cargo-target`
and `CARGO_INCREMENTAL=0`; resolve storage before writing. The recovered release's
isolated recipe binds its already-owned SSD target instead. Never duplicate
large targets or install tools/backups on the system disk to bypass capacity.
Backups belong on Desktop B; bulk staging belongs on mounted `/mnt/vk-storage`.

Prepare/check/build online with a fresh source/tool/config manifest. Preserve
private retained-history inputs omitted from public Git. Require a verified
current backup and compatible current-data cutback, then an actually drained,
owned writer boundary under the operator's authorization. Total elapsed time
is not a success/failure criterion; retain independent no-progress supervision
and separate failure recovery. Never reuse consumed manifests/PIDs/controllers.

After a change, verify running hash, public frontend/assets, ordinary send,
protected/recent history, review/attention/queue/settings, native resume paths
and resumed consumers. No fake completion or uncertain-input replay. Update
the manifest/checklist with exact evidence and explicit gaps. Frontend-only
publication uses a new paired release plus atomic pointer, not an in-place
directory overwrite. Native provider end-to-end QA is separate from mocks.
