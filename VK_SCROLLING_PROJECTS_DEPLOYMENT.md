# Scrolling projects menu publication — 2026-11-02

The operator authorized deployment. The public frontend at <https://vibe.local>
was activated at **2026-11-02T17:28:06.166500+00:00**. Reload existing tabs.
Version remains 0.1.42; asset/source hashes identify this release.

- JavaScript: `/assets/index-CRD24Nkw.js`.
- CSS: `/assets/index-BDlsFLgm.css`.
- Feature commit: `d0496eb1d4d6904aa69eb6b087d29c39ece488f0`.
- Receipt/source root: `/mnt/vk-storage/vk-scrolling-projects-20261102-9cb7`.
- Public frontend: `paired/candidate`; immediate frontend fallback: `paired/fallback`.

## Preserved source and behavior

The feature branch starts at October 31 staging. Fresh live discovery found two
newer frontend changes: chat notices (`800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`)
and explicit unread-state preservation (`70d7f5b0516a784ca6f27ba9fc6245b441666663`).
The candidate copies the actual live source snapshot and replaces exactly
`AppBar.tsx`, `MobileDrawer.tsx` and `SharedAppLayout.tsx` with the feature versions.
Each replaced file's live input matched the feature parent. All other 1,307
source inputs remain byte-identical. `source-composition.json` and
`frontend-artifact.json` pin the composed inputs and all 417 build output files.
No combined Git commit is implied by the feature commit ID.

The desktop content row permits the project rail to shrink within the viewport.
Rail/flyout/mobile project lists hide scrollbars and contain overscroll; actions
and footer remain outside the scrolling list. Mobile project navigation opts into
a flex drawer layout while other drawers retain their default scrolling.

## Validation

The bounded production `tsc && vite build` passed with a 4096 MiB Node heap,
5 GiB service limit, one CPU and 3.0 GiB observed peak memory. Source hashes
were checked before and after the build. All 17 explicit-unread/navigation and
10 chat-notice mounted regressions pass against the composed source. Feature
UI/shared/local types, UI/shared layout lint, required repository formatting,
ops governance and diff checks pass.

Exact production-candidate and served-public browser checks pass at 1440×900,
1024×600, 393×852, 393×600 and 740×393 with 60 disposable fixture projects.
They verify internal wheel/touch scrolling, hidden standard/WebKit scrollbars,
viewport-sized document, stationary actions, reachable final project and desktop
names-flyout scrolling. Normal-data smoke checks pass at 1440 and 393 px with
all 19 real projects. No page errors. All application writes are intercepted;
backend read-only API/history and normal WebSocket paths remain in use. Public
Chromium trusts the known certificate's public-key pin; independent HTTPS readback
checks hostname/validity against the trusted leaf certificate.

Trusted public/local asset hashes, health/capability APIs, five service identities,
backend executable hash, database device/inode and 99 migrations all pass.
Feature implementation fixtures also verified selection and keyboard reordering.
No physical-phone QA, full Rust/PR baseline or native-provider inference was run.

## Recovery and activation

Both paired roots retain all **770** old/new hashed assets; existing same-name
assets must be byte-identical. Previous public entry assets remain retrievable.
The **74,848,460-byte** source/software recovery archive was fully extracted on
SSD and every candidate, fallback and source file was independently hash-checked.
The existing shared Desktop B object client then uploaded/reused and independently
read back the same archive. Its receipt is `Desktop-B-recovery-verified.json`;
archive SHA256 is `6d993a11f498ea799c0685dd1f0669c01342a612a02cf87c93c04d1511f1ae0c`. Prior mutable-state recovery is
preserved; this frontend update does not restore or migrate any database.

The Desktop B writer lane initially belonged to another VK backend recovery job.
Its lock and process were left intact; activation waited for this release's own
successful backup and readback. A fresh activation script then rechecked the old
pointer, public entrypoint hash, source/output hashes, backup receipt, all five
service identities, backend executable and database identity before replacement.
The atomic pointer replacement took **0.014277 seconds**.
All five service PIDs/invocation IDs stayed unchanged. Backend remains
`137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
No backend restart, service/routing change, data restoration or device action.

Key receipts: `activation.json`, `frontend-artifact.json`, `source-composition.json`,
`pair-receipt.json`, `recovery-restore-check.json`, `Desktop-B-recovery-verified.json`,
`browser-candidate/results.json`, `browser-live/results.json`,
`normal-live-smoke.json` and `final-readonly.json`. Exact controller and browser
sources are retained alongside the receipts. Future cutback requires fresh pointer
ownership/hash checks and uses the paired fallback without touching current data.
Backend/history-proxy direct frontend roots and existing previews are preserved.

Source and deployment documentation remain local; no push, PR or main promotion.
