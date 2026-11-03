# Scrolling restored after later publication — 2026-11-03

Current public frontend: `https://vibe.local`, published 09:59:20 UTC.
JS index-BRto7v9M.js; CSS index-BDlsFLgm.css. Reload existing tabs. The operator
reported no change because the later unread fix-release-4 omitted all three
scrolling files. The original November 2 receipt describes a superseded release.
Fresh reproduction confirmed 2850 px document height with 60 projects, and 1134 px
with 19 real projects in a 600 px desktop window.

Restored the unchanged d0496eb1d scrolling files onto the actual latest live source
9a45a3abf2d99eb44c14ef7a744d6f7bf0fbb73e. All other 1314 live inputs are exact.
Source snapshot: `/mnt/vk-storage/vk-scrolling-projects-20261103-9cb7-correction/source`.
Never rebuild from the older feature branch alone: it omits newer unread fixes.
The correction passed five packaged/public desktop-touch browser sizes, 19-project
public desktop/mobile scrolling through the list boundary, 27 unread/chat-notice
regressions and five source-preservation tests. Real desktop document now stays
600 px while its menu scrolls. No page errors or application writes. Physical
S25 testing and full Rust/PR baseline were not run. Operator acceptance pending.

All receipts are under `/mnt/vk-storage/vk-scrolling-projects-20261103-9cb7-correction`.
`paired/candidate` is live; `paired/fallback` retains the previous unread frontend.
926 assets retained; 88,674,581-byte recovery archive fully restored and independently
read back from Desktop B. All five service identities, backend hash, DB inode and
99 migrations unchanged. No backend restart, database restore, inference or device
action; direct backend/history frontend roots and previews preserved.

Publication must run `scripts/deployment/check_frontend_preservation.py` against
the resolved current live artifact/source and candidate, with only reviewed paths
allowed to change. Recheck pointer ownership before activation. The new gate
rejects the exact stale-source unread publication which dropped scrolling.
Workflow and runbook include this requirement. See
[release record](VK_SCROLLING_PROJECTS_DEPLOYMENT.md) and [manifest](LIVE_DEPLOYMENT.json).
Code/deployment notes remain local; no PR, push or main promotion requested.

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
