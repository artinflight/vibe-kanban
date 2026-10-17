# Project sidebar — live October 17

Seamus requested deployment after reviewing the prepared feature. Dot services
activated at **2026-10-17 11:38:35 UTC**; the frontend switched at **11:39:12 UTC**.
Dot-only restart/readiness took **1.012 seconds**. Vibe backend, static server,
gateway, notifier and workspace-agent processes were not restarted.

[Open live VK Dev project](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d)
· [Open deployment report](https://vibe.local/vk-artifact-viewer.html?id=e37baa76-cd9a-4c07-a65d-9a60fc1ac341&name=deployment-report.html&v=1)
· [Merged PR267](https://github.com/artinflight/vibe-kanban/pull/267).

## Exact release

- App/API version remains **0.1.42**.
- Build source: `4ecaa2f812ee8d635e0d265f2b97ffb9d94db741`, including
  implementation `f60c8d1d6b2c874a4324ae9af61e71677faec387`.
- Staging merge: `4ba47fe66e1cafc528ddaa84c3f4fbd71f9548c8`. Full Git trees are
  identical; canonical staging was fast-forwarded. This is a scoped component
  release; unrelated backend changes and frozen PR264 were not activated.
- Exact-head [CI39027967182](https://github.com/artinflight/vibe-kanban/actions/runs/39027967182)
  passed completely: frontend, Rust tests, Clippy, schema/remote/Tauri checks,
  governance, preservation and all 66 sidechat tests. The source-equivalent first
  run was superseded by the documentation head; its Cargo tests had also passed.
- Frontend: `/mnt/vk-storage/vk-project-sidebar-rollout-20261017/frontend-release`.
  `/home/mcp/.local/share/vibe-kanban/frontend-dist/current` selects it.
- Entry JavaScript: `/assets/index-DpbIoqaC.js`.
- Entry CSS: `/assets/index-C9c5vx_3.css`.
- Complete Python sidechat runtime, including `project_collaboration.py`:
  `/mnt/vk-storage/vk-project-sidebar-rollout-20261017/sidechat-release`.
  Connector/publisher `current` and the browser's existing release override
  select this package. Existing TLS/origin/proxy/hardening settings are retained.
- Live backend remains PID 3927146, SHA256
  `6f0230111142d6a002c1108e69ddc3e871951d1ef2f21f472619cc9fb75731c7`.
  Static 3368, gateway 602359 and notifier 587346 also remain unchanged.

The immutable package preserves all 1970 incumbent static file bytes. Only the
new index selects new JS/CSS entries. All prior hashed assets and compatibility
polyfill remain available for existing tabs. 295 differing debug source maps for
identical unchanged JavaScript retain their incumbent bytes. The actual artifact
viewer equals the versioned source. All non-sidebar Mobile/Steering/Dot frontend
source is identical to the accepted public equivalent baseline 7222b127c.

## Acceptance and preservation

The production build passed through the versioned preparation runner, with
bounded CPU/memory and existing dependencies. An initial small-heap build failed;
the successful build used a 4 GiB Node heap within a 6 GiB process cap and one CPU.
No failed build was published. Preparation/runtime receipts live under the
rollout root above; secrets and private data stay outside GitHub.

Actual served frontend and actual live authenticated Dot API pass at **393px
and 1440 px**: private project sends, persisted reply receipts, visible reads and
Resolve, all four planning kinds, canonical issue/workspace links, stale-edit
rejection, retained-edit reload, mobile Back, project isolation and no horizontal
overflow or browser errors. The live API also passes exact request replay and
independent unread/attention handling. Installed MCP `tools/list` and real
`tools/call` dispatch pass project read/write; the write is attributed to Dot.
Existing CU reporting tool names remain present.

Existing issue/workspace Dot unread/Needs Attention also passes actual served
UI/API checks at both viewports: reading clears unread, attention survives read
and reload, Resolve/Reopen is explicit, and coding-agent flags stay unchanged.

All acceptance used separate ten-minute synthetic QA owners and identifiable
planning entries. Every Vibe mutation was blocked. Zero outbound wake attempts
occurred; all synthetic grants/sessions/threads/messages/entries were removed.
No real owner session, cookie or CSRF value was inspected or replaced. Final
readback confirms all prior messages and all real pairing/grant/subscription
rows are retained. All 43 projects, names/order and 27 archived states match the
pre-deployment snapshot. Automatic future-project scope is unchanged.

All seven live CU/Stop module pins from Preserve Dot remain unchanged. An actual
registered `get_workspace_reconciliation_status` call after reload still returns
both `usage_report` and `credit_budget`. Usage is recorded; credit remains stale,
and original delivery `readback_fresh:false` is retained. These are independent
freshness signals, not a new allowance or delivery claim. No adapter/usage/Stop
module was replaced; the optional cutoff wrapper remains uninstalled.

**Limits:** installed new-tool discovery/dispatch is verified; adoption by each
retained main Dot conversation's platform-managed catalog is not established.
A natural automatic root reply and human-visible receipt were not manufactured
by synthetic QA. Physical S25+/Safari acceptance and unrelated live Kanban,
workspace creation/archive/menu, clipboard, attachment and saved-message writes
were not repeated. Their source/backend and the actual artifact viewer were
preserved; these limits are not claims that those interactions were exercised.

## Backup and rollback

Desktop restore-grade backups are verified under
`desktop:B:/vk-backups/vk-project-sidebar-rollout-20261017/`:

- `before.tar.zst`: SHA256
  `a3d162c60f35fda618bea33b12254a310900c91f1e486b33f01d27202fa6899c`.
  Complete incumbent frontend, consistent Dot/Vibe SQLite safety snapshots,
  private Dot configuration/code/service definitions. Upload/hash/download/full
  isolated restore verified 1970 static and 74 private files, exact permissions
  and both database integrity checks. Initial restore permission differences
  from umask were corrected with same-permissions extraction before activation.
- `sidechat-boundary.sqlite`: fresh consistent snapshot, mirrored/hash checked
  and downloaded immediately before service activation.
- `after.tar.zst`: SHA256
  `662fb1a697a2840a364e65c03fdf831d23914fe7839ff1c57b8522c4960fc820`.
  Latest Dot state, active service definitions, pinned validation helpers,
  manifests and 106 new/changed frontend files. Off-machine readback and complete
  delta restore plus SQLite integrity pass. Unchanged files remain covered by
  the before archive. Recovery-chain metadata is inside this private archive.

UI rollback atomically selects the retained previous frontend:
`/mnt/vk-storage/vk-dot-notification-rollout-20261016/release`.
Keep the upgraded compatible Dot service and current SQLite state during a UI
rollback. Never restore a stale snapshot over accepted conversations/plans.
Service rollback needs the pinned prior code/override and a data-preserving
procedure; it is not part of normal UI rollback and never restarts Vibe.

Durable sanitized receipts: `release-manifest.json`, `source-promotion.json`,
`sidechat-release-manifest.json`, `backup-verification.json`, `dot-activation.json`,
`dot-api-acceptance.json`, `frontend-activation.json`, `final-readback.json`,
`cu-registered-readback.json`, `post-deploy-backup.json`, and both live browser
result directories. Staging and Preserve Dot receive the final activation
handoff so later candidates retain this component release.
