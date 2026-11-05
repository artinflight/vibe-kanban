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

// Supplied only by the trusted management registry, never inferred from activity.
export type DotManagedWorkspace = {
  workspace_id: string;
  issue_id: string;
  project_id: string;
  manager: 'dot';
  state: 'managed';
};

export function workspaceDotManaged(
  workspaceId: string,
  issueId: string | null,
  association?: DotManagedWorkspace
): boolean {
  return !!(
    issueId &&
    association?.workspace_id === workspaceId &&
    association.issue_id === issueId &&
    association.project_id &&
    association.manager === 'dot' &&
    association.state === 'managed'
  );
}

// Shared history remains available. Only explicit workspace notification rows
// badge a workspace; issue aggregates and legacy unknown scope do not fan out.
export function workspaceDotNotification(
  issueId: string | null,
  issue?: DotNotification,
  workspace?: DotWorkspaceNotification
): DotNotification | undefined {
  if (!issueId || issueId.startsWith('project:')) return undefined;
  const scoped = workspace?.issue_id === issueId ? workspace : undefined;
  if (!issue && !scoped) return undefined;
  return {
    project_id: issue?.project_id ?? scoped!.project_id,
    issue_id: issueId,
    unread_count: scoped?.unread_count ?? 0,
    needs_attention_count: scoped?.needs_attention_count ?? 0,
  };
}
