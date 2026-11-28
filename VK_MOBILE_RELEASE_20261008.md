# Phone frontend release — October 8, 2026

The operator reviewed the redesigned task/workspace screens and style pass,
then explicitly requested deployment, push/PR and rebase merge. This supersedes
the original development-only boundary. [PR224](https://github.com/artinflight/vibe-kanban/pull/224)
rebase-merged into staging; [PR226](https://github.com/artinflight/vibe-kanban/pull/226)
rebase-merged into main. The frontend became live at 17:41 UTC on `https://vibe.local`.

## Source and activation

- Production frontend commit: main `22f09e245332d22301d532f0ee3e8229906773ac`.
- Clean build commit: `bdf6346d32cc177a1e2b02646bf12afc03fa9852`.
- The entire Git tree is identical across the build and promoted commits:
  `4ab63545a05e01ff865a4be779092e6f77632a25`. GitHub rebase changed commit identities.
- Clean build worktree: `/mnt/vk-storage/vk-mobile-release-20261008/_vibe_kanban_repo`;
  detached HEAD was advanced to the byte-identical main commit after the build.
- Immutable frontend: `/mnt/vk-storage/vk-mobile-release-20261008/release/frontend`.
- The live process uses `/mnt/vk-storage/vk-green-cutover-20261005/release/frontend`
  directly. An atomic Linux `RENAME_EXCHANGE` replaced that directory with a
  symlink to the new release, preserving the entire previous directory as
  `frontend-rollback-20261008`. The general `frontend-dist/current` pointer was
  updated atomically as well. There was no missing-directory interval.
- Old hashed assets remain served for existing tabs. No live-only HTML shim was
  present in the previous index; its crypto UUID polyfill remains in source.
- Backend unit: `vibe-kanban-green-production-20261005.service`, unchanged PID 3027197.
  Binary SHA256: `5e7948921f962b9ea74597781ca2e1b0c7bd745edc0d1901a8274dab444097a2`.
- The backend/database, 5511/5512 routing, services, cleanup flags, agent execution,
  configured model/effort and Recommend-only routing were preserved. This is an
  explicitly approved frontend-only release using existing backend APIs.
  Future backend packages must include this frontend rather than restore the
  October 5 UI.

## Served assets

| Asset                        | SHA256                                                             |
| ---------------------------- | ------------------------------------------------------------------ |
| `/assets/index-JMqAOzZ4.js`  | `71b470cb64f3dffcb6abf77cb753204b67f8a4ca97225fae9399dd9c32bb7dfa` |
| `/assets/index-CQFlZPbR.css` | `371ade02267e207abce0f803c4bc38b5e09ee87ebae056c7980269fe88db8290` |
| `index.html`                 | `ab7c3637e64b3bafe1db5ec85f33d132e5c92609a80fd93a08cf83ed277d0f34` |

HTTPS bytes matched the manifest. `/api/info`, the previous JS/CSS entry assets,
notification service worker and web manifest remained healthy. Project API order
and counts stayed 16 active/27 archived; all 12 saved messages and their complete
payload hash were preserved. The configuration hash and backend PID/binary also
matched the pre-release baseline.

## Validation and regression coverage

Implementation CI at `bdf6346d3` and promotion CI at `515ddd118` passed all jobs,
including frontend checks/build, schema generation/SQLx, Cargo tests/Clippy and
Tauri. Local frontend TypeScript/lint, format, governance, legacy-path and i18n
checks passed. Local aggregate Rust checks could not run without GTK pkg-config
dependencies; CI supplies that coverage. The clean production build passed.
It emitted existing large-chunk/Tailwind/Sentry warnings; no Sentry upload is
claimed.

The candidate and live built bundle passed Chromium acceptance at 360, 390, 412 and
1440 CSS px, plus 390px dark mode. Tests cover switching projects/tasks/workspaces,
full-screen task details, explicit selection, status/activity filters, 48px targets,
compact search/clear, history-aware sheets/focus/Back, restored scroll/draft/search,
reading agent messages, composing without submission, Options/model preservation,
local file-chooser attachment simulation and keyboard/pinch viewport geometry.
Saved-message hydration passed separately in desktop and mobile Chromium at the
actual HTTPS origin. The browser harness intercepts writes to both `/api` and
`/v1`; it never executes a prompt or forwards browser WebSocket frames to the
backend. Project selectors match exact visible titles while allowing an accessible
needs-review indicator to extend the button name.

The first candidate attempt exposed a test-server omission: `/v1` was not proxied.
It was corrected before activation. A second attempt exposed an overly strict
project-button locator when review indicators were present; its visible-title
selector was corrected. Neither required an application change or production
rollback. Both subsequent candidate and live full matrices passed.

| Required smoke area                                                          | Result                                                                                                                                                        |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Active/archive project counts and order                                      | Verified unchanged by API; active project switching and selected state verified in browser.                                                                   |
| Archived projects excluded; archive access                                   | Active sheet source still filters archived projects; archive action retained. Archive dialog interaction not repeated.                                        |
| Removed Remote/Export/GitHub/Discord actions                                 | Desktop source remains unchanged; full menu enumeration not repeated.                                                                                         |
| Issue/workspace Rename, Archive/Unarchive, Unlink, Delete and spin-off menus | Existing source retained; destructive/action submissions not exercised.                                                                                       |
| Project-linked workspace repository defaults                                 | Existing source retained; creation form reachable, creation/default submission unverified.                                                                    |
| Needs-review markers, intentional clearing, interrupted state                | Existing activity source retained; project review indicators visible. Review-clearing mutations unverified.                                                   |
| Collapsed Kanban labels/counts                                               | Phones now use counted status chips and a task feed; desktop columns remain unchanged.                                                                        |
| Kanban drag persistence and queued follow-up reconciliation                  | Production write behavior not exercised.                                                                                                                      |
| Direct issue status selector                                                 | Reachable and 48px target verified; production status mutation not sent.                                                                                      |
| Codeblock copy                                                               | Existing component retained; clipboard interaction not repeated. Message action visibility/touch target verified.                                             |
| Paste/drag/drop/mobile attachments                                           | Native file chooser selection, visible chip, separate remove/download targets verified with intercepted upload. Paste/drop/error/network upload not repeated. |
| Active sub-agent indicators                                                  | Existing source retained; live historical/active attribution not independently exercised.                                                                     |
| Saved messages on desktop/mobile                                             | 12 messages visible at HTTPS in both viewport cases; API payload hash unchanged.                                                                              |
| Legacy scratch saved-message preservation                                    | Current backend uses durable `/api/saved-chat-messages`; legacy scratch write preservation not exercised.                                                     |
| Left-nav coloring/flyouts/archive/markers                                    | Desktop source retained and navigation smoke passed; exhaustive visual/menu comparison not repeated.                                                          |
| Instance inventory                                                           | Unit/PID, ports, database paths/sizes, frontend paths and cgroup freeze state recorded; historical units preserved.                                           |

Physical Android keyboard/browser chrome, installed PWA, Safari and Firefox remain
unverified. Keyboard coverage simulates VisualViewport geometry. No send, creation,
review/stop/approval or destructive production mutation was performed.

## Backup, rollback and artifacts

The task-scoped rollback archive contains all 765 previous frontend files; every
member matched its recorded SHA256 locally. Desktop full-file SHA256 also matched:
`4c55332bf91f4bbdff9f218ce1d9078af99ce103ee849be078f983e1dc64cfab`.
Desktop archive: `desktop:B:/vk-backups/vk-phone-frontend-20261008/frontend-before.tar.gz`.
The standard full-state backup latest pointers were not replaced. The legacy lean
wrapper targets retired state/system-disk staging; it was not used for this
frontend-only artifact swap. No full mutable-state backup or backend continuity
rehearsal is claimed. A frontend rollback restores assets and preserves latest data.

All release manifests, hashes, backup receipts, baseline unit/listener inventories,
production build/check logs, candidate/live results and screenshots are under
`/mnt/vk-storage/vk-mobile-release-20261008` on mounted secondary storage.
`release/manifest.json`, `activation.json`, `live-http.json`, `live-state.json` and
`after-saved-smoke.json` bind the result. Before/after review screenshots and
attachments are listed in VK_MOBILE_UX.md; no private screenshots enter Git.

If a frontend rollback is required, run the guarded task script
`python3 /mnt/vk-storage/vk-mobile-release-20261008/rollback_frontend.py`, then verify
old index/assets, API health and unchanged backend identity. It atomically repoints
the actual runtime frontend path and the general pointer to the preserved directory.
It does not restart VK, restore databases or delete current state.
