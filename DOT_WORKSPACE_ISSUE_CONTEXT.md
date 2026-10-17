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
