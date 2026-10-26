# T68 pickup — direct launcher Claude support

New issue T68 (`0eb31691-b6e1-406a-a2b9-a4b9bf5ca1f2`) is linked to the
current dedicated workspace. Read [the contract](VK_DIRECT_LAUNCHER_CLAUDE.md).
The direct adapter is external; changes are prepared only as a hash-pinned
repository overlay. Native Rust MCP already supports Claude. The new backend
handoff requires the migration and existing serialized admission; long/incomplete
history, unknown past approval settings and pending work fail closed.

Validation: 42 connector tests and 28 installed-source policy/status
regressions plus JSON Schema/discovery/dispatch checks pass entirely offline.
All 12 focused Rust handoff tests pass. The offline workspace baseline is blocked by uncached `arboard v3.6.1`
(Tauri dependency). Broader server-library tests: 98 passed, 3 failed, 2 ignored.
The three `original_worker` production-fixture tests share process globals;
one large-history case passes isolated, while the two launch/timeout cases still
fail isolated with `Worker collision or capacity guard blocked`. Their cause is
unresolved; no baseline equivalence or all-green backend suite is claimed. `pnpm run ops:check` passes. `pnpm run format`
completed Rust formatting, then failed on missing Prettier. `pnpm run check` and
`pnpm run lint` cannot run without this checkout's TypeScript/ESLint dependencies.
No live handoff, paid-model call or deployment is exercised.

Inherited pickup/release history follows; its old release ownership remains intact.

# Pickup

Current bounded follow-up: [compact durable job outcomes](USAGE_JOB_OUTCOMES.md).
PR266 is merged; preserve its archives/reuse and the newer release coordination.

1. Read [STATE](STATE.md) for active protections and the topic map, then
   [STREAM](STREAM.md) for this branch. Do not load historical archives by default.
2. Read [USAGE_EFFICIENCY](USAGE_EFFICIENCY.md) for exact measured results,
   commands and outstanding integration. Preserve owners' existing changes.
3. Reuse the existing fingerprinted Preparation runner: prerequisites before
   build, immutable source/tool/config/artifact identity, one cache owner,
   and fresh volatile acceptance on every run. A cache hit never authorizes
   deployment or skips current owner/data/queue/QA checks.
4. Staging owns release and actual native queue start/drain readback. Nightly
   workspace604d owns the sole B backup/package/schedule; its counted capacity
   phase is not a backup. Neither is replaced by this efficiency branch.
5. No restart, schedule activation, cleanup, privilege change or extra worker
   is authorized here. Observe fresh resource admission and leave a user lane.

All former pickup text is preserved exactly in
[HANDOFF history](HANDOFF_HISTORY_20261017.md). Locate relevant dated sections
with `python3 scripts/continuity/pickup.py find QUERY` rather than reading the
whole archive. The [archive manifest](CONTINUITY_ARCHIVE.json) records the
original source commit, byte counts, hashes and every heading/line locator.
Archives contain historical contradictory checkpoints: use current validated
owner evidence, never a stale heading that says "current".

Current release coordination, newer Sidebar adoption and remaining private gates:
[October 17 release status](VK_RELEASE_COORDINATION_20261017.md).

Collapsible issue behavior and approved frontend release: [topic evidence](VK_COLLAPSIBLE_ISSUES.md).
