# Local assignments and workspace visibility

Branch `vk/442b-vk-user-assignme` starts from fork staging `e8c450fb5`.
This is implementation for review, not a release or permission change.

The additive migration `20261009000000_local_issue_assignments.sql` creates
stable Seamus (`5ea00000-0000-4000-8000-000000000001`) and dot
(`5ea00000-0000-4000-8000-000000000002`) participant records. These are assignment
identities only; they do not create login accounts, memberships or ACL grants.
The member-profile shape and its role value are used only for picker rendering.
No existing task receives an assignment during migration.

The local SQLite assignment table stores the existing `IssueAssignee` fields:
`id`, `issue_id`, `user_id`, `assigned_at`. Issue IDs reference `tasks.id` and
participant IDs are foreign keys. A task may have multiple assignees; the pair
is unique, retried insertion preserves its original record, and deletion of a
task cascades to assignments. No parallel workspace owner or ownership label is
introduced. The existing blank local `owner_user_id` stays a compatibility
placeholder; it cannot represent multiple assignees and is not a filter input.

Local endpoints under `/v1`:

- `GET /local-participants`: existing picker member profiles and the default
  Seamus assignment identity (`current_user_id`).
- `GET /fallback/issue_assignees?project_id=...`: project-scoped assignees for
  the existing fallback/Electric collection.
- `GET /issue_assignees?issue_id=...`, `GET /issue_assignees/{id}`,
  `POST /issue_assignees`, `DELETE /issue_assignees/{id}`: existing mutation
  semantics and `{data, txid}` / `{txid}` response contracts.
- `GET /fallback/workspace_assignments`: a read-only projection through
  `workspaces.task_id -> tasks.id -> local_issue_assignees.issue_id`, including
  null links/assignees. It includes active and archived workspaces.

The existing picker supports Seamus, dot, both and neither for local issues,
including create-mode drafts. Creation awaits every selected assignment’s
persisted promise before closing the composer, navigating to the issue or
preparing a workspace draft. Partial failure names unsaved participants and
shows **Retry saving issue**. A composer checkpoint retains the created issue,
the submitted form and confirmed assignments across panel remounts. Retry writes
only failed assignments to that same issue, without repeating successful
attachment preparation or creating another issue. Saved form fields stay locked;
concurrent submissions, reset and reopen cannot overwrite a pending recovery.
This checkpoint is in browser memory, not durable across a full page reload;
the created issue remains discoverable and can be assigned through its edit picker.
Edit-picker behavior and unread state are preserved. Local Personal/Me resolves to Seamus without
changing the authentication provider. The sidebar defaults to Mine and offers
All in always-visible assignment controls on desktop and phone, with the choice
retained in browser localStorage. Phone controls retain 48px touch targets. Mine excludes explicitly
assigned work that does not include Seamus. Shared and Seamus-only work remain
visible. Unassigned, unlinked, synthetic and unknown historical rows remain
visible. Remote/cloud-host sidebar behavior is retained. Assignment filtering
runs before search/project/PR filters, sorting, pagination, activity grouping and
counts for active and archived lists. Selecting All restores every assignment
category; existing search/project/PR filters remain independently selectable.
Assignment refresh runs every three seconds, on window focus, and after picker
mutations. Failed mutation persistence produces a visible error. An unavailable
assignment API reports a status message and initially retains visibility.

Filtering only changes the rendered lists. No review flag, unread marker,
workspace pin/archive state, issue status, journal, or authentication setting is
written. Hidden work retains its attention marker and reappears with that marker
in All. All and direct issue/workspace routes preserve discoverability; Mine is
not access control.

## Validation and review boundary

Sixteen focused Node creation/visibility/pagination regressions pass locally.
The seven creation regressions cover multi-assignee partial failure, waiting for
all results, repeated failure, successful retry, dot-only/shared/Seamus-only/
unassigned creation, synchronous errors and attachment preparation retry.
Rendered acceptance of the actual create panel verifies visible failure, enabled
Retry with locked form, checkpoint retention during/after remount, one created
issue, retrying only dot, no early navigation and unchanged edit picker/unread. Two database
regressions and an HTTP API contract test are included for hosted Cargo testing:
stable identities, dot-only/shared/Seamus-only/unassigned/unlinked inheritance,
retry uniqueness, deletion, invalid foreign keys and unread preservation.
The full historical migration chain plus the additive migration passes in-memory
SQLite replay with unchanged existing-table counts and no seeded assignments.
Formatting, ops governance, web-core TypeScript, local-web/UI lint and targeted
ESLint with zero warnings pass. A rendered React container acceptance confirms
Mine/All switching, active/archive/group counts, persisted reload choice, unread
preservation and unchanged remote visibility. The reproducible fixture and logs
are in the task artifact directory. The source regressions run in hosted CI on
[draft PR #237](https://github.com/artinflight/vibe-kanban/pull/237); its final head
checks are required before integration. CI executes the nine Node regressions,
the database and real HTTP tests, workspace Cargo tests excluding Tauri, Clippy,
frontend builds and type/schema checks. The remote job may skip private checks
when its deploy key is absent; do not infer private coverage from that status. No Cargo build is run on the MCP host:
mounted SSD has roughly 2.4 GiB available. Existing matching-lockfile frontend
dependencies are reused via private links; bulk artifacts/logs are under
`/mnt/vk-storage/vk-user-assignment-20261009`.

No production deployment, restart, service change, task assignment/backfill,
unread clearing, merge, or permission grant is performed in this task. Browser
acceptance against a new backend and reviewed assignment of historical work are
rollout steps, not claimed live acceptance.

## Safe integration and eventual rollout

The operator-specified live baseline is backend `c3c48e63` and frontend
`5ce84ee2`. These commits are present in the isolated combined-release checkout
`/mnt/vk-storage/vk-safe-release-20261009/frontend66-over-c3`. They contain
additional live recovery, report-review, MCP approval and routing work absent
from normal staging. The application source patch applies cleanly to frontend `5ce84ee2` (which
includes backend `c3c48e63`). Its CI frontend job differs: integrate the new Node
assignment-test step into the current combined workflow rather than replacing
that workflow; preserve its newer approval/runtime checks. Receipt:
`/mnt/vk-storage/vk-user-assignment-20261009/combined-release-compatibility.json`.
This proves patch applicability, not a compiled/rehearsed release.

In particular the `20261007190000_workspace_report_receipts`
migration and newer report-review runtime must be retained. Do not deploy this
feature branch or rebuild an older main/staging tree over the combined release.

1. Review this focused draft PR into staging and its exact-head hosted checks.
   No merge or production activation is included in this task.
2. The integration/release owner must carry this assignment diff into a candidate
   that preserves both combined-release baselines and any later accepted live
   changes. Check the exact deployment manifest again at adoption time. A patch
   applicability check is useful evidence, not binary compatibility certification.
3. Run hosted Rust/schema/type/lint tests and build backend/frontend together on
   a builder with adequate disk. No new generated shared types are required.
4. Rehearse migration against an isolated current SQLite backup on mounted SSD
   with cleanup disabled. Check retained report receipts, assignments, task links,
   saved messages, unread journal/flags and runtime routing invariants. Backups
   and rollback receipts belong on Desktop B: per the restart protocol.
5. On the candidate backend, fault-inject a failed dot assignment POST during
   shared creation, verify the visible partial error, then retry successfully:
   there must be one created issue, both assignees, no early navigation, no
   duplicate assignment and unchanged unread. Exercise the existing picker: assign an explicit
   dot-only test issue to dot, a shared issue to both, and a Seamus-only issue to
   Seamus. Verify active/archive Mine/All, pagination, counts, reload persistence,
   Personal/Me and direct links. Confirm unread markers survive filter changes.
   Do not infer assignments from names, branches or unread state.
6. Prepare the normal restart/cutover package and obtain separate production
   authorization per `VK_BACKEND_RESTART_PROTOCOL.md`. The live old backend has
   no local assignment endpoints: a frontend-only publication cannot activate
   this feature. Upgrading the backend first is compatible with the old frontend;
   use a coordinated release for functional adoption. Do not downgrade a database
   after the new migration without a tested rollback reader/restore plan that
   preserves all subsequent writes.
7. After activation, individually review historical tasks. Assign dot internal
   tasks only to dot and shared tasks to both using the supported picker/API.
   Leave ambiguous/unlinked/unassigned tasks visible until reviewed. No bulk-hide
   or unread-clear operation belongs to assignment rollout.
