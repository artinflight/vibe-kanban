# Disappearing unread notifications: investigation and proposed fix

Investigated 2 November 2026 on branch `vk/3ad7-vk-disappearing`.

## Finding

**Confirmed: workspace agent-reply unread state can clear without the reply
being read.** The UI treats displaying a workspace or returning to its browser
tab as a workspace-wide read action. It does not establish which reply was
rendered or visible. The server clears all unseen turns across that workspace's
sessions, including replies that arrive before the request is processed.

This explains a plausible mechanism for the reported disappearance. It does not
identify which historical notifications disappeared, or prove that every reported
instance followed this path. This investigation concerns workspace agent-reply
badges. Dot chat and the signed-in Notifications list have separate read systems;
there is no evidence here establishing a defect in either of those systems.
The reply history is not deleted by the investigated read operation.

## Confirmed paths

| Trigger | Observed behavior | Consequence |
| --- | --- | --- |
| Return to an open workspace tab | `visibilitychange` calls `markSeen` whenever the document becomes visible, even without focus or a rendered reply. | Returning to VK can clear an unread reply below the scroll position. |
| Open a project conversation | The read effect gates on the workspace record; it does not wait for sessions or transcript readiness. | Loading, missing or failed conversation content can be acknowledged prematurely. |
| View one session of a workspace | The backend updates every unseen turn in every session of the workspace. | Unopened sibling-session replies are acknowledged. |
| A reply arrives after render, before the seen transaction | The request supplies only the workspace ID, so SQL includes the new turn. | A reply the client never displayed can lose its badge. |
| Return/remount after marking unread | Automatic UI calls the same `manual_intent(read=true)` path as an explicit read action, releasing the hold. | A manual unread reminder can disappear without an explicit read action. |
| Reselect the same project workspace | Route equality causes an immediate read request without checking the loaded record or transcript. | Reselection can acknowledge content before it is available. |

The absence of scroll/focus/readiness checks is established by source inspection.
The mounted reproductions directly exercise calls without focus, selected-session
content, a loaded record, or user interaction after remount. They use mocked
transport and child conversation rendering; they are not physical-phone or full
browser demonstrations of a particular scroll position.

## Evidence and affected code

- `packages/web-core/src/shared/hooks/useMarkWorkspaceSeen.ts`: visibility-only
  guard; unconditional read on mount and return; no reply/session identity.
- `packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx`:
  `WorkspaceSessionPanel` passes the loaded workspace ID to the hook independently
  of `isSessionsLoading`, `selectedSession`, transcript readiness and `isAtBottom`.
- `packages/web-core/src/pages/workspaces/WorkspacesLayout.tsx`: chat/panel
  visibility gating exists, but does not establish transcript readiness or which
  reply has been read.
- `packages/web-core/src/shared/hooks/useOpenProjectWorkspace.ts`: same-route
  reselection calls the workspace-wide read action directly.
- `packages/web-core/src/shared/lib/api.ts`: `markSeen` sends a bodyless
  `PUT /api/workspaces/:id/seen`.
- `crates/server/src/routes/workspaces/core.rs`: `/seen` invokes
  `manual_intent(..., true)`.
- `crates/server/src/routes/workspaces/report_review.rs`: `MANUAL_SEEN` selects
  all executions joined through sessions by workspace ID; `manual_intent` sets
  `held=false` and advances the intent version.

Fresh read-only provenance at **12:33 UTC on 2 November** found that the serving
frontend is newer than this branch's October 31 deployment notes:

- Served JS: `index-BvmbFTPN.js`, SHA256
  `fc683d01d272989dffb7ad107f185faaf26d434731b754e48485a7a6786e4e6b`.
- Current release source: `800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`.
- The four frontend files above and the backend review route match that release's
  retained source byte for byte. The served JS was independently fetched from
  the public gateway and matched the selected release bytes; it contains the
  visibility-only automatic read hook.
- Backend PID `645213` remains active with SHA256
  `137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.

The older `LIVE_DEPLOYMENT.json` is historical provenance for this branch, not a
fresh account of the currently selected public frontend. No release pointer,
service, backend, or database was changed by this investigation.

## Validation

The existing mounted suite passes **13/13**. Those tests intentionally expect
opening and returning to a chat to mark the workspace seen; a passing baseline
therefore does not prove the reply was read.

An evidence-only extension ran those 13 tests plus **four diagnostic cases**, all
17 passing with assertions that confirm the unwanted current behavior:

1. Returning to a tab sends a read without document focus or rendered reply content.
2. A project panel sends a read without a selected session/transcript.
3. Remounting the same chat repeats the read without an interaction.
4. Same-route reselection sends a read while the workspace record is loading.

Disposable in-memory SQLite executes the actual `MANUAL_SEEN` constant and the
actual review migration. It confirms three defects: cross-session clearing,
clearing a reply inserted after the displayed snapshot, and releasing manual
unread hold. An unrelated workspace remains unread. A positive control confirms
that changing a summary after acknowledgement reopens unread via the existing
trigger. This protection does not cover a new turn inserted before a broad read.

Raw evidence is retained on mounted SSD at
`/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`:
`live-code-provenance.json`, `mounted-diagnostics.log`, `sql-diagnostics.json`,
`diagnostic-runner.mjs` and `sql-diagnostics.py`. These paths are provenance;
use the published report attachment for browser delivery.

No production seen/unread writes, device access, service restart, deployment,
provider invocation, or recovery of historical unread state was performed.
Rust HTTP integration, full browser scrolling, physical S25 interaction and a
candidate fix were not tested. The SQL check is isolated, not a live API test.

Repository-required `pnpm run format`, `pnpm run ops:check` and
`git diff --check` pass. The final patch changes investigation/continuity
documentation only; the formatter made no application source changes.

## Proposed fix

**Replace automatic workspace-wide reads with exact-reply acknowledgements.**
Keep a separate explicit “Mark all read” action for deliberate bulk clearing.

1. Move automatic read observation into the actual conversation renderer, shared
   by project and Workspaces views. Require the selected session's content to be
   loaded, the document visible and focused, the chat unobscured, and the reply's
   end visible within both the chat viewport and screen. Re-evaluate on scrolling,
   focus and layout changes; tab return alone cannot acknowledge unseen content.
   A short dwell may improve the heuristic but is not proof of comprehension.
2. Acknowledge only the exact rendered reply revisions. Add an additive UI read
   endpoint carrying bounded execution/turn IDs, selected session, server-issued
   reply revision tokens and the observed intent version. Validate ownership,
   revision and current manual intent transactionally; update only validated
   replies. Newly arrived turns, other sessions, changed revisions and conflicting
   manual unread intent must remain unread. Preserve existing changed-reply
   reopening and completion behavior. Reuse existing review-intent locking and
   conditional revision concepts; do not impersonate a Dot delivery receipt.
3. Automatic reads must respect manual unread hold and must never release it.
   Give the user an explicit read action to override their reminder. Keep existing
   connector delivery receipts and explicit workspace-read contracts compatible.
4. Route reselection should navigate/reveal the conversation and let the same
   content observer decide what was seen. Remove its direct blanket read call.
5. Record a bounded, content-free read audit: action source (visible reply,
   explicit bulk action, or verified delivery), IDs/revisions, time and changed
   row count. This enables attribution of future incidents without storing chat
   content in audit events.

Changing only the visibility listener is insufficient: opening/remounting and
cross-session/racing replies would still clear unread. Reusing `/seen` for the
new observer would retain the race and scope problems.

## Acceptance gates for implementation

- Returning while scrolled above a new reply preserves unread; viewing its end in
  the focused visible chat acknowledges only that reply revision.
- Pending/failed sessions or transcript loads, hidden panels, other phone tabs,
  remounts, polling and same-route clicks cannot clear unrendered replies.
- Viewing session A preserves unseen replies in session B of the same workspace.
- A reply inserted or revised between render and acknowledgement stays unread;
  concurrent Mark unread wins over a stale automatic acknowledgement.
- Manual unread survives automatic visibility events. Explicit read and bulk read
  actions work predictably; failed requests retain badges and can retry safely.
- Existing project navigation/reselection, completion reopening, review flags,
  connector receipts, Dot chat and unrelated-workspace preservation still pass.
- Run mounted renderer and isolated HTTP/SQLite concurrency tests, then candidate
  browser checks at desktop and phone widths with no unrelated live mutations.
  Follow repository checks and release gates before any deployment.

The requested investigation and proposal are complete. Application changes,
historical badge restoration and deployment are separate follow-up work.
