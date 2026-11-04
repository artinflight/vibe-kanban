# Read Later frontend deployment — 2026-11-04

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
