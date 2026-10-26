# Local issue discussion compatibility repair — October 26, 2026

Prepared source fix; not deployed. Tracked as VK Dev T72
(`0da02ba1-7d50-4461-9a9b-0701e341c753`), linked through the native API to workspace
`a6f852f0-d00c-4dee-8864-1201d66ae6e1`. Original report: Operations T100
(`b1fcd23b-b6b0-440c-80dd-ac646dbbec09`).

## Cause and repair

Both `/v1/fallback/issue_comments?issue_id=...` and
`/v1/fallback/issue_comment_reactions?issue_id=...` return HTTP 200 `text/html`
directly from the running backend, identified on port 5621 at investigation time.
Their response SHA256 matches `/` exactly. This rules out a phone-only parser,
browser cache, or outer reverse-proxy rewrite as the source of these responses.

The shared IssueProvider has cloud comment/reaction shape and mutation contracts,
but the SQLite local compatibility router never implemented those routes.
Axum consequently selects the outer SPA wildcard and serves index.html. The
fallback collection calls response.json(), producing the reported doctype error.
A nested Router fallback alone does not fix this: a real HTTP regression proved
the outer wildcard still wins. An explicit wildcard inside `/v1` is required.

The patch adds:

- A SQLite migration for comments and reactions, with task/comment foreign keys,
  cascade cleanup, indexed issue lookup, nonempty content and unique reactions.
- Persistent local list/get/create/edit/delete routes matching the existing
  shared contracts, including issue-scoped reaction feeds, client-generated IDs,
  idempotent retries, cross-issue parent rejection and reply-cycle rejection.
- A `/v1` wildcard returning a JSON 404 for unsupported API paths while preserving
  the outer SPA routes.
- The existing local participant identity for author edit rights and selected
  reaction toggles. Remote-profile identity behavior is retained.

These local participant IDs are display identities, not new authentication
accounts or authorization grants. No shared/generated types were edited.

## Validation and evidence

Evidence directory: `/mnt/vk-storage/vk-issue-comments-20261026`.

The focused Rust HTTP regression passes against the actual product route module
and migration. It covers empty JSON feeds, mutation response contracts, stable-ID
retry, conflicting IDs, cross-issue isolation, replies/cycles, edits, reaction
uniqueness/updates/removal, SQLite close/reopen persistence and deletion cascades.
It reproduces the outer SPA wildcard and verifies unknown local APIs return JSON.

The focused harness substitutes only Deployment/ApiError and the local participant
constant; it imports the real API request types, handlers, migration and inline
test. It does not boot LocalDeployment, migrate production, or execute an agent.
The full Rust workspace was not built/tested: secondary SSD free capacity was
below 1 GiB after focused preparation. The initial broad server test build was
stopped and replaced with this harness before risking capacity exhaustion.

Chromium at 1440px desktop and 393px touch/mobile passes actual branch UI creation,
author/edit controls, comment reload persistence, add/reload/remove reaction,
edit/reload and delete. All discussion writes go to disposable SQLite through
the actual Rust routes. Other application writes are blocked; scratch drafts stay
inside the test browser. `browser-results.json` and `comments-*.png` record this.
This is mobile viewport acceptance, not physical S25 or Safari acceptance.

Additional passing checks: focused Rust Clippy with warnings denied, web-core TypeScript with a 4096 MiB Node heap,
local-web lint, changed-file lint using the local-web config, required repository
formatting, governance and git diff whitespace checks. Default-heap TypeScript
ran out of memory; the larger-heap rerun passed. Cached dependencies were reused
because the offline package store lacked a tarball. Temporary dependency links
are not committed.

## Workspace-start assessment

T100 currently has no directly linked workspace. Both existing OP::Zonnic Labels
workspaces (`06fa0efb-75fe-405b-8358-64707010c0a1` and
`b0a5a693-cc68-4636-91da-ac8d9c71bc12`) are linked to implementation issue T101
(`7b90bacb-abbd-49d7-9231-6d76e974a7df`), and both have a Codex session.
Those links were inspected and preserved.

The `/api/workspaces/start` route exists independently of the discussion feeds.
A deliberately blank prompt returns HTTP 400 application/json before creating a
workspace. The UI submit predicate depends on repository/branch, prompt and
executor selection, not on comment/reaction sync readiness. Desktop and 393px mobile browser startup
acceptance captures the linked-issue start request and blocks it at the HTTP
boundary, deliberately restoring both original HTML discussion-feed failures.
No actual Zonnic execution is launched or resumed by this investigation.

Separate baseline background HTML responses were observed in this branch-preview
configuration for `/v1/fallback/user_workspaces`, `/api/dot-sidechat/session` and
the external Discord widget. The first is another missing local/cloud feed;
the Dot route belongs to the gateway rather than the direct backend preview.
These are outside comment persistence and are recorded rather than claimed fixed.
The user-workspace feed supplies navigation/sidebar data, not the workspace-start
submit predicate. The new `/v1` guard makes unsupported local feeds fail with a
JSON route error rather than silently returning index.html.

## Remaining release and device work

No production backend restart, migration, frontend swap, service setting change,
network reconfiguration, or unrelated issue/workspace modification occurred.
Only the requested tracking issue and this workspace's issue link were created.

The initial maintained `s25-adb status` returned unavailable:
`no_current_tls_port`, no advertised endpoints and `tailscaleVerified: false`.
No resets, pairing, radio changes, listeners or access grants were attempted.
Physical Android validation needs the existing authorized phone route to become
available, then desktop/phone acceptance against the deployed candidate.

A normal approved backend release must include the new migration and routes;
a frontend-only swap cannot repair the missing server handlers. Follow the
existing restart protocol for candidate construction, capacity, backup/rehearsal,
operator approval and post-release acceptance. Production still has the original
missing routes until that release is activated. Keep T72 open until live and
physical acceptance are recorded; do not mark the current production repaired.

Reproduce the focused test with:

```sh
python3 scripts/testing/run-local-comments.py --output /mnt/vk-storage/vk-issue-comments-20261026
```

Start its disposable browser database with `--serve 5676`, then run
`scripts/testing/issue-comments-browser.mjs` with `VK_TEST_BASE` for the branch
frontend, `VK_TEST_BACKEND` for the discovered read-only backend,
`VK_TEST_DISCUSSION=http://127.0.0.1:5676`, and `VK_TEST_OUTPUT` on SSD.
Set `VK_TEST_START=1` to include captured startup with failing discussion feeds.
Stop the fixture and lightweight preview after validation.
