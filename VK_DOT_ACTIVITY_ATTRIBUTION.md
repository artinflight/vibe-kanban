# T63: Running and workspace-specific Dot dispatch activity

**Activation update:** the exact combined package is now owner-approved and live.
[October18 rollout and live acceptance](VK_T63_ACTIVITY_ROLLOUT.md) supersedes the
preparation-only status below; source merge remains separate.

[Open source review](https://vibe.local/vk-artifact-viewer.html?id=15ab9428-4241-426e-a27c-95bc5dacacd9&name=t63-attention-review.html&v=1).
This extends the completed [manual unread implementation](VK_DOT_MANUAL_UNREAD.md)
in the same T63 workspace and draft PR268. It authorizes no merge or rollout.

## Intended grouping

Running is an activity view; Attention is an action view. Real actions remain
visible without removing their active workspace from Running. Ordinary unread
alone is a badge while active. The categories intentionally overlap for explicit
Dot attention and approvals; All still counts unique workspaces.

| Workspace state | Running | Attention | Idle/Ready |
| --- | --- | --- | --- |
| Running, with ordinary Dot or agent unread | Yes | No | No |
| Running, with explicit Dot Needs Attention or pending approval | Yes | Yes | No |
| Active or unresolved subagents, with ordinary unread | Yes | No | No |
| Active or unresolved subagents, with attention/approval | Yes | Yes | No |
| Idle, with agent unseen, Dot unread, attention or approval | No | Yes | No |
| Idle without these flags | No | No | Yes |

The same membership feeds desktop accordion and phone filters. Dot unread and
attention badges remain independent. Pending approval keeps the existing phone
caption/hand; desktop now shows its accessible hand even when the parent agent
is idle. No coding-agent seen flag, execution status or approval is changed.
Existing pagination still retains actionable work beyond the first history page.

## Dispatch attribution and presentation

The newer connector records verified receipts in `dispatch_notes`, keyed by
owner/execution and bound to a unique message, thread and target workspace.
Use that binding, never message text, role alone or `reply_to:null`, to distinguish
an internal dispatch note from genuine shared conversation.

- Issue notification totals remain aggregate, preserving issue-level indicators.
  Two additive shared-count fields exclude verified dispatch notes.
- A new `workspaces` notification array contains dispatch-only counts for their
  exact workspace. Workspace cards combine genuine shared conversation counts
  with only their own dispatch counts. Unknown/new sibling workspaces inherit
  genuine conversation, not another agent's dispatch note. Legacy service data
  retains the existing fallback until the compatible service is adopted.
- Browser workspace history filters foreign dispatch notes in SQL **before**
  pagination. Genuine owner/Dot messages remain issue-shared. Target notes are
  labeled “Agent dispatch note”; connector whole-thread reads retain annotated
  target/execution metadata for context.
- Automatic read, manual read/unread and attention changes reject foreign
  dispatch notes. A stale sibling client cannot acknowledge the target's note;
  batch validation remains atomic. Genuine replies retain shared read/attention.
- The existing receipt-table definition is reused exactly. Existing notes are
  attributed retroactively from their retained bindings. No cleanup, message
  deletion, blanket mark-read, resending, new note or new agent is necessary.

## Nominated T18 observation

Read-only/query-only inspection confirmed exactly the owner's nominated single
Dot note, unseen, attention null, bound to the T18 manager's accepted execution.
Evaluating the new notification query directly on that existing metadata yields
aggregate unread **1**, shared/sibling unread **0**, target dispatch unread **1**,
and target attention **0**. The note/read/attention state was not mutated.

This is a read-only preview of the correction, not live clearing: the existing
live frontend/service still need the separately approved combined release.
Private message/execution identities and transcript content are not published.

## Validation and preservation

- All **76** current Python sidechat tests pass, including Mark unread durability,
  target/sibling read protection, shared genuine messages/attention, independent
  dispatch attention, reload, pagination, isolation and unchanged delivery.
- An isolated three-way integration over current live continuation/context source
  passes the same **76** tests and all **34** official newer connector regressions.
  No live source, service, grant, subscription, paired session or agent changed.
  The installed dispatch module matches PR272 head
  `71252feaeca0b9deba53d0faed59731e07f76d95` byte-for-byte (SHA256
  `9b8aedbda9e233c80a2df5c1e1da9b4b915ccfc463902c1434605186210d821d`).
- **7** TypeScript attribution/pagination cases pass. Actual sidebar DOM and
  Chromium pass at **390/1440 px** for ordinary unread, explicit attention,
  approvals, idle/unseen and active/unresolved subagents, including transitions.
- Existing manual unread/read/reload/race, uncertain-send and receipt tests pass.
  All four frontend type checks, local-web/UI and changed shared-file lint,
  translation scan, repository format, ops and diff checks pass.
- The initial remote-web type check exhausted its default heap after the shell
  applied the configured bound only to local-web. Applying the existing 4 GiB
  bound to every package completed successfully. No type failure was concealed.
- Rust source is unchanged. Full local Rust check/lint/test baseline remains
  blocked by the previously reproduced missing `glib-2.0.pc`, rechecked with
  pkg-config. It was not compiled again to repeat the known prerequisite failure.
  Hosted exact-head CI is a separate publication gate, not a local pass claim.

Reproduce the source regressions without a live browser or production writes:

```sh
python3 -B -m unittest discover -s scripts/dot-sidechat
node scripts/dot-sidechat/test-notifications-ui.mjs
node scripts/dot-sidechat/test-live-ui.mjs
node scripts/dot-sidechat/test-sidebar-activity.mjs
node --experimental-strip-types --test packages/web-core/src/shared/lib/dotWorkspaceActivity.test.ts packages/web-core/src/pages/workspaces/workspaceSidebarPagination.test.ts
```

For isolated Chromium, set the installed `PLAYWRIGHT_MODULE`/`CHROMIUM_PATH`,
read-only `DOT_BASELINE_RELEASE` and a mounted-SSD `VK_TEST_OUTPUT`, then run
`node scripts/dot-sidechat/test-sidebar-activity-browser.mjs`. These tests create
only a fresh unpaired fixture browser and loopback server, not another Vibe backend.

## Release ownership and state

Source is tested and published for review in existing **PR268 / T63**; **not
merged, installed or deployed**. Root will seek exact release approval. Preserve
selected model/effort, Recommend routing and all current CU/Stop controls.

Staging and Preserve Dot retain integration ownership. Combine this frontend
with the compatible Python sidechat/browser service, preserving current live
`vk-dot-dispatch-notes-20261018-v2` continuation/context/dispatch changes and
Mark unread. No Rust backend rebuild is required. The isolated compatibility
copy is not a production candidate or an accepted rollout package. Do not replace
live modules with this checkout's older baseline or roll back to stale SQLite.
Exact candidate, cutback, latest-state preservation and live acceptance remain
release work; no new deployment authority follows from the October 17 release.
