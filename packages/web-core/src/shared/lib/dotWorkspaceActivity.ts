export type DotNotification = {
  project_id: string;
  issue_id: string;
  unread_count: number;
  needs_attention_count: number;
  shared_unread_count?: number;
  shared_needs_attention_count?: number;
};
export type DotWorkspaceNotification = DotNotification & {
  workspace_id: string;
};

// Issue badges retain aggregate counts. Workspace badges combine the shared
// conversation with only that workspace's verified dispatch receipts.
export function workspaceDotNotification(
  issueId: string | null,
  issue?: DotNotification,
  dispatch?: DotWorkspaceNotification
): DotNotification | undefined {
  if (!issueId) return undefined;
  const scoped = dispatch?.issue_id === issueId ? dispatch : undefined;
  if (!issue && !scoped) return undefined;
  return {
    project_id: issue?.project_id ?? scoped!.project_id,
    issue_id: issueId,
    unread_count:
      (issue?.shared_unread_count ?? issue?.unread_count ?? 0) +
      (scoped?.unread_count ?? 0),
    needs_attention_count:
      (issue?.shared_needs_attention_count ??
        issue?.needs_attention_count ??
        0) + (scoped?.needs_attention_count ?? 0),
  };
}
