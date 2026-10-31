export type WorkspaceAssignmentFilter = 'mine' | 'all';

export interface WorkspaceAssignmentLink {
  workspace_id: string;
  issue_id: string | null;
  user_id: string | null;
}

export function workspaceAssigneesById(links: WorkspaceAssignmentLink[]) {
  const byId = new Map<string, Set<string>>();
  for (const link of links) {
    if (!link.issue_id) continue;
    const assignees = byId.get(link.workspace_id) ?? new Set<string>();
    if (link.user_id) assignees.add(link.user_id);
    byId.set(link.workspace_id, assignees);
  }
  return byId;
}

export function filterWorkspaceAssignments<T extends { id: string }>(
  workspaces: T[],
  filter: WorkspaceAssignmentFilter,
  currentUserId: string | null,
  assigneesById: Map<string, Set<string>>
): T[] {
  if (filter === 'all' || !currentUserId) return workspaces;
  return workspaces.filter((workspace) => {
    const assignees = assigneesById.get(workspace.id);
    // Unlinked, unassigned and unknown historical rows stay visible until reviewed.
    return !assignees?.size || assignees.has(currentUserId);
  });
}
