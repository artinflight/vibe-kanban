# Persistent Dot management indicator

Workspace rows show **Dot managed** only for an explicit trusted association.
This neutral label is separate from unread counts and Needs Attention. It remains
after read/clear, refresh, task completion and reload. It neither changes grouping
nor inherits from an issue, project, parent workspace or dispatch receipt.
Unknown workspaces and older services stay neutral.

## Association and lifecycle

`workspace_management.py` adds an append-only `dot_workspace_management` table
to the existing private sidechat SQLite database. Each local assignment/release
records an owner, exact project/issue/workspace, state, approval reference and
timestamp. The latest explicit state wins; repeated identical actions are
idempotent. Release retains prior history. Reassignment requires another explicit
owner-authorized local action. Deletion or relinking suppresses the label;
migrating an association is deliberately unsupported without separate review.

Only the trusted local administration CLI writes this metadata, following the
existing local provisioning pattern. It requires an existing exact owner scope,
an authoritative read-only Vibe resolver match, an approval reference and
`--apply`. It creates no scope, credential, grant or subscription and changes no
message, read flag, attention, execution or task. There is no HTTP/MCP management
write route and no automatic enrollment. Generic `origin=dot` dispatch receipts,
reads and shared-tool use cannot establish management.

This introduces persistent **display metadata**, not a new persistent access or
security capability. It uses existing private-file/local-administrator trust and
paired-owner/project grants. No new credentials, access expansion or agent-action
authority are required or enabled. The association is not an authorization grant.

The existing authenticated `GET /api/dot-sidechat/notifications` adds an optional
`managed_workspaces` array of `{project_id, issue_id, workspace_id, manager:"dot",
state:"managed"}`. Counts remain separate. Returned associations match the current
authoritative mapping, registered owner scope and browser project allowlist.
Internal approval references/audit history are not sent to the browser.
The hook's existing pairing-reset/remote-host safeguards apply. Workspace and
issue workspace rows render the independent label on desktop and mobile.

## Bounded T89 backfill and release ownership

The only supplied backfill is [management-backfill-t89.json](scripts/dot-sidechat/management-backfill-t89.json):
workspace `811828af-f58f-48b3-ab51-0d594a1c4f4e`, issue
`c34993a6-c342-44be-873d-95ec42bb7a05`, project
`48c03c77-4207-48c1-86ed-686262c1116a`. It is not automatically imported. T18
children/subordinates and every other unknown workspace remain neutral.

Staging applies that exact association using the existing scoped owner identity
from its private records after fresh mapping/ownership and backup checks:

```sh
python3 -B <combined-dot-release>/workspace_management.py \
  --data <existing-private-sidechat-db> --vibe-db <current-vibe-db> \
  --owner <existing-scoped-owner> \
  --project 48c03c77-4207-48c1-86ed-686262c1116a \
  --issue c34993a6-c342-44be-873d-95ec42bb7a05 \
  --workspace 811828af-f58f-48b3-ab51-0d594a1c4f4e \
  --state managed --approval-ref 'Owner confirmed T89; T63 request 2026-10-18' --apply
```

No new authentication is needed. If the existing exact owner scope is absent,
stop and reconcile through its existing owner; do not create auth rows or infer
another owner. Do not loop over dispatches, siblings or other workspaces.

This feature needs the new Python module, additive schema, browser metadata hook
and frontend together. Staging owns the combined release with
[Reply to](VK_DOT_MESSAGE_REPLIES.md) and [Jump](VK_DOT_ATTENTION_NAVIGATION.md),
preserving live Eastern timestamps/collapsible UI. Preserve Dot Integration
execution `88a68ab1-59be-4ec5-8a15-8173286b9c7c` retains dispatch provenance and
selective-acknowledgement ownership. Its newer changes must be composed with the
small browser initialization/metadata diff; no dispatch or acknowledgement
contract is changed here. The isolated compatibility overlay preserves the
latest checked live Python and Reply implementation; it is not a sealed release.

No live backfill, build, activation, service restart or real conversation/auth
mutation is performed here. No Rust/Vibe backend change is needed. Package the
new module before restarting the Dot browser in Staging's owned release plan.
Retain the latest database/audit table on rollback, along with reply-aware Python
once linked replies exist; never restore older data to hide a label.

After activation, read the authenticated notifications endpoint without marking
messages read: T89 must appear exactly once in `managed_workspaces` even with
zero counts; T18 subordinates and other unassigned siblings must not appear.
Verify actual served desktop/mobile rows and isolated-owner read/clear/reload.
Selected model/effort, Recommend, CU/Stop and active jobs remain unchanged.

## Validation

Tests exercise explicit lifecycle/repeated actions, SQLite reopen, read/clear and
manual unread/attention independence, exact target versus siblings, neutral
reads/generic dispatches, project/owner/role isolation, scope drift/removal,
unchanged auth/messages, and the real CLI against a read-only Vibe fixture.
The real metadata hook plus workspace/issue cards pass at390/1440 with GET-only
synthetic traffic, legacy neutrality and reload. Isolated Chromium uses the live
timestamp styles to verify readable rows, grouping, independent labels and no
overflow at both widths. Existing Reply/Jump and notification regressions are
retained; actual live delivery and physical-phone QA are not claimed.
