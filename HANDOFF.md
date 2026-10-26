# T68 pickup — direct launcher Claude support

New issue T68 (`0eb31691-b6e1-406a-a2b9-a4b9bf5ca1f2`) is linked to the
current dedicated workspace. [Draft PR281](https://github.com/artinflight/vibe-kanban/pull/281)
is open into staging; implementation commit `6b1ee0270` is pushed. Read
[the contract](VK_DIRECT_LAUNCHER_CLAUDE.md).
The direct adapter is external; its hash-pinned repository overlay is now
installed and the connector-only runtime adoption is verified below. Native Rust MCP already supports Claude. The new backend
handoff requires the migration and existing serialized admission; long/incomplete
history, unknown past approval settings and pending work fail closed.

Live connector follow-up completed: Seamus explicitly authorized the connector
file installation, its service-only restart, and two short disposable Claude
turns. Restarted only `vibe-dot-connector.service`; Vibe backend identity stayed
unchanged and readiness passed. Dot's actual `run_session_prompt` continued
session `2f929b09-daab-4850-89b5-fcef4b0df29f` in T68 test workspace
`69a8415a-8e5f-4754-812f-f164490bdc43`. Follow-up execution
`9d5f491c-797d-464c-9e9b-d9930f79de4b` completed exit0 and recalled the exact
prior marker without restatement. Sonnet/low/SUPERVISED selection stayed exact;
Dot reads confirm two model turns plus setup, all completed. Do not repeat tests.
New-workspace Dot schema metadata Refresh remains separate and unverified;
existing-session continuation works. Codex handoff still needs a separately
approved compatible backend/migration release. No Staging Check, production
session, billing/global setting or recovery-data changes occurred. Native failed
Git observations remain retained. Read the contract for complete evidence.

Validation follow-up: 14 focused Rust handoff fixtures, 42 connector tests and
28 installed-source regressions plus schema/dispatch/allowlist checks pass offline.
The final bounded server-library run on code head `888518dcb0` uses one process
per test: **103 passed, 0 failed, 2 ignored**, no timeouts. Earlier launch/timeout
failures reproduced at the identical assertion on exact staging base
`5b43524ea35b2eb5dd80d0881dc8445489f4442f` with seven native engines. The host count
naturally fell to six; both positive paths then passed with unchanged guards.
Large-history and monitor-startup fixtures pass isolated on base and branch.
Mixed-process base failures prove the old global-home / worker-registry isolation
requirement; CI uses nextest. The ownership/capacity sources remain byte-identical
to staging. See the contract's before/after table.

Normal locked pnpm dependencies and the previously missing Cargo `arboard` are
resolved. Full formatting, ops checks, frontend lint and strict focused server
library/test clippy (`-D warnings`) pass. TypeScript checking
exits 134 near its default 750 MiB V8 heap; this task has a 3,000 MiB hard limit,
while the supported CI/preparation heap is 8,192 MiB. Full Cargo workspace build
exits 101 at missing `glib-2.0 >= 2.70` (`glib-sys`); GTK/WebKit development packages
are also absent. No resource/guard threshold, system package, security policy or
global configuration was changed. Full check/lint/workspace-test gates remain
unverified on this host. No live Codex handoff or Vibe backend deployment was
exercised. The two approved Claude acceptance turns and connector-only release
passed as recorded above.

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
