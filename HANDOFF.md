# Scrolling projects menu deployed — 2026-11-02

Live URL: `https://vibe.local`, published 17:28:06 UTC. Reload existing tabs.
JS `index-CRD24Nkw.js`; CSS `index-BDlsFLgm.css`. Feature source is committed at
`d0496eb1d4d6904aa69eb6b087d29c39ece488f0`, branch `vk/9cb7-vk-scrolling-pro`.
The deployment source snapshot preserves the newer live explicit-unread and
chat-notice fixes; rebuilding the older feature branch alone would omit them.
Use [manifest](LIVE_DEPLOYMENT.json) and [release evidence](VK_SCROLLING_PROJECTS_DEPLOYMENT.md).

Desktop rail, names flyout and mobile project list scroll internally with hidden
scrollbars and contained overscroll. Project actions/footer remain visible.
Five candidate and five served-public browser sizes pass with 60 synthetic
projects. Real-data desktop/mobile smoke checks show 19 projects and no page
errors; all application writes were intercepted. Current live-source unread and
chat-notice mounted regressions pass (17 + 10). Production tsc/Vite build, feature
frontend types/lint, required format and ops checks pass. Full Rust/PR baseline
and physical-phone QA were not run.

Receipt root: `/mnt/vk-storage/vk-scrolling-projects-20261102-9cb7`.
Public root: `paired/candidate`; fallback: `paired/fallback` under that root.
770 old/new assets retained. Software recovery archive independently restored
and read back from Desktop B. All five service identities, backend hash, DB inode
and 99 migrations unchanged. No backend restart, DB restore or provider call.
Only the public frontend pointer changed; direct backend/history-proxy roots and
preview routes remain untouched. Before any future cutback, recheck exact pointer
ownership and retained fallback hashes; never restore old data over current writes.

Code and deployment notes are committed locally; no push or PR requested.
Further Git integration/main promotion remains separate from this publication.

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
