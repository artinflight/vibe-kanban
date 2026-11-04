<!-- save-read-pending-start -->
# Already-read workspace candidate — not deployed

Status 2026-11-04T21:20:55.397887+00:00: `8aa46ba36` adds already-read workspace bookmarks;
`449819b1e` fixes long-list phone section overlap and adds a browser bounds check.
Saved workspaces preserve read state and remain until explicitly removed.
The icon stays inline; removal labels are translated in all seven locales.

Candidate evidence: `/mnt/vk-storage/vk-read-later-20261104-f57c/save-read-fixed`. Types/lint/format/ops, 57 focused regressions,
four desktop/phone × read/unread packaged cases, and five scrolling layouts pass.
The bounded tsc/Vite build passed. All 1,324 source inputs and 417 outputs are
hashed; only 11 reviewed production inputs differ from the exact live source.
Paired roots retain 1,137 assets. VITE_DOT_SIDECHAT=0 remains preserved.
No live acceptance for this candidate is claimed; it has not been activated.
Full Rust/hosted CI, physical devices and real provider sends were not exercised.

The 116,678,639-byte software recovery archive passed full isolated restore with
5,071 files checked; SHA-256
`d3495e68585b46d33439754601cd94a6899b8e143e5a06c68709cb395357885c`.
Desktop B copy has not started because another owner holds the shared native
backup lane. Step 6 of VK_AGENT_DEPLOYMENT_RUNBOOK.md requires that verified
copy before publication. An explicit copy waiver/continuation decision is pending;
no waiver was received. The owned idle waiter was stopped, preserving the other
backup. Nothing will publish automatically. Current live assets/backend/data
remain unchanged. See HANDOFF.md for safe resume and ownership checks.
<!-- save-read-pending-end -->

# Inline icon correction — 2026-11-04

Published **2026-11-04T20:16:46.412428+00:00** at <https://vibe.local>; reload existing tabs.
Version 0.1.42, JS `index-BT-0CtGx.js`, CSS `index-CIK7OAX6.css`.
Source commit `b1f60971908611058f3f1d066e6fdd7fcbf7d58e` changes six UI files on the exact first Read Later live
source. Inline bookmark controls keep tooltip, keyboard label, pressed state and
a 44 px phone touch target. Workspace/project/saved-issue actions share the row;
Kanban actions occupy the existing header, and inbox/list actions remain inline.

## Dot notification regression

The first deployment below accidentally built with `VITE_DOT_SIDECHAT=1`.
The preceding visibility bundle compiled notification polling disabled. Enabling
it exposed stored Dot notices; deployment never reset their acknowledgements.
Source hashes alone did not catch this build-setting change. This correction
explicitly uses `VITE_DOT_SIDECHAT=0`, restoring the previous runtime setting
without bulk-clearing, marking read or changing any stored notification state.
A disposable browser compared all three packaged releases: request counts were
0, 1 and 0 respectively. The expected disabled behavior is now asserted by the
candidate/live browser test and publication controller, and documented in
VK_WORKFLOW.md. This does not claim that saved Dot notices were acknowledged.

## Current validation and recovery

All 1,324 pinned inputs were checked; only the six reviewed files differ. The
417-file build passed in 3m34s with one CPU, 5 GiB cap, 1.9 GiB peak and no swap.
Paired roots retain 1,084 hashed assets. Source preservation
passed before build, after build and immediately before activation.

UI/web-core/local-web types, focused ESLint, formatting/ops, 11 Read Later,
15 conversation-read, 10 notice and five preservation regressions pass. Candidate
and public HTTPS browser tests pass at 1440/393 px: icon-only same-row geometry,
defer/reload/restore, no overflow/errors, zero Dot polls and zero read/application
writes. Scrolling wheel/touch acceptance passes five layouts in both phases.
Trusted public health/assets and backend/database identity checks pass.
Full Rust/hosted PR baseline, physical devices, ordinary user sends and real
provider execution were not exercised by this frontend-only correction.

Evidence: `/mnt/vk-storage/vk-read-later-20261104-f57c/inline-icons`. The 112,244,120-byte software archive passed a
full isolated restore (4,966 files) and independent Desktop B
readback before publication. SHA-256 `977e0018736873b8ad41d6cc677915008dcb3410c0c449497f4adc54a5ae2ca8`.
Atomic switch: 0.007241 seconds. All five service identities,
backend executable hash and database inode/99 migrations remained unchanged.
No restart, DB restore, notification write, device action, push or PR. The paired
fallback retains the immediately previous index, including its known flag drift;
any fallback requires fresh ownership checks. Existing preview routes are intact.

Receipts: `activation.json`, `source-composition.json`, `frontend-artifact.json`,
`preservation-after-build.json`, `pair-receipt.json`, `recovery-restore-check.json`,
`Desktop-B-recovery-verified.json`, `dot-build-setting-browser.json`,
`browser-candidate-verified/browser-results.json`, `browser-live/browser-results.json`,
`scrolling-browser-candidate/results.json`, `scrolling-browser-live/results.json`,
and `live-before-verified.json`/`live-after-verified.json` in the evidence root.

The following is historical; its feature behavior remains, while its flag setting,
entry assets and publication identity are superseded by this correction.

## Original Read Later frontend deployment — 2026-11-04

Read Later was published at **2026-11-04T15:11:24.760627+00:00** to
<https://vibe.local>. Existing tabs must reload. Package version stays 0.1.42;
entry asset identity is JS `index-By-1MIma.js` and CSS `index-hk6iCElX.css`.

## Source and behavior

Feature commit: `d91ae4f69` on `vk/f57c-read-later`. The deployment source is a
composition, not that branch alone: the patch was applied to the previous exact
visibility release source under
`/mnt/vk-storage/vk-invisible-workspaces-20261103-75db/frontend-source`.
All 1,319 prior inputs were authenticated against their recorded hashes; the
patch changes 16 existing files and adds five frontend files. Every other input
is byte-identical. The final artifact pins all 1,324 input files and 417 output
files. Source hashes were checked after the build and immediately before switch.
The prior live visibility, project scrolling, chat notice and unread fixes remain.

Sidebar order is Attention, Read Later, Running, then Completed/idle history.
Read Later starts folded. Unread workspace rows, issue cards/list rows, project
notices and inbox notifications have reversible defer actions. Deferring does
not call read/seen or navigation APIs. The preference is browser-local, scoped by
host/user/entity ID, and survives reloads. It does not synchronize across devices.
Completed is the existing idle/history collection; no issue lifecycle status changes.

## Validation

- Production `tsc && vite build` succeeded in a one-CPU user service capped at
  5 GiB, with a 4 GiB Node heap. Observed peak was 1.0 GiB, zero swap.
- Against composed source: 11 Read Later interactions, 15 conversation-read,
  10 chat-notice and five preservation-gate tests passed. Source integrity and
  the preservation gate passed after build and again before publication.
- Packaged candidate and actual public HTTPS Read Later checks each passed at
  1440 and 393 px: defer, retained unread state, persisted reload, restore,
  no horizontal overflow and no page errors. Zero read calls and zero
  application writes occurred in these checks.
- The preserved scrolling-project-menu test passed five viewport cases on both
  candidate and public frontend, including wheel/touch scrolling, stationary
  actions, names flyout, last project access and a viewport-sized document.
- Public hostname/certificate validity, entrypoint/asset byte parity, API health
  and workflow/provider capability routes passed trusted read-only verification.
  All five service PID/invocation identities, backend executable hash,
  database inode and 99 migrations stayed unchanged.
- Repository formatting, ops governance and diff checks passed. Earlier source
  checks include UI/web-core/local-web types and focused lint. No full Rust or
  hosted PR baseline, physical-device test or native-provider inference was run.
  Ordinary user sending and provider execution were not exercised by deployment.

## Recovery and activation

Evidence root: `/mnt/vk-storage/vk-read-later-20261104-f57c/deployment`.
The active pointer is `/home/mcp/.local/share/vibe-kanban/frontend-dist/current`.
Both fresh paired roots retain **1,031** old/new assets, with conflicting asset
names rejected unless bytes match. The fallback carries the previous live index;
old public entry assets remain retrievable over HTTPS.

The **107,802,193-byte** software recovery archive was fully extracted to an
isolated SSD directory and all **4,853** files were checked. Archive SHA-256:
`9e07c01905243b36e4cdfcc6ea999c9710b61e0424def2bed7a6becdce06c95f`.
The existing native Desktop B client independently read back the complete archive
before publication. Its existing shared writer lane was busy initially; this
release waited for it to finish and used the same lane without interruption or
bypass. No SSD-only backup exception was used.

The fresh controller rechecked exact pointer target/inode, source/output hashes,
Desktop B receipt, public entrypoint, five services and database identity before
activation. The atomic pointer replacement took **0.012086 seconds**. Public
smoke and browser tests passed afterwards; no cutback was needed. No service
restart, backend binary replacement, data migration/restore, agent launch or
device action occurred. Backend/history direct roots and existing preview routes
were preserved. Recovery is software-only against current data, never an old
DB restored over newer writes.

Important receipts: `activation.json`, `frontend-artifact.json`,
`source-composition.json`, `preservation-after-build.json`, `pair-receipt.json`,
`recovery-restore-check.json`, `Desktop-B-recovery-verified.json`,
`browser-candidate-verified/browser-results.json`, `browser-live/browser-results.json`,
`scrolling-browser-candidate/results.json`, `scrolling-browser-live/results.json`,
`live-before-verified.json`, and `live-after-verified.json`.
The exact activation controller and isolated restore are retained in the same
root. Any future fallback requires fresh ownership, health and source checks;
the consumed publication controller must not be blindly re-run.

The original read_live CLI rejected the trusted leaf because it does not set
partial-chain trust. The successful read-only observations used that tool's
unchanged checks with a process-local TLS context trusting only the exact public
leaf, retaining hostname and validity checks. No TLS validation was disabled.

Only local commits were made; no push, PR or main promotion. User acceptance is
pending ordinary use after reload. No additional deployment approval is needed
for this completed publication.
