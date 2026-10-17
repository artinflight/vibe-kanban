# Dot Chat needs an authoritative issue association

## Diagnosis and supported repair

Dot Chat resolves a workspace through `workspaces.task_id -> tasks.project_id`.
A paired browser and a project identifier in a workspace-start request do not
supply this association. The connector previously discarded `project_id` unless
`issue_id` was also supplied. Native Vibe permits standalone workspaces, so the
start could succeed with `task_id:null` while Dot Chat correctly rejected its
missing issue context. This is a creation-workflow gap, not a pairing failure.

Repair an existing workspace rather than recreating it:

1. Read its exact ID, branch, worktree location and current `task_id`. Check the
   selected project's existing issues for the intended dedicated issue.
2. If needed, create a generic issue through `POST /v1/issues` with explicit
   `id`, `project_id`, title, description and appropriate nonterminal `status_id`.
   Keep personal account details and the private agent prompt out of the issue.
   After a timeout, reconcile that exact issue ID before another write.
3. Link through `POST /api/workspaces/{workspace_id}/links` with `project_id` and
   `issue_id`. Re-read first if the original association was uncertain or changed.
   Never edit SQLite mappings directly or relink an existing different issue
   without reconciling its retained private conversation.
4. Re-read the workspace and confirm its identity, branch and worktree are
   unchanged, with its original sessions and execution history retained. Keep
   the issue nonterminal while work is active; terminal status can archive work.
5. Verify the normal authenticated browser `thread?workspace=...` response and
   the cached `get_workspace_reconciliation_status.sidechat` lookup. No new
   pairing, frontend deployment, Vibe restart or agent start/stop is required.

The reported workspace was repaired using these routes. Its original workspace,
branch, worktree, session and four existing executions were retained. The issue
has a generic description with no personal account details. Live HTTPS thread
retrieval returned 200 for the exact project/issue/workspace, existing browser
access rows were unchanged, and temporary test access was removed. Actual cached
connector status and history reads then succeeded. A real owner message also
arrived in the repaired conversation and its webhook was accepted; this stream
left that request for main Dot rather than consuming it with a test reply.

## Prevention in the existing connector

`workspace_issue_context.require_issue_context` verifies both `project_id` and
`issue_id` against the existing fixed project-issues read before a workspace can
start. Missing, invalid, mismatched or unavailable evidence fails closed before
any workspace/agent POST. The existing `start_workspace` advertises both IDs as
required; old cached callers receive an explicit supported-workflow error if
those existing arguments are omitted. There is no new tool-name dependency.

Create/select the issue in Vibe first, then pass its exact ID and project ID to
`start_workspace`. The guard does not auto-create issues, copy prompts into issue
descriptions, add permissions, infer project membership from a repository UUID,
or change native Vibe's standalone-workspace support outside this connector.
Existing paired access and all-project subscriptions remain unchanged.

Prepare with `prepare_workspace_issue.py` against the exact installed adapter
SHA. Its AST check preserves everything outside workspace-start preflight and
tool discovery. Recommend mode, selected model/effort, repository/branch and
prompt remain unchanged. CU/report/budget, Stop, sidechat follow-ups and current
sidebar/attention/frontend remain separate, preserved runtime modules.

## Validation

20 public Python connector tests pass (14 incumbent steering and six new context
checks). Candidate integration additionally passed 27 incumbent control tests,
an updated issue-linked start fixture with exactly one mocked POST, required
schema verification and missing/invalid/wrong-project no-start cases. The obsolete
unlinked-start fixture was replaced by the explicit issue-linked fixture rather
than counted as passing unchanged. No real agent was launched for validation.

The supported issue-link repair is live independently of guard deployment. The
exact candidate and runtime adoption receipts must be checked before claiming
the preventative guard is active. Operational identities and private transcripts
remain only in the owning Vibe handoff/private receipts, not this document.

## Live prevention adoption — October 17, 23:45 UTC

Functional source `4a5674de321bdc7aa9c4fbdf5b43443a78226a3f` is installed.
[PR271](https://github.com/artinflight/vibe-kanban/pull/271) preserves the guard,
preparation helper, tests and handoff into staging. Protocol version remains 1.6.

Installed adapter SHA256:
`62081e895d2d5ae14abb06df1ab44076588a32f3f798f1c9d8ba63cb3b69d97f`.
Guard module SHA256:
`348a3cf7d8e2471714932258bcba76c8b8d312997ad7ce327ed1680d5b434691`.

The first adoption attempt held without changing files because the idle gate
was not satisfied. After fresh idle evidence, only the connector restarted;
HTTP readiness recovered in 0.395 seconds. Current data and all existing access,
subscriptions and messages were retained. Browser/publisher, Vibe, agents,
frontend, gateway and notifier stayed running with the same PIDs. The live
PR270 follow-up bundle/shim/status, CU/report/budget and Stop hashes are unchanged.
Desktop B source/state backup passed download and isolated restore/integrity.

Actual cached status and generic issue readback still pass after adoption. The
new issue is nonterminal and its description contains no personal account
details. A live negative `start_workspace` probe was rejected by automatic
approval review: invoking a real start route could create a workspace/agent,
and the user had not authorized a validation workspace. It was not retried via
another route. No validation workspace or agent was created. The live negative
start path remains unverified; candidate mocked dispatch, installed source/hash
and read-only registered acceptance are the evidence actually available.

The lightweight CI sidechat job also runs connector tests so this preflight is
checked without waiting for backend compilation. Local governance/diff checks
pass. Full formatting ran Rust formatting, then stopped at missing Prettier;
no local Cargo/frontend build was run. Broad CI completion is separate.

## Stable explanation contract — approved PR271 follow-up

A known issue-context rejection is an MCP tool result with `isError:true`, a
`structuredContent` object and a JSON text content block containing the same
three fields: `code`, `reason`, `next_step`. These fields require no new tool,
input argument or catalog refresh. Only the typed preflight rejection is caught;
valid creation results and errors/uncertainty after a start POST retain their
previous behavior. The guard still runs before any workspace/agent side effect.

| Stable code | Plain-English reason | Actionable next step |
| --- | --- | --- |
| `workspace_issue_ids_missing` | Workspace creation was blocked because both project_id and issue_id are required. | Create or select an issue in Vibe, then provide its project_id and issue_id. |
| `workspace_issue_ids_invalid` | Workspace creation was blocked because project_id or issue_id is not a valid UUID. | Copy the project and issue UUIDs from Vibe, then submit the matching IDs again. |
| `workspace_issue_not_verified` | The issue could not be verified in the selected project. | List issues in the selected project and select one, or create a dedicated issue there; then provide its project_id and issue_id. |
| `workspace_issue_lookup_unavailable` | Vibe could not complete the selected project issue lookup. | Retry the read-only project issue lookup when Vibe is available; start the workspace only after issue verification succeeds. |
| `workspace_issue_lookup_malformed` | Vibe returned incomplete or malformed project issue evidence. | Check the project issue service response and retry the read-only lookup; start the workspace only after complete, valid evidence is available. |

A complete scoped negative result and positively mismatched project evidence
intentionally produce the **same public not-verified result**. The response must
not reveal whether an issue exists elsewhere, nor echo other-project IDs, names
or evidence. The guard makes only the selected-project lookup; it never searches
other projects. It does not describe a failed/unavailable lookup as absence.
Malformed rows, duplicate identities and partial/paginated evidence fail closed.
Network/service failures and malformed evidence remain distinguishable from a
valid empty lookup. Returned messages never include request IDs/prompts, raw
service errors, response bodies or credentials.

Validation: 20 public connector tests pass, with exact explanation and MCP text/
structured-field assertions. The offline full private-adapter dispatch harness
passes 28 rejection vectors with zero start POSTs, one valid issue-linked mocked
start with unchanged full payload/response, post-timeout uncertainty preservation,
and 27 incumbent control tests. All reads/starts in that harness are mocked; it
never starts the adapter's main loop, an upstream process, a live tool request,
a workspace or an agent. The previous denied live negative-start probe remains
out of scope and is not repeated. No voice or call routing is changed.

Preparation uses the installed `62081e89…` adapter as the exact baseline. For this
follow-up only the start dispatch branch changes in that adapter; existing
preflight placement, other methods, tools, access, CU/Stop and private chat
modules retain their original bytes. Installation still requires verified
Desktop B backup/restore, fresh pins/idle evidence and connector-only adoption.
Read-only cached status acceptance is separate from the deliberately unperformed
live negative-start probe. CI cannot exercise the private adapter unless the
retained source is supplied; public fixture dispatch tests run in the lightweight
connector CI job.
