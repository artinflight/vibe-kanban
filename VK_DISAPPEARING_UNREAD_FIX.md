# Explicit workspace reads — frontend-only correction

Published to `https://vibe.local` at 2026-11-02T16:27:39.360218+00:00.
The operator requested completion with no backend changes.

## Behavior

Opening a project or Workspaces conversation, returning to a tab, reloading,
remounting, polling or reselecting a project workspace no longer marks replies
read. The existing **Mark unread** action therefore survives those UI events.

Choose **Mark all replies read** in either conversation view or Workspace Actions
to clear the workspace deliberately. The label and tooltip disclose its scope:
all agent replies across that workspace's sessions. Pending duplicate clicks are
blocked. Failed requests show an error, leave the query cache unacknowledged,
and require another explicit click to retry. Dot chat, issue review flags and
connector delivery/read contracts are unchanged.

This frontend-only solution deliberately removes automatic acknowledgement.
The existing bodyless workspace-wide read API cannot represent exact rendered
reply revisions. The original exact-reply proposal in
`VK_DISAPPEARING_UNREAD_INVESTIGATION.md` remains historical investigation context,
not an implemented backend contract. Explicit bulk reads retain the existing
server scope and include replies present when the request executes.

**Reload every existing VK tab/device to load the fix.** Older already-loaded
bundles can still perform the former automatic read. Historical cleared unread
flags were not reconstructed. Backend/history-proxy direct frontend roots retain
their prior assets; the certified entrypoint is the public `https://vibe.local`.

## Source and publication

- Feature source: `70d7f5b0516a784ca6f27ba9fc6245b441666663`.
- Preserved live frontend base: `800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`.
- Version remains `0.1.42`; artifact hashes identify this release.
- Entry assets: `/assets/index-CfDh4WtO.js` and `/assets/index-C-pTuj_j.css`.
- Serving release: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/fix-release-1/paired/candidate`.
- Immediate frontend-only fallback: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/fix-release-1/paired/fallback`.
- Both paired roots retain 717 hashed assets, including all prior entry assets.
- Newer git-preservation chat notices are retained byte for byte. This is a
  composition of the current live source and the scoped feature patch; the
  branch feature commit alone is not claimed to contain every live-only feature.

Atomic pointer replacement took 0.012907 seconds.
Public HTTPS certificate/hostname verification, loopback/public entry bytes,
new JS/CSS and the previous JS all pass. All five service PIDs/invocations,
backend executable SHA256 and database path/device/inode are unchanged;
99 migrations remain present. No restart, API/schema/config change, provider
inference, phone action, historical unread repair or live read-state mutation
was performed by this task.

## Validation and recovery

- Seventeen mounted explicit-read regressions pass; restoring the previous
  project/reselection code produces nine expected failures.
- Seven adjacent nested-card/review/navigation regressions pass.
- Local, shared, UI and remote frontend type checks pass with a bounded Node
  heap, as do focused ESLint, required format, import guards and ops governance.
- The exact preserving production build passes. Existing build warnings about
  Browserslist, Tailwind configuration and mixed imports remain.
- Candidate packaged-browser checks pass on both chat surfaces at 1440 and
  393 pixels: no automatic reads, sibling-session preservation, explicit bulk
  read, failure/retry, reload persistence, later unread preservation and a
  visible in-viewport control. No page errors. Browser read-state persistence is
  disposable SQLite; every application write is intercepted.
- A real-browser negative control on the previous live mobile frontend observes
  an automatic seen request on opening, with that write intercepted.
- All four served-release browser cases also pass with the same write isolation,
  unread-preservation checks and zero page errors. These validate the actual
  served frontend; they do not claim a live database read-state mutation.
- The 78,181,682-byte software recovery archive was restored on mounted SSD;
  3,293 regular files and their permissions were verified, with 189 directory
  modes restored from validated archive metadata. Desktop B independently
  reopened and hash-verified the archive before activation. Existing full-state
  recovery remains retained; this publication needs only frontend rollback.

Full Rust/hosted PR CI, actual live seen/unread mutations, provider execution and
physical S25 interaction are not claimed. No backend code was changed.

Evidence root: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.
Key receipts: `browser-before/results.json`, `browser-candidate/results.json`,
`fix-types.log`, `fix-remote-types.log`, `fix-lint.log`, `fix-format.log`,
`fix-navigation.log`, `browser-live/results.json` and, under `fix-release-1`, `frontend-artifact.json`,
`preserved-live-features.json`, `pair-receipt.json`, `runtime-before.json`,
`recovery-restore-check.json`, `Desktop-B-recovery-verified.json` and
`activation.json`. Private/raw receipts and screenshots are not published to Git.
