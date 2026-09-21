# Chat scroll frontend deployment — September 20, 2026

User authorized the frontend-only deployment. Published atomically through
`/home/mcp/.local/share/vibe-kanban/frontend-dist/current` to
`/mnt/vk-storage/vk-chat-scroll-20260920/release`.

Release source is clean commit `3da008db2aeeda1a36c9d53871a477327223827f`,
based on live frontend `f175c1b5b` plus this stream's chat changes. This retains
the live model-selector fix absent from the feature branch. Application source
matches the feature branch's scroll fix; the candidate does not include unrelated
backend changes. Existing hashed assets remain available to open browser tabs.
Live entry asset: `/assets/index-DWPtCqbK.js`; CSS remains `index-QO1t6__J.css`.

The initial seven hook tests missed late tail layout changes. Production-build
acceptance exposed that gap before publication. A content ResizeObserver now
follows delayed unvirtualized row resizing; upward scroll detection prevents
layout-generated scroll events from releasing the bottom lock. The eighth hook
regression covers resizing without a timeline update.

## Validation

- Eight isolated Chromium hook checks pass, including manual upward scrolling.
- Production build (`tsc && vite build`) passes with existing build warnings.
- Candidate and live desktop (1440px) and mobile (390px) browser checks pass:
  initial load, upward scrolling, simulated visibility return, and reload.
  Final distance from bottom is zero at both widths; no page errors.
- Model menus retain GPT-6 reasoning controls and intended models at both widths.
- Live entry HTML and referenced JS/CSS hashes match the release manifest.
- API project list/order, saved-message data, and profiles are unchanged across
  publication. Active backend `vibe-kanban-green-production-20260915.service`
  remains PID `1674994` on port 5091; no service restart or backend change.
- `pnpm run format`, ops governance and diff whitespace checks pass. Earlier
  web-core typecheck passed with an 8 GiB heap. Focused ESLint still reports the
  four pre-existing hook dependency warnings documented in HANDOFF.md.

Legacy `scripts/vk_live_regression_smoke.py` hardcodes an obsolete service,
release and project baseline; it was not used to certify this release. Current
API/hash comparisons and browser scripts are under the evidence directory.

Not exercised: physical phone/app switching; separate Tailscale origin; scratch
WebSocket persistence; Kanban drag/status/order writes and collapsed-column
interaction; archive/nav action mutations; workspace creation/link/menu actions;
review-marker transitions; queue submission/reconciliation; codeblock clipboard;
attachment upload/download/paste/drop; subagent indicators. Those paths retain
live source and assets but are not claimed as newly tested. No database rollback
or attachment/session cleanup was performed.

## Recovery and evidence

Evidence, browser screenshots/results, build log, source bundle and release
manifest: `/mnt/vk-storage/vk-chat-scroll-20260920`.
Previous frontend: `/mnt/vk-storage/vk-model-selector-20260915/release`.
Verified frontend recovery archive (previous assets and current source bundle):
`desktop:B:/vk-backups/vk-chat-scroll-20260920/frontend-recovery.tar.zst`.
This is an artifact-only rollback package, not a new backend/data snapshot.
The previous frontend directory remains intact. Roll back by atomically pointing
`current` to that directory; never restore a database for this frontend change.
