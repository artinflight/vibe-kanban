# Project sidebar: implementation and release handoff

Prepared on `vk/7db7-vk-project-dot-c` from fork `staging` at `7110930b6`.
Not deployed. The release owner is VK::Staging Check.

Tracking: [VK Dev issue](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d/issues/1900eb48-bf48-4500-97fd-56eb5ae01a3e),
linked workspace `7db73dbd-3b5d-4c21-87f1-4924be648284`.
GitHub Issues are disabled on the fork; the staging PR is the GitHub work item.

## Behavior

The local Projects board has a Project space sidebar. Desktop opens it beside
board/issue/workspace views; phone opens a full-width panel, with Back/Escape,
focus containment and return focus. Existing issue panels and board state remain.
Remote-host project views never call the local private sidechat service.

Each project has its own owner-private Dot conversation, independent of every
issue conversation and of other owners' conversations. It reuses pairing,
project grants, the same event, publisher/subscription filters, stable history
pagination, exact owner-message/event reply matching, delivery receipts,
uncertain-send retry keys, focused-visible-reply reads, and explicit attention
resolution. Project unread/Needs Attention appears in project navigation and the
sidebar. Issue notifications and coding-agent review flags retain their meaning.

Shared planning has checklist items, dated milestones, decisions and open
questions, with notes and links to one or more existing Vibe tasks. Shared means
all authorized participants in the project, including Dot through the connector.
Chat remains owner-private. Plan entries store no task status or assignee copy.
Task links show live ProjectProvider status, owners and linked workspaces; they
navigate to the existing Vibe views. Checklist/milestone completion is derived
from linked tasks; explicit completion applies only to unlinked items. Decision
recording and question resolution are separate planning facts. Deleted task
references remain visible as unavailable rather than becoming invented tasks.

Entry writes have revision checks, exact bounded fields and request-key
idempotency. A stale edit fails with HTTP409. Uncertain saves retain the exact
request and editable content in tab storage, including reload recovery. Shared
entries and private messages live in the existing private sidechat SQLite DB;
Vibe's database is read-only to these features. Existing and future projects use
server-resolved project IDs and the current all-project reconciliation policy;
no project-specific setup, synthetic issue or workspace is created.

## Contract and packaging

- `thread?project=<uuid>` reads project chat; send/seen/attention accept exactly
  one `project` or `workspace` target. Existing workspace requests are unchanged.
- `project-plan?project=<uuid>` reads shared entries; `project-entry` writes one
  exact entry with project, request UUID and revision. Normal session, origin,
  CSRF and project grant checks apply to every path.
- Notifications retain `issues` and add a separate `projects` collection.
- The private `project:<uuid>` context occupies the existing sidechat protocol's
  issue/workspace context fields. It is explicitly distinguished by
  `thread.scope_kind=project` on read. It is **not** a Vibe UUID or a task row.
  Never pass it to CU, agent-control, workspace/session or execution tools.
- Existing event and existing sidechat tool schemas are unchanged. New tools:
  `read_project_collaboration`, `write_project_collaboration_entry`. Read first;
  write only the documented entry fields, with a stable request UUID and current
  revision. Tool advertisement is not proof of main Dot catalog adoption.
- Package the complete `scripts/dot-sidechat` runtime, including the newly
  imported `project_collaboration.py`. Deploy browser/store/connector together;
  preserve the private DB, grants, sessions and existing event subscriptions.
  The current adapter dynamically imports sidechat tools; replacing it is not
  necessary. Publisher behavior/event definitions remain compatible.

## Coordination and release boundary

Preserve Dot Integration (`de2d98a3-b73f-4e70-9445-caee5cae188c`) independently
compared the unchanged tool/event contracts and found no CU/Stop source overlap.
Their live CU1.6 pins must be preserved: adapter `3a590169…`, reconciliation
`48e63ee6…`, usage wrapper `a47ee622…`, CU helper `92b2b3b7…`. The optional cutoff
wrapper `ef7dfaa8…` is prepared but was not installed at that handoff. Read their
current sealed receipt before packaging; do not infer live adoption from a PR.
Their reporting work is [PR265](https://github.com/artinflight/vibe-kanban/pull/265).

Staging session `7d6734c1-c8d0-4d55-ac27-b1f763d15a6e` received the same contract
and preservation requirements. Current release preparation is
[PR264](https://github.com/artinflight/vibe-kanban/pull/264). This feature must be
integrated as an explicit later inclusion, with combined Mobile/Steering/Dot and
artifact delivery frontend preservation. No production restart is armed here.

**Backend release required:** the separate Python Dot sidechat service and
connector bundle must be adopted, with the combined frontend. No Rust Vibe
backend source/migration/type generation changes or Vibe backend Stop/restart
are required. Do not install an older adapter over CU1.6. After authorized
adoption, verify a genuine project-chat roundtrip, live shared-entry write/read,
phone visible-read/Resolve behavior, and actual registered new-tool dispatch.

## Validation and preview

- `python3 -B -m unittest discover -s scripts/dot-sidechat -q`: 66 tests pass.
  New coverage includes owner/project/issue isolation, shared planning across
  owners and Dot, exact delivery/reply receipts, independent unread/attention,
  stable pagination, reopen durability, revision conflicts, request replay,
  task-link membership, rejected duplicate task state and connector dispatch.
- Existing `test-notifications-ui.mjs` and `test-live-ui.mjs` pass, including
  uncertain message send/reload and unchanged coding-agent API boundaries.
- Frontend type checks for local-web, remote-web, web-core and UI passed through
  the frontend phase of `pnpm run check`. The changed web-core was checked again.
  Local-web/UI lint and focused web-core lint (zero warnings) pass.
- `pnpm run format`, `pnpm run ops:check`, `git diff --check` pass.
- Broad Rust validation is incomplete: `cargo test --workspace --offline` could
  not open the dedicated shared target under sandbox permissions; broad
  check/lint backend phases were stopped rather than continuing a separate
  local-target build during the reserved Staging build window. Their unused
  reproducible local output was removed after a consumer check. No Rust source
  changed; CI must supply the outstanding workspace Rust checks before merge.
- Browser acceptance passes at both 393px and 1440px, using the actual branch frontend and real disposable Python
  sidechat API at 393px and 1440px. It intercepts all Vibe mutations. The sidebar
  itself must issue none; opening the existing issue panel may attempt its usual
  autosave, which is also blocked. No production chat/grant/plan data is used.
  Run `scripts/testing/project-collaboration-browser.mjs` with `VK_TEST_BASE`,
  `VK_TEST_OUTPUT` on SSD and installed Playwright/Chromium. Optional
  `VK_TEST_PROJECT_ID`, `VK_TEST_OTHER_PROJECT_ID`, `VK_TEST_ISSUE_ID` select context.
  Both cases pass chat send/reply/Resolve, all four planning kinds, canonical
  task/workspace navigation, stale-edit rejection, retained-edit reload recovery,
  phone Back, project isolation and no document overflow. There were 64/63
  sidechat requests; zero production writes occurred (one existing issue-panel
  autosave attempt was intercepted on desktop). Final receipt and screenshots: `/mnt/vk-storage/vk-project-collaboration-20261017`.

The lightweight preview runs on port3003 against the existing live gateway4720.
The guide's historical4511 has no listener; direct `/api/info` readback verifies
0.1.42 and the same live dataset. It cannot exercise this unadopted sidechat
backend. Public Funnel8443 already belongs to another preview and is preserved.
The published self-contained screenshot/status report is the operator preview.
This is desktop/phone viewport acceptance, not physical S25+ or Safari testing.
No live frontend swap, Vibe restart, private service reload, routing/configuration
change or existing task mutation was performed. The requested tracking issue and
workspace link were created through the normal Vibe APIs.
