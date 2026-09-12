# STREAM.md

## Current Scope

- Branch: `vk/ab54-vk-long-threads`, based on fork staging `2df3e4333`.
- Objective: open completed long workspace turns at their latest messages and
  fetch older content as the reader scrolls upward.
- Scope: completed-log page endpoint, bounded finite-replay cache, incremental
  frontend history loader, reading-position preservation, retry UI and tests.
- Live streams keep their existing transport. No migrations, log deletion,
  live deployment, service restart, routing or asset-pointer changes.

## Status and next steps

See `VK_LONG_THREADS.md` and the latest `HANDOFF.md` entry for validation and
limitations. Source preparation is isolated in this worktree. Browser/runtime
validation with the matching backend remains required; the normal lightweight
preview cannot exercise the new API. Cold reconstruction still reads the whole
saved turn server-side. Production changes remain a separate authorized step.
