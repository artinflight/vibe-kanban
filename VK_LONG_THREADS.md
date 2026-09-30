# Long workspace conversations

Source branch: `vk/ab54-vk-long-threads`. This feature is not deployed. Staging integration is tracked in
[PR #111](https://github.com/artinflight/vibe-kanban/pull/111).

Completed conversation history opens at the newest 40 log entries, including
when a single turn contains thousands of entries. Scrolling upward near the top
requests another 50 entries. A Load earlier messages button also covers short,
collapsed pages and keyboard navigation. Initial positioning does not request
older pages automatically.

The server exposes `GET /api/execution-processes/{id}/log-history` with `limit`
(default 40, maximum 200) and optional exclusive `before` index. It reduces the
finite raw/normalized replay to final entry values before sending a page. Entry
indices are retained as row identities, including sparse indices. Scripts retain
stdout/stderr types. Running processes return a conflict and retain their existing
live websocket transport.

Finite reconstructions from persisted logs can be reused for five minutes. The
cache retains at most four turns and 32 MiB of serialized entry payload, keyed by
process ID and revision. Object overhead is additional. Oversized turns are not
cached. Resident execution stores are not cached because they may still be
draining their final patches after a completion status event. No database schema
or saved log files are changed.

The frontend retains already loaded pages, merges by absolute entry index,
serializes upward requests, aborts requests/streams when the workspace changes,
and shows a retry control on failure. Completion status and final live patches
can arrive in either order. Earlier messages remain available during that race.
Prepending history restores the visible row and its offset, including identifying
an entry within an aggregated row.

## Validation

- Rust: `CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target CARGO_INCREMENTAL=0 cargo test -p server log_history --lib`.
- React integration fixtures use the actual hook, context, HTTP transport and
  websocket reducer. Eight tests cover a 10,000-entry turn, concurrent upward
  requests, cross-turn boundaries, failures/retry, workspace changes, removed
  processes, new completed turns initially empty process lists and completion during partial live replay.
- Fixture runner (Node 24; external React 18.3.1 test renderer):
  `VK_TEST_OUTPUT=/mnt/vk-storage/vk-long-threads TEST_RENDERER_PATH=/mnt/vk-storage/vk-long-threads/test-tools/node_modules/react-test-renderer/index.js node scripts/testing/run-long-thread-history-tests.mjs`.
  For a fresh environment, install `react-test-renderer@18.3.1` into an external
  tools directory on the mounted build volume and set `TEST_RENDERER_PATH`.
- Frontend: `NODE_OPTIONS=--max-old-space-size=4096 pnpm run web-core:check` and
  focused ESLint using the local-web configuration. Two existing hook-dependency
  warnings in ConversationListContainer are outside this change.
- Repository: `pnpm run format`, `pnpm run ops:check`, `git diff --check`.
- Exact final results are in the latest HANDOFF entry. Test/build output is under
  `/mnt/vk-storage/vk-long-threads`; Cargo uses the existing shared SSD target.

## Remaining runtime validation and rollout

Cold historical normalization still scans the saved turn on the server; this
change bounds browser transfer/rendering, not cold normalization time. Oversized
uncached turns repeat that reconstruction on subsequent page requests. Running
turns retain full live replay when opened. No real-workspace latency improvement
has yet been measured. Browser checks of initial-bottom positioning, upward
scroll anchoring (including expanded groups), mobile touch, reconnect and Stop
remain required before promotion.

This needs matching backend and frontend releases. A frontend-only publish or a
lightweight preview against the currently deployed backend cannot validate the
new endpoint. Use an authorized isolated backend preview with disposable data;
never point a candidate at the live database. Run the full PR validation baseline
before opening a staging PR, then follow the restart protocol for any separately
authorized production cutover. No live service, route or asset pointer was changed.
