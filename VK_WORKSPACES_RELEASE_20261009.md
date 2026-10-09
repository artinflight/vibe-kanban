> October 9, 11:56 UTC update: this is historical preparation evidence. Production
> still serves October 8. The prepared bundle lacks the newly verified tab-route
> and PWA launch follow-up; read VK_MOBILE_LAUNCH_20261009.md. Its activation helper
> is held for VKStaging coordination. The operator prohibits alternate PR232 merge
> or deployment while approval is pending; earlier merge-method requests below are
> superseded. Do not activate this candidate as the complete latest fix.

# Workspace-first frontend release preparation — October 9, 2026

The operator requested deployment, push and rebase merge of the Workspaces opening
screen, To do default on untouched phone project feeds, and whole-card review or
approval emphasis. Chat remains inside a selected workspace; explicit status
choices survive navigation and desktop Kanban columns remain available.

## Delivery status

[PR #228](https://github.com/artinflight/vibe-kanban/pull/228) rebase-merged into
staging as `c3cea2c75`. Production promotion [PR #232](https://github.com/artinflight/vibe-kanban/pull/232)
is open with all ten CI jobs successful at `e8c450fb5`. GitHub refused its requested
rebase merge with `This branch can't be rebased (mergePullRequest)`. Permission to
use a merge commit was requested; protected staging was not rewritten. No live
frontend assets changed. Production still serves the October 8 phone release.

Main's application/backend/dependency tree matches the pre-follow-up staging
application tree. A history reconciliation with main `22f09e245` retained the
entire reviewed candidate tree unchanged. The clean build at `9b53418fc` and
reconciled staging both have tree `e1fdf1a5f0fc887e2032c2d79ae1e2d21ccdf521`.
The prepared immutable frontend is under
`/mnt/vk-storage/vk-workspaces-release-20261009/release/frontend` and retains old
hashed assets for existing tabs. Its candidate manifest records all 975 files.
Before activation, the promoted main tree must match the complete clean-build
tree, and the manifest must bind the actual production commit.

## Validation

Source and promotion CI passed frontend checks/build, backend tests/Clippy,
schema/SQLx and Tauri jobs. Private remote checks remain skipped when the deployment
key is absent. The host's previously recorded aggregate Rust attempts require
missing GTK pkg-config dependencies; they were not repeated. The clean production
build, repository formatting and governance passed. Existing chunk/Tailwind and
Sentry CLI warnings remain; no verified Sentry upload is claimed.

The built bundle passed all five workflow cases at 360/390/412/1440 CSS px and
390px dark mode. Coverage includes the Workspaces opening screen without standalone
Chat, To do and explicit All selection, status state across project/task/workspace
navigation and Back, conversation reading, prompt composition without submission,
48px targets, sheets, attachment simulation, keyboard/pinch geometry and preserved
model options. Three additional cases at 390/1440px and 390px dark passed full-card
review/approval/interrupted/read/cleared fixtures without writing attention state.
All cases exited successfully. Saved-message hydration passed on candidate and
current HTTPS production at desktop and phone sizes; all 12 messages remained
available. A candidate-only saved-message probe initially lacked the static test
server's WebSocket bridge; adding the same read-only bridge used by the workflow
harness fixed that test setup. Production code did not change.

Application writes to both `/api` and `/v1` are intercepted. No prompt or inference
was submitted, and browser WebSocket frames are not forwarded by the acceptance
bridge. Screenshots, results and release evidence are stored on mounted SSD under
`/mnt/vk-storage/vk-workspaces-release-20261009`. The fresh before screenshot shows
the old Create Workspace opening screen; after screenshots show the candidate.
Physical Android keyboard/browser chrome, installed PWA, Safari/Firefox and
production creation/approval/drag/destructive mutations remain unverified.

## Candidate entry assets

| Asset                       | SHA256                                                             |
| --------------------------- | ------------------------------------------------------------------ |
| `index.html`                | `12648cc5a47e4bb929816b0c56337ddb9ccfc9be3ac70e4f13977cb8c97ae27d` |
| `assets/index-CCDYp2hT.js`  | `10b64df9ad5fe212e10f99dcc27ac329cadf7646f522273be671439b10a77104` |
| `assets/index-Y5IFow0P.css` | `661669197ccc2d660f56e8e811d80807c827db7b2419f0828e3c642212986576` |

These are prepared artifact hashes, not a claim that HTTPS serves the candidate.

## Backup and activation boundary

All 870 current frontend files were verified inside the rollback archive. The
34,122,943-byte archive SHA256 matches locally and on Desktop:
`bd8d50bdf50c883eb44dc0a3558fd0cbf06cbcfaf6e36dd8f3434a8f6e95f2b0`.
Desktop location:
`desktop:B:/vk-backups/vk-workspaces-frontend-20261009/frontend-before.tar.gz`.
Desktop initially timed out, then returned; mirroring and verification completed
at 09:38 UTC. Full-state latest backup pointers were not changed. As documented
for the October 8 release, this is an artifact-only frontend rollback; the legacy
lean wrapper targets retired state/system-disk staging. No mutable-state backup,
restore or backend interruption rehearsal is claimed.

Production remains `vibe-kanban-green-production-20261005.service`, PID3027197,
binary SHA256 `5e7948921f962b9ea74597781ca2e1b0c7bd745edc0d1901a8274dab444097a2`,
using `/mnt/vk-storage/vk-green-cutover-20261005/release/frontend`. That symlink and
`/home/mcp/.local/share/vibe-kanban/frontend-dist/current` still resolve to the
October 8 frontend. Baseline recorded 16 active/27 archived projects and 12 saved
messages; configuration, instance identities and database paths were inventoried.
The prepared activation script rechecks backup verification, prior/candidate
hashes, main promotion, browser results, configuration, project order, saved
messages and backend identity before atomically switching both symlinks. It does
not restart services or restore application data. The guarded rollback restores
the preserved October 8 assets and leaves latest user/agent writes intact.

Configured execution model/effort and Recommend-only routing remain unchanged.
After the merge-method decision, run the prepared promotion/activation workflow,
repeat live browser and HTTPS hash acceptance, then record the actual release.
